# The Pedro authoring benchmark

Pedro claims to be the **go-to language for LLMs**. This harness makes that claim
*measurable*: it scores how reliably a model authors **correct Pedro** from a
natural-language spec, using `pedroc check` as the ground-truth oracle.

The harness itself needs **no API key**. It grades `.pedro` files you provide
(a model's outputs, or hand-written solutions) against hidden test cases. Wiring an
actual model call to generate those files is a thin, opt-in layer described at the
bottom — the scoring core stays deterministic and offline.

## The loop it measures: NL → Pedro → check → fix

This is the authoring loop Pedro is designed around, and exactly what the benchmark
scores end-to-end:

1. **NL → Pedro.** A model reads a task's `spec.md` (natural language + the exact
   required task signature) — ideally with `docs/language-card.md` in context — and
   emits a `.pedro` program. This step is fuzzy and creative: the LLM's job.
2. **check.** The grader splices the model's task definitions onto the task's
   **hidden** `expect:` oracle and runs `pedroc check`. This is exact and
   mechanical: `pedroc`'s job. No LLM in this half.
3. **fix.** `check` returns structured feedback — per-expectation `passed` +
   `detail` (`got X, expected Y`, or `counterexample: n=…`), `errors` (with `code`,
   `line:col`, `hint`, `suggestion`), `holes`, and abnormal `status`. That JSON is
   the exact signal a model self-corrects from. The model edits and re-checks.

A *good* language for LLMs is one where step 3 converges fast and often. The
benchmark's headline number — **tasks fully correct / tasks total** — is a proxy for
that: how often a model lands a program that passes every hidden expectation.

## Anatomy of a task

Each task lives in `benchmark/<id>/`:

| file              | shown to the model? | purpose                                            |
| ----------------- | ------------------- | -------------------------------------------------- |
| `spec.md`         | **yes**             | the NL prompt + the exact required task signature  |
| `oracle.pedro`    | **no (hidden)**     | the grader's `expect:` block — concrete cases and `for all` properties |
| `reference.pedro` | no                  | a known-good solution that self-tests the harness  |

The spec always pins down the **exact signature** (`task name(params) returns type`)
so the hidden oracle can call the solution. Grading drops any `expect:`/`target:`
lines the candidate wrote itself — a model's own tests never count, only the hidden
oracle does — then splices on `oracle.pedro` and runs `check`.

The benchmark seeds ~10 tasks spanning **arithmetic** (`abs_diff`, `clamp`,
`is_leap_year`), **strings** (`greet`, `initials`), **lists** (`sum_list`,
`count_even`, `maximum`), and **small algorithms** (`fizzbuzz`, `gcd`). Several
oracles include property-based `for all n from a to b` cases, so a solution has to be
right across a whole range, not just on the listed examples.

## Running the benchmark

```sh
# List the tasks / read a task's prompt (what you'd hand a model)
PYTHONPATH=. python -m tools.eval list
PYTHONPATH=. python -m tools.eval spec 08_maximum

# Grade ONE candidate .pedro file against a task's hidden oracle
PYTHONPATH=. python -m tools.eval score 01_abs_diff mysolution.pedro [--json]

# Grade a WHOLE run: a directory holding <id>.pedro for each task attempted
PYTHONPATH=. python -m tools.eval run path/to/solutions/ [--json]

# Self-test the harness: every reference solution must satisfy its hidden oracle
PYTHONPATH=. python -m tools.eval selftest
```

`score` exits non-zero unless the candidate passes every hidden expectation. `run`
prints a scorecard and the headline `tasks_ok / tasks_total`. The `--json` form of
each emits the full structured verdict — the same shape a model reads to self-correct.

`selftest` also runs (non-negotiably green) inside `python tools/regress.py`, so the
benchmark can't rot: if an oracle ever becomes unsatisfiable or the splice/grade
wiring breaks, CI fails.

## Wiring a real model call (to close the loop end-to-end)

The harness deliberately stops at *scoring provided files* so it needs no API key and
stays deterministic. To measure a live model, add a thin driver **outside** this
package (e.g. `tools/eval/drivers/anthropic_driver.py`) that does, per task:

1. Read `spec.md` and prepend `docs/language-card.md` as the system/context prompt.
2. Call the model to produce a `.pedro` program; write it to `solutions/<id>.pedro`.
3. Grade it with `scorer.grade(load_task(id), candidate_source)`.
4. **If not `ok`**, feed the returned `errors`/`holes`/failed-`expectations` JSON
   back to the model verbatim and ask for a corrected program; repeat up to *k*
   rounds. Record how many rounds each task needed — that's the real "self-correction
   convergence" metric.
5. Finally, `scorer.score_solutions({id: source, ...})` for the aggregate scorecard.

Everything the driver needs is already exposed by `scorer.py`
(`task_ids`, `load_task`, `grade`, `score_solutions`); the driver only adds the model
call and the retry loop. Keep the API key and any network access confined to that
driver so `python -m tools.eval` and `tools/regress.py` remain offline.

Use the latest, most capable Claude model for the driver (see the repo's
`claude-api` skill / Anthropic SDK docs for current model IDs) — the benchmark is
meant to track how well a *strong* model authors Pedro.
