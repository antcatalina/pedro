# In-flight task

_None._ The 2026-08-02 normative-spec work landed and is green: `docs/SPEC.md`
(normative spec + canonical per-construct Pedro→Python→TypeScript translation
tables) and `docs/grammar.md` (formal EBNF) now exist, derived from the compiler
and reconciled with README/language-card. Two genuine doc drifts were fixed on the
doc side (the corpus is truth): the non-existent `<T>?` optional shorthand and the
non-existent bare `nothing` value literal. `python3 tools/check_docs.py` clean and
`python3 tools/regress.py` green (exit 0). See that WORKLOG entry. No task in flight.
