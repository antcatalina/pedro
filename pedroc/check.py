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

# Default cap on how many integers a `for all n from a to b` property may
# enumerate during `check`. Pedro is not a theorem prover: it PROVES a property
# by brute force over a bounded range, so the range must stay small enough that
# `check` stays fast. A range wider than this is reported as a failed expectation
# (narrow the range, or raise the cap with `check --forall-cap N`). This governs
# only the check-time guard; `build` output enumerates the exact range as written.
FORALL_CAP = 10000

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
          cpu_timeout=None, forall_cap=FORALL_CAP):
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
    steps = _build_steps(program, forall_cap)
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


def check_targets(source, filename="<pedro>", targets=("python", "typescript"),
                  timeout=DEFAULT_TIMEOUT, forall_cap=FORALL_CAP):
    """Compile the program to EVERY listed target, run each target's expect suite,
    and report whether all targets AGREE on every expectation.

    This is `tools/differential.py`'s cross-backend agreement check, promoted into a
    first-class, user-facing guarantee: one source, many verified targets. If two
    targets disagree on a single expectation, one of them has a codegen bug, and the
    returned report names WHICH targets disagreed on WHICH expectation and what each
    got — a compiler bug report, treated with the same rigor as a check failure.

    Reuses `tools/backends.py`'s per-backend run/report adapter (the same runners
    the differential tester and fuzzer trust) rather than duplicating it. A
    capability program runs Python-only for now (the TS backend has no adapter path
    yet); the TypeScript lane is reported as `skipped` for it, not a disagreement.
    """
    # Lazy import: `tools.backends` imports `pedroc.check` at module load, so a
    # top-level import here would be circular. Add the repo root to `sys.path` so
    # this works regardless of the cwd `pedroc` was invoked from.
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    from tools.backends import run_typescript, ts_available, _normalize

    targets = list(dict.fromkeys(targets))  # dedupe, preserve order
    report = {
        "ok": False,
        "file": filename,
        "targets": targets,
        "capabilities": [],
        "errors": [],
        "holes": [],
        "results": {},         # target -> normalized run result
        "agree": True,
        "disagreements": [],
        "summary": "",
    }

    # The canonical Python `check` gives us the shared static surface (syntax/name/
    # type/capability errors, holes, declared capabilities) once for all targets.
    base = check(source, filename=filename, target="python", timeout=timeout,
                 forall_cap=forall_cap)
    report["capabilities"] = base["capabilities"]
    report["errors"] = base["errors"]
    report["holes"] = base["holes"]

    # A compile-level failure is identical across every target — nothing to diff.
    if base["errors"]:
        report["agree"] = None
        report["summary"] = base["summary"]
        for t in targets:
            report["results"][t] = {"ran": False, "status": None, "ok": False,
                                    "expectations": [], "error": base["summary"]}
        return report

    has_caps = bool(base["capabilities"])
    for t in targets:
        if t == "python":
            report["results"]["python"] = _normalize(base)
        elif t == "typescript":
            if has_caps:
                report["results"]["typescript"] = {
                    "ran": False, "status": "skipped", "ok": True, "expectations": [],
                    "error": None,
                    "skipped": "capabilities are Python-only in the TypeScript backend"}
            elif not ts_available():
                report["results"]["typescript"] = {
                    "ran": False, "status": "unavailable", "ok": False, "expectations": [],
                    "error": "the TypeScript backend requires `node` on PATH"}
            else:
                report["results"]["typescript"] = run_typescript(
                    source, filename=filename, timeout=timeout)
        else:
            report["results"][t] = {"ran": False, "status": "unknown-target", "ok": False,
                                    "expectations": [], "error": f"unknown target {t!r}"}

    _diff_targets(report, targets)

    ran = [t for t in targets if report["results"][t]["ran"]]
    all_ran_ok = all(report["results"][t]["ok"] for t in ran)
    any_unavailable = any(report["results"][t].get("status") == "unavailable"
                          for t in targets)
    report["ok"] = (report["agree"] is not False and all_ran_ok
                    and not any_unavailable and not base["holes"])

    report["summary"] = _targets_summary(report, targets, ran)
    return report


