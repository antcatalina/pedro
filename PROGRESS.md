# In-flight task

_None._ The 2026-07-31 `pedroc check --targets python,typescript` feature
(cross-target-check-cli) landed and is green: `check_targets` in `pedroc/check.py`
compiles to every listed target, runs each `expect` suite, and reports whether all
targets agree on every expectation (a disagreement names which target lost which
expectation) — reusing `tools/backends.py`'s runners. Single-target `--targets`
is byte-identical to today's `check`. Proven across the whole cookbook + with an
injected one-target codegen bug. See that WORKLOG entry. No task in flight.
