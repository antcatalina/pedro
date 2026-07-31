"""pedroc check — the structured feedback oracle for the LLM authoring loop.

Reports, as data:
  - `errors`:       syntax errors (line, code, message, hint)
  - `holes`:        unresolved `todo` intents (line, message)
  - `expectations`: per-assertion pass/fail, obtained by ACTUALLY RUNNING the
                    generated code; failures include `got X, expected <op> Y`.

An LLM emits Pedro, runs this, reads the JSON, and fixes — instead of guessing.

The generated program is run in a SUBPROCESS with a wall-clock timeout and a
restricted environment (see `pedroc/_expect_runner.py`), so untrusted or
non-terminating Pedro can only hang or crash that child — never the compiler.
Timeouts and crashes are surfaced as structured results, not as a parent hang.
"""
import json
import math
import os
import subprocess
import sys

from .lexer import tokenize
from .parser import Parser
from .errors import PedroSyntaxError, PedroNameError
from .resolve import resolve
from .annotate import annotate
from .capabilities import check_capabilities
from . import nodes as N
from .codegen_python import generate, _gen_expr

_CMP = {"==", "!=", "<", "<=", ">", ">="}

# Wall-clock budget for running a program's expect block, in seconds. A well
# behaved corpus program runs in milliseconds; this only bites infinite loops.
DEFAULT_TIMEOUT = 10.0

_RUNNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_expect_runner.py")
_ADAPTERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "adapters.py")


def _adapters_source():
    """The in-memory reference adapters, injected into the sandbox as
    `pedro_capabilities` so a capability program is runnable there with no setup."""
    with open(_ADAPTERS, "r", encoding="utf-8") as f:
        return f.read()

# Environment variables the sandboxed child is allowed to inherit. Notably absent:
# PYTHONPATH (so it can't import project code) and anything app-specific.
_ENV_ALLOW = ("PATH", "SYSTEMROOT", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "TEMP", "TMP")


def _snippet(source, line, col):
    """The offending source line plus a caret line pointing at `col` (1-based),
    joined by a newline — e.g. `let x = \\n        ^`. Returns None if unavailable."""
    if not line or col is None:
        return None
    lines = source.split("\n")
    if line < 1 or line > len(lines):
        return None
    text = lines[line - 1]
    caret = " " * (col - 1) + "^"
    return text + "\n" + caret


def _diag(source, e):
    """Build a COMPACT diagnostic dict from a PedroSyntaxError/PedroNameError.
    Null/empty fields are omitted to save tokens in the model's context; an absent
    key therefore means null. `col` is 1-based; `snippet` carries a caret."""
    d = {"code": e.code, "line": e.line, "message": e.message}
    if getattr(e, "col", None) is not None:
        d["col"] = e.col
    if getattr(e, "hint", None):
        d["hint"] = e.hint
    if getattr(e, "suggestion", None):
        d["suggestion"] = e.suggestion
    snip = _snippet(source, e.line, getattr(e, "col", None))
    if snip:
        d["snippet"] = snip
    return d


def _collect_holes(program):
    holes = []

    def walk(stmts):
        for s in stmts:
            if isinstance(s, N.Todo):
                holes.append(s)
            elif isinstance(s, N.Match):
                for _, body in s.cases:
                    walk(body)
            elif isinstance(s, N.Try):
                walk(s.body)
                walk(s.handler)
            elif isinstance(s, N.If):
                for _, body in s.branches:
                    walk(body)
                if s.orelse:
                    walk(s.orelse)
            elif isinstance(s, (N.While, N.Repeat, N.For)):
                walk(s.body)

    for it in program.items:
        if isinstance(it, N.Task):
            walk(it.body)
    return holes


def _strip_parens(s):
    return s[1:-1] if s.startswith("(") and s.endswith(")") else s


