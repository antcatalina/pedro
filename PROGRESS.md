# In-flight task — Diagnostics / oracle quality (roadmap #5)

Improve pedroc diagnostics for the LLM authoring loop: columns, richer codes+hints,
did-you-mean suggestions, enriched `check --json` (fix suggestion, source snippet w/
caret, capability surface), a pytest under tests/, docs update. Keep regress green.

## Plan / checklist
- [x] Phase A — column numbers: lexer emits 4-tuples (type,value,line,col);
      errors.py carries `col`+`suggestion`; parser threads col into all raises;
      check.py + __main__ surface col. regress green.
- [x] Phase B — suggest.py: deterministic edit-distance `nearest()`; wire keyword
      suggestions into the top-level "expected task/expect" and `is at least/most`.
- [x] Phase C — name-resolution pass (resolve.py): add optional line/col to
      Name & Call nodes; flow-insensitive per-task declared set; emit
      `undefined-name` / `unknown-task` with did-you-mean suggestion.
- [x] Phase D — enrich check JSON: add col, suggestion, source `snippet` (line +
      caret), `capabilities` surface (empty list for now); make JSON COMPACT
      (omit null fields, no indent).
- [ ] Phase E — tests/test_diagnostics.py (pytest-style + __main__ fallback since
      pytest isn't installed): feed broken snippets, assert code/line/column/hint/
      suggestion. Wired into tools/regress.py so CI runs it.
- [ ] Phase F — docs: language-card "read the JSON" section, README, WORKLOG,
      CLAUDE.md coverage.

## Gotchas / decisions
- pytest NOT installed in env → test file must also run under plain `python3`.
- Capabilities don't exist yet → `capabilities` surface is an empty list, schema
  reserved + documented; did-you-mean for capabilities deferred until they land.
- Name resolution is flow-insensitive (Python function scope): collect ALL assigned
  names in a task as declared to avoid false "undefined" on use-before/branch-assign.
  Synthesized `N.Name("None")` (from `is present/nothing`) must be in the globals set.
- Compact JSON: omit null/empty fields; absent key == null (documented).

## Next action
Phase E: write tests/test_diagnostics.py (pytest-style + __main__ runner), wire into tools/regress.py.
