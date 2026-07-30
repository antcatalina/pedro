# Pedro Work Log

Reverse-chronological log of substantive changes and next steps, so we can
resume cleanly across sessions.

---

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
