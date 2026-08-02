"""Tamper-evidence tests for `pedroc verify` (README compiler-contract rule 8).

Every generated file's banner carries a hash of the *source*. `pedroc verify`
recomputes it and distinguishes three states:

  * clean         — banner hash matches source AND bytes match a fresh compile;
  * stale         — the .pedro source changed since the file was generated;
  * drift         — the generated file was hand-edited after generation.

Proves all three end-to-end, on both backends, plus the no-banner case.

Runs under pytest but pytest is optional: `python3 tests/test_verify.py` runs the
same assertions directly, and `tools/regress.py` invokes that runner.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pedroc import compile_source
from pedroc.verify import verify
from pedroc.hashing import source_hash, parse_banner

_SRC = (
    "target: python\n\n"
    "task inc(x: whole) returns whole:\n"
    "    return x + 1\n\n"
    "expect:\n"
    "    inc(1) == 2\n"
)


def test_banner_carries_source_hash():
    for target, comment in (("python", "#"), ("typescript", "//")):
        out = compile_source(_SRC, filename="inc.pedro", target=target)
        banner = parse_banner(out)
        assert banner is not None, f"{target}: no banner parsed"
        assert banner["hash"] == source_hash(_SRC), f"{target}: wrong hash stamped"
        assert banner["target"] == target
        assert out.startswith(comment), f"{target}: banner not first line"


def test_hash_is_of_source_not_output():
    # Same source compiled to two targets -> same stamped hash (it's the source
    # hash, not the output hash). This is what keeps `verify` target-agnostic.
    py = parse_banner(compile_source(_SRC, filename="inc.pedro", target="python"))
    ts = parse_banner(compile_source(_SRC, filename="inc.pedro", target="typescript"))
    assert py["hash"] == ts["hash"] == source_hash(_SRC)


def test_verify_clean_matches():
    for target in ("python", "typescript"):
        out = compile_source(_SRC, filename="inc.pedro", target=target)
        rep = verify(_SRC, out, source_name="inc.pedro", output_name=f"inc.{target}")
        assert rep["ok"] is True, rep["summary"]
        assert rep["status"] == "match", rep


def test_verify_catches_hand_edit():
    # Generate, then hand-edit the generated file WITHOUT touching the source.
    # The banner hash still matches the source, but the bytes no longer match a
    # fresh compile -> drift.
    out = compile_source(_SRC, filename="inc.pedro", target="python")
    tampered = out + "\n# a human snuck this in\n"
    rep = verify(_SRC, tampered, source_name="inc.pedro", output_name="inc.py")
    assert rep["ok"] is False
    assert rep["status"] == "drift", rep
    # The hash didn't change (source untouched) — that's how we know it's a hand
    # edit and not a stale rebuild.
    assert rep["stamped_hash"] == rep["current_hash"]
    assert "hand-edited" in rep["summary"]


def test_verify_catches_stale_source():
    # Generate, then change the SOURCE without regenerating -> stale.
    out = compile_source(_SRC, filename="inc.pedro", target="python")
    changed = _SRC + "\n# a new comment in the source\n"
    rep = verify(changed, out, source_name="inc.pedro", output_name="inc.py")
    assert rep["ok"] is False
    assert rep["status"] == "stale", rep
    # The two failure reasons are distinguishable: here the hashes DIFFER.
    assert rep["stamped_hash"] != rep["current_hash"]
    assert "STALE" in rep["summary"]


def test_stale_and_drift_are_distinct():
    out = compile_source(_SRC, filename="inc.pedro", target="python")
    drift = verify(_SRC, out + "\n#x\n", output_name="inc.py")
    stale = verify(_SRC + "\n#y\n", out, output_name="inc.py")
    assert drift["status"] != stale["status"]
    assert {drift["status"], stale["status"]} == {"drift", "stale"}


def test_verify_no_banner():
    rep = verify(_SRC, "print('not from pedroc')\n", output_name="hand.py")
    assert rep["ok"] is False
    assert rep["status"] == "no-banner", rep


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
    print(f"\n{len(tests) - failures}/{len(tests)} verify tests passed")
    return failures == 0


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
