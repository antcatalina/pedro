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
  `codegen_python.py`, `check.py` (the oracle), `errors.py`, `__main__.py` (CLI),
  `__init__.py` (`compile_source`).
- `examples/cookbook/*.pedro` — the regression corpus (22 algorithms).
- `examples/math.pedro` — integer algorithms. `examples/order_total.pedro` (records)
  and `examples/signup.pedro` (capabilities) are language-designed but **not yet
  compilable**.
- `tools/regress.py` — compiles and RUNS the whole corpus (this is CI).
- `docs/` — `design-for-llms.md`, `language-card.md`, `cookbook.md` (+ `SPEC.md`
  planned). `skills/write-pedro/` — the NL→Pedro authoring skill.

## How to run

```
# compile Pedro to a target (python today)
PYTHONPATH=. python -m pedroc build <file>.pedro -o out.py [--target python]

# check: compile, run the expect block, report per-assertion pass/fail as JSON
PYTHONPATH=. python -m pedroc check <file>.pedro --json

# regression / CI (must stay green)
python tools/regress.py
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
   `WORKLOG.md` entry describing what you did and what is next.

## Branch & workflow

Autonomous agents run round-robin on the shared **`agent/dev`** branch (queue on
AntMac); all agent work accumulates there and is reviewed + merged to `master` by a
human. If a prior run already did your task, advance it (more coverage, tests,
robustness) rather than redoing it.

## Current coverage (as of this writing)

**Supported by the compiler:** scalars (`text`/`whole`/`number`/`flag`), lists,
maps, `let`/reassign, `increase`/`decrease`, `when`/`otherwise`, `while`, `repeat`,
`for each` (+index), recursion, arithmetic + readable comparisons, membership,
`followed by`, the collection operations (`count of`, `item at`, `filter`, `sum of`,
`numbers from`, …), string interpolation, `fail with`, typed holes (`todo`), and
`expect` with `given`/`fails with`. **Target:** Python.

**Designed but NOT yet in the compiler** (see `WORKLOG.md` roadmap, highest first):
TypeScript backend (fully designed, in progress on `agent/dev`), `record`/`enum`,
capabilities/effects + adapter layer, `match`/`case`, `try`/`on failure`. The
`WORKLOG.md` roadmap section is the source of truth for what to build next.
