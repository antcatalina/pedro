"""pedroc check — the structured feedback oracle for the LLM authoring loop.

Reports, as data:
  - `errors`:       syntax errors (line, code, message, hint)
  - `holes`:        unresolved `todo` intents (line, message)
  - `expectations`: per-assertion pass/fail, obtained by ACTUALLY RUNNING the
                    generated code; failures include `got X, expected <op> Y`.

An LLM emits Pedro, runs this, reads the JSON, and fixes — instead of guessing.

NOTE: this executes generated code in-process. Fine for trusted local use, but
must be sandboxed before running untrusted input. (Tracked in WORKLOG.)
"""
from .lexer import tokenize
from .parser import Parser
from .errors import PedroSyntaxError, PedroNameError
from .resolve import resolve
from . import nodes as N
from .codegen_python import generate, _gen_expr

_CMP = {"==", "!=", "<", "<=", ">", ">="}


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


def check(source, filename="<pedro>", target="python"):
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

    for h in _collect_holes(program):
        report["holes"].append({"line": h.line, "message": h.message})

    if target != "python":
        report["summary"] = f"target {target!r} is not runnable by `check` yet"
        return report

    code = generate(program, filename)
    ns = {"__name__": "pedroc_check"}
    try:
        exec(compile(code, filename, "exec"), ns)
    except Exception as e:  # a failure loading generated code is a compiler bug
        report["errors"].append({"line": 0, "code": "codegen-error", "message": str(e), "hint": None})
        report["summary"] = "internal error while loading generated code"
        return report

    pedro_error = ns.get("PedroError", Exception)
    n_pass = n_total = 0
    for it in program.items:
        if not isinstance(it, N.Expect):
            continue
        for item in it.items:
            kind = item[0]
            if kind == "given":
                try:
                    ns[item[1]] = eval(_gen_expr(item[2]), ns)
                except Exception as e:
                    report["errors"].append({"line": 0, "code": "given-error", "message": str(e), "hint": None})
                continue

            n_total += 1
            if kind == "assert":
                a = item[1]
                expr = _gen_expr(a)
                passed = False
                detail = None
                try:
                    passed = bool(eval(expr, ns))
                    if not passed and isinstance(a, N.BinOp) and a.op in _CMP:
                        lv = eval(_gen_expr(a.left), ns)
                        rv = eval(_gen_expr(a.right), ns)
                        detail = f"got {lv!r}, expected {a.op} {rv!r}"
                except Exception as e:
                    detail = f"error: {e}"
                text = _strip_parens(expr)
            else:  # fails
                call = _gen_expr(item[1])
                msg = item[2]
                passed = False
                detail = None
                try:
                    eval(call, ns)
                    detail = f"expected failure {msg!r}, but it returned normally"
                except pedro_error as e:
                    if str(e) == msg:
                        passed = True
                    else:
                        detail = f"failed with {str(e)!r}, expected {msg!r}"
                except Exception as e:
                    detail = f"raised {type(e).__name__}: {e}, expected failure {msg!r}"
                text = f"{_strip_parens(call)} fails with {msg!r}"

            n_pass += 1 if passed else 0
            report["expectations"].append({"text": text, "passed": passed, "detail": detail})

    report["ok"] = (not report["errors"]) and (not report["holes"]) and (n_pass == n_total)
    parts = [f"{n_pass}/{n_total} expectations passed"]
    if report["holes"]:
        parts.append(f"{len(report['holes'])} unresolved hole(s)")
    report["summary"] = "; ".join(parts)
    return report
