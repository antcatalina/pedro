# In-flight task

_None._ The 2026-08-03 **database `update`/`delete` verbs** landed and are green:
the `database` capability now has its full `insert`/`find`/`update`/`delete` CRUD
surface on BOTH backends. `update <row> in <table> set <field> to <value>` and
`delete <row> from <table>` act on a row VALUE (usually a `find one` result) — no new
scoping machinery. Parser + `CapCall.field` + both codegens + `_Table.update`/`.delete`
(python + `pedro_capabilities.ts`) + `capabilities.py` verb registration +
`annotate.py` `unknown-field` check on the update label. Proof:
`examples/cookbook/inventory.pedro` (a `record` with an `enum` status, full CRUD,
9/9 green, both backends agree). `python tools/regress.py` GREEN (corpus **126**
expectations, **TS lane 19/19**, **47/47** diagnostics), differential PASS,
`check_docs.py` clean. Docs updated (README, language-card, SPEC, grammar, cookbook,
CLAUDE, WORKLOG). No task in flight.

Remaining roadmap (WORKLOG): the remaining capability verbs (`http`/`files`/`time`/
`random`) and modules (`use "file.pedro"`). GOTCHA for `time`/`random`: they break
the determinism / byte-identical guarantee unless the reference adapter is
seeded/frozen (fixed clock, seeded RNG) — design them deterministic so `check` stays
reproducible. Two ergonomic gaps still open: no `set m[i][j]`/`set list[i]`; no
char-code conversion.
