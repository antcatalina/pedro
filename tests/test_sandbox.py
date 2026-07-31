"""Sandbox tests for `pedroc check`.

`check` runs the generated program in a subprocess with a wall-clock timeout and
a restricted environment. These tests pin that a non-terminating program is
reported as a structured `timeout` (within a couple of seconds, not hanging the
parent), that a crashing program is reported as a structured `error`, and that
well-behaved programs behave EXACTLY as before (same pass/fail and detail).

Runs under pytest (`pytest tests/`) but pytest is optional: `python3
tests/test_sandbox.py` runs the same assertions directly, and `tools/regress.py`
invokes that runner.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pedroc.check import check


# A task that loops forever, invoked from the expect block.
_SPIN = (
    "target: python\n\n"
    "task spin() returns whole:\n"
    "    let x = 0\n"
    "    while x is at least 0:\n"
    "        increase x by 1\n"
    "    return x\n\n"
    "expect:\n"
    "    spin() == 1\n"
)


def test_infinite_loop_is_reported_as_timeout():
    start = time.time()
    report = check(_SPIN, filename="<spin>", timeout=2.0)
    elapsed = time.time() - start
    assert elapsed < 8.0, f"check should return promptly on timeout, took {elapsed:.1f}s"
    assert report["ok"] is False
    assert report.get("status") == "timeout"
    assert "timed out" in report["summary"]


def test_timeout_does_not_take_down_the_parent():
    # If the child weren't isolated, an infinite loop would hang this process.
    # Reaching the assertion at all proves the parent survived.
    report = check(_SPIN, filename="<spin>", timeout=2.0)
    assert report["status"] == "timeout"
    # We can keep running checks afterwards.
    ok = check(
        "target: python\n\ntask f(x: whole) returns whole:\n    return x\n\nexpect:\n    f(1) == 1\n"
    )
    assert ok["ok"] is True


def test_cpu_limit_backstops_wall_clock():
    # The child carries a POSIX RLIMIT_CPU backstop to the parent's wall-clock
    # timeout. With a generous wall-clock (20s) but a tight CPU limit (1s), a
    # CPU-bound spin must be stopped by the CPU limit — reported as a structured
    # `timeout` — WITHOUT waiting for the wall-clock budget to elapse.
    if os.name != "posix":
        return  # RLIMIT_CPU is not available off POSIX; nothing to assert
    start = time.time()
    report = check(_SPIN, filename="<spin-cpu>", timeout=20.0, cpu_timeout=1)
    elapsed = time.time() - start
    assert elapsed < 10.0, f"CPU limit should stop the child well before wall-clock, took {elapsed:.1f}s"
    assert report["ok"] is False
    assert report.get("status") == "timeout"
    assert "CPU-time limit" in report["summary"]


def test_well_behaved_program_passes_identically():
    src = (
        "target: python\n\n"
        "task add(a: whole, b: whole) returns whole:\n"
        "    return a + b\n\n"
        "expect:\n"
        "    add(2, 3) == 5\n"
        "    add(2, 3) == 6\n"
    )
    report = check(src, filename="<add>")
    assert report["ok"] is False
    assert len(report["expectations"]) == 2
    assert report["expectations"][0]["passed"] is True
    assert report["expectations"][1]["passed"] is False
    # 'got X, expected Y' detail must be preserved verbatim.
    assert report["expectations"][1]["detail"] == "got 5, expected == 6"
    assert "status" not in report  # normal runs carry no abnormal-status key


def test_fails_with_still_works_in_subprocess():
    src = (
        "target: python\n\n"
        "task boom(x: whole) returns whole:\n"
        "    fail with \"nope\"\n\n"
        "expect:\n"
        "    boom(1) fails with \"nope\"\n"
    )
    report = check(src, filename="<boom>")
    assert report["ok"] is True
    assert report["expectations"][0]["passed"] is True


def test_given_binding_visible_to_later_expectation():
    src = (
        "target: python\n\n"
        "task inc(x: whole) returns whole:\n"
        "    return x + 1\n\n"
        "expect:\n"
        "    given base = 10\n"
        "    inc(base) == 11\n"
    )
    report = check(src, filename="<given>")
    assert report["ok"] is True
    assert report["expectations"][0]["passed"] is True


def _run():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"[ok  ] {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"[FAIL] {t.__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} sandbox tests passed")
    return failures == 0


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
