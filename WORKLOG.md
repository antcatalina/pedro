# Pedro Work Log

Reverse-chronological log of substantive changes and next steps, so we can
resume cleanly across sessions.

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
6. **Sandbox `check`** — run generated code in a subprocess with a timeout.
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
4. **Sandbox `check`.** It currently `exec`s generated code in-process — fine for
   trusted local use, unsafe for untrusted input. Sandbox before any hosted use.
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
