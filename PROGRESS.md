# In-flight task

_None._ The 2026-08-03 **TypeScript adapter path** landed and is green: capability
programs (`signup.pedro`, `credentials.pedro`) now compile AND run on the TypeScript
backend, routed through a new reference `pedro_capabilities.ts` (the mirror of
`pedro_capabilities.py`/`pedroc/adapters.py`). `codegen_ts.py` emits the capability
import, table bindings, `CapCall` verbs (`insert`/`send`/`hash`/`verify`), and
`given t is empty`; `tools/backends.py` writes the adapter next to the temp program
so the relative `.ts` import resolves; `check_targets`/`regress`/`differential` no
longer skip capability programs on TS. `python tools/regress.py` GREEN (corpus 117
expectations, **TS lane 18/18**, 45/45 diagnostics), `--slow` PASS (differential +
200-program fuzz on python+typescript), `check_docs.py` clean, TS output byte-
identical across builds. Docs updated (README, language-card, SPEC, CLAUDE). No task
in flight.

Remaining roadmap (WORKLOG): the remaining capability verbs (db `update`/`delete`,
`http`/`files`/`time`/`random`) and modules (`use "file.pedro"`). Two ergonomic gaps
still open: no `set m[i][j]`/`set list[i]`; no char-code conversion.
