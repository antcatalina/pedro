"""Structured-diagnostic tests for the LLM authoring loop.

Feed intentionally-broken Pedro snippets to `pedroc.check` and assert the exact
structured diagnostics an authoring model would read: `code`, `line`, `col`,
`hint`, and the did-you-mean `suggestion`. Errors are prompts, so this pins their
shape so it can't silently regress.

Runs under pytest (`pytest tests/`) but pytest is optional: `python3
tests/test_diagnostics.py` (or `PYTHONPATH=. python3 -m tests.test_diagnostics`)
runs the same assertions directly, and `tools/regress.py` invokes that runner.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pedroc.check import check
from pedroc.suggest import nearest, edit_distance


def _first_error(src):
    report = check(src, filename="<test>")
    assert not report["ok"], "expected the snippet to be rejected"
    assert report["errors"], "expected at least one error"
    return report, report["errors"][0]


def _wrap(body_lines):
    """A minimal valid program with `body_lines` spliced into a task body."""
    return "target: python\n\ntask f(x: whole) returns whole:\n" + "".join(
        "    " + ln + "\n" for ln in body_lines
    ) + "\nexpect:\n    f(1) == 1\n"


# --- column numbers ---------------------------------------------------------

def test_missing_colon_reports_line_and_col():
    src = "target: python\n\ntask g(x: whole) returns whole\n    return x\n"
    _, err = _first_error(src)
    assert err["code"] == "unexpected-token"
    assert err["line"] == 3
    assert err["col"] == 31          # just past 'whole', where ':' was expected
    assert err["hint"]               # actionable hint present
    assert "^" in err["snippet"]     # caret snippet present


def test_snippet_caret_points_at_column():
    _, err = _first_error(_wrap(["return xx + 1"]))
    src_line, caret = err["snippet"].split("\n")
    assert caret.index("^") == err["col"] - 1
    assert src_line[err["col"] - 1:err["col"] + 1] == "xx"


# --- did-you-mean for identifiers / tasks -----------------------------------

def test_undefined_name_suggests_nearest():
    report, err = _first_error(_wrap(["return xx + 1"]))
    assert err["code"] == "undefined-name"
    assert err["line"] == 4
    assert err["col"] == 12
    assert err["suggestion"] == "x"
    assert err["hint"]


def test_unknown_task_suggests_nearest():
    src = "target: python\n\ntask add(x: whole) returns whole:\n    return x\n\nexpect:\n    addd(1) == 1\n"
    _, err = _first_error(src)
    assert err["code"] == "unknown-task"
    assert err["suggestion"] == "add"
    assert err["line"] == 7 and err["col"] == 5


def test_top_level_typo_suggests_keyword():
    src = "target: python\n\ntsak f(x: whole) returns whole:\n    return x\n"
    _, err = _first_error(src)
    assert err["code"] == "unexpected-token"
    assert err["suggestion"] == "task"


def test_is_at_typo_suggests_least_or_most():
    _, err = _first_error(_wrap(["return x is at leats 3"]))
    assert err["suggestion"] == "least"


# --- specific codes + hints -------------------------------------------------

def test_unterminated_string_has_code_and_hint():
    _, err = _first_error(_wrap(['fail with "oops']))
    assert err["code"] == "unterminated-string"
    assert err["col"] == 15
    assert err["hint"]


def test_unexpected_character_has_hint():
    _, err = _first_error(_wrap(["return x @ 1"]))
    assert err["code"] == "unexpected-character"
    assert err["hint"]
    assert err["col"] == 14


def test_empty_match_reports_code():
    _, err = _first_error(_wrap(["match x:", "    return x"]))
    # `return` is not a `case`, so the match has no arms
    assert err["code"] == "empty-match"
    assert err["hint"]


# --- report shape -----------------------------------------------------------

def test_capabilities_surface_present_and_compact():
    report = check(_wrap(["return x"]))
    assert report["capabilities"] == []          # reserved, empty until capabilities land
    # compact contract: null fields are omitted, so no error carries None values
    for err in report["errors"]:
        assert None not in err.values()


def test_valid_program_has_no_errors():
    report = check(_wrap(["return x"]))
    assert report["ok"] is True
    assert report["errors"] == []


# --- the suggestion engine itself -------------------------------------------

def test_nearest_is_deterministic_and_bounded():
    assert nearest("whle", ("while", "when", "repeat")) == "while"
    assert nearest("x", ("y", "z")) == "y"          # tie -> lexicographically first
    assert nearest("totallyunrelated", ("x", "y")) is None
    assert edit_distance("kitten", "sitting") == 3
    assert edit_distance("abc", "abc") == 0


# --- runner (pytest-free) ---------------------------------------------------

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
    print(f"\n{len(tests) - failures}/{len(tests)} diagnostic tests passed")
    return failures == 0


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
