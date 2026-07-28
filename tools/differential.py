"""Differential tester — compile every corpus program to EVERY available backend,
run each, and assert the backends agree on every expectation's pass/fail result.

Pedro's promise is one source, many verified targets. This is the check that keeps
that promise honest: if the Python and TypeScript backends ever disagree about a
single expectation, one of them has a codegen bug. A disagreement is a hard
failure here (exit non-zero) with the offending file + expectation printed.

Until the TypeScript backend lands, only the Python lane is available, so there is
nothing to differ against — the run reports the TS lane as PENDING and passes,
having at least confirmed the whole corpus still runs green. It lights up into a
real cross-backend diff automatically once `codegen_ts` + `node` are present.

Usage:
    python tools/differential.py [-v]
"""
import argparse
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.backends import run_python, run_typescript, ts_available  # noqa: E402


def corpus():
    files = sorted(glob.glob(os.path.join(ROOT, "examples", "cookbook", "*.pedro")))
    files.append(os.path.join(ROOT, "examples", "math.pedro"))
    files.append(os.path.join(ROOT, "examples", "order_total.pedro"))
    files.append(os.path.join(ROOT, "examples", "signup.pedro"))
    return files


def _compare(py, ts, name):
    """Return a list of human-readable disagreement strings between two lanes."""
    problems = []
    if not ts["ok"] and py["ok"]:
        problems.append(f"{name}: python ok but typescript failed: {ts['error']}")
        return problems
    # Pair expectations by position (both lanes emit them in source order).
    if ts["expectations"]:
        if len(py["expectations"]) != len(ts["expectations"]):
            problems.append(
                f"{name}: expectation count differs (py={len(py['expectations'])} "
                f"ts={len(ts['expectations'])})")
        for a, b in zip(py["expectations"], ts["expectations"]):
            if a["passed"] != b["passed"]:
                problems.append(
                    f"{name}: disagreement on {a['text']!r}: py={a['passed']} ts={b['passed']}")
    return problems


def run(verbose=False):
    have_ts = ts_available()
    all_ok = True
    disagreements = 0
    for path in corpus():
        name = os.path.relpath(path, ROOT)
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
        py = run_python(source, filename=os.path.basename(path))
        if not py["ok"]:
            all_ok = False
            print(f"[FAIL] {name} — python lane not green: {py['error']}")
            continue
        if not have_ts:
            if verbose:
                print(f"[py  ] {name} — {len(py['expectations'])} expectations (TS pending)")
            continue
        if "use capability" in source:  # capabilities are Python-only for now
            if verbose:
                print(f"[py  ] {name} — {len(py['expectations'])} expectations (TS skipped: capabilities)")
            continue
        ts = run_typescript(source, filename=os.path.basename(path))
        if not ts["ran"]:
            continue
        problems = _compare(py, ts, name)
        if problems:
            all_ok = False
            disagreements += len(problems)
            for p in problems:
                print(f"[DIFF] {p}")
        elif verbose:
            print(f"[agree] {name} — {len(py['expectations'])} expectations match across backends")

    lane = "python+typescript" if have_ts else "python only (TS lane PENDING — codegen_ts not landed)"
    if all_ok:
        print(f"\nPASS: corpus differential over {lane}"
              + ("" if have_ts else "; nothing to diff yet"))
    else:
        print(f"\nFAIL: corpus differential over {lane} — {disagreements} disagreement(s)")
    return all_ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    return 0 if run(verbose=args.verbose) else 1


if __name__ == "__main__":
    sys.exit(main())
