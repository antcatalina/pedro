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
from pedroc.check import check, check_targets, _diff_targets
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


# --- string interpolation (holes are compiled, not pasted) ------------------

def test_interpolation_hole_is_compiled_through_codegen():
    # A `{a div b}` hole must translate the operator per backend, not paste raw
    # Pedro source. If it were pasted, Python would raise a codegen f-string error.
    src = ('target: python\n\ntask f(a: whole, b: whole) returns text:\n'
           '    return "avg {a div b} rem {a mod b}"\n\n'
           'expect:\n    f(17, 5) == "avg 3 rem 2"\n')
    report = check(src, filename="<test>")
    assert report["ok"], report
    assert report["expectations"][0]["passed"]


def test_comprehension_binder_resolves_in_expect_block():
    # The comprehension binder scopes over `where`, including in an `expect` line
    # (which has no task-level pre-pass to pre-declare it). Regression guard.
    src = ('target: python\n\nexpect:\n'
           '    filter v in [1, 8, 3] where v is at most 4 == [1, 3]\n')
    report = check(src, filename="<test>")
    assert report["ok"], report


def test_bad_interpolation_reports_code():
    _, err = _first_error(_wrap(['return "value {a +}"']))
    assert err["code"] == "bad-interpolation"
    assert err["hint"]


def test_empty_interpolation_reports_code():
    _, err = _first_error(_wrap(['return "value {}"']))
    assert err["code"] == "empty-interpolation"
    assert err["hint"]


def test_unterminated_interpolation_reports_code():
    _, err = _first_error(_wrap(['return "value {a"']))
    assert err["code"] == "unterminated-interpolation"
    assert err["hint"]


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


_CRUD = (
    'target: python\n\nuse capability database\n\n'
    'record Item:\n    name: text\n    quantity: whole\n    id: text = ""\n\n'
    'table items: Item\n\n'
    'task setup() returns whole:\n'
    '    let a = insert into items { name: "apple", quantity: 5 }\n'
    '    return count of items\n\n'
    'task restock(name: text, amount: whole) returns whole:\n'
    '    let it = find one it in items where it.name is name\n'
    '    update it in items set quantity to it.quantity + amount\n'
    '    return it.quantity\n\n'
    'task remove_item(name: text) returns whole:\n'
    '    let it = find one it in items where it.name is name\n'
    '    delete it from items\n'
    '    return count of items\n\n'
)


def test_update_and_delete_run_against_the_adapter():
    src = (_CRUD + 'expect:\n    given items is empty\n'
           '    setup() == 1\n    restock("apple", 10) == 15\n'
           '    remove_item("apple") == 0\n')
    report = check(src, filename="<test>")
    assert report["capabilities"] == ["database"]
    assert report["ok"] is True


def test_update_unknown_field_reports_code_and_suggestion():
    # `quantitee` is not a field of Item — the update field label must resolve.
    src = (_CRUD.replace("set quantity to", "set quantitee to")
           + 'expect:\n    given items is empty\n    setup() == 1\n')
    _, err = _first_error(src)
    assert err["code"] == "unknown-field"
    assert "'quantitee'" in err["message"]
    assert err["suggestion"] == "quantity"


def test_files_capability_round_trips_through_the_adapter():
    # `write value to file path` then `read file path` — the files capability end
    # to end, against the in-memory reference filesystem.
    src = ('target: python\n\nuse capability files\n\n'
           'task save(path: text, value: text) returns text:\n'
           '    write value to file path\n    return value\n\n'
           'task load(path: text) returns text:\n'
           '    return read file path\n\n'
           'expect:\n    save("k", "v") == "v"\n    load("k") == "v"\n')
    report = check(src, filename="<test>")
    assert report["capabilities"] == ["files"]
    assert report["ok"] is True


