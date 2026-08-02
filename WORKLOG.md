# Pedro Work Log

Reverse-chronological log of substantive changes and next steps, so we can
resume cleanly across sessions.

---

## 2026-08-02 — Normative spec LANDED (`docs/SPEC.md` + `docs/grammar.md`), reconciled with the compiler

Turned the long-planned `docs/SPEC.md` 🧭 into a real, normative specification and
added a formal EBNF grammar `docs/grammar.md`, both derived DIRECTLY from the
compiler source (`lexer.py`, `parser.py`, `nodes.py`, `annotate.py`,
`capabilities.py`, both codegens, `hashing.py`) and cross-checked against the green
corpus. Documentation-only job — **no compiler behavior changed**.

**What landed.**
- **`docs/SPEC.md`** (new) — the normative language definition: design invariants,
  lexical structure, program shape, types, records/enums (incl. context-typed record
  literals), statements, the full expression/precedence surface, capabilities +
  verbs, the `expect` block + checking semantics (properties, sandbox, `--targets`),
  determinism + the tamper-evident banner, the diagnostics code list, and a
  "not-yet-implemented" section. Its spine is a **canonical per-construct translation
  table** — every construct shown as Pedro → Python → TypeScript, transcribed from
  the two codegens (e.g. `div` → `//` / `Math.floor`, `followed by` → `+` /
  `__concat`, `==` → `==` / `__eq`, comprehensions → list-comp / `.filter/.map/
  .reduce/.find`, capability verbs → adapter calls). States plainly that the compiler
  (as run by the green corpus) is the source of truth on any doc disagreement.
- **`docs/grammar.md`** (new) — EBNF for the lexer (tokens, layout, comments,
  string rules) and the parser (program/declarations/types/statements/expressions
  with exact precedence, keyword-led operations, string interpolation), plus the
  reserved-word list. Mirrors the recursive-descent structure of `parser.py`.

