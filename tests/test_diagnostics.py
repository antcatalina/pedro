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

from pedroc import compile_source
from pedroc.check import check
from pedroc.suggest import nearest, edit_distance
from pedroc.permissions import render as render_permissions, permission_manifest, CAPABILITY_RULES


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


def test_misspelled_statement_keyword_suggests_nearest():
    # A misspelled statement keyword previously fell through to a confusing
    # "expected NEWLINE, found ..." with no suggestion. Now it's a dedicated
    # `unknown-keyword` diagnostic that points at the keyword and names the fix.
    _, err = _first_error(_wrap(["repaet 3 times:", "    increase x by 1"]))
    assert err["code"] == "unknown-keyword"
    assert err["suggestion"] == "repeat"
    assert err["line"] == 4 and err["col"] == 5   # caret on the keyword, not later
    assert err["hint"]


def test_misspelled_when_keyword_suggests_nearest():
    _, err = _first_error(_wrap(["wen x is 5:", "    return x"]))
    assert err["code"] == "unknown-keyword"
    assert err["suggestion"] == "when"


def test_bare_call_statement_is_not_mistaken_for_a_keyword_typo():
    # A valid bare expression statement must never be flagged as a keyword typo.
    src = ("target: python\n\ntask helper(x: whole) returns whole:\n    return x\n\n"
           "task f(x: whole) returns whole:\n    helper(x)\n    return x\n\n"
           "expect:\n    f(1) == 1\n")
    report = check(src, filename="<test>")
    assert report["ok"], report["summary"]


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


def test_case_after_otherwise_reports_code():
    _, err = _first_error(_wrap([
        "match x:",
        "    case otherwise:",
        "        return 0",
        "    case 1:",
        "        return 1",
    ]))
    assert err["code"] == "case-after-otherwise"
    assert err["hint"]


def test_try_without_on_failure_reports_code():
    _, err = _first_error(_wrap([
        "try:",
        "    return x",
        "return 2",
    ]))
    assert err["code"] == "missing-on-failure"
    assert err["hint"]


# --- records & enums --------------------------------------------------------

_REC = ("target: python\n\nenum Color:\n    red\n    green\n\n"
        "record Dot:\n    x: whole\n    y: whole\n    hue: Color = Color.red\n\n"
        "task at(d: Dot) returns whole:\n    return d.x\n\nexpect:\n")


def test_unknown_field_reports_code_and_suggestion():
    src = _REC + "    at({ x: 1, y: 2, z: 3 }) == 1\n"
    _, err = _first_error(src)
    assert err["code"] == "unknown-field"
    assert err["message"] == "record 'Dot' has no field 'z'"
    assert err["suggestion"] in ("x", "y")   # nearest declared field
    assert err["hint"]


def test_missing_required_field_reports_code():
    src = _REC + "    at({ x: 1 }) == 1\n"       # y is required (no default)
    _, err = _first_error(src)
    assert err["code"] == "missing-field"
    assert "'y'" in err["message"]


def test_ambiguous_record_when_no_expected_type():
    src = _REC + "    given d = { q: 9 }\n    at(d) == 1\n"
    _, err = _first_error(src)
    assert err["code"] == "ambiguous-record"
    assert err["hint"]


def test_valid_record_and_enum_program_is_clean():
    # a record literal typed by its expected argument, an enum default filled in
    report = check(_REC + "    at({ x: 4, y: 5 }) == 4\n", filename="<test>")
    assert report["ok"] is True
    assert report["errors"] == []


# --- capabilities -----------------------------------------------------------

def test_undeclared_capability_is_a_compile_error():
    src = ('target: python\n\ntask f(p: text) returns text:\n    return hash p\n'
           '\nexpect:\n    f("x") is present\n')
    _, err = _first_error(src)
    assert err["code"] == "undeclared-capability"
    assert "crypto" in err["message"]
    assert err["hint"] == "add `use capability crypto` at the top of the program"


def test_unknown_capability_suggests_nearest():
    src = ('target: python\n\nuse capability databse\n\n'
           'task f(x: whole) returns whole:\n    return x\n\nexpect:\n    f(1) == 1\n')
    _, err = _first_error(src)
    assert err["code"] == "unknown-capability"
    assert err["suggestion"] == "database"


def test_table_needs_database_capability():
    src = ('target: python\n\nrecord R:\n    a: whole\n\ntable rs: R\n\n'
           'task f(x: whole) returns whole:\n    return x\n\nexpect:\n    f(1) == 1\n')
    _, err = _first_error(src)
    assert err["code"] == "undeclared-capability"
    assert "database" in err["message"]


def test_capability_surface_is_reported_and_program_runs():
    src = ('target: python\n\nuse capability crypto\n\n'
           'task same(a: text, b: text) returns flag:\n'
           '    return hash a is hash b\n\n'
           'expect:\n    same("x", "x") == true\n    same("x", "y") == false\n')
    report = check(src, filename="<test>")
    assert report["capabilities"] == ["crypto"]
    assert report["ok"] is True


def test_email_adapter_import_renamed_on_collision():
    # `email` is a parameter, so the email capability must import under an alias
    # (mailer) — the import is renamed, never the user's identifier.
    src = ('target: python\n\nuse capability email\n\n'
           'task notify(email: text) returns nothing:\n'
           '    send email to email with subject "hi" body "there"\n\n'
           'expect:\n    notify("a@b.c") is nothing\n')
    out = compile_source(src, filename="<test>")
    assert "from pedro_capabilities import email as mailer" in out
    assert "mailer.send(to=email" in out


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


# --- the capability -> permission manifest bridge ---------------------------

_SIGNUP = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "examples", "signup.pedro",
)


def _read_signup():
    with open(_SIGNUP, "r", encoding="utf-8") as f:
        return f.read()


def test_permissions_manifest_grants_only_declared_capabilities():
    src = _read_signup()  # declares database, email, crypto (not http/files/…)
    surface, rules = permission_manifest(src, filename="signup.pedro")
    assert surface == ["database", "email", "crypto"]
    # An UNDECLARED capability's rules must NEVER appear in the output.
    for cap in ("http", "files"):
        for rule in CAPABILITY_RULES[cap]:
            assert rule not in rules, f"{rule!r} leaked from undeclared {cap}"
    # Only what database + email justify (crypto is local-only → no rule).
    assert rules == ["Bash(psql:*)", "Bash(sendmail:*)"]


def test_permissions_manifest_is_byte_identical_on_regeneration():
    src = _read_signup()
    a = render_permissions(src, filename="signup.pedro")
    b = render_permissions(src, filename="signup.pedro")
    assert a == b                      # deterministic, same guarantee as codegen
    assert '"allow"' in a and "Bash(psql:*)" in a


def test_permissions_pure_program_emits_empty_manifest():
    src = _wrap(["return x"])          # declares no capabilities
    surface, rules = permission_manifest(src)
    assert surface == []
    assert rules == []
    settings = render_permissions(src, fmt="claude-settings")
    assert '"allow": []' in settings


def test_permissions_json_format_shows_derivation():
    import json as _json
    doc = _json.loads(render_permissions(_read_signup(), fmt="json"))
    assert doc["capabilities"] == ["database", "email", "crypto"]
    assert doc["byCapability"]["crypto"] == []   # local-only, contributes nothing
    assert doc["allow"] == ["Bash(psql:*)", "Bash(sendmail:*)"]


def test_permissions_rejects_unknown_format():
    try:
        render_permissions(_read_signup(), fmt="yaml")
        assert False, "expected an unknown-format error"
    except ValueError as e:
        assert "yaml" in str(e)


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