def test_read_file_without_capability_is_a_compile_error():
    src = ('target: python\n\ntask peek(path: text) returns text:\n'
           '    return read file path\n')
    _, err = _first_error(src)
    assert err["code"] == "undeclared-capability"
    assert "files" in err["message"]


def test_files_adapter_import_renamed_on_collision():
    # `files` is a parameter, so the files capability imports under an alias
    # (filesystem) — the import is renamed, never the user's identifier.
    src = ('target: python\n\nuse capability files\n\n'
           'task keep(files: text, value: text) returns text:\n'
           '    write value to file files\n    return read file files\n\n'
           'expect:\n    keep("k", "v") == "v"\n')
    out = compile_source(src, filename="<test>")
    assert "from pedro_capabilities import files as filesystem" in out
    assert "filesystem.write(files" in out
    assert "filesystem.read(files)" in out


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
_JOURNAL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "examples", "cookbook", "journal.pedro",
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


def test_permissions_files_only_program_grants_only_filesystem():
    # The reverse direction of the "undeclared never appears" guarantee: a
    # program that declares ONLY `files` gets exactly the filesystem grant, and
    # NONE of the network/database/email rules leak in.
    with open(_JOURNAL, "r", encoding="utf-8") as f:
        src = f.read()
    surface, rules = permission_manifest(src, filename="journal.pedro")
    assert surface == ["files"]
    assert rules == ["Read", "Write", "Edit"]
    for cap in ("http", "database", "email"):
        for rule in CAPABILITY_RULES[cap]:
            assert rule not in rules, f"{rule!r} leaked from undeclared {cap}"


# --- the suggestion engine itself -------------------------------------------

def test_nearest_is_deterministic_and_bounded():
    assert nearest("whle", ("while", "when", "repeat")) == "while"
    assert nearest("x", ("y", "z")) == "y"          # tie -> lexicographically first
    assert nearest("totallyunrelated", ("x", "y")) is None
    assert edit_distance("kitten", "sitting") == 3
    assert edit_distance("abc", "abc") == 0


# --- cross-target agreement (`check --targets`) -----------------------------

_TARGETS_PROG = (
    "target: python\n\n"
    "task half(x: whole) returns whole:\n"
    "    return x div 2\n\n"
    "expect:\n"
    "    half(10) == 5\n"
    "    half(7) == 3\n"
)


def test_check_targets_agrees_on_a_clean_program():
    report = check_targets(_TARGETS_PROG, filename="<test>",
                           targets=("python", "typescript"))
    assert report["agree"] is not False, report["summary"]
    assert report["disagreements"] == []
    assert report["results"]["python"]["ok"]
    # If node is on PATH the TS lane ran green too, so the whole thing is ok; if
    # not, python still agrees with itself (nothing to cross-check).
    if report["results"]["typescript"]["ran"]:
        assert report["ok"], report["summary"]


def test_check_targets_agrees_on_a_capability_program():
    # A capability program now runs on BOTH backends (the TS lane writes the
    # reference `pedro_capabilities.ts` adapter next to the generated program), so
    # the two targets are cross-checked like any other program.
    report = check_targets(_read_signup(), filename="signup.pedro",
                           targets=("python", "typescript"))
    assert report["agree"] is not False, report["summary"]
    assert report["disagreements"] == []
    assert report["results"]["python"]["ok"]
    # If node is on PATH, the TS lane ran the adapter path green too.
    if report["results"]["typescript"]["ran"]:
        assert report["ok"], report["summary"]


