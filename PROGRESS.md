# In-flight task

_None._ The 2026-08-03 **`files` capability** landed and is green: `write <text> to
file <path>` (statement) + `read file <path>` (expression), emitting on BOTH backends
through a swappable in-memory reference filesystem (`Files` in `pedroc/adapters.py` /
`pedro_capabilities.ts`). Undeclared use is an `undeclared-capability` compile error;
a user identifier named `files` renames the IMPORT to `filesystem` (contract #7).
Parser + `capabilities.py` verb registration + both codegens + both adapters. Proof:
`examples/cookbook/journal.pedro` (a persisted key/value store — save/load/overwrite,
3/3 green, both backends agree). `python3 tools/regress.py` GREEN (corpus **129**
expectations, **TS lane 20/20**, **50/50** diagnostics), differential PASS,
`check_docs.py` clean. Docs updated (README, language-card, SPEC, grammar, cookbook,
CLAUDE, WORKLOG). No task in flight.

Remaining roadmap (WORKLOG): the remaining capability verbs (`http`/`time`/`random`)
and modules (`use "file.pedro"`). GOTCHA for `time`/`random`: they break the
determinism / byte-identical guarantee unless the reference adapter is seeded/frozen
(fixed clock, seeded RNG) — design them deterministic so `check` stays reproducible.
Two ergonomic gaps still open: no `set m[i][j]`/`set list[i]`; no char-code conversion.
