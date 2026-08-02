# In-flight task

_None._ The 2026-08-02 cookbook expansion landed and is green: 11 new classic
algorithms (selection/insertion sort, DFS, topological sort, Dijkstra, LCS, 0/1
knapsack, RLE enc/dec, Caesar cipher, matrix transpose, sliding-window maximum)
across 5 new `examples/cookbook/*.pedro` files, each with a passing `expect` block
and green on BOTH backends. `docs/cookbook.md` updated to match. No `todo` holes —
everything used supported constructs. `python3 tools/regress.py` green (corpus 117
expectations, TS lane 16/16), `tools/differential.py` PASS, `check_docs.py` clean.
Two ergonomic gaps noted in WORKLOG (no `set m[i][j]`/`set list[i]`; no char-code
conversion). No task in flight.
