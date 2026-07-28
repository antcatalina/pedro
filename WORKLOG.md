# Pedro Work Log

Reverse-chronological log of substantive changes and next steps, so we can
resume cleanly across sessions.

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
