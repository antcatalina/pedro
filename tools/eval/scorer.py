"""The Pedro authoring benchmark — the core scorer.

Pedro claims to be the "go-to language for LLMs". This harness makes that claim
MEASURABLE: it scores how reliably a model authors *correct* Pedro from a natural-
language spec, using `pedroc check` as the ground-truth oracle.

The benchmark is a set of tasks under `tools/eval/benchmark/<id>/`:

    spec.md          the natural-language prompt handed to the model, INCLUDING the
                     exact required task signature (name, params, return type) so the
                     hidden oracle can call it. This is the only thing the model sees.
    oracle.pedro     the HIDDEN grader oracle: an `expect:` block of concrete cases
                     (and, where useful, `for all` properties). The model never sees
                     this. It is what a correct solution must satisfy.
    reference.pedro  a known-good solution, used to self-test the harness (every
                     reference must score `ok` — that proves the oracle is
                     satisfiable and the scorer wiring is sound). Not shown to models.

Grading a candidate is deterministic and needs NO API key: we take the candidate's
task definitions, drop any `expect:`/`target:` lines it wrote itself (we grade only
against the hidden oracle, never the model's own tests), splice on the hidden
`expect:` block, and run `pedroc check`. The returned report — pass/fail per
expectation plus the structured failure `detail`/`errors` — is exactly the signal a
model would self-correct from in the NL -> Pedro -> check -> fix loop.

See `tools/eval/README.md` for the loop and how to wire a real model call.
"""
import os

from pedroc.check import check, FORALL_CAP

BENCH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark")


# --------------------------------------------------------------------------- #
# Loading the benchmark
# --------------------------------------------------------------------------- #

def task_ids():
    """Every benchmark task id (subdirectory name), sorted for determinism."""
    if not os.path.isdir(BENCH_DIR):
        return []
    ids = []
    for name in sorted(os.listdir(BENCH_DIR)):
        d = os.path.join(BENCH_DIR, name)
        if os.path.isdir(d) and os.path.isfile(os.path.join(d, "oracle.pedro")):
            ids.append(name)
    return ids


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_task(task_id):
    """Load one task's spec, hidden oracle, and reference solution.

    `reference` is None if the task ships without one (references exist only to
    self-test the harness; a task can be graded without one)."""
    d = os.path.join(BENCH_DIR, task_id)
    oracle_path = os.path.join(d, "oracle.pedro")
    if not os.path.isfile(oracle_path):
        raise FileNotFoundError(f"no such benchmark task: {task_id!r}")
    spec_path = os.path.join(d, "spec.md")
    ref_path = os.path.join(d, "reference.pedro")
    return {
        "id": task_id,
        "spec": _read(spec_path) if os.path.isfile(spec_path) else "",
        "oracle": _read(oracle_path),
        "reference": _read(ref_path) if os.path.isfile(ref_path) else None,
    }


# --------------------------------------------------------------------------- #
# Splicing candidate + hidden oracle
# --------------------------------------------------------------------------- #

def _strip_own_expects_and_target(source):
    """Remove any top-level `target:` line and any `expect:` block the candidate
    wrote itself. We grade ONLY against the hidden oracle, so a model's own tests —
    right or wrong — must not count. Indentation-based, matching Pedro's block
    structure: an `expect:` at column 0 owns the following blank/indented lines."""
    out = []
    skipping = False
    for line in source.split("\n"):
        stripped = line.strip()
        indented = bool(line) and line[0].isspace()
        if skipping:
            if stripped == "" or indented:
                continue  # still inside the candidate's expect block
            skipping = False  # dedented back to column 0 — fall through and keep it
        if not indented and stripped.startswith("expect:"):
            skipping = True
            continue
        if not indented and stripped.startswith("target:"):
            continue  # we always re-emit `target: python` ourselves
        out.append(line)
    return "\n".join(out)


