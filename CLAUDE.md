# CLAUDE.md — guidance for Claude and automated agents in this repo

Read this first. It's the standing context for anyone (human or agent) changing
Pedro. For deeper reading: `WORKLOG.md` (status + prioritized roadmap),
`docs/design-for-llms.md` (the philosophy), `docs/language-card.md` (the compact
language spec), `docs/cookbook.md` (worked examples).

## What Pedro is

Pedro is an **LLM-first intent language with a real, deterministic compiler
(`pedroc`)**. It is the *verifiable intermediate language between natural-language
intent and executable code*:

- **plain English → Pedro** is fuzzy and creative — that is the LLM's job.
- **Pedro → code** is exact and mechanical — that is `pedroc`'s job. **There is NO
  LLM in the Pedro→code pipeline.** Same source → byte-identical output.

The value is that an LLM emits Pedro, runs `pedroc check`, and self-corrects from
structured feedback — so the language must stay small, regular, and verifiable.

## Where things are

- `pedroc/` — the compiler: `lexer.py`, `parser.py`, `nodes.py` (AST),
  `codegen_python.py`, `codegen_ts.py` (the TypeScript backend), `check.py` (the oracle), `_expect_runner.py` (the sandboxed
  subprocess that runs `expect` blocks), `resolve.py` (name-resolution
  pass → `undefined-name`/`unknown-task`), `annotate.py` (record-literal typing
  pass → sets `RecordLit.type_name`, `ambiguous-record`/`unknown-field`/
  `missing-field`), `capabilities.py` (the capability/effect enforcement pass →
  declared surface + `undeclared-capability`/`unknown-capability`; adapter-name
  collision handling), `adapters.py` (in-memory reference adapters injected by
  `check`), `permissions.py` (the capability → agent-permission bridge: derives a
  Claude Code `settings.json`-shaped manifest from the declared surface, behind
  `pedroc permissions`), `suggest.py` (deterministic
  edit-distance "did you mean X?"), `errors.py`, `__main__.py` (CLI),
  `__init__.py` (`compile_source`). `pedro_capabilities.py` (repo root) re-exports
  the reference adapters so built examples run.
- `tests/` — `test_diagnostics.py` (structured-diagnostic tests) and
  `test_sandbox.py` (subprocess timeout/crash isolation); both are pytest-shaped
  but also self-runnable, and `tools/regress.py` invokes them.
- `examples/cookbook/*.pedro` — the regression corpus (incl. `tickets.pedro`,
  which models data with a `record` + an `enum`; and `credentials.pedro`, which
  uses the `database` + `crypto` capabilities).