def check(source, filename="<pedro>", target="python", timeout=DEFAULT_TIMEOUT,
          cpu_timeout=None):
    report = {
        "ok": False,
        "file": filename,
        "target": target,
        "capabilities": [],   # declared capability surface (none yet — reserved)
        "errors": [],
        "holes": [],
        "expectations": [],
        "summary": "",
    }

    try:
        tokens = tokenize(source)
        program = Parser(tokens, filename).parse()
    except PedroSyntaxError as e:
        report["errors"].append(_diag(source, e))
        report["summary"] = f"syntax error at line {e.line}:{e.col}: {e.message}"
        return report

    name_errors = resolve(program)
    if name_errors:
        for e in name_errors:
            report["errors"].append(_diag(source, e))
        first = name_errors[0]
        report["summary"] = f"{len(name_errors)} unresolved name(s); first at line {first.line}:{first.col}: {first.message}"
        return report

    type_errors = annotate(program)   # resolve record-literal types
    if type_errors:
        for e in type_errors:
            report["errors"].append(_diag(source, e))
        first = type_errors[0]
        report["summary"] = f"{len(type_errors)} type error(s); first at line {first.line}:{first.col}: {first.message}"
        return report

    surface, cap_errors = check_capabilities(program)
    report["capabilities"] = surface   # the program's declared blast radius
    if cap_errors:
        for e in cap_errors:
            report["errors"].append(_diag(source, e))
        first = cap_errors[0]
        report["summary"] = f"{len(cap_errors)} capability error(s); first at line {first.line}:{first.col}: {first.message}"
        return report

    for h in _collect_holes(program):
        report["holes"].append({"line": h.line, "message": h.message})

    if target != "python":
        report["summary"] = f"target {target!r} is not runnable by `check` yet"
        return report

    code = generate(program, filename)
    steps = _build_steps(program)
    adapters = _adapters_source() if surface else None
    run = _run_expectations(code, steps, timeout, adapters, cpu_timeout)

    if run["load_error"] is not None:
        report["errors"].append({"line": 0, "code": "codegen-error", "message": run["load_error"], "hint": None})
        report["summary"] = "internal error while loading generated code"
        return report
    if run["crash"] is not None:
        report["status"] = "error"
        report["errors"].append({"line": 0, "code": "runtime-error", "message": run["crash"], "hint": None})
        report["summary"] = f"execution crashed: {run['crash']}"
        return report

    for msg in run["given_errors"]:
        report["errors"].append({"line": 0, "code": "given-error", "message": msg, "hint": None})
    report["expectations"] = run["expectations"]

    n_total = sum(1 for s in steps if s["kind"] not in ("given", "exec"))
    n_pass = sum(1 for x in run["expectations"] if x["passed"])

    if run["timed_out"]:
        report["status"] = "timeout"
        report["ok"] = False
        where = f" while running {run['hung']!r}" if run["hung"] else ""
        if run["cpu_exhausted"]:
            report["summary"] = (
                f"execution exceeded its CPU-time limit (possible infinite loop){where}; "
                f"{n_pass}/{n_total} expectations passed before it was stopped"
            )
        else:
            report["summary"] = (
                f"execution timed out after {timeout:g}s (possible infinite loop){where}; "
                f"{n_pass}/{n_total} expectations passed before timeout"
            )
        return report

    report["ok"] = (not report["errors"]) and (not report["holes"]) and (n_pass == n_total)
    parts = [f"{n_pass}/{n_total} expectations passed"]
    if report["holes"]:
        parts.append(f"{len(report['holes'])} unresolved hole(s)")
    report["summary"] = "; ".join(parts)
    return report


def _build_steps(program):
    """Render each expect item to the pre-computed strings the sandboxed runner
    needs, so the child process needs no pedroc imports. Order is preserved so a
    `given` binding is visible to later expectations."""
    steps = []
    for it in program.items:
        if not isinstance(it, N.Expect):
            continue
        for item in it.items:
            kind = item[0]
            if kind == "given":
                steps.append({"kind": "given", "name": item[1], "expr": _gen_expr(item[2])})
            elif kind == "given-empty":
                steps.append({"kind": "exec", "expr": f"{item[1]}.clear()"})
            elif kind == "assert":
                a = item[1]
                expr = _gen_expr(a)
                cmp = None
                if isinstance(a, N.BinOp) and a.op in _CMP:
                    cmp = {"left": _gen_expr(a.left), "right": _gen_expr(a.right), "op": a.op}
                steps.append({"kind": "assert", "expr": expr, "text": _strip_parens(expr), "cmp": cmp})
            else:  # fails
                call = _gen_expr(item[1])
                msg = item[2]
                steps.append({"kind": "fails", "call": call, "msg": msg,
                              "text": f"{_strip_parens(call)} fails with {msg!r}"})
    return steps


