"""Command-line entry point for the Pedro authoring benchmark.

    python -m tools.eval list                       # list benchmark tasks
    python -m tools.eval spec <id>                  # print a task's NL prompt
    python -m tools.eval score <id> <candidate.pedro> [--json]
    python -m tools.eval run <solutions_dir> [--json]   # grade a whole run
    python -m tools.eval selftest [--json]          # grade the reference solutions

`score`/`run` grade PROVIDED `.pedro` files against hidden oracles — no API key, no
model call. `run` expects `<solutions_dir>/<id>.pedro` for each task it can find.
See `tools/eval/README.md` for the NL -> Pedro -> check -> fix loop.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.eval import scorer  # noqa: E402


def _summary_line(spec):
    """First non-heading, non-blank line of a spec — a one-line description."""
    for line in spec.split("\n"):
        s = line.strip()
        if s and not s.startswith("#"):
            return s
    return ""


def _cmd_list(args):
    ids = scorer.task_ids()
    if "--json" in args:
        out = [{"id": t, "description": _summary_line(scorer.load_task(t)["spec"])}
               for t in ids]
        print(json.dumps(out, indent=2))
        return 0
    print(f"{len(ids)} benchmark task(s):")
    for t in ids:
        print(f"  {t:20s}  {_summary_line(scorer.load_task(t)['spec'])}")
    return 0


def _cmd_spec(args):
    if not args:
        print("usage: python -m tools.eval spec <id>", file=sys.stderr)
        return 2
    try:
        task = scorer.load_task(args[0])
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    sys.stdout.write(task["spec"])
    if not task["spec"].endswith("\n"):
        sys.stdout.write("\n")
    return 0


def _print_result(r):
    mark = "PASS" if r["ok"] else "FAIL"
    total = "?" if r["total"] is None else r["total"]
    print(f"[{mark}] {r['id']} — {r['passed']}/{total} — {r['summary']}")
    for e in r.get("errors", []):
        loc = f"line {e['line']}" + (f":{e['col']}" if e.get("col") is not None else "")
        print(f"    error [{e.get('code')}] {loc}: {e.get('message')}")
        if e.get("hint"):
            print(f"      hint: {e['hint']}")
        if e.get("suggestion"):
            print(f"      did you mean {e['suggestion']!r}?")
    for h in r.get("holes", []):
        print(f"    hole line {h['line']}: {h['message']}")
    for x in r.get("expectations", []):
        if not x["passed"]:
            detail = f"   ({x['detail']})" if x.get("detail") else ""
            print(f"    FAIL {x['text']}{detail}")


def _cmd_score(args):
    positional = [a for a in args if a != "--json"]
    as_json = "--json" in args
    if len(positional) != 2:
        print("usage: python -m tools.eval score <id> <candidate.pedro> [--json]",
              file=sys.stderr)
        return 2
    task_id, path = positional
    try:
        task = scorer.load_task(task_id)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    result = scorer.grade(task, source)
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        _print_result(result)
    return 0 if result["ok"] else 1


def _cmd_run(args):
    positional = [a for a in args if a != "--json"]
    as_json = "--json" in args
    if len(positional) != 1:
        print("usage: python -m tools.eval run <solutions_dir> [--json]", file=sys.stderr)
        return 2
    sol_dir = positional[0]
    if not os.path.isdir(sol_dir):
        print(f"error: no such directory: {sol_dir}", file=sys.stderr)
        return 2
    solutions = {}
    for tid in scorer.task_ids():
        path = os.path.join(sol_dir, f"{tid}.pedro")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                solutions[tid] = f.read()
    report = scorer.score_solutions(solutions)
    if as_json:
        print(json.dumps(report, indent=2))
        return 0 if report["summary"]["tasks_ok"] == report["summary"]["tasks_total"] else 1
    for r in report["results"]:
        _print_result(r)
    s = report["summary"]
    print(f"\nSCORE: {s['tasks_ok']}/{s['tasks_total']} tasks fully correct "
          f"({s['task_pass_rate']:.0%}); "
          f"{s['expectations_passed']}/{s['expectations_total']} hidden expectations passed")
    return 0 if s["tasks_ok"] == s["tasks_total"] else 1


def _cmd_selftest(args):
    as_json = "--json" in args
    ok, results = scorer.self_test()
    if as_json:
        print(json.dumps({"ok": ok, "results": results}, indent=2))
    else:
        for r in results:
            _print_result(r)
        print(f"\n{'PASS' if ok else 'FAIL'}: reference solutions "
              f"{'all satisfy their hidden oracles' if ok else 'DO NOT all pass'}")
    return 0 if ok else 1


def main(argv):
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    dispatch = {
        "list": _cmd_list,
        "spec": _cmd_spec,
        "score": _cmd_score,
        "run": _cmd_run,
        "selftest": _cmd_selftest,
    }
    if cmd not in dispatch:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    return dispatch[cmd](rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