def _diff_targets(report, targets):
    """Compare the ran targets' results and fill `agree`/`disagreements`. Any
    divergence is a codegen bug, recorded with what each target got.

    Backends report at two granularities. The Python lane emits a per-expectation
    pass/fail record for each assertion. The TypeScript lane currently prints only a
    whole-program pass/fail (its expect block throws on the first failed assertion),
    so its `expectations` list is empty — a COARSE lane. We compare a coarse lane at
    the whole-program level (`ok` vs `ok`) and a per-expectation lane position by
    position, so a coarse lane never produces a spurious count mismatch. If the TS
    backend ever grows per-expectation records, the finer comparison lights up
    automatically."""
    ran = [t for t in targets if report["results"][t]["ran"]]
    if len(ran) < 2:
        # Nothing to cross-check (e.g. TS skipped for a capability program). One
        # green lane can't contradict itself, so agreement is vacuously true.
        report["agree"] = True if ran else None
        return

    # Reference lane = the first ran lane that reports per-expectation detail
    # (Python always does); every other lane is compared against it.
    detailed = [t for t in ran if report["results"][t]["expectations"]]
    ref = detailed[0] if detailed else ran[0]
    ref_res = report["results"][ref]

    for t in ran:
        if t == ref:
            continue
        r = report["results"][t]
        if r["expectations"]:
            _diff_per_expectation(report, ref, t)
        elif ref_res["ok"] != r["ok"]:
            # Coarse lane: it agrees or disagrees on the whole-program verdict only.
            report["agree"] = False
            report["disagreements"].append({
                "kind": "program",
                "detail": f"{ref} and {t} disagree on the overall result",
                "results": {
                    ref: {"ok": ref_res["ok"],
                          "failed": [e["text"] for e in ref_res["expectations"]
                                     if not e["passed"]]},
                    t: {"ok": r["ok"], "error": r.get("error")},
                }})


def _diff_per_expectation(report, ref, t):
    """Compare two per-expectation lanes position by position."""
    a = report["results"][ref]["expectations"]
    b = report["results"][t]["expectations"]
    if len(a) != len(b):
        report["agree"] = False
        report["disagreements"].append({
            "kind": "expectation-count", "counts": {ref: len(a), t: len(b)},
            "detail": "targets produced different numbers of expectations"})
    for i in range(min(len(a), len(b))):
        if bool(a[i]["passed"]) != bool(b[i]["passed"]):
            report["agree"] = False
            report["disagreements"].append({
                "kind": "expectation", "index": i, "expectation": a[i]["text"],
                "results": {
                    ref: {"passed": bool(a[i]["passed"]), "detail": a[i].get("detail")},
                    t: {"passed": bool(b[i]["passed"]), "detail": b[i].get("detail")}}})


def _targets_summary(report, targets, ran):
    if report["agree"] is False:
        return (f"targets DISAGREE — {len(report['disagreements'])} difference(s) "
                f"across {', '.join(ran)}; this is a compiler bug")
    lanes = ", ".join(ran)
    n = len(report["results"][ran[0]]["expectations"]) if ran else 0
    unavailable = [t for t in targets
                   if report["results"][t].get("status") == "unavailable"]
    if unavailable:
        return f"could not verify agreement — target(s) unavailable: {', '.join(unavailable)}"
    if report["ok"]:
        note = "" if len(ran) > 1 else " (single lane — nothing to cross-check)"
        return f"all targets agree — {lanes} green on {n}/{n} expectations{note}"
    if report["holes"]:
        return f"{lanes} agree but {len(report['holes'])} unresolved hole(s)"
    return f"{lanes} agree but not all expectations pass"


def _build_steps(program, forall_cap=FORALL_CAP):
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
            elif kind == "forall":
                name, lo, hi, body = item[1], item[2], item[3], item[4]
                lo_s, hi_s, body_s = _gen_expr(lo), _gen_expr(hi), _gen_expr(body)
                steps.append({"kind": "forall", "name": name,
                              "lo": lo_s, "hi": hi_s, "expr": body_s, "cap": forall_cap,
                              "text": f"for all {name} from {_strip_parens(lo_s)} "
                                      f"to {_strip_parens(hi_s)}: {_strip_parens(body_s)}"})
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
