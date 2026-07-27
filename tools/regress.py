#!/usr/bin/env python
"""Regression suite for the pedroc compiler.

Compiles and `check`s every .pedro file in the supported corpus (examples/math
and examples/cookbook), running each program's `expect` block. Exits non-zero if
anything fails. Run from anywhere:

    python tools/regress.py
"""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pedroc.check import check  # noqa: E402


def corpus():
    files = sorted(glob.glob(os.path.join(ROOT, "examples", "cookbook", "*.pedro")))
    files.append(os.path.join(ROOT, "examples", "math.pedro"))
    return files


def main():
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

    # Also run the structured-diagnostics tests (pytest not required).
    from tests.test_diagnostics import _run as run_diag_tests
    print()
    if not run_diag_tests():
        all_ok = False

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
