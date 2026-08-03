"""Backend runners for the correctness harness (differential tester + fuzzer).

Normalizes "compile this Pedro source for target T, run it, and report per-
expectation pass/fail" to a single shape across backends, so the differential
tester and the fuzzer can treat every backend the same way:

    {"ran": bool, "status": str|None, "ok": bool,
     "expectations": [{"text": str, "passed": bool, "detail": str|None}, ...],
     "error": str|None}

`status` mirrors `pedroc check`: None on a normal run, "timeout"/"error" on an
abnormal one. `ran` is False only when the backend is unavailable in this
environment (e.g. the TypeScript backend hasn't landed yet, or `node` is not on
PATH) — the caller then SKIPS that lane rather than failing.

The Python lane reuses `pedroc.check.check()` — the same oracle CI already trusts.
The TypeScript lane is written against the planned `codegen_ts` backend + `node`
(see WORKLOG); until that backend exists, `ts_available()` is False and the lane
is skipped, so this module is safe to ship Python-only and lights up automatically
when TS lands.
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pedroc import compile_source  # noqa: E402
from pedroc.check import check  # noqa: E402


def _normalize(report):
    """A `pedroc check` report → the harness's normalized shape."""
    return {
        "ran": True,
        "status": report.get("status"),
        "ok": report["ok"],
        "expectations": [
            {"text": x["text"], "passed": x["passed"], "detail": x.get("detail")}
            for x in report["expectations"]
        ],
        "error": None if report["ok"] else _first_error(report),
    }


def _first_error(report):
    if report["errors"]:
        e = report["errors"][0]
        return f"[{e.get('code')}] {e.get('message')}"
    if report["holes"]:
        return f"hole: {report['holes'][0]['message']}"
    return report.get("summary")


def run_python(source, filename="<fuzz>", timeout=10.0):
    return _normalize(check(source, filename=filename, target="python", timeout=timeout))


# ---- TypeScript lane (activates automatically once codegen_ts lands) ----------

def ts_available():
    """True only if the TypeScript backend AND a `node` runtime are both present.

    Kept deliberately conservative: a false here means the differential/fuzz TS
    lane is SKIPPED, never that CI fails."""
    if shutil.which("node") is None:
        return False
    try:
        compile_source("target: typescript\n\nexpect:\n    1 == 1\n",
                       filename="<probe>", target="typescript")
    except Exception:
        return False
    return True


# The reference TS adapter module (`pedro_capabilities.ts`), written next to a
# capability program's temp file so its `import "./pedro_capabilities.ts"` resolves
# — the TypeScript mirror of `pedroc.check._adapters_source()`.
_TS_ADAPTERS = os.path.join(ROOT, "pedro_capabilities.ts")


def run_typescript(source, filename="<fuzz>", timeout=10.0):
    """Compile to TypeScript and run it with `node`, returning the normalized shape.

    Returns a `ran: False` result when the backend isn't available. The generated
    program prints one JSON record per expectation (planned `codegen_ts` contract);
    if a future backend instead throws on the first failure, this still reports a
    coarse pass/fail from the process exit + stderr. A capability program's output
    imports `./pedro_capabilities.ts`, so the reference adapter is written alongside
    it in the temp directory."""
    if not ts_available():
        return {"ran": False, "status": None, "ok": False, "expectations": [],
                "error": "typescript backend unavailable"}
    try:
        ts = compile_source(source, filename=filename, target="typescript")
    except Exception as e:  # compile error is itself a divergence signal
        return {"ran": True, "status": "error", "ok": False, "expectations": [],
                "error": f"ts compile: {e}"}

    tmpdir = tempfile.mkdtemp(prefix="pedro-ts-")
    path = os.path.join(tmpdir, "program.ts")
    with open(path, "w", encoding="utf-8") as f:
        f.write(ts)
    if "pedro_capabilities.ts" in ts:
        shutil.copyfile(_TS_ADAPTERS, os.path.join(tmpdir, "pedro_capabilities.ts"))
    try:
        proc = subprocess.run(["node", path], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ran": True, "status": "timeout", "ok": False, "expectations": [],
                "error": "ts execution timed out"}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    expectations, parsed = _parse_ts_records(proc.stdout)
    if parsed:
        ok = proc.returncode == 0 and all(x["passed"] for x in expectations)
        return {"ran": True, "status": None if proc.returncode == 0 else "error",
                "ok": ok, "expectations": expectations, "error": None if ok else (proc.stderr or "").strip()}
    # No per-expectation records: fall back to a coarse pass/fail.
    ok = proc.returncode == 0
    return {"ran": True, "status": None if ok else "error", "ok": ok,
            "expectations": [], "error": None if ok else (proc.stderr or "").strip().splitlines()[-1:] or None}


def _parse_ts_records(stdout):
    """Parse newline-delimited JSON expectation records, if the TS backend emits
    them. Tolerates non-JSON banner lines. Returns (expectations, any_parsed)."""
    import json
    out = []
    any_parsed = False
    for ln in (stdout or "").splitlines():
        ln = ln.strip()
        if not ln.startswith("{"):
            continue
        try:
            rec = json.loads(ln)
        except ValueError:
            continue
        if "passed" in rec and "text" in rec:
            any_parsed = True
            out.append({"text": rec["text"], "passed": bool(rec["passed"]),
                        "detail": rec.get("detail")})
    return out, any_parsed