def build_graded_program(candidate_source, oracle_source):
    """Splice a candidate's task definitions onto the hidden oracle's `expect:`
    block, producing one self-contained Pedro program `check` can run.

    The result is deterministic: `target: python`, then the candidate's definitions
    (its own tests removed), then the hidden expectations."""
    body = _strip_own_expects_and_target(candidate_source).strip()
    oracle = oracle_source.strip()
    return f"target: python\n\n{body}\n\n{oracle}\n"


# --------------------------------------------------------------------------- #
# Grading
# --------------------------------------------------------------------------- #

def grade(task, candidate_source, forall_cap=FORALL_CAP):
    """Grade one candidate solution against one task's hidden oracle.

    Returns a compact, model-facing result: whether it fully passed, the score
    (expectations passed / total), and the structured failure signal (`errors`,
    `holes`, per-expectation `detail`, abnormal `status`). Nothing here is fuzzy —
    it is the raw `pedroc check` verdict, the same JSON a model reads to self-correct.
    """
    program = build_graded_program(candidate_source, task["oracle"])
    report = check(program, filename=f"{task['id']}.pedro", forall_cap=forall_cap)

    exps = report["expectations"]
    n_total = len(exps)
    n_pass = sum(1 for x in exps if x["passed"])
    # `ok` already folds in "no errors, no holes, all expectations pass".
    result = {
        "id": task["id"],
        "ok": bool(report["ok"]),
        "passed": n_pass,
        "total": n_total,
        "summary": report["summary"],
        "errors": report["errors"],
        "holes": report["holes"],
        "expectations": exps,
    }
    if report.get("status"):
        result["status"] = report["status"]
    return result


def grade_source(task_id, candidate_source, forall_cap=FORALL_CAP):
    """Convenience: load a task by id and grade a candidate source string."""
    return grade(load_task(task_id), candidate_source, forall_cap=forall_cap)


def score_solutions(solutions, forall_cap=FORALL_CAP):
    """Grade a whole benchmark run. `solutions` maps task_id -> candidate source
    (a missing/None entry counts as an unattempted task: 0 points).

    Returns `{results: [...], summary: {...}}`. The headline metric is
    `tasks_ok / tasks_total` — the fraction of tasks the model got FULLY correct
    (every hidden expectation green) — with expectation-level totals alongside.
    """
    results = []
    for tid in task_ids():
        src = solutions.get(tid)
        if not src:
            results.append({"id": tid, "ok": False, "passed": 0, "total": None,
                            "summary": "not attempted", "unattempted": True,
                            "errors": [], "holes": [], "expectations": []})
            continue
        results.append(grade(load_task(tid), src, forall_cap=forall_cap))

    tasks_ok = sum(1 for r in results if r["ok"])
    exp_total = sum(r["total"] or 0 for r in results)
    exp_pass = sum(r["passed"] for r in results)
    return {
        "results": results,
        "summary": {
            "tasks_ok": tasks_ok,
            "tasks_total": len(results),
            "expectations_passed": exp_pass,
            "expectations_total": exp_total,
            "task_pass_rate": (tasks_ok / len(results)) if results else 0.0,
        },
    }


def self_test(forall_cap=FORALL_CAP):
    """Grade every task's REFERENCE solution against its own hidden oracle. This
    validates the benchmark itself: every oracle must be satisfiable by a known-good
    solution, and the splice/grade wiring must work. Returns `(ok, results)` where
    `ok` is True only if every reference scores `ok` (and every task HAS a reference).
    """
    results = []
    all_ok = True
    for tid in task_ids():
        task = load_task(tid)
        if task["reference"] is None:
            all_ok = False
            results.append({"id": tid, "ok": False, "passed": 0, "total": None,
                            "summary": "no reference.pedro to self-test",
                            "errors": [], "holes": [], "expectations": []})
            continue
        r = grade(task, task["reference"], forall_cap=forall_cap)
        all_ok = all_ok and r["ok"]
        results.append(r)
    return all_ok, results