def _restricted_env():
    env = {k: os.environ[k] for k in _ENV_ALLOW if k in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


# Records the child emits once per completed step (one and only one of these per
# step). Used to align a partial record stream with `steps` on timeout, ignoring
# out-of-band records like `cpu-limit`.
_STEP_RECORDS = ("given-ok", "given-error", "exp")


def _cpu_preexec(cpu_seconds):
    """A POSIX `preexec_fn` that caps the child's CPU time as a backstop to the
    parent's wall-clock timeout. Soft limit fires SIGXCPU (the runner turns that
    into a clean `cpu-limit` record); the +1s hard-limit grace lets it emit before
    the kernel SIGKILLs. Returns None where `RLIMIT_CPU` isn't available (non-POSIX),
    so the sandbox behaves exactly as before there."""
    if os.name != "posix":
        return None
    try:
        import resource
    except ImportError:
        return None

    def _apply():
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        except (ValueError, OSError):
            pass  # best-effort; the wall-clock timeout is still the primary guard

    return _apply


def _run_expectations(code, steps, timeout, adapters=None, cpu_timeout=None):
    """Run the generated program's expect block in a sandboxed subprocess and
    collect per-step results. Never hangs or raises: a non-terminating program is
    reported via `timed_out`, a crashing one via `crash`. `adapters` (if given) is
    the reference in-memory capability module source, injected as
    `pedro_capabilities` so a capability program is runnable in the sandbox.

    Besides the parent-side wall-clock `timeout`, the child gets a POSIX
    `RLIMIT_CPU` backstop (defaults to just beyond the wall-clock budget) so a
    CPU-bound loop is still stopped even if the parent's timer is starved; a hit is
    surfaced via `timed_out`+`cpu_exhausted`."""
    result = {"expectations": [], "given_errors": [], "load_error": None,
              "crash": None, "timed_out": False, "cpu_exhausted": False, "hung": None}
    if cpu_timeout is None:
        cpu_timeout = int(math.ceil(timeout)) + 1
    payload = json.dumps({"code": code, "steps": steps, "adapters": adapters})
    try:
        proc = subprocess.run(
            [sys.executable, _RUNNER],
            input=payload, capture_output=True, text=True,
            timeout=timeout, env=_restricted_env(), cwd=os.path.dirname(_RUNNER),
            preexec_fn=_cpu_preexec(cpu_timeout),
        )
        out, err, timed_out, rc = proc.stdout, proc.stderr, False, proc.returncode
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        timed_out, rc = True, None

    records = []
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            records.append(json.loads(ln))
        except ValueError:
            pass  # ignore a torn final line from a killed child

    for rec in records:
        t = rec.get("t")
        if t == "load-error":
            result["load_error"] = rec.get("message", "")
        elif t == "given-error":
            result["given_errors"].append(rec.get("message", ""))
        elif t == "exp":
            result["expectations"].append(
                {"text": rec.get("text"), "passed": bool(rec.get("passed")), "detail": rec.get("detail")})
        elif t == "cpu-limit":
            result["cpu_exhausted"] = True

    if timed_out or result["cpu_exhausted"]:
        result["timed_out"] = True
        # The first step with no emitted record is the one still running. Count only
        # per-step records so an out-of-band `cpu-limit` record doesn't skew the index.
        done = sum(1 for r in records if r.get("t") in _STEP_RECORDS)
        if done < len(steps):
            result["hung"] = steps[done].get("text") or steps[done].get("expr")
    elif result["load_error"] is None and rc not in (0, None):
        detail = (err or "").strip().splitlines()
        result["crash"] = detail[-1] if detail else f"runner exited with code {rc}"
    return result