**Drift found and fixed (docs side, per the job's rule — corpus is truth).** Two
genuine README/language-card claims contradicted the compiler; both are unused by
the corpus, so the fix was to the docs, not the compiler:
1. **`<T>?` optional shorthand does not exist.** The lexer has no `?` token
   (`SINGLE_OPS` omits it) and `_parse_type` has no `?` branch — `whole?` is an
   `unexpected-character` error. README line 275 even marked it "**implemented**".
   Removed the false shorthand from README + `docs/language-card.md`; `optional T`
   is the only form (confirmed by compiling).
2. **No bare `nothing` value literal.** `nothing` is a *type* keyword and part of
   the `is nothing`/`is present` predicates; `return nothing` / `let x = nothing`
   is an `undefined-name` error (the parser never special-cases the word — only the
   predicates synthesize an internal `Name("None")`). The language-card listed
   `nothing` among value literals. Corrected the card + noted the real story in
   SPEC §7.6 (an absent value comes from `find one … where`, tested with
   `is nothing`).

**Reconciliation + wiring.** README's authoring-contract "spec is normative" rule,
repo-layout tree, and Done/Next roadmap now point at the real SPEC + grammar (the
🧭/"planned" markers are gone; SPEC moved from Next → Done). `docs/language-card.md`
gained a header note that it is a teaching *subset* and SPEC/grammar are normative.

**Verified.** `python3 tools/check_docs.py` clean; `python3 tools/regress.py` green
end-to-end (exit 0 — 78 corpus expectations, 11/11 TS lane, 45 diagnostic + 6
sandbox + 5 packaging + 7 verify tests, 10/10 eval self-test, fuzz clean, doc-drift
clean). Both drift fixes reproduced by hand-compiling. Spot-checked that the banner
hash is identical across targets for one source (matching SPEC §10.2) and that
`set x[i] to` (SPEC §6) is exercised by `dp_graph.pedro`.

**Next:** nothing blocking. As the compiler grows (the remaining capability verbs,
the TS adapter path), keep SPEC's translation tables + the not-yet-implemented
section (§12) in step — they're now part of the docs-touching checklist alongside
README/language-card. A future nicety: have `tools/check_docs.py` also scan
`docs/SPEC.md`/`grammar.md` for construct-surface drift.

---

## 2026-08-02 — Tamper-evident generated output (source-hash banner + `pedroc verify`)

The 🧭 `verify-drift-detection` bet is now a real, documented feature. Every file
`pedroc build` emits carries a short hash of its **`.pedro` source** in the
`Do not edit by hand` banner, and a new `pedroc verify` command detects when a
generated file no longer matches its source.

**Banner format (compiler contract, README rule 8 — a single deliberate change).**
```
# Generated from <file>.pedro by pedroc v0.1 (target: <target>) source-hash: <12-hex>. Do not edit by hand.
```
(`//` prefix for TypeScript.) The hash is 12 hex chars of SHA-256 of the SOURCE
bytes — **not** the generated output — so it stays as deterministic as codegen
itself: same source + same compiler version → same hash → byte-identical file. A
clean `verify` never flickers.

**What landed.**
- **`pedroc/hashing.py`** (new) — `source_hash(src)` (12-hex SHA-256), `banner(...)`
  (renders the banner; the single source of truth for its format, called by both
  codegens), and `parse_banner(text)` (extracts filename/target/hash for `verify`).
- **`pedroc/codegen_python.py` + `pedroc/codegen_ts.py`** — `generate()` takes an
  optional `source_hash=` and stamps it via `hashing.banner(...)`. `None` renders as
  `source-hash: unknown` (only for callers without the source; never build/`check`).
- **`pedroc/__init__.py` + `pedroc/check.py`** — pass `source_hash(source)` through
  so both the built output and the code `check` runs carry the real hash.
- **`pedroc/verify.py`** (new) + **`pedroc verify <file>.pedro <output> [--json]`**
  in `__main__.py` — reads the stamped hash, recomputes it from the current source,
  and reports one of: **match** (hash matches AND bytes match a fresh compile; exit
  0), **stale** (source hash changed — the `.pedro` moved on; exit 1), **drift**
  (hash still matches but bytes differ from a fresh compile — the output was
  hand-edited; exit 1), or **no-banner** (not a pedroc file). The two failure modes
  are distinguished in the one-line message and in the `--json`
  `status`/`stamped_hash`/`current_hash` fields. `--json` mirrors `check`'s compact
  style.
- **`tests/test_verify.py`** (new, wired into `tools/regress.py`) — proves the
  banner carries the source hash on both backends, that the hash is of the source
  (same hash across targets), and the full end-to-end story: generate → verify clean;
  hand-edit the output → `drift`; change the source → `stale`; and that drift ≠ stale.
- **`tests/test_packaging.py`** — the byte-identical-codegen assertion now computes
  the expected banner from `source_hash(_SAMPLE)` so it tracks the new field.
- **Docs** — README rule 8 rewritten (tamper-evident, with the new banner shape),
  the three in-README "actual output" banners updated to the real new hashes, a new
  "Verifying generated output" subsection under "Using Pedro today", the 🧭 bet marked
  LANDED, and the Done/coverage lines updated. `docs/language-card.md` adds a short
  authoring-loop note (never hand-edit output; `verify` catches it). `CLAUDE.md`
  "How to run" + file map updated. `python tools/check_docs.py` clean.

**Verified:** `python tools/regress.py` green end-to-end (exit 0), including the new
7 verify tests. Hand-checked all four `verify` outcomes on `examples/math.pedro`
(clean/hand-edited/stale/no-banner) on both Python and TypeScript output.

**Determinism unchanged:** the hash is of the source, so anything that already
compiled still produces byte-identical output for the same source + compiler version;
only the banner line gained a stable `source-hash:` field.

**Next:** nothing blocking. A natural follow-on: teach the `skills/write-pedro/`
authoring skill to run `pedroc verify` after `build` in its loop.

---

## 2026-08-01 — `pedroc` is now an installable CLI (`pip install -e .`, no more `PYTHONPATH=.`)

Until now every invocation needed `PYTHONPATH=. python -m pedroc …`. `pedroc` is
now a proper packaged console script: `pip install -e .` puts a bare `pedroc`
command on PATH, and **both** `pedroc …` and `python -m pedroc …` route through the
same CLI. No language or codegen changes.

**What landed.**
- **`pyproject.toml`** (repo root) — setuptools build backend, `[project.scripts]`
  `pedroc = "pedroc.__main__:run"`, `requires-python >=3.8`, packages = `["pedroc"]`.
  The package stays zero-runtime-dependency (stdlib only).
- **`pedroc/__main__.py`** — added `run()` (no-arg console entry point that calls
  `main(sys.argv[1:])`; setuptools' wrapper does `sys.exit(run())`). `main` now also
  tolerates `argv=None`. `python -m pedroc` and the bare `pedroc` command are
  byte-for-byte the same behavior.
- **Sandbox was already relocation-safe.** `check()` runs `pedroc/_expect_runner.py`
  by ABSOLUTE path and injects `pedroc/adapters.py`'s source as `pedro_capabilities`
  into the child, and the child's env deliberately drops `PYTHONPATH` — so `check`
  works identically whether pedroc is pip-installed, run in-tree, or invoked from any
  cwd. Verified `pedroc check` on a capability-free program from `/tmp`. Both those
  files are `.py` modules inside the package, so the wheel bundles them automatically
  (confirmed by inspecting a built `pedroc-0.1-py3-none-any.whl`).
- **`tests/test_packaging.py`** (new, wired into `tools/regress.py`) — imports
  `pedroc`, compiles a tiny sample and asserts the generated Python is byte-identical,
  asserts determinism, runs `python -m pedroc` in a clean subprocess with `PYTHONPATH`
  stripped, and runs the bare `pedroc` console script when it is on PATH (skips
  gracefully in a fresh in-tree checkout where nothing is installed).
- **`tools/regress.py`** already bootstrapped `sys.path` itself, so it never needed
  `PYTHONPATH`; the new packaging tests run inside it. CI (`.github/workflows/regress.yml`)
  now does `pip install -e .` first (so the console-script test actually exercises the
  real entry point) and runs `python tools/regress.py` with no `PYTHONPATH`.
- **Docs** — `README.md` (usage block leads with `pip install -e .` + bare `pedroc`;
  all `PYTHONPATH=.` examples dropped), `CLAUDE.md` "How to run", and `.gitignore`
  (`*.egg-info/`, `*.egg`, `.eggs/`) updated. `python tools/check_docs.py` clean.

**Verified:** `python tools/regress.py` green end-to-end (exit 0; 78 corpus
expectations, 11/11 TS lane, 45 diagnostic + 6 sandbox + 5 packaging tests, 10/10
eval self-test, fuzz clean, no doc drift). Editable install + a from-`/tmp` run of
both entry points confirmed by hand.

**Next:** nothing blocking. If a future job wants a published package, add project
classifiers/long-description and consider `python -m build` in CI; otherwise the
roadmap below (remaining capability verbs, the TS adapter path) is unaffected.

---

## 2026-08-01 — LLM-authoring benchmark LANDED (`tools/eval/` — the "go-to language for LLMs" claim, made MEASURABLE)

Pedro's central claim is that it is the go-to *intent* language for LLMs. Until now
that was prose. `tools/eval/` turns it into a number: **how reliably does a model
author correct Pedro from a natural-language spec?** — scored deterministically with
`pedroc check` as the ground-truth oracle, and with **no API key** required (the
harness scores provided `.pedro` files; a live model call is a thin opt-in layer,
documented below).

**The design — hidden oracles.** Each benchmark task lives in
`tools/eval/benchmark/<id>/`:
- `spec.md` — the natural-language prompt, INCLUDING the exact required task
  signature (`task name(params) returns type`) so the hidden oracle can call the
  solution. This is the only thing a model sees.
- `oracle.pedro` — the HIDDEN grader oracle: an `expect:` block of concrete cases
  (several also use property-based `for all n from a to b` so a solution must be
  right across a whole range, not just the listed examples). The model never sees it.
- `reference.pedro` — a known-good solution, used to self-test the harness.

**The scorer** (`tools/eval/scorer.py`). Grading is exact and mechanical: take the
candidate's task definitions, DROP any `target:`/`expect:` lines it wrote itself (a
model's own tests never count — only the hidden oracle does), splice on
`oracle.pedro`, and run `check`. The returned report — per-expectation `passed` +
`detail` (`got X, expected Y`, `counterexample: n=…`), `errors` (code/line:col/hint/
suggestion), `holes`, abnormal `status` — is exactly the signal a model self-corrects
from. `grade`, `score_solutions` (aggregate: **tasks fully correct / total**), and
`self_test` (grade every reference) are the public surface a future model-driver reuses.

**The CLI** (`python -m tools.eval`): `list` (the tasks), `spec <id>` (print a task's
prompt), `score <id> <candidate>.pedro [--json]` (grade one), `run <solutions_dir>
[--json]` (grade a whole run — expects `<id>.pedro` per task; a missing file scores 0),
`selftest [--json]` (grade all references). `score`/`run` exit non-zero unless every
hidden expectation passes.

**Seeded corpus — 10 tasks, 56 hidden expectations**, spanning arithmetic
(`abs_diff`, `clamp`, `is_leap_year`), strings (`greet`, `initials`), lists
(`sum_list`, `count_even`, `maximum` — which must `fail with "empty list"`), and small
algorithms (`fizzbuzz`, `gcd`). Verified: every reference scores `ok`; a deliberately
wrong `abs_diff` (subtraction only) is caught with `got -4, expected == 4` AND the
property counterexample `n=1, got false`; a signature syntax error surfaces
`unexpected-token` with line:col + hint. The candidate's own `expect:` block is
correctly stripped (its passing-looking test never leaks into the score).

**Wired into CI.** `tools/regress.py` now runs the benchmark self-test as a
non-negotiable lane: all 10 reference solutions must satisfy their hidden oracles, so
the benchmark can't silently rot (an unsatisfiable oracle or broken splice fails CI).
`python tools/regress.py` stays fully green (corpus + TS lane + 45 diagnostics + 6
sandbox + eval self-test + fuzz + doc-drift). Docs updated: `README.md` (repo layout +
a "measure it" callout), `CLAUDE.md` (where-things-are + how-to-run), and a dedicated
`tools/eval/README.md` documenting the NL → Pedro → check → fix loop.

**Next — close the loop with a live model.** The harness stops at scoring provided
files on purpose (deterministic, offline). To measure a real model, add a driver
OUTSIDE the package (e.g. `tools/eval/drivers/anthropic_driver.py`) that per task:
(1) prompts the model with `spec.md` + `docs/language-card.md`; (2) writes the reply
to `solutions/<id>.pedro`; (3) `scorer.grade(...)`; (4) on not-`ok`, feeds the
structured JSON back and re-prompts up to *k* rounds, recording rounds-to-green (the
real self-correction-convergence metric); (5) `scorer.score_solutions(...)` for the
scorecard. Keep the API key + network confined to that driver so
`python -m tools.eval` and `tools/regress.py` stay offline. `tools/eval/README.md`
spells this out. Also easy to grow: more tasks (records/enums, `match`, capabilities),
and a difficulty/coverage tag per task.

---

## 2026-08-01 — Property-based `expect` LANDED (`for all n from a to b`, agent-native bet #3)

Turned the 🧭 `property-based-expect` bet into a real, documented feature. An
`expect:` block can now assert a **property** that must hold across a bounded
integer range, not just hand-picked examples:

```pedro
expect:
    for all n from 0 to 200: is_even(double(n))
    for all n from 0 to 50: count of sort numbers from 1 to n == n
```

**Semantics — honest brute force, not a prover.** `pedroc check` ENUMERATES the
inclusive range `[a, b]`, binds `<name>` to each integer, and evaluates the
flag-valued body. The first value that isn't true fails the expectation with
`detail: "counterexample: <name>=<v>, got false"`. Ranges stay bounded so `check`
stays fast: a range wider than the default cap (**10000**, `FORALL_CAP` in
`pedroc/check.py`) is refused as a failed expectation (`"range spans N values, over
the cap of 10000 …"`); `pedroc check --forall-cap N` overrides it. A strict
SUPERSET of the example-based syntax — every existing `expect` block is unchanged.

**What landed.**
- **Parser** (`pedroc/parser.py`, `_parse_expect`): a new `for` branch parses
  `for all <name> from <lo> to <hi>: <body>` into an expect item
  `("forall", name, lo, hi, body)`, reusing `_parse_add` for the bounds (same as
  `numbers from … to …`) and `_parse_expr` for the body. No new AST node — it rides
  the existing expect-item tuple machinery.
- **Static passes** all learned the new item shape: `resolve.py` (bounds see the
  surrounding scope, body additionally binds `<name>` — an unbound name in the
  bounds is a normal `undefined-name`), `annotate.py` (record-literal typing walks
  lo/hi/body), `capabilities.py` (verb-use walks all three).
- **`check` / the sandbox runner.** `_build_steps` renders a `forall` step (lo/hi/
  body as pre-computed expression strings + the cap + a readable `text`);
  `pedroc/_expect_runner.py` enumerates in the sandboxed child, enforces the cap,
  and emits the first counterexample. `check(..., forall_cap=)` and
  `check_targets(..., forall_cap=)` thread the override; `__main__.py` adds the
  `--forall-cap N` flag to `check`.
- **Both backends, identically.** `codegen_python.py` emits `for n in range(lo,
  (hi)+1): assert (body), "counterexample: n=…"`; `codegen_ts.py` emits the
  equivalent `for` loop throwing on the first counterexample. So `build` output on
  BOTH targets runs the property standalone, and the TS lane (which runs generated
  code via `node`) proves the property too — `check --targets python,typescript`
  agrees on property programs.

**Proof (the task's "PROVE IT").** New cookbook example
`examples/cookbook/properties.pedro` (is_even/double, a sort length-preservation
property, "primes > 2 are odd", plus ordinary examples) — passes `check`, runs
green on `node`, and agrees across targets; it's in the regress corpus (now 78
expectations). Five new tests in `tests/test_diagnostics.py` (now 45/45): a true
property passes; a false property (`n mod 7 is not 0`) is caught with the EXACT
`counterexample: n=7, got false`; an over-cap range is refused and `--forall-cap`
overrides it; the `for all` binder is scoped to the body but not the bounds; and a
property agrees across Python + TypeScript. `python tools/regress.py` green
(corpus + TS lane + 45 diagnostics + 6 sandbox + fuzz + doc-drift).

**TS note.** The TypeScript lane runs the generated program (which throws on the
first counterexample), so it reports a whole-program verdict; the check-time cap is
a Python-side guard on `check`'s enumeration. Real corpus ranges are tiny, so the
cap never bites and the backends always agree.

**Next.** No gap. Remaining roadmap unchanged: the pending capability verbs (db
`update`/`delete`, `http`/`files`/`time`/`random`) + the TypeScript adapter path;
then `docs/SPEC.md`.

---

## 2026-07-31 — `pedroc check --targets` LANDED (cross-target-check-cli, agent-native bet #2)

Promoted `tools/differential.py`'s cross-backend agreement check from a dev-only
test tool into a **first-class, user-facing pedroc feature**:
`pedroc check <file>.pedro --targets python,typescript [--json]` compiles the program
to every listed target, runs each target's `expect` suite, and reports whether all
targets **agree** on every expectation. A disagreement is a codegen bug, and the
report treats it with the same rigor as a normal check failure — it names WHICH
targets disagreed on WHICH expectation and what each got.

**What landed.**
- **`pedroc/check.py` → `check_targets(source, filename, targets, timeout)`** — the
  orchestrator. It runs the canonical Python `check` once (for the shared static
  surface: syntax/name/type/capability errors, holes, declared `capabilities`), then
  **reuses `tools/backends.py`'s per-backend run/report adapter** (`run_typescript`,
  `ts_available`, `_normalize` — the exact runners the differential tester + fuzzer
  trust) rather than duplicating it. Lazy-imports `tools.backends` (adds repo root to
  `sys.path`) to dodge the circular import, since `tools.backends` imports
  `pedroc.check` at load. Returns a report: `{targets, agree, ok, capabilities,
  errors, holes, results:{<target>:…}, disagreements:[…], summary}`.
- **Two comparison granularities (`_diff_targets`/`_diff_per_expectation`).** The
  Python lane emits a per-expectation pass/fail record for each assertion; the TS lane
  currently prints only a **whole-program** verdict (its expect block throws on the
  first failed assertion → empty `expectations`). So a coarse lane is compared at the
  `ok`-vs-`ok` level (kind `"program"`, carrying python's failing expectations + the
  TS error string) and a per-expectation lane position-by-position (kind
  `"expectation"`, naming index + text + each target's passed/detail; kind
  `"expectation-count"` on a length mismatch). This means a coarse lane never
  produces a spurious count mismatch, and if the TS backend ever grows per-expectation
  records the finer diff lights up automatically.
- **Capability programs run Python-only** (no TS adapter path yet): the TS lane is
  reported `skipped`, NOT a disagreement — mirrors `differential.py`, but keyed off
  the actual declared `capabilities` surface rather than a `"use capability"` string
  match. `ts_available()` False → TS lane `unavailable` → clear "could not verify"
  summary + non-`ok`.
- **`pedroc/__main__.py`.** New `--targets a,b` flag on `check` (validated to
  python/typescript, deduped). **A single target behaves exactly like today's `check
  --target <t>`** (verified byte-identical: `--targets python --json` diffs clean
  against plain `check --json`), so existing callers are untouched. `--json` prints
  the compact multi-target report; the human printer names each lane's result and,
  on disagreement, prints the offending expectation and what each target got. Exit 0
  iff all targets agree AND every ran lane is green.

**Proof (the task's "PROVE IT").** `--targets python,typescript` across the whole
cookbook (12 files) → full agreement, every file exit 0 (2 capability files run
Python-only, TS skipped). Then injected a one-target codegen bug (mirroring
`tools/fuzz.py`'s validation trick — flipped TS `div` from `Math.floor` to
`Math.ceil` in `codegen_ts.py`): `--targets` caught it, reporting
`agree:false` + a `program`-kind disagreement (`python: ok=True` / `typescript:
ok=False`), exit 1. Reverted; corpus back to full agreement.

**Tests** (`tests/test_diagnostics.py`, now 40/40): end-to-end agreement on a clean
`div` program (guards TS specifics behind `ts_available`), a capability program's
vacuous single-lane agreement, and two deterministic node-free `_diff_targets` unit
tests — a per-expectation disagreement (asserts index/text/both-sides detail) and a
whole-program coarse-lane disagreement (asserts the `program` record carries python's
failed list + the TS error).

**Docs.** README "Using Pedro today" gains a `--targets` run example + a full
paragraph; the committed-bet "Cross-target consistency as a CLI guarantee" is marked
LANDED and the Done/Next roadmap lines updated. `docs/language-card.md` documents the
flag in the authoring loop. CLAUDE.md "How to run" + coverage updated. `check_docs.py`
clean; full `python tools/regress.py --slow` green (73 corpus + 10/10 TS + 40
diagnostic + 6 sandbox + 200-program fuzz + corpus differential + doc-drift clean).

**Next:** unchanged from the roadmap below — the remaining capability verbs (db
`update`/`delete`, `http`, `files`, `time`, `random`) and the TS adapter path (which
would also let the TS lane emit per-expectation records, sharpening `--targets`'
disagreement reporting from whole-program to per-assertion for capability-free code).

## 2026-07-31 — Fuzzer grammar expansion → found + fixed two cross-backend bugs

The assigned job was the cross-backend correctness harness (differential tester +
grammar fuzzer, wired behind a flag). Both had **already landed** and are green.
Per the "advance it" branch rule I widened the fuzzer's grammar so it exercises
codegen paths that were untested — and it immediately surfaced **two real
compiler bugs**, both now fixed.

**Fuzzer coverage (`tools/fuzz.py`).** `gen_expect_line` grew from
arithmetic/bool/list/membership/concat to also cover: strings (`followed by` on
text + `"{interpolation}"`), collection ops (`item at`, `first/last of`,
`take`/`drop`, `copy of`, `sort`, `numbers from a to b`), and comprehensions
(`sum of … for each … where`, `collect … for each`, `filter … where`,
`count of (filter …)`). New `gen_task_program` emits a `task f(a, b) returns
whole` with a random statement body (`let`, reassign/`set`, `increase`/`decrease`,
`when`-return, `for each` accumulation over `numbers from …`) — the statement
codegen surface the fuzzer never touched — interpreted in lockstep so the
`expect f(a,b) == <exact result>` is self-checking. Everything stays
non-negative so `div`/`mod` are portable (Python `//` vs JS `Math.floor`). All
seedable/reproducible; 500 programs × several seeds green on python+typescript.

**Bug 1 — comprehension binder not scoped in `expect` blocks (`resolve.py`).**
`filter v in xs where v …` reported `undefined-name: 'v'` when written in an
`expect` line. `check_expr`'s `N.Comp` case resolved `elem`/`cond` in the *outer*
env without adding the binder; inside a task it worked only by accident because
`_bound_in` pre-collects every comprehension var into the flat task env, but the
`expect`-block env has no such pre-pass. Fixed with proper lexical scoping: bind
`e.var` locally over `elem`/`cond` (but not the iterated collection). Correct in
both contexts now.

**Bug 2 — string interpolation pasted raw Pedro source (`parser.py` +
both codegens).** A `{a div b}` hole was copied verbatim into the target string,
so operators/builtins were never translated — Python raised a codegen f-string
error and TS would have emitted `${… div …}`. Fixed with **structured
interpolation**: the parser now splits a string literal into ordered
`("text", …)` / `("expr", ast)` parts (`_parse_interpolation` → `_parse_hole`,
balancing nested braces, honoring `\{`/`\}`), stored on `N.Str.parts`. Both
backends re-generate each hole through their own `_gen_expr` (Python f-string,
TS template literal), so `div`→`//` / floored `/`, `mod`→`%`, `count of …`, etc.
all translate. Plain strings and simple `{name}` holes are byte-identical to
before (verified against the corpus). New diagnostics: `bad-interpolation`,
`empty-interpolation`, `unterminated-interpolation`.

**Tests / corpus.** `examples/cookbook/text.pedro` gains a `receipt` task that
interpolates `{total div count}` (guards bug 2 in the corpus + differential lane).
`tests/test_diagnostics.py` +5 (36 total): interpolation-hole-compiles,
comprehension-binder-in-expect regression, and the three interpolation error
codes. Full `python tools/regress.py --slow` green: 72 corpus + 10/10 TS +
36 diagnostic + 6 sandbox + 200-program fuzz + corpus differential + doc-drift
clean.

**Next:** unchanged from the roadmap below — the remaining capability verbs (db
`update`/`delete`, `http`, `files`, `time`, `random`) and the TS adapter path.

## 2026-07-31 — Sandbox hardening: in-child CPU-time rlimit backstop

The assigned job was the subprocess sandbox for `pedroc check` (run generated
code out-of-process with a wall-clock timeout + restricted env; surface
timeouts/crashes as structured JSON, not a parent hang). That **landed
2026-07-27** and is mature. Per the branch rule ("if a prior run already did your
task, advance it") I hardened it one notch deeper.

**The gap.** The only stop on a runaway child was the parent-side wall-clock
`subprocess.run(timeout=)`. That's a single mechanism living in the *parent*: if
the parent is starved/paused (loaded box, stopped in a debugger), the child keeps
burning a core. Defense-in-depth wants a limit the **kernel** enforces on the
child itself. `RLIMIT_AS` (a memory cap) was the tempting choice but is **broken
on Darwin** (confirmed empirically: `setrlimit(RLIMIT_AS, …)` fails with "current
limit exceeds maximum limit"), so a memory-based test would diverge between the
two CI machines (AntMac/darwin + GitHub Actions/ubuntu). `RLIMIT_CPU` **is**
enforced on both.

**The fix.**
- `pedroc/check.py`: new `_cpu_preexec(cpu_seconds)` — a POSIX-guarded
  `preexec_fn` that sets `RLIMIT_CPU` on the child (soft = `cpu_seconds`, hard =
  `+1s` grace). Defaults to `ceil(wall_clock)+1`, so it's a pure backstop that
  never bites a well-behaved program (corpus runs in ms). Off POSIX it returns
  `None` → the sandbox behaves exactly as before. New `cpu_timeout` param threaded
  through `check(...)` and `_run_expectations(...)`.
- `pedroc/_expect_runner.py`: installs a **SIGXCPU handler** that emits a clean
  `{"t":"cpu-limit"}` record and `os._exit(0)`s. So hitting the CPU limit is
  reported as a structured **timeout**, not a cryptic `runner exited with code
  -24` crash. The hard-limit grace window lets the handler emit before SIGKILL.
- Reporting: a `cpu-limit` record sets `cpu_exhausted` → `status:"timeout"` with a
  distinct summary ("execution exceeded its CPU-time limit …"). The hung-step index
  now counts only per-step records (`_STEP_RECORDS`), so the out-of-band `cpu-limit`
  record can't skew which expectation is named as stuck.

**Behavior for well-behaved programs is unchanged** — same pass/fail, same `got X,
expected Y`, no `status` key on a normal run (regress-verified byte-for-byte green).

**Test** (`tests/test_sandbox.py`, now 6/6): `test_cpu_limit_backstops_wall_clock`
runs the spin program with a *generous* wall-clock (20s) but a *tight* CPU limit
(1s) and asserts it's stopped as a structured `timeout` in <10s (≈1s in practice)
— proving the CPU backstop works independently of the wall-clock. POSIX-guarded
(skips cleanly off POSIX).

**Docs.** README "Sandboxed by default" bullet + CLAUDE.md sandbox line note the
CPU-time backstop; language-card's "time budget" wording already covers it. Full
`python tools/regress.py` green (72 corpus + 10/10 TS + 31 diagnostic + **6
sandbox** + fuzz + doc-drift clean).

**Next:** unchanged from the roadmap below — the remaining capability verbs (db
`update`/`delete`, `http`, `files`, `time`, `random`) and the TS adapter path.

## 2026-07-30 — Diagnostics: `unknown-keyword` suggestion for misspelled statement keywords

The assigned job was the diagnostics work (columns, specific codes+hints,
did-you-mean suggestions, compact `check --json` with snippet/caret/capability
surface). Almost all of it had **already landed** across prior runs: every
diagnostic carries 1-based `line:col`, a stable `code`, an actionable `hint`, a
`snippet` with a `^` caret, nearest-match `suggestion`s for unknown
identifiers/tasks/top-level keywords/`is at least|most`/record fields/capabilities,
and `check --json` is compact with the declared `capabilities` surface. Per the
"advance it" rule, I found and closed the one real remaining gap.

**The gap.** A misspelled *statement* keyword (`repaet`, `wen`, `incrase`,
`retrun`) fell through the statement dispatch to a bare-expression parse, then
died at the trailing `self._expect("NEWLINE")` with a confusing
`unexpected-token: expected NEWLINE, found 'x'` — caret on the *next* token, and
**no suggestion**. That's the worst kind of "errors are prompts" failure: the
model is pointed away from the actual fix.

**The fix** (`pedroc/parser.py`). Added a module-level `STATEMENT_KEYWORDS` tuple
and wrapped the fall-through `expr = _parse_expr(); _expect("NEWLINE")` in a
`try`. On a `PedroSyntaxError`, if the statement's leading word is a near-match
(edit distance, via `suggest.nearest`) to a statement keyword, it re-raises a
dedicated **`unknown-keyword`** diagnostic: caret on the keyword itself, a hint,
and the `suggestion`. Crucially it triggers **only on a parse failure**, so it
can never mis-flag a valid program — a valid bare call (`helper(x)`) or
name-operator statement (`x mod 2`, `x is 5`) parses fine and is untouched
(regress-verified). Deterministic (pure edit distance), no new synonyms.

**Tests** (`tests/test_diagnostics.py`, now 31/31): `repaet`→`repeat` (asserts
code/suggestion/line/col — caret on the keyword, not the later token),
`wen`→`when`, and a negative test that a valid bare call statement stays `ok`.

**Docs.** Added `unknown-keyword` to the language-card "read the JSON" code list
with its `repaet`→`repeat` example. README doesn't enumerate codes (no change).
`check_docs.py` clean; full `python tools/regress.py` green (corpus Python+TS,
differential, fuzz, doc-drift).

**Next:** unchanged from the roadmap below — the remaining capability verbs
(db `update`/`delete`, `http`, `files`, `time`, `random`) and the TS adapter path.

## 2026-07-30 — `match`/`try` already landed; hardened the `try` diagnostic

The assigned job was to implement `match`/`case` and `try:`/`on failure as err:`.
Both had **already landed** in a prior run: parser (`pedroc/parser.py`
`_parse_match`/`_parse_try`), both backends (`codegen_python.py` → if/elif chain +
`try/except PedroError`; `codegen_ts.py` → if-chain + `try/catch`), and `check`.
The two requested cookbook examples exist and pass on both backends —
`examples/cookbook/state_machine.pedro` (a state machine `match`-ing over an enum,
5/5) and `examples/cookbook/recover.pedro` (wraps a failing op in `try`/`on failure`
and recovers, 6/6); `tickets.pedro` also exercises `match` over enum variants.

Per the branch rule ("if a prior run already did your task, advance it"), I
**hardened the parser diagnostic** instead of redoing the feature. A `try:` body
not followed by `on failure` previously fell out as a generic
`unexpected-token` ("expected 'on', found …") with no hint — a weak "errors are
prompts" case. `_parse_try` now raises a dedicated **`missing-on-failure`** error
with a hint ("follow the try body with `on failure as err:` and a recovery block").
Added diagnostic tests for it and for the already-implemented-but-untested
`case-after-otherwise` arm ordering (`tests/test_diagnostics.py`, now 28/28).

Docs: added `missing-on-failure` to the language-card diagnostic-codes list. Full
`python tools/regress.py` green (corpus on Python+TS, differential, fuzz,
doc-drift clean).

**Next:** unchanged from the roadmap below — the remaining capability verbs
(db `update`/`delete`, `http`, `files`, `time`, `random`) and the TS adapter path.

## 2026-07-30 — Mechanical doc-drift backstop (`docs-consistency-checker`)

Built `tools/check_docs.py`, the mechanical backstop CLAUDE.md ground rule 6 (and
the `docs-alignment-audit` job) has been asking for. The 2026-07-28 audit found
`docs/language-card.md` listing `for each` under "NOT yet supported" for weeks after
it shipped — a *prose* reminder to "update the docs" already existed and still didn't
catch it. This applies Pedro's own "verify by running" discipline to its docs.

**What it does.** Extracts pedroc's real construct surface straight from source
(no imports; regex over the files):
- from `pedroc/parser.py`: every `kw == "..."`, `_is_name("...")`, and
  `_expect(..., "...")` string literal — the real keyword/construct surface;
- from `pedroc/codegen_python.py`: the `BINOP_MAP` and `_BUILTINS` dict *keys*
  (split on `_` so `count_of`/`followed_by` → the doc words `count`/`of`/`followed`/
  `by`). Careful to grab exactly those two dicts' keys, **not** the neighbouring
  `TYPE_MAP`/`CONVERT_MAP` type names (an early greedy regex leaked `whole` and
  produced a false `whole from` finding — fixed).

Then cross-references against the docs:
- **HIGH confidence** — the exact 2026-07-28 bug class. In doc "unsupported"
  regions (language-card's "## NOT yet supported" section + 🧭-marked spans in
  README/language-card), flag any code span containing an **adjacent run of ≥2
  implemented keywords** — i.e. an implemented *multi-word construct* declared
  not-yet-real. The adjacent-run≥2 rule is what keeps it quiet: base-with-
  unimplemented-variant lines (keyed/descending `sort`, module `use <name> from
  "..."`, `random whole from … to …`, `is a valid email`) never form such a run
  because a non-keyword/placeholder token breaks it. Meta-lines *about* the 🧭
  convention are excluded, and 🧭 must be within 30 chars of the span.
- **LOW confidence** (clearly labelled, separate) — the reverse: a bare keyword-
  shaped code span in a language-card "(supported)"/Statements/Expressions **bullet**
  (no negation cue, not fenced) whose word appears as a string literal *nowhere* in
  `pedroc/*.py`. Conservative on purpose (bullet-only + negation filter + host-word
  stoplist) so it's silent on a clean repo.

**Wiring.** Runs as a clearly-separated, labelled step in `tools/regress.py`,
**non-fatal by default** (new heuristic — false positives possible) but printed
loudly. `python tools/regress.py --strict-docs` (or `python tools/check_docs.py
--strict-docs`) promotes HIGH findings to a nonzero exit.

**Proven.** Clean (zero findings) on the current post-2026-07-28-audit repo. Then
temporarily re-added `for each` to language-card's "NOT yet supported" list — the
tool flagged it HIGH (`--strict-docs` exit 1) — and reverted; still clean. Full
`python tools/regress.py` green.

**Next (follow-up job): flip the default to strict.** Once `check_docs.py` has run
across a few sessions with no false positives, a future job should make HIGH findings
fail `tools/regress.py` by default (drop the `--strict-docs` gate for HIGH), keeping
LOW advisory. Also possible: single-word HIGH detection (currently the adjacent-run≥2
rule intentionally ignores a lone implemented keyword marked unsupported, to avoid the
base/variant false positives), and scanning `docs/cookbook.md` too.

Docs updated: `README.md` (tooling tree + "Docs can't silently drift" note + roadmap
item marked LANDED + Done list), `CLAUDE.md` (ground rule 6, "Where things are", "How
to run"), this entry. No compiler behavior changed.

---

## 2026-07-29 — Docs-accuracy audit (`docs-alignment-audit`, docs only)

Recurring README/language-card/CLAUDE.md/WORKLOG-vs-actual-compiler cross-check.
Derived the real keyword surface from `pedroc/parser.py` (`kw ==` / `_is_name`
branches) and collection-op / capability-verb parsing, plus `codegen_python.py`
/ `codegen_ts.py`, and diffed every doc claim against it — not against each other.
Spot-checked by compiling the README's worked examples (`recover.pedro`,
`order_total.pedro` Python **and** TypeScript, `signup.pedro` permissions) and
diffing real output against what's shown.

**Drift found and fixed (all stale-in-the-conservative-direction — real features
described as not-yet, the exact bug this job guards against):**

- `README.md` status blurb (line 7) still said "Capabilities/effects and modules
  are fully designed and next up" — capabilities **landed** on the Python backend
  weeks ago (the body + coverage section already say so). Now: capabilities
  implemented; TS adapter path + modules are what's next.
- `README.md` FAQ "Which languages can it target?" still said `pedroc` emits
  **Python** today with "TypeScript is the next backend" — TS **landed**. Now
  states both backends emit today with the differential tester asserting agreement.
- `README.md` TS worked-output snippet showed `interface LineItem` immediately
  after the banner, silently omitting the ~35-line `__eq`/`__in`/`__sort`/`__concat`
  runtime preamble the real output emits (and which line 268 itself documents).
  Added an explicit elision marker, matching the `# ...` precedent in the Python
  `recover.py` snippet.
- `CLAUDE.md` "Where things are": `tools/differential.py` note said the TS lane is
  "pending until the TS backend lands" — it has landed and runs a live cross-backend
  diff. Also fixed the build-command comment `(python today)` → `(python or
  typescript)`.

**Verified accurate, left unchanged:** `docs/language-card.md` (keyword surface,
collection ops, capability verbs, "NOT yet supported" list all match the compiler);
README's permissions mapping table vs. `pedroc/permissions.py` (exact); README
coverage section (line 597); the "known predicates" / capability-verb 🧭 tags; the
dated WORKLOG entries whose "TS PENDING" language was accurate *at their time* and
correctly scoped to the still-pending TS capability-adapter path.

No compiler behavior changed. `python tools/regress.py` green (no-op for this job).
`tools/check_docs.py` still does not exist — that mechanical backstop is the separate
`docs-consistency-checker` job, not yet built.

---

## 2026-07-29 — Machine-independent CI on GitHub Actions (`regress-workflow`)

Added `.github/workflows/regress.yml`: a second, independent verification path for
the green/red signal that does **not** depend on AntMac at all. It runs on every
push to `agent/dev`/`master` and on every pull_request; checks out the repo, sets up
Python 3.11 and Node 24, and runs `PYTHONPATH=. python tools/regress.py`. A non-zero
exit fails the GitHub check — no `continue-on-error`, no allowed failures.

**Why.** Until now the *only* signal that a branch was green was this one Mac's local
cron running `regress.py`. If the Mac is down, logged out (has happened for real), or
misconfigured, nobody found out except by SSHing in and reading logs. GitHub Actions
removes that single point of failure.

**Authoritative signal, going forward.** The `regress` workflow is now the
authoritative, machine-independent source of truth for whether a branch is green.
**AntMac's cron is a convenience/build engine on top of it** (it also drives the
agent queue), *not* the source of truth. Both run the identical command, so a pass in
either means the same thing.

**Mirrors CI exactly.** There is no separate `ci.sh` in this repo — the single
canonical CI command (documented in `CLAUDE.md` and `README.md`) is
`PYTHONPATH=. python tools/regress.py`. The workflow runs precisely that, so a green
GitHub check means the same thing a green local run means. pedroc is zero-dependency
(stdlib only), so the workflow installs nothing beyond the Python and Node runtimes;
Node is present purely so the TS lane's `ts_available()` probe (`tools/backends.py`)
lights up automatically (node v24+ strips TS types at runtime — no build step).

**Docs.** Added a `regress` status badge to the top of `README.md` (points at the
workflow, so the GitHub repo page shows green/red with no SSH), and a
"CI is machine-independent" note in the tooling section.

**Verification.** `regress.yml` is syntactically valid YAML (parsed clean by Ruby's
`YAML.load_file`), and `python tools/regress.py` stays green locally (26/26
diagnostics, 5/5 sandbox, corpus green on both backends, fuzz smoke 0 failures). Live
GitHub Actions verification happens on the next real push from this branch — this
sandbox can't trigger Actions, but the pipeline is correct by inspection and mirrors
the local command exactly.

**Next.** Nothing required. Once a push lands, confirm the badge renders and the first
run is green; if GitHub's runner Python (3.11) ever diverges from local behavior,
pin/adjust `python-version` here.

---

## 2026-07-29 — Capability → agent-permission bridge LANDED (`capability-permission-bridge`)

`pedroc permissions <file>.pedro [--format claude-settings|json]` turns a program's
declared capability surface into a ready-to-use permission manifest for an agent
harness. This is the first of the four agent-native bets (roadmap addendum
2026-07-28) to land, unblocked by capabilities-and-adapters shipping the day before.

**What landed.**
- **New `pedroc/permissions.py`** — a `CAPABILITY_RULES` mapping table + a pure
  `permission_manifest(source)` (returns `(surface, rules)`) + `render(source, fmt)`.
  The manifest is DERIVED from `check_capabilities(program)`'s declared surface, so
  regenerating from the same source is **byte-identical** (same determinism guarantee
  as codegen). A program that declares no capabilities emits an empty, no-op manifest.
- **The mapping (simple + documented, a starting bridge not a policy engine):**
  `http` → `WebFetch`, `Bash(curl:*)`, `Bash(wget:*)`; `database` → `Bash(psql:*)`;
  `email` → `Bash(sendmail:*)`; `files` → `Read`, `Write`, `Edit`; `time`/`crypto`/
  `random` → nothing (local-only, no external I/O to grant). Rules are deduped and
  emitted in canonical capability order.
- **Two formats.** `claude-settings` (default) → a `{"permissions":{"allow":[…]}}`
  block droppable straight into a Claude Code config; `json` → an auditable breakdown
  (`capabilities`, flat `allow`, and `byCapability` showing which cap justified what).
- **CLI:** new `permissions` subcommand in `pedroc/__main__.py` (syntax/format errors
  reported like `build`).

**Proof (against `examples/signup.pedro`, which declares database + email + crypto).**
The manifest is exactly `["Bash(psql:*)", "Bash(sendmail:*)"]` — `crypto` is local so
grants nothing, and `http`/`files` (never declared) never appear. Five new tests in
`tests/test_diagnostics.py` (26/26): grants-only-declared (asserts an UNDECLARED
capability's rules never leak into the output), byte-identical regeneration, empty
manifest for a pure program, the `json` derivation breakdown, and unknown-format
rejection.

**Docs.** README "Built for agent-heavy teams" replaces the 🧭 permission-bridge bet
with a real description + the mapping table + the signup worked example; the committed-
bets list marks it LANDED and the "Done" line includes it. `docs/language-card.md`
notes the command in the capabilities section (flagged as downstream tooling — it does
not change the authoring loop). CLAUDE.md layout + "How to run" updated.

**Regression.** `python tools/regress.py` → 72 corpus expectations + 10/10 TS (2
capability programs Python-only, skipped) + 26 diagnostic + 5 sandbox + 12-program
fuzz, all green. Manifest verified byte-identical on regeneration.

**Next (roadmap):** the remaining capability verbs + the TS adapter path; then the
other three agent-native bets (`cross-target-check-cli`, `property-based-expect`,
`verify-drift-detection`).

---

## 2026-07-28 — Capabilities + the adapter layer LANDED (roadmap #3)

Pedro's core differentiator — **auditable by construction** — is real now. A program
is pure until it declares `use capability <name>`; the set of declarations is its
**blast radius**, and using a verb whose capability isn't declared is a **compile
error**, never a silent import. `examples/signup.pedro` (design-only for weeks) now
compiles and passes `pedroc check` against in-memory mock adapters, and a second
effectful example (`examples/cookbook/credentials.pedro`) joins the corpus.

**What landed (Python backend):**
- **Directives:** `use capability database|http|email|files|time|crypto|random`
  parse and are enforced. **Verbs emitted today:** `insert into <table> { … }`
  (database, returns id), `send email to <a> with subject <s> body <b>` (email),
  `hash <t>` + `verify <t> against <h>` (crypto). Reading a table needs no new verb —
  a `table` handle is iterable, so `find one … in <table>`, `count of <table>`, and
  `for each … in <table>` reuse the existing collection path.
- **Tables:** `table users: User` binds a row type EXPLICITLY (never by pluralizing a
  name) → `users = database.table("users", User)`. `given <table> is empty` (in an
  `expect:` block) resets a table for test isolation.
- **The adapter layer.** Capability calls compile through a swappable
  `pedro_capabilities` module — one adapter object per capability. Generated code
  stays clean (`crypto.hash(...)`, `users.insert(...)`, `mailer.send(...)`). The
  in-memory reference adapters live in `pedroc/adapters.py`; `check` injects that
  source into its sandboxed subprocess as `pedro_capabilities`, so an effectful
  program is runnable with zero setup and no real I/O. Repo-root
  `pedro_capabilities.py` re-exports them so a *built* example runs too (verified:
  `build examples/signup.pedro` → run → `all expectations passed ✓`).
- **Contract #7 (collision rename).** The adapter is imported under a non-colliding
  alias when the default name is a user identifier: signup's `email` parameter forces
  `from pedro_capabilities import database, email as mailer, crypto` — the *import* is
  renamed, never the user's identifier. Deterministic (default → fallback → suffix).
- **Enforcement + surface.** New `pedroc/capabilities.py` holds the metadata and the
  enforcement pass (run in both `compile_source` and `check`): `unknown-capability`
  (with did-you-mean), `undeclared-capability` (verb used without its `use`),
  `unknown-record` (bad table row type). `check --json` reports the declared surface
  as its (previously reserved) `capabilities` field, e.g.
  `"capabilities":["database","email","crypto"]`.

**Design notes.** `CapCall(cap, verb, args)` is a pure EXPRESSION node; a bare verb
statement (`send …`) parses as `ExprStmt(CapCall(...))`, so only the four
expr-walkers (resolve/annotate/codegen) needed to learn it. `Use`/`Table` are
top-level items. Verbs are reserved words in their positions (`hash`/`insert`/
`send`/`verify`) — documented in the language card.

**TypeScript: PENDING.** The TS backend has no JS reference-adapter + injection path
yet, so `codegen_ts.generate` raises on a capability program and the corpus/differential
TS lanes SKIP them (Python-only, clearly noted). Everything else stays green on both.

**Regression.** `python tools/regress.py --slow` → **72 corpus expectations** (Python)
+ 10/10 TS (2 capability programs skipped) + **21 diagnostic tests** (5 new capability
tests: undeclared/unknown/table-needs-db/surface-reported/alias-rename) + 5 sandbox +
200-program fuzz over python+typescript + full differential, all green. Output verified
byte-identical on recompile.

**Next (roadmap):** the remaining capability verbs (db `update`/`delete`, `http`,
`files`, `time`, `random`) + the TypeScript adapter path; then the
`capability-permission-bridge` (`pedroc permissions`, now unblocked) and
`pedroc check --targets`.

---

## 2026-07-28 — `record` and `enum` types LANDED (roadmap #2)

Pedro can model data now. `record` and `enum` are top-level declarations that
compile on **both** backends, and `examples/order_total.pedro` (which declares
`record LineItem`) is finally a real, passing corpus program on Python and
TypeScript — it was a design-only example for weeks.

**Syntax + the map-vs-record split.** A `record Name:` block has typed fields with
optional defaults; an `enum Name:` block lists variant names (referenced as
`Name.variant`). The key design call: a `{ ... }` literal is classified
**syntactically** — bare-identifier keys (`{ name: "pen" }`) make it a **record
literal**, string/expression keys (`{ "a": 1 }`) keep it a **map**. This avoids
type inference for the *classification* step (the only corpus map, in dp_graph,
already uses string keys, so nothing regressed).

**Which record a literal is → `pedroc/annotate.py`.** A record literal carries no
type name in the source, so a new post-parse pass propagates an EXPECTED TYPE
top-down from the anchors that know it — a task-call argument (callee param type),
a `return` (task return type), a nested record field, and `list`/`map` element
types — and sets `RecordLit.type_name`. No expected type → a unique field-set
match. Anything unresolved is `ambiguous-record`; a bad/absent field is
`unknown-field`/`missing-field`. The pass runs in both `compile_source` (build)
and `check`.

**Codegen (both backends, kept in agreement).**
- Python: record → `@dataclass` (so `item.price` is attribute access, not a dict
  lookup), with `from __future__ import annotations` so field-type order never
  bites; enum → `class C(str, Enum)` (the `str` mixin makes `C.x == "x"`, matching
  the TS string). A record literal → `C(field=value, ...)`.
- TypeScript: record → `interface` + a plain object literal; enum → a
  `const C = { x: "x", ... } as const` value plus a `type C = ...` union (the
  erasable stand-in for `enum`, which Node's type-stripping can't run). `C.x` is
  just the string `"x"`, so `match`/`==` over variants agree with Python.
- Record-literal codegen **fills in any omitted defaulted fields at codegen time**,
  so both backends emit the identical, complete field set (TS interface fields stay
  required; the two lanes can't drift).

**Sandbox fix.** `@dataclass` resolves its module via `sys.modules[cls.__module__]`,
so the check runner's bare-dict namespace made record programs crash on load. The
runner now execs into a real `types.ModuleType("pedroc_check")` registered in
`sys.modules` (still not `__main__`, so the generated expect block stays dormant).

**Design question resolved (table → record binding).** WORKLOG's open question was
how a collection/table name binds to its record type. Rule chosen (simplest,
deterministic): **explicitly, via the type annotation** — `items: list of LineItem`
— never by naming convention (no `users` → `User` pluralization). Documented in
`docs/language-card.md`; `# pedro-note` added where it applies in
`examples/order_total.pedro` and `examples/signup.pedro` (the future-`database`
example).

**Proof + regression.** `examples/order_total.pedro` compiles + passes, and a new
`examples/cookbook/tickets.pedro` models an issue tracker with a `record Ticket`, an
`enum Priority` (with defaults), and a `match` over enum variants — green on both
backends. Both files were added to the `regress.py` + `differential.py` corpus.
Four new record/enum diagnostic tests in `tests/test_diagnostics.py` (16/16).
`python tools/regress.py --slow` → **65 corpus expectations + 10/10 TS + 16
diagnostic + 5 sandbox + 200-program fuzz over python+typescript + full
differential, all green.** Output verified byte-identical on recompile.

**Next (roadmap):** capabilities + adapter layer (#3, unblocks
`examples/signup.pedro`); promote the differential into `pedroc check --targets`.

---

## 2026-07-28 — TypeScript backend LANDED (roadmap #1)

Pedro now compiles to **TypeScript as well as Python** from the same AST — the
"one source, many verified targets" promise is real, not aspirational. Every
corpus program (22 cookbook algorithms across 7 files + `examples/math.pedro`)
builds with `--target typescript` and runs green on `node` (v26 here; v24+ strips
types, so `.ts` runs with no build step), and `tools/differential.py` now runs a
**live cross-backend diff**: it asserts Python and TypeScript agree expectation-
for-expectation on the whole corpus, and the fuzzer runs both backends too.

**Refactor first (so `followed by` and `let` retarget cleanly):**
- `parser.py`: `let x = …` now sets `Assign(is_decl=True)` (JS needs `let x` for a
  fresh binding vs. bare `x =` for reassignment; Python ignores the flag). `set`
  keeps `is_decl=False`.
- `parser.py`: `followed by` now emits `BinOp("followed_by", …)` instead of `"+"`
  — list-concat differs from `+` in JS (`[1]+[2]` is `"12"` there).
- `codegen_python.py`: added `"followed_by": "+"` to `BINOP_MAP` so Python still
  concatenates. Python lane stayed green (57 expectations) through the refactor.

**New `pedroc/codegen_ts.py`** — `generate(program, filename)` → TypeScript, using
only *erasable* type syntax so `node` can run it directly. Types: text→`string`,
whole/number→`number`, flag→`boolean`, nothing→`void`, `list of T`→`T[]`,
`map of K to V`→`Record<K,V>`, `optional T`→`T | null`. A fixed runtime preamble
of `__`-helpers bridges the Python→JS semantic gaps:
- `__eq` — **deep value equality** (JS `===` is reference-equal for arrays/objects,
  so without this every array expectation would fail).
- `__in` (arrays/strings `.includes`, objects `in`), `__len`, `__range` (inclusive),
  `__sort` (numeric+string-safe comparator, since JS default sort is lexicographic),
  `__concat` (arrays `.concat`, strings `+`), `__last`, `__whole` (`Math.trunc`).
- `class PedroError extends Error {}` is emitted only when `fail`/`try`/`fails` use it.

Per-node bridges: `==`→`__eq`, `!=`→`!__eq`, `div`→`Math.floor(a/b)`, `mod`/`%`→`%`,
`followed_by`→`__concat`, `in`/`not in`→`__in`/`!__in`, `is`/`is not`→`===`/`!==`
with `None`→`null`, `and`/`or`→`&&`/`||`; `add`→`.push`, `swap`→array destructuring,
`fail with`→`throw new PedroError()`, string interpolation→template literals,
comprehensions→`.filter`/`.map`/`.reduce`/`.find`, `for each (+index)`→`for..of` /
`.entries()`, `repeat n`→a counted `for`-loop. Map literals use computed keys
(`{[k]: v}`) so any key expression works. The `expect` block becomes a top-level
IIFE that runs the checks and prints the file's success line ending in ✓.

**Wired up:** `pedroc/__init__.py` registers `"typescript"` in `_TARGETS` and sets
`program.target = target` in `compile_source` so the generated banner matches the
chosen backend. Output is deterministic (byte-identical recompiles verified).

**Regression:** `tools/regress.py` gained a TS corpus lane that runs automatically
whenever `node` is on PATH (skips cleanly otherwise, never a CI fail). `backends.py`
already had a `run_typescript` runner + `ts_available()` probe waiting for this — it
lights up now, so `differential.py`/`fuzz.py` cover both backends with no changes.
`python tools/regress.py` → Python 57 expectations + **8/8 corpus programs green on
TS** + 12 diagnostic + 5 sandbox + 12-program fuzz over both backends, exit 0.
`--slow` (200-program fuzz + full differential over python+typescript) also green.

**Known gap (noted, not blocking):** the TS backend maps `let x` to a block-scoped
JS `let`, so a variable first declared with `let` *inside* a branch and used after
the branch would be out of scope in TS but in scope in Python (function scope). No
corpus/fuzz program does this, so both lanes are green; if it ever bites, a small
hoisting pass (declare all `let` names at task top) fixes it.

Docs updated: README (retired the "TypeScript planned / not yet" caveats — it's real
now; added a TS type column, a `--target typescript` run example, updated roadmap),
`docs/language-card.md` (target line + build step), CLAUDE.md (coverage + layout).

**Next (roadmap):** `record`/`enum` types (#2); capabilities + adapter layer (#3);
promote the differential into a first-class `pedroc check --targets` guarantee.

---

## 2026-07-28 — README + language-card accuracy pass (docs only, no compiler changes)

Audited README.md and docs/language-card.md against the actual parser/codegen
(not against WORKLOG's own summaries, to catch drift in the summaries too) —
several claims in both had gone stale as the compiler grew around them.

**Confirmed unimplemented but presented as working (README):** `record`/`enum`
declarations and construction, `use capability …` (all verbs), `module:`
directive, `use "file.pedro"` imports, the `raw <lang>: … end raw` escape
hatch, loop `stop`/`skip` (no break/continue exists at all — zero matches for
break/continue/stop/skip anywhere in parser.py, nodes.py, codegen_python.py),
keyed/descending `sort` (parser only accepts a single bare expression — the
"`sort users by created_at descending`" example was never valid syntax), and
three of the five "known predicates" (`is a valid email`, `is a valid url`,
`is even`, `is odd` — only `is empty`/`is present`/`is nothing`/`is divisible
by` actually parse). Also fixed the generated-file banner shown in the README
contract to match the real one verbatim (`# Generated from {file} by pedroc
v0.1 (target: {target}). Do not edit by hand.` — was previously shown with a
capital "Pedro", an em-dash, and an embedded version number that codegen
doesn't actually emit).

**docs/language-card.md was worse** — its "NOT yet supported" list said
lists, maps, `for each`, and string methods weren't supported, when they've
been implemented since the 2026-07-25 session and are exercised throughout
the cookbook corpus. Since this file is the actual in-context spec the
authoring skill (`skills/write-pedro/`) injects into the model's prompt, this
was actively steering the authoring LLM away from constructs that work fine,
and toward unnecessary `todo` holes.

**Fix approach:** rather than deleting the aspirational content (it's good
design work and documents real roadmap intent), tagged every not-yet-compiled
construct inline with 🧭 in both docs, moved the record+TypeScript worked
example in the README under an explicit "the full vision" heading with an
up-front disclaimer instead of a caveat buried after the fact, and swapped the
README's primary worked example for `examples/cookbook/recover.pedro`
(try/on-failure) with real `pedroc build` output pasted in verbatim — verified
by actually compiling it, not hand-written.

Also added a "Built for agent-heavy teams" pitch section (determinism as a
safety property across many agent runs, the check-loop as a machine-readable
oracle, typed holes vs. hallucination, sandboxed execution, the planned
capability manifest as an agent-governance primitive) and a "Where Pedro could
go next" subsection naming four concrete, not-yet-committed feature bets
aimed specifically at agent-driven workflows: a capability-manifest → agent
permission bridge, property-based `expect` blocks, tamper-evident generated
output (content-hash drift detection via a new `pedroc verify`), and promoting
`tools/differential.py`'s cross-target agreement check into a first-class
`pedroc check --targets` CLI guarantee. None of these are built — flagged for
discussion, not implied as done.

No compiler code changed; `python tools/regress.py` unaffected (still green).

**Decision (same day):** all four "where Pedro could go next" bets are
approved — see the roadmap addendum immediately below. They're now real,
prioritized work, queued on AntMac alongside two new jobs that address a
second problem this session surfaced: docs drift itself. `docs/language-card.md`
telling the authoring LLM that lists/maps/`for each` were unsupported (when
they'd worked since 2026-07-25) wasn't a one-off slip — CLAUDE.md ground rule
6 already says to update README/WORKLOG/language-card together, and it still
didn't happen, so the fix is mechanical enforcement, not another reminder.

## Roadmap addendum (2026-07-28) — 4 agent-native feature bets + doc-alignment tooling

Added to the AntMac queue (`~/jobs/pedro/queue.json`) in this priority order,
positioned by dependency:

1. **`capability-permission-bridge`** — depends on capabilities-and-adapters.
   `pedroc permissions <file>.pedro` derives an agent-harness permission
   manifest (starting with a Claude Code `settings.json`-shaped block) from a
   program's declared capability surface — never hand-maintained, always
   regenerated from source.
2. **`cross-target-check-cli`** — depends on the TypeScript backend +
   `tools/differential.py`. Promotes the differential tester from a dev-only
   test tool into `pedroc check <file>.pedro --targets python,typescript`, a
   guarantee any user's own code can assert, not just the corpus.
3. **`property-based-expect`** — extends `expect:` with a bounded quantified
   form (`for all n from a to b: <predicate>`), enumerated and checked (not a
   theorem prover), as a strict superset of today's example-based syntax.
4. **`verify-drift-detection`** — embeds a source content-hash in the
   generated-file banner and adds `pedroc verify <file>.pedro <output>` to
   detect stale-vs-hand-edited generated code.
5. **`docs-alignment-audit`** (recurring) — periodically re-runs the exact
   cross-reference this session did by hand (README/WORKLOG/CLAUDE.md/
   language-card.md claims vs. actual parser/codegen behavior) and fixes
   drift as it's found, instead of waiting for a human to notice.
6. **`docs-consistency-checker`** — builds `tools/check_docs.py`: greps
   pedroc's own source for the keyword/construct surface it actually
   implements and cross-references that against docs/language-card.md's "NOT
   yet supported" list and README's 🧭 tags, wired into `tools/regress.py` so
   a construct that ships without its doc catch-up gets flagged mechanically
   — the same "verify by running" principle Pedro applies to programs,
   applied to its own docs.

See `~/jobs/pedro/queue.json` on AntMac for the full prompts (they're
self-contained — an agent picking one of these up doesn't need this WORKLOG
entry, just the job prompt and the current repo state).

---

## 2026-07-27 — Differential tester + grammar fuzzer (roadmap #7, Python lane)

Built the cross-backend correctness harness. It is designed for two backends but
the **TypeScript backend has not landed** (`pedroc/codegen_ts.py` absent, `_TARGETS`
is Python-only), so per the task's own guidance the harness ships **against Python
now and the TS lane is marked PENDING** — both lanes light up automatically the
moment `codegen_ts` + `node` are present (a `ts_available()` probe gates them).

**New pieces (all under `tools/`):**
- `backends.py` — normalizes "compile source for target T, run it, report
  per-expectation pass/fail" to one shape across backends. `run_python` reuses the
  trusted `pedroc.check.check()` oracle; `run_typescript` compiles via
  `compile_source(target="typescript")` and runs the output with `node`, parsing
  newline-delimited expectation records (falling back to a coarse exit-code result).
  `ts_available()` is conservative: false → the TS lane is SKIPPED, never a CI fail.
- `differential.py` — runs every corpus program on every available backend and
  asserts they agree on each expectation. With one backend there is nothing to diff,
  so it confirms the Python lane is green and prints the TS lane as PENDING.
- `fuzz.py` — a **seedable** grammar fuzzer. It builds each expression bottom-up as
  an (source, value) pair via a reference evaluator mirroring Pedro semantics
  (`div`→floor-div, `mod`→remainder, `followed by`→concat, value-equality for
  lists), and emits `expect` lines arranged to be TRUE under the oracle. So a correct
  compiler must make every expectation pass; a failure (or a cross-backend
  disagreement) is a real bug. The domain is kept non-negative for `div`/`mod` so the
  semantics are backend-portable (Python `//` and JS `Math.floor` agree there),
  meaning the same generated corpus exercises the TS lane identically later. Failures
  print the exact seed + source for standalone reproduction
  (`python tools/fuzz.py --seed <N> --count 1`).

**Wired behind flags; default stays fast.** `python tools/regress.py` runs only a
12-program fuzz **smoke** (~1s on top of the existing ~6s suite). The heavy sweeps
are opt-in: `--fuzz` (200 programs), `--diff` (corpus differential), `--slow` (both).

**Proven to have teeth.** Injecting a codegen bug (`mod`→`//` in `BINOP_MAP`) makes
the fuzzer fail 9/40 programs with a clean repro dump; restoring it passes again.
Otherwise no bug surfaced across thousands of programs (seeds 0–5, depth ≤5) — which
is expected while both the oracle and the SUT are Python: the fuzzer's real teeth are
codegen-crash/regression detection now, and cross-backend divergence once TS lands.

`python tools/regress.py` → **57 corpus + 12 diagnostic + 5 sandbox tests + 12-program
fuzz smoke, all green.** Docs updated: README (layout, roadmap), CLAUDE.md.

**Next (roadmap):** land the TypeScript backend (#1) — it flips both harness lanes
from pending to a live cross-backend diff; then LLM authoring eval (#8).

---

## 2026-07-27 — Sandbox `check` in a subprocess (roadmap #6)

`pedroc check` used to `exec` generated code **in-process** and `eval` every
expectation in the parent — fine for the trusted corpus, but a non-terminating
program (`while x is at least 0: increase x by 1`) would hang the whole compiler,
and untrusted Pedro could run arbitrary code in-process. Now the generated program
runs in a **separate Python process** with a wall-clock timeout and a restricted
environment.

**How.** New `pedroc/_expect_runner.py` is a tiny stdlib-only script (no pedroc
imports, invoked by file path so the package isn't even importable to it). The
parent renders every expect item to plain expression strings (`_build_steps`), ships
`{code, steps}` as JSON over stdin, and reads back **newline-delimited JSON**, one
record per completed step, each `flush`ed so partial progress survives a SIGKILL.
`_run_expectations` in `check.py` runs it via `subprocess.run(..., timeout=,
env=_restricted_env(), capture_output=True)`. The restricted env drops `PYTHONPATH`
and app vars, keeping only a small allowlist (`PATH`, locale, temp dirs).

**Structured outcomes, not hangs.**
- **timeout** (infinite loop): `subprocess.TimeoutExpired`, child SIGKILLed;
  report gets `status:"timeout"`, `ok:false`, and a summary naming the expectation
  that hung (the first step with no emitted record) and how many passed before it.
- **crash** (child exits non-zero without loading cleanly): `status:"error"` + a
  `runtime-error` diagnostic carrying the last stderr line.
- **load-error** (generated code won't import): unchanged `codegen-error` behavior.

**Identical for well-behaved programs.** Same pass/fail and the same `got X,
expected Y` / `fails with` details — the runner replicates the old per-step logic
verbatim, just in the child. Normal reports carry **no** `status` key, so the
compact JSON for the whole green corpus is byte-for-byte what it was.

Default timeout `DEFAULT_TIMEOUT = 10.0s` (per-file), overridable via
`check(..., timeout=)`.

**Tests.** New `tests/test_sandbox.py` (pytest-shaped + self-runnable, wired into
`tools/regress.py`): a deliberately non-terminating program is reported as a
`timeout` in ~2s without hanging the parent; a well-behaved program keeps its exact
pass/fail + `got X, expected Y` detail and carries no `status`; `fails with` and
`given` bindings still work across the process boundary. `python tools/regress.py`
→ **57 corpus expectations + 12 diagnostic + 5 sandbox tests, all green.**

Docs updated: README, `docs/language-card.md`, CLAUDE.md.

**Next (roadmap):** differential Python/TS testing (#7); LLM authoring eval (#8).

---

## 2026-07-27 — Diagnostics / oracle quality (roadmap #5)

Sharpened `pedroc`'s diagnostics, since errors are the prompts the authoring model
self-corrects from — better errors ⇒ higher authoring reliability.

**Columns everywhere.** The lexer now emits `(type, value, line, col)` 4-tuples with
absolute 1-based columns (indentation folded back in), `PedroSyntaxError` carries
`col` + `suggestion`, and the parser threads `col` into every raise site. `build`
and `check` both report `line:col`.

**Did-you-mean.** New `pedroc/suggest.py` — a pure, deterministic Levenshtein
`nearest()` (bounded edit distance, deterministic tie-break). Wired into the
top-level "expected task/expect" error and `is at least/most`.

**Name resolution.** New `pedroc/resolve.py` runs after a successful parse and finds
`undefined-name` (unknown identifier) and `unknown-task` (unknown call target), each
with a nearest-match suggestion. Scoping is flow-insensitive (Python function scope:
every name bound anywhere in a task counts as declared) so it never false-flags a
use-before-assign or a branch-local binding — it flags only names declared *nowhere*,
i.e. typos. `Name`/`Call` AST nodes gained optional source `line`/`col`.

**Richer, compact `check --json`.** Each diagnostic now carries `col`, `suggestion`,
and a `snippet` (offending line + `^` caret); the report gained a reserved
`capabilities` surface (empty until capabilities land). The JSON is emitted COMPACT
(no indent, null/empty fields omitted) because it is consumed inside a model's
context window. New specific codes with hints: `expected-expression`,
`unterminated-string` (hint), `unexpected-character` (hint).

**Tests.** New `tests/test_diagnostics.py` feeds intentionally-broken snippets to
`pedroc.check` and asserts the structured diagnostics (code, line, col, hint,
suggestion). Pytest isn't installed in the agent env, so the file is pytest-shaped
*and* self-runnable (`python3 tests/test_diagnostics.py`); `tools/regress.py` now
invokes it, so CI covers it. `python tools/regress.py` → **57 corpus expectations +
12 diagnostic tests, all green.** No corpus program trips the resolver.

Docs updated: README, `docs/language-card.md` ("read the JSON" section), CLAUDE.md.

**Next (roadmap):** did-you-mean for undeclared capabilities once capabilities land;
sandbox `check` (roadmap #6); differential Python/TS testing (#7).

---

## 2026-07-26 — `match`/`case` + `try`/`on failure` (control-flow, roadmap #4)

Added two control-flow constructs to `pedroc` (Python backend — the TS backend
isn't landed yet, so "both backends" is Python-only for now; the AST is shaped so
TS codegen drops in trivially later).

**`match <subject>:`** with `case <value>:` arms and a final optional
`case otherwise:` default. The subject is evaluated **once** into a fresh temp
(`_subjectN`, counter reset per `generate()` call → deterministic) and compared by
equality against each case → a Python `if`/`elif`/`else` chain. Enum variants
aren't in the compiler yet, so cases match plain values (text/whole/…); the
state-machine example uses text-valued states. `case otherwise` must be last
(parser enforces `case-after-otherwise`; empty match → `empty-match`).

**`try:` / `on failure as <err>:`** → Python `try` / `except PedroError`. On
recovery, `<err>` is bound to the failure *message text* (`str(e)`), not the
exception object, so it stays a plain `text` usable in interpolation. Any `try`
now forces the `PedroError` class into the output (`_uses_pedro_error`).

**New pieces:** `nodes.Match`, `nodes.Try`; parser `_parse_match`/`_parse_try`;
codegen `_gen_stmt` arms + `_fresh_subject`; recursion added to the codegen
`_uses_pedro_error` walker and `check._collect_holes` (so holes/fail-detection
descend into match arms and try/handler bodies).

**Examples (both pass `pedroc check`):**
- `examples/cookbook/state_machine.pedro` — a turnstile state machine via `match`
  over its states, with `case otherwise: fail with "unknown state"`.
- `examples/cookbook/recover.pedro` — `checked_divide` fails on a zero divisor;
  `safe_divide` recovers with a fallback and `describe_divide` recovers using the
  bound `err` message.

`python tools/regress.py` → **57 expectations green** (was 46). Output verified
deterministic (byte-identical recompiles). Docs updated: README, CLAUDE.md
coverage, `docs/language-card.md`.

**Next (still open on the roadmap):** TS codegen for `match`/`try` when the TS
backend lands (switch/if-chain + try/catch); enum variants so `match` can switch
over `Status.active`-style cases; optional `on failure:` without a binding if it
proves useful.

---

## 2026-07-25 (later 3) — Autonomous agent queue live on AntMac

Unattended development is set up. `~/jobs/pedro/` on AntMac (apple@192.168.0.109)
runs pedroc's CI (`python tools/regress.py`) and drives Claude (model
`claude-opus-4-8`) on the shared **`agent/dev`** branch, round-robin over the
queue, on cron at 12:00 AM, 5:15 AM, and 2:30 PM (America/Denver). GitHub push
from the Mac was fixed by switching its remote to SSH (the Mac's key is already
registered on the account). All agent work lands on `agent/dev`; review and merge
to `master` periodically.

**Reprioritized roadmap — highest first (this IS the agent queue order):**
1. **TypeScript backend** — designed in full below; do this first. Second target
   proves Pedro is a language, not a Python front-end. Verify with `node` on the Mac.
2. **Records + enums** — data modeling; unblocks `examples/order_total.pedro`.
3. **Capabilities + adapters** — THE differentiator (auditable, capability-gated
   I/O); unblocks `examples/signup.pedro`.
4. **Control-flow completeness** — `match`/`case` and `try`/`on failure as err`.
5. **Diagnostics / oracle quality** — column numbers, did-you-mean, richer
   `pedroc check --json` (fix suggestions, capability surface).
6. **Sandbox `check`** — DONE (2026-07-27); run generated code in a subprocess
   with a timeout. See the dated entry below.
7. **Differential + fuzz testing** — compile each corpus program to Python AND
   TypeScript, run both, assert identical results; grammar-based fuzzer.
8. **LLM authoring eval harness** — measure how reliably a model authors correct
   Pedro (NL → Pedro → check → fix). Makes the "go-to language for LLMs" claim
   measurable.
9. **Packaging** — `pyproject.toml`, `pedroc` entry point, `pip install -e .`.
10. **Normative `docs/SPEC.md` + `docs/grammar.md`.**
11. **Cookbook expansion** — more algorithms as verified `.pedro` files.

---

## 2026-07-25 (later 2) — TypeScript backend: STARTED, handed off mid-way

**Goal:** a second codegen backend (TS) to prove Pedro is a *language*, not a
Python front-end — one source, two verified targets. Paused at the user's
request; the tree is clean and green (46/46). Resume from here.

**Environment fact (verified):** Node **v24.16.0** runs `.ts` files directly via
type-stripping — `node file.ts` works with zero setup (no npm/tsc/ts-node). So
generated TypeScript is verifiable *by running it*, same bar as Python. Generated
TS should use only erasable type syntax (annotations, interfaces, `as`) — no
`enum`/`namespace`.

**Done so far (committed):** added `is_decl: bool = False` to `nodes.Assign`
(harmless; nothing reads it yet). Compiler unchanged in behavior.

**Remaining steps to finish the backend (in order):**
1. `parser.py`: in the `let` branch set `Assign(..., is_decl=True)`; change the
   `followed by` handling in `_parse_add` from `BinOp("+", ...)` to
   `BinOp("followed_by", ...)` (list-concat differs from `+` in JS).
2. `codegen_python.py`: add `"followed_by": "+"` to `BINOP_MAP` (keeps Python
   working after step 1). `is_decl` is ignored by the Python backend.
3. New `pedroc/codegen_ts.py` — `generate(program, filename)` returning TS
   (design below).
4. `pedroc/__init__.py`: register `"typescript": generate_ts` in `_TARGETS`, and
   in `compile_source` set `program.target = target` before dispatch (so the
   header comment matches the requested backend).
5. Verify: for each `examples/cookbook/*.pedro` (+ `examples/math.pedro`),
   `python -m pedroc build <f> --target typescript -o build/x.ts` then
   `node build/x.ts` (expect "…all expectations passed ✓"). Then add a TS lane
   to `tools/regress.py` that shells out to `node` when it's on PATH.

**TS codegen design — the Python→JS semantic gaps and how to bridge them:**
- **Types:** text→`string`, whole/number→`number`, flag→`boolean`,
  nothing→`void`; `list of T`→`T[]`; `map of K to V`→`Record<K, V>`;
  `optional T`→`T | null`. (All erased at runtime.)
- **Locals:** use `is_decl` → `let x = …` for declarations, `x = …` for
  reassignment. (JS needs the distinction; Python didn't.)
- **Runtime preamble helpers (emit once at top):**
  - `__eq(a,b)` deep value-equality — **required**: JS `===` is reference-equal
    for arrays/objects but Pedro `==` is value-equal, so without this EVERY array
    expectation (fizzbuzz, quicksort, unique, merge_sort, is_anagram…) fails.
  - `__in(x,c)` — arrays/strings → `.includes`, objects → `x in c`. (Raw JS
    `x in array` checks indices, not values — must not use it.)
  - `__len`, `__range(a,b)` (inclusive), `__sort` (comparator via `< >`, since
    JS default sort is lexicographic), `__last`, `__concat` (arrays `.concat`,
    strings `+`).
- **BinOp map:** `==`→`__eq(l,r)`, `!=`→`!__eq(l,r)`, `div`→`Math.floor(l / r)`,
  `mod`→`%`, `followed_by`→`__concat`, `in`→`__in`, `not in`→`!__in`,
  `and`→`&&`, `or`→`||`, `is`/`is not`→`===`/`!==` (and `Name("None")`→`null`),
  `< <= > >=` passthrough.
- **Builtins:** count_of→`__len`, first_of→`x[0]`, last_of→`__last`,
  copy_of→`x.slice()`, chars_of→`Array.from(x)`, take→`x.slice(0,n)`,
  drop→`x.slice(n)`, item_at→`x[i]`, split→`x.split(sep)`, sort→`__sort`,
  empty_map→`{}`, range→`__range(a,b)`.
- **Comprehensions:** filter→`.filter`, collect→`.filter().map()` (or `.map()`),
  count→`.filter().length`, sum→`.reduce((acc,x)=>acc+(elem),0)`,
  find→`.find(...) ?? null`.
- **Strings:** interpolation `"{a}{b}"`→template literal `` `${a}${b}` `` (convert
  `{`→`${`, honor `\{`→literal `{`); plain strings → double-quoted.
- **Statements:** `add`→`.push`, `swap`→`[a[i],a[j]]=[a[j],a[i]]`,
  `fail with`→`throw new PedroError(msg)` (emit `class PedroError extends Error {}`
  when used), `repeat n times`→`for (let __r<depth>=0; __r<depth> < n; __r<depth>++)`,
  `for each i, x`→`for (const [i, x] of c.entries())`.
- **expect main:** emit as a top-level IIFE `(() => { …; console.log("<file>: all
  expectations passed ✓"); })();` (runs when `node file.ts` executes).
  `given`→`const`, `assert`→`if (!(expr)) throw new Error(...)`, `fails`→a block
  with `let __threw=false; try{call}catch(e){__threw=true; if(!(e instanceof
  PedroError)||e.message!==msg) throw e;} if(!__threw) throw ...`.
- **`check`** stays Python-only for execution; TS verified via build + `node`.

---

## 2026-07-25 (later) — `pedroc` compiles the whole cookbook

Grew the compiler from the integer subset to the full cookbook feature set, and
made the cookbook a passing regression suite.

### Added to `pedroc`
- Types: `list of T`, `map of K to V`, `optional T`.
- Literals: lists `[...]`, maps `{k: v}`; indexing `x[i]`; string interpolation
  (`"{a}{b}"` -> f-string); conversions `x as text|whole|number`.
- Statements: `for each x in c` and `for each i, x in c`; `add x to list`;
  `swap items at i and j in list`; `fail with "..."`; `set m[k] to v`.
- Operators: membership `in` / `not in`; `followed by` (concat); predicates
  `is empty` / `is present` / `is nothing` / `is not empty`.
- Keyword operations: `count of`, `first/last of`, `copy of`, `characters of`,
  `take/drop n from`, `item at i in`, `split by`, `sort`, `numbers from a to b`,
  `empty map of K to V`, and comprehensions `filter/collect/count/sum/find`.
- `expect` gained `given <name> = <expr>` setup and `<call> fails with "<msg>"`;
  `fail with` compiles to a generated `PedroError`, and `check` runs both forms.

### Corpus + regression
- `examples/cookbook/*.pedro` — the 22 cookbook algorithms as real source, in 5
  files (numbers, text, search_sort, collections, dp_graph).
- `tools/regress.py` — compiles + `check`s the whole corpus.
  **Current: 46/46 expectations pass across 6 files, exit 0.** This is the
  compiler's regression suite going forward.
- README reconciled with the real architecture (Claude authors -> pedroc
  compiles; the check loop; coverage/status).

### Not yet in the compiler (language-designed; next up)
`record` types, `enum`, capabilities/effects + adapter layer, `match`/`case`,
`try/on failure`, TypeScript backend. (`order_total.pedro` and `signup.pedro` use
these, so they don't compile yet — kept as design examples.)

---

## 2026-07-25 — LLM-first tooling: `check`, holes, language card, authoring skill

**Direction:** Pedro = the verifiable IR between natural-language intent and
code. The LLM does NL → Pedro (fuzzy); `pedroc` does Pedro → code
(deterministic). This session made the **generate → check → fix loop** real,
because the loop — not the compiler — is what makes a language good for LLMs.

### Added
- **Typed holes: `todo "<why>"`** — first-class uncertainty. The model flags
  unknowns instead of hallucinating. Parsed (`nodes.Todo`), compiled to a loud
  `raise NotImplementedError(...)`, and reported by `check`.
- **`pedroc check <file> [--json]`** — the machine oracle for the loop
  (`pedroc/check.py`). Reports syntax `errors` (line/code/message/hint),
  `holes`, and per-`expectation` pass/fail by **actually running** the generated
  code; failures carry `detail` = "got X, expected <op> Y". Exit 0 iff `ok`.
- **Structured error codes + hints** (`errors.py`, `lexer.py`, `parser.py`) —
  errors are prompts: `unexpected-token`, `bad-indentation`,
  `unterminated-string`, `unexpected-character`, plus hints for `:` / `returns`.
- **`docs/language-card.md`** — the compact, in-context spec the authoring LLM
  reads. Describes the SUPPORTED subset + the loop protocol. Fits in a prompt.
- **`skills/write-pedro/SKILL.md`** — the Claude Code authoring skill (NL → Pedro
  in the check loop). NOTE: needs registration to auto-load in Claude Code.

### Verified this session (all green)
- `examples/math.pedro` still compiles + runs — no regression.
- Loop demo: buggy `classify` → check flagged `classify(0)`: got 'positive',
  expected == 'zero' → fixed `otherwise` branch → `ok: true`, exit 0.
- Hole demo: `shipping_cost` with a `todo` → check reported the hole at line 6
  and marked the program incomplete.
  (Demo files live in the gitignored `build/`.)

### Decisions made (didn't ask; per "don't compromise")
- **Authoring layer = a Claude Code skill, not an API service.** The "LLM" in the
  loop is Claude-in-the-editor following the language card, so the loop needs no
  API key. An API-driven `pedroc author` CLI stays optional/future.
- **Keep significant-indentation syntax.** LLMs handle Python-style indentation
  very well (heavily represented in training data) and it is token-cheap; we
  invest in precise indentation diagnostics instead. Revisit only if LLM indent
  errors show up in practice.

## Next steps (priority order)
1. **Grow `pedroc` to the cookbook**: lists, maps, records, `for each`, and the
   collection operations. Then make `build/cookbook_check.py` the compiler's
   regression suite (compile each cookbook algorithm, run its expects through
   `check`).
2. **Capabilities + adapter layer in the compiler** (database/http/email/…).
   This is where the "auditable by construction" advantage becomes real —
   `check` should also report the declared capability surface.
3. **Second target: TypeScript codegen** from the same AST, to prove
   retargeting from one source.
4. **Sandbox `check`.** DONE (2026-07-27) — runs generated code in a subprocess
   with a wall-clock timeout and a restricted env.
5. **Reconcile README** with the new framing (retire "Claude is the compiler" in
   the body) and fold everything into `docs/SPEC.md`.

## Open questions
- Indentation vs. explicit `end`/braces for LLM robustness. Current lean: keep
  indentation + great diagnostics.
- How a table name binds to its `record` type (dict rows vs. typed records) —
  surfaced by the `signup.pedro` compile earlier.
- Cosmetic: negative literals compile with an extra paren (`classify((-3))`);
  harmless, tidy up in codegen later.

## What I need from you (all optional)
- Only if you want an **API-driven** authoring CLI (beyond the in-editor skill):
  an `ANTHROPIC_API_KEY`. The skill-based loop needs nothing.
- A **primary target language** preference beyond Python, for the retargeting
  step (TypeScript is my default guess).
- Any **reference languages** whose feel you want Pedro to match (you mentioned
  you'd share some — Inform 7 / Gherkin / SQL were on my list).
