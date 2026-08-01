#!/usr/bin/env python
"""Regression suite for the pedroc compiler.

Compiles and `check`s every .pedro file in the supported corpus (examples/math
and examples/cookbook), running each program's `expect` block. Exits non-zero if
anything fails. Run from anywhere:

    python tools/regress.py

Correctness harness (kept OFF the default fast path):
    python tools/regress.py --diff    # cross-backend differential over the corpus
    python tools/regress.py --fuzz     # full grammar fuzzer (200 programs)
    python tools/regress.py --slow     # both of the above

The default run includes only a tiny fuzz SMOKE (a dozen programs) so CI stays
fast; use the flags above for the heavier sweeps.
"""
import argparse
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pedroc.check import check  # noqa: E402


def corpus():
    files = sorted(glob.glob(os.path.join(ROOT, "examples", "cookbook", "*.pedro")))
    files.append(os.path.join(ROOT, "examples", "math.pedro"))
    files.append(os.path.join(ROOT, "examples", "order_total.pedro"))
    files.append(os.path.join(ROOT, "examples", "signup.pedro"))
    return files


def _declares_capabilities(path):
    """Capability programs are Python-only for now (the TS backend can't emit the
    adapter layer yet), so the TypeScript lane skips them — see WORKLOG."""
    with open(path, "r", encoding="utf-8") as f:
        return "use capability" in f.read()


def main(argv=None):
    ap = argparse.ArgumentParser(description="pedroc regression suite")
    ap.add_argument("--diff", action="store_true", help="run the cross-backend differential tester")
    ap.add_argument("--fuzz", action="store_true", help="run the full grammar fuzzer (200 programs)")
    ap.add_argument("--slow", action="store_true", help="run both --diff and --fuzz")
    ap.add_argument("--strict-docs", action="store_true",
                    help="promote doc-drift HIGH findings from a warning to a failure")
    args = ap.parse_args(argv)
    run_diff = args.diff or args.slow
    run_full_fuzz = args.fuzz or args.slow

    all_ok = True
    total_expectations = 0
    for path in corpus():
        with open(path, "r", encoding="utf-8") as f:
            report = check(f.read(), filename=os.path.basename(path))
        total_expectations += sum(1 for _ in report["expectations"])
        status = "ok  " if report["ok"] else "FAIL"
        print(f"[{status}] {os.path.relpath(path, ROOT)} — {report['summary']}")
        if not report["ok"]:
            all_ok = False
            for e in report["errors"]:
                print(f"        error [{e['code']}] line {e['line']}: {e['message']}")
            for h in report["holes"]:
                print(f"        hole line {h['line']}: {h['message']}")
            for x in report["expectations"]:
                if not x["passed"]:
                    print(f"        FAIL {x['text']}  ({x['detail']})")
    print(f"\n{'PASS' if all_ok else 'FAIL'}: {total_expectations} expectations checked across the corpus")

    # TypeScript lane: automatically runs when `node` is on PATH. Compiles every
    # corpus program to TypeScript and executes it with node, asserting each
    # program prints its success line — the same green bar the Python lane holds.
    from tools.backends import run_typescript, ts_available
    print()
    if ts_available():
        ts_files = [p for p in corpus() if not _declares_capabilities(p)]
        skipped = len(corpus()) - len(ts_files)
        ts_ok = 0
        for path in ts_files:
            with open(path, "r", encoding="utf-8") as f:
                res = run_typescript(f.read(), filename=os.path.basename(path))
            name = os.path.relpath(path, ROOT)
            if res["ran"] and res["ok"]:
                ts_ok += 1
                print(f"[ts  ] {name} — ran green on node")
            else:
                all_ok = False
                print(f"[FAIL] {name} — typescript lane: {res.get('error')}")
        note = f" ({skipped} capability program(s) Python-only, skipped)" if skipped else ""
        print(f"\n{'PASS' if ts_ok == len(ts_files) else 'FAIL'}: "
              f"{ts_ok}/{len(ts_files)} corpus programs green on the TypeScript backend{note}")
    else:
        print("SKIP: TypeScript lane (node not on PATH)")

    # Also run the structured-diagnostics tests (pytest not required).
    from tests.test_diagnostics import _run as run_diag_tests
    print()
    if not run_diag_tests():
        all_ok = False

    # ...and the subprocess-sandbox tests (timeout / crash isolation).
    from tests.test_sandbox import _run as run_sandbox_tests
    print()
    if not run_sandbox_tests():
        all_ok = False

    # ...and the packaging tests (pedroc is importable + both CLI entry points
    # work with no PYTHONPATH).
    from tests.test_packaging import _run as run_packaging_tests
    print()
    if not run_packaging_tests():
        all_ok = False

    # ...and the LLM-authoring benchmark's self-test: every task's reference
    # solution must satisfy its hidden oracle (proves each oracle is satisfiable
    # and the scorer wiring is sound — see tools/eval/).
    from tools.eval.scorer import self_test as eval_self_test
    print()
    eval_ok, eval_results = eval_self_test()
    n_ok = sum(1 for r in eval_results if r["ok"])
    for r in eval_results:
        if not r["ok"]:
            print(f"[FAIL] eval/{r['id']} — {r['summary']}")
    print(f"{'PASS' if eval_ok else 'FAIL'}: eval benchmark self-test "
          f"({n_ok}/{len(eval_results)} reference solutions satisfy their hidden oracle)")
    if not eval_ok:
        all_ok = False

    # Doc-drift backstop (CLAUDE.md ground rule 6). Clearly separated + labelled.
    # NON-FATAL by default (new heuristic — false positives possible); prints loudly
    # if it finds anything. `--strict-docs` promotes HIGH findings to a failure.
    # Once it has proven itself over a few runs with no false positives, a future
    # job should flip this default to strict (see WORKLOG 2026-07-30).
    from tools.check_docs import find as find_doc_drift
    print("\n" + "-" * 72)
    print("DOC-DRIFT CHECK (tools/check_docs.py) — advisory" +
          (" [--strict-docs: HIGH fails]" if args.strict_docs else ""))
    print("-" * 72)
    doc_high, doc_low = find_doc_drift()
    if not doc_high and not doc_low:
        print("[ok  ] no doc/compiler drift detected")
    else:
        for msg in doc_high:
            print(f"[WARN] HIGH: {msg}")
        for msg in doc_low:
            print(f"[warn] LOW:  {msg}")
        if args.strict_docs and doc_high:
            print("FAIL: --strict-docs set and HIGH doc-drift findings present")
            all_ok = False
        else:
            print("(advisory only — not failing CI; run with --strict-docs to enforce)")

    # Correctness harness. A tiny fuzz smoke always runs (fast); the heavier
    # sweeps are opt-in so the default `python tools/regress.py` stays quick.
    from tools.fuzz import run as run_fuzz
    from tools.differential import run as run_differential
    print()
    fuzz_count = 200 if run_full_fuzz else 12
    if not run_fuzz(seed=0, count=fuzz_count):
        all_ok = False
    if run_diff:
        print()
        if not run_differential():
            all_ok = False

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