def test_diff_targets_flags_per_expectation_disagreement():
    # Two per-expectation lanes that differ on expectation #1 → a named codegen bug.
    report = {"targets": ["python", "typescript"], "agree": True, "disagreements": [],
              "results": {
                  "python": {"ran": True, "ok": True, "expectations": [
                      {"text": "a == 1", "passed": True, "detail": None},
                      {"text": "b == 2", "passed": True, "detail": None}]},
                  "typescript": {"ran": True, "ok": False, "expectations": [
                      {"text": "a == 1", "passed": True, "detail": None},
                      {"text": "b == 2", "passed": False, "detail": "got 3, expected == 2"}]},
              }}
    _diff_targets(report, report["targets"])
    assert report["agree"] is False
    assert len(report["disagreements"]) == 1
    d = report["disagreements"][0]
    assert d["kind"] == "expectation" and d["index"] == 1
    assert d["expectation"] == "b == 2"
    assert d["results"]["python"]["passed"] is True
    assert d["results"]["typescript"]["passed"] is False
    assert d["results"]["typescript"]["detail"] == "got 3, expected == 2"


def test_diff_targets_flags_whole_program_disagreement_for_coarse_lane():
    # The TS lane reports only a whole-program verdict (empty expectations); a
    # divergence must still be caught and name what each target got.
    report = {"targets": ["python", "typescript"], "agree": True, "disagreements": [],
              "results": {
                  "python": {"ran": True, "ok": True, "expectations": [
                      {"text": "a == 1", "passed": True, "detail": None}]},
                  "typescript": {"ran": True, "ok": False, "expectations": [],
                                 "error": "expectation failed: a == 1"},
              }}
    _diff_targets(report, report["targets"])
    assert report["agree"] is False
    d = report["disagreements"][0]
    assert d["kind"] == "program"
    assert d["results"]["python"]["ok"] is True
    assert d["results"]["typescript"]["ok"] is False
    assert d["results"]["typescript"]["error"] == "expectation failed: a == 1"


# --- property-based expectations (`for all n from a to b: ...`) --------------

def _forall_prog(body, lo=1, hi=20):
    return f"target: python\n\nexpect:\n    for all n from {lo} to {hi}: {body}\n"


def test_property_holds_over_the_whole_range():
    report = check(_forall_prog("n * n is at least n", lo=0))
    assert report["ok"], report
    assert report["expectations"][0]["passed"] is True
    assert report["expectations"][0]["text"].startswith("for all n from 0 to 20:")


def test_property_wrong_impl_caught_with_exact_counterexample():
    # A deliberately false property: `n mod 7 is not 0` holds until n=7. `check`
    # must enumerate the range and report the FIRST failing value precisely.
    report = check(_forall_prog("n mod 7 is not 0"))
    assert report["ok"] is False
    exp = report["expectations"][0]
    assert exp["passed"] is False
    assert exp["detail"] == "counterexample: n=7, got false"


def test_property_range_over_cap_is_refused_and_cap_is_overridable():
    src = _forall_prog("n is at least 1", lo=1, hi=100000)  # 100000 > default cap
    over = check(src)
    assert over["expectations"][0]["passed"] is False
    assert "over the cap" in over["expectations"][0]["detail"]
    # Raising the cap lets the same property run to completion.
    raised = check(src, forall_cap=200000)
    assert raised["ok"], raised


def test_property_binder_is_scoped_to_body_not_bounds():
    # `n` is in scope in the body...
    assert check(_forall_prog("n is at least 0", lo=0))["ok"]
    # ...but the bounds see only the surrounding scope: an unbound name there is
    # an ordinary name error, not silently the loop variable.
    bad = check("target: python\n\nexpect:\n"
                "    for all n from k to 5: n is at least 0\n")
    assert bad["ok"] is False
    assert bad["errors"][0]["code"] == "undefined-name"


def test_property_agrees_across_python_and_typescript():
    src = ("target: python\n\n"
           "task dbl(n: whole) returns whole:\n    return n + n\n\n"
           "expect:\n    for all n from 0 to 30: dbl(n) mod 2 == 0\n")
    report = check_targets(src, filename="<test>", targets=("python", "typescript"))
    assert report["agree"] is not False, report["summary"]
    assert report["disagreements"] == []
    if report["results"]["typescript"]["ran"]:
        assert report["ok"], report["summary"]


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
