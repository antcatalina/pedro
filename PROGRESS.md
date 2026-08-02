# In-flight task

_None._ The 2026-08-02 tamper-evident-output work landed and is green: every
generated file's `Do not edit by hand` banner now embeds a 12-hex hash of the
`.pedro` **source** (`source-hash: …`), and `pedroc verify <file>.pedro <output>
[--json]` recomputes it and reports match / stale (source changed) / drift (output
hand-edited). New `pedroc/hashing.py` + `pedroc/verify.py`; `tests/test_verify.py`
(7 tests, wired into `tools/regress.py`) proves all three states end-to-end on both
backends. Determinism unchanged (the hash is of the source). See that WORKLOG entry.
No task in flight.