- `examples/math.pedro` — integer algorithms. `examples/order_total.pedro`
  (a `record`) and `examples/signup.pedro` (database/email/crypto capabilities via
  the adapter layer) both compile and are in the corpus (signup is Python-only —
  the TS backend can't emit adapters yet).
- `tools/regress.py` — compiles and RUNS the whole corpus (this is CI). Also runs
  a small fuzz smoke by default; `--fuzz`/`--diff`/`--slow` run the full sweeps.
- `tools/backends.py` — per-backend "run + report expectations" adapter (Python via
  `check`; TypeScript via `node`, gated by `ts_available()`).
- `tools/differential.py` — runs each corpus program on every available backend and
  asserts they agree (live cross-backend diff; the TS lane runs whenever `node` is on
  PATH — capability programs are Python-only until the TS adapter path lands).
- `tools/fuzz.py` — seedable grammar fuzzer with a reference oracle; generates valid
  self-checking Pedro and asserts every backend agrees.
- `tools/eval/` — the **LLM-authoring benchmark** (makes the "go-to language for LLMs"
  claim measurable): `scorer.py` splices a candidate `.pedro` onto a task's HIDDEN
  `expect:` oracle and runs `pedroc check`; `benchmark/<id>/` holds `spec.md` (shown to
  the model) + `oracle.pedro` (hidden) + `reference.pedro` (self-tests the harness);
  `__main__.py` is the CLI (`list`/`spec`/`score`/`run`/`selftest`, no API key). The
  reference solutions are self-tested green inside `regress.py`. See `tools/eval/README.md`.
- `tools/check_docs.py` — doc-drift backstop (ground rule 6): extracts pedroc's real
  construct surface from `parser.py`/`codegen_python.py` and flags any construct the
  compiler implements that a doc marks "NOT yet supported"/🧭 (and, low-confidence, the
  reverse). Runs non-fatally inside `regress.py`; `--strict-docs` makes HIGH findings fail.
- `docs/` — `design-for-llms.md`, `language-card.md`, `cookbook.md` (+ `SPEC.md`
  planned). `skills/write-pedro/` — the NL→Pedro authoring skill.

## How to run

```
# install once (editable) so the `pedroc` command is on PATH; no PYTHONPATH needed
pip install -e .

# compile Pedro to a target (python or typescript)
pedroc build <file>.pedro -o out.py [--target python|typescript]

# check: compile, run the expect block, report per-assertion pass/fail as JSON
pedroc check <file>.pedro --json

# check EVERY target and assert they agree, expectation-for-expectation (a
# disagreement is a codegen bug, reported down to which target lost which expectation)
pedroc check <file>.pedro --targets python,typescript [--json]

# permissions: derive an agent-harness permission manifest from the declared
# capability surface (Claude Code settings.json shape by default)
pedroc permissions <file>.pedro [--format claude-settings|json]

# not installed? `python -m pedroc …` is identical when run from the repo root
python -m pedroc check <file>.pedro --json

# LLM-authoring benchmark: score how reliably a model writes correct Pedro (no API key)
python -m tools.eval list                       # the seeded tasks
python -m tools.eval score <id> <candidate>.pedro   # grade one solution
python -m tools.eval run <solutions_dir>        # grade a whole run

# regression / CI (must stay green)
python tools/regress.py
# heavier correctness sweeps (off the fast path):
python tools/regress.py --slow          # differential + full fuzz
python tools/fuzz.py --seed 0 --count 200
python tools/differential.py -v
# doc-drift backstop (also runs, non-fatally, inside regress.py):
python tools/check_docs.py              # advisory; --strict-docs to fail on HIGH findings
```

## Non-negotiable ground rules for ANY change

1. **Keep `python tools/regress.py` GREEN.** Never weaken, skip, or delete
   expectations to make it pass. If you add a backend, its lane must be green too.
2. **Verify by running.** Every new language feature ships with at least one
   `.pedro` program that exercises it (with an `expect` block) and passes
   `pedroc check`. Don't claim something works until you've run it.
3. **Keep the language SMALL and REGULAR.** It must stay learnable from
   `docs/language-card.md` within a single context window. Prefer canonical forms
   over new synonyms; every construct costs context tokens.
4. **The compiler stays DETERMINISTIC.** No LLM in Pedro→code; same source →
   byte-identical output.
5. **Errors are prompts.** Keep `pedroc check --json` structured and useful for the
   authoring loop (codes, hints, `got X, expected Y`).
6. **Update the docs.** Any change must be reflected in `README.md`, `WORKLOG.md`,
   `docs/language-card.md` (and this file if conventions change). Append a dated
   `WORKLOG.md` entry describing what you did and what is next. This rule was
   already here once and still got violated — `docs/language-card.md` told the
   authoring LLM that lists/maps/`for each` were unsupported for weeks after
   they shipped, because only some of the four docs got touched. Don't trust
   yourself to remember this by prose alone: `tools/check_docs.py` is the
   mechanical backstop (landed 2026-07-30) — it extracts pedroc's real construct
   surface from source and flags any construct the compiler implements that a doc
   still marks "NOT yet supported"/🧭. It runs automatically as a non-fatal
   warning inside `python tools/regress.py`; before you finish a docs-touching
   change, run `python tools/check_docs.py` and fix anything it flags (HIGH
   findings especially). It stays advisory until it has proven itself over a few
   runs; `--strict-docs` (on either script) promotes HIGH findings to a failure.

## Branch & workflow

Autonomous agents run round-robin on the shared **`agent/dev`** branch (queue on
AntMac); all agent work accumulates there and is reviewed + merged to `master` by a
human. Each run **merges `origin/master` into `agent/dev` first**, so your branch
always includes the latest `master` (docs, conventions, and fixes pushed from the
dev machine) — resolve any resulting merge conflict as part of your run. If a prior
run already did your task, advance it (more coverage, tests, robustness) rather than
redoing it.

## Progress & handoff (multi-session tasks)

A working session — especially an unattended agent run — can end abruptly (a
usage limit or a timeout). The toolchain commits and pushes whatever is on disk
at the end of every run, so partial *code* survives; what's easily lost is
knowing *what remains*. So:

- **`PROGRESS.md` (repo root) is the baton.** It records the ONE in-flight task:
  a checklist of what is done (`[x]`) and what remains (`[ ]`), the exact next
  action, and any gotchas/decisions made.
- **Resume first.** At the start of a session, read `PROGRESS.md` and
  `WORKLOG.md`; if there is an unfinished task, continue and finish it before
  starting anything new.
- **Update it as you go**, not just at the end — only what is on disk survives an
  abrupt stop. Keep `python tools/regress.py` green whenever you pause so partial
  work is safe to build on.
- **Clear it when done.** When a task is fully complete and green, remove it from
  `PROGRESS.md` and add a dated `WORKLOG.md` entry. If it is blocked, record the
  blocker and move on.

## Current coverage (as of this writing)

**Supported by the compiler:** scalars (`text`/`whole`/`number`/`flag`), lists,
maps, **`record`/`enum` types**, **capabilities + the adapter layer** (`use
capability …`; `table`; verbs `insert`/`send`/`hash`/`verify`; undeclared use is a
compile error; `check --json` reports the declared `capabilities` surface),
`let`/reassign, `increase`/`decrease`,
`when`/`otherwise`, `while`, `repeat`,
`for each` (+index), recursion, arithmetic + readable comparisons, membership,
`followed by`, the collection operations (`count of`, `item at`, `filter`, `sum of`,
`numbers from`, …), string interpolation, `fail with`, `match`/`case` (+ `case
otherwise`, over values *and* enum variants), `try`/`on failure as err`, typed
holes (`todo`), and `expect` with `given`/`fails with`/**property-based `for all
<name> from <a> to <b>: <flag>`** (enumerated over the bounded range; first
counterexample fails the check; capped for speed, `--forall-cap` to override).
Records → Python
`@dataclass` / TS `interface`; enums → Python `str, Enum` / TS const object. A
`{ field: value }` literal (bare keys) is a **record literal typed by context**
(resolved by `pedroc/annotate.py`); `{ "k": v }` (quoted keys) stays a map. A
collection binds its element record type via the type annotation (`list of
LineItem`), never by naming convention. **Targets:** Python **and TypeScript** (`--target typescript`
→ runnable `.ts`; `node` v24+ strips types, so no build step). Every corpus program
runs green on both, and `tools/differential.py` asserts the two backends agree.
**Diagnostics:** `line:col`, stable
`code`s + actionable `hint`s, source `snippet` with `^` caret, nearest-match
`suggestion` ("did you mean X?") for unknown identifiers/tasks/keywords, and the
program's declared `capabilities` surface; `check --json` is compact (null fields omitted).
`check` runs the generated program in a **sandboxed subprocess** (wall-clock
timeout + a POSIX `RLIMIT_CPU` backstop + restricted env,
`pedroc/_expect_runner.py`), reporting a non-terminating or crashing program as
`status:"timeout"`/`"error"` instead of hanging.

**Designed but NOT yet in the compiler** (see `WORKLOG.md` roadmap, highest first):
the remaining capability verbs (db `update`/`delete`, `http`, `files`, `time`,
`random`) and the TypeScript adapter path. The `WORKLOG.md` roadmap section is the
source of truth for what to build next. (The TypeScript backend, `record`/`enum`
types, the **capability/adapter layer**, and the first-class cross-target agreement
check — `check --targets` — have all **landed**: `pedroc/codegen_ts.py`,
`pedroc/annotate.py`, `pedroc/capabilities.py` + `pedroc/adapters.py`, and
`check_targets` in `pedroc/check.py`.)
