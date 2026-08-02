"""Packaging / installability tests.

Pin that `pedroc` is a real importable package with a deterministic compile API,
and that its CLI entry point is reachable exactly two ways: `python -m pedroc`
and the bare `pedroc` console script (the `pip install -e .` entry point wired in
`pyproject.toml`). None of this depends on `PYTHONPATH` being set.

Runs under pytest (`pytest tests/`) but pytest is optional: `python3
tests/test_packaging.py` runs the same assertions directly, and
`tools/regress.py` invokes that runner.
"""
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pedroc
from pedroc import compile_source

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A tiny, fully-deterministic sample. The compiler is deterministic (same source
# -> byte-identical output), so we can assert the generated code exactly.
_SAMPLE = (
    "target: python\n\n"
    "task inc(x: whole) returns whole:\n"
    "    return x + 1\n\n"
    "expect:\n"
    "    inc(1) == 2\n"
)

from pedroc.hashing import source_hash  # noqa: E402

_EXPECTED_PY = (
    f"# Generated from inc.pedro by pedroc v0.1 (target: python) "
    f"source-hash: {source_hash(_SAMPLE)}. Do not edit by hand.\n\n"
    "def inc(x: int) -> int:\n"
    "    return (x + 1)\n\n"
    'if __name__ == "__main__":\n'
    "    assert (inc(1) == 2)\n"
    '    print("inc.pedro: all expectations passed \\u2713")\n'
)


def test_pedroc_is_importable():
    # Importing the package and its public compile entry point must work with no
    # PYTHONPATH ceremony once installed (this test file bootstraps sys.path so
    # it also passes in-tree).
    assert hasattr(pedroc, "compile_source")
    assert hasattr(pedroc, "__version__")


def test_compile_sample_is_byte_identical():
    out = compile_source(_SAMPLE, filename="inc.pedro", target="python")
    assert out == _EXPECTED_PY, f"generated code drifted:\n{out!r}"


def test_compile_is_deterministic():
    a = compile_source(_SAMPLE, filename="inc.pedro")
    b = compile_source(_SAMPLE, filename="inc.pedro")
    assert a == b


_SAMPLE_FILE = os.path.join(ROOT, "examples", "math.pedro")


def _clean_env():
    """The environment with PYTHONPATH stripped — proves the CLI needs no
    `PYTHONPATH=.` ceremony."""
    return {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}


def test_python_dash_m_entry_point():
    # `python -m pedroc` from the repo root, with NO PYTHONPATH set. cwd is on
    # sys.path for `-m`, so this works in-tree without any install.
    proc = subprocess.run(
        [sys.executable, "-m", "pedroc", "check", _SAMPLE_FILE, "--json"],
        cwd=ROOT, env=_clean_env(), capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert '"ok":true' in proc.stdout


def test_console_script_entry_point():
    # The bare `pedroc` command exists only after `pip install -e .`. When it is
    # on PATH we assert it behaves identically to `python -m pedroc`; otherwise
    # (fresh in-tree checkout) there is nothing to test, so we skip.
    exe = shutil.which("pedroc")
    if exe is None:
        print("      (skipped: `pedroc` not on PATH — package not installed)")
        return
    proc = subprocess.run(
        [exe, "check", _SAMPLE_FILE, "--json"],
        cwd=os.path.dirname(ROOT), env=_clean_env(),
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert '"ok":true' in proc.stdout


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
    print(f"\n{len(tests) - failures}/{len(tests)} packaging tests passed")
    return failures == 0


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
