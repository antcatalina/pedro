"""Command-line interface for pedroc.

    python -m pedroc build <file.pedro> [-o <out.py>] [--target python]
    python -m pedroc check <file.pedro> [--json] [--target python]
    python -m pedroc verify <file.pedro> <generated-output> [--json]
    python -m pedroc permissions <file.pedro> [--format claude-settings|json]
"""
import json
import os
import sys

from . import compile_source, PedroSyntaxError, PedroTypeError, PedroCapabilityError
from .check import check, check_targets, FORALL_CAP
from .verify import verify
from .permissions import render as render_permissions

BUILD_USAGE = "usage: python -m pedroc build <file.pedro> [-o <out.py>] [--target python]"
CHECK_USAGE = ("usage: python -m pedroc check <file.pedro> [--json] "
               "[--target python | --targets python,typescript] [--forall-cap N]")
VERIFY_USAGE = "usage: python -m pedroc verify <file.pedro> <generated-output> [--json]"
PERMS_USAGE = "usage: python -m pedroc permissions <file.pedro> [--format claude-settings|json]"
USAGE = BUILD_USAGE + "\n" + CHECK_USAGE + "\n" + VERIFY_USAGE + "\n" + PERMS_USAGE


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _cmd_build(args):
    if not args:
        print(BUILD_USAGE, file=sys.stderr)
        return 2
    infile = args[0]
    out = None
    target = "python"
    i = 1
    while i < len(args):
        if args[i] == "-o" and i + 1 < len(args):
            out = args[i + 1]
            i += 2
        elif args[i] == "--target" and i + 1 < len(args):
            target = args[i + 1]
            i += 2
        else:
            print(f"unknown or incomplete argument: {args[i]}", file=sys.stderr)
            return 2
    try:
        code = compile_source(_read(infile), filename=os.path.basename(infile), target=target)
    except (PedroSyntaxError, PedroTypeError, PedroCapabilityError) as e:
        loc = f"{e.line}" if e.col is None else f"{e.line}:{e.col}"
        print(f"{infile}:{loc}: error [{e.code}]: {e.message}", file=sys.stderr)
        if e.suggestion:
            print(f"  did you mean {e.suggestion!r}?", file=sys.stderr)
        return 1
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"compiled {infile} -> {out}")
    else:
        sys.stdout.write(code)
    return 0


def _cmd_check(args):
    if not args:
        print(CHECK_USAGE, file=sys.stderr)
        return 2
    infile = args[0]
    as_json = False
    target = "python"
    targets = None
    forall_cap = FORALL_CAP
    i = 1
    while i < len(args):
        if args[i] == "--json":
            as_json = True
            i += 1
        elif args[i] == "--target" and i + 1 < len(args):
            target = args[i + 1]
            i += 2
        elif args[i] == "--targets" and i + 1 < len(args):
            targets = [t.strip() for t in args[i + 1].split(",") if t.strip()]
            i += 2
        elif args[i] == "--forall-cap" and i + 1 < len(args):
            try:
                forall_cap = int(args[i + 1])
            except ValueError:
                print(f"--forall-cap needs an integer, got {args[i + 1]!r}", file=sys.stderr)
                return 2
            if forall_cap < 1:
                print("--forall-cap must be at least 1", file=sys.stderr)
                return 2
            i += 2
        else:
            print(f"unknown or incomplete argument: {args[i]}", file=sys.stderr)
            return 2
    try:
        source = _read(infile)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if targets is not None:
        for t in targets:
            if t not in ("python", "typescript"):
                print(f"unknown target {t!r}: expected 'python' or 'typescript'",
                      file=sys.stderr)
                return 2
        if not targets:
            print("--targets needs at least one target", file=sys.stderr)
            return 2
        targets = list(dict.fromkeys(targets))  # dedupe, preserve order
        # A single target behaves exactly like today's `check --target <t>`.
        if len(targets) == 1:
            target = targets[0]
        else:
            report = check_targets(source, filename=os.path.basename(infile),
                                   targets=targets, forall_cap=forall_cap)
            if as_json:
                print(json.dumps(report, separators=(",", ":")))
            else:
                _print_targets_human(report)
            return 0 if report["ok"] else 1

    report = check(source, filename=os.path.basename(infile), target=target,
                   forall_cap=forall_cap)
    if as_json:
        # Compact on purpose: this is read inside a model's context window.
        print(json.dumps(report, separators=(",", ":")))
    else:
        _print_human(report)
    return 0 if report["ok"] else 1


def _cmd_verify(args):
    if len(args) < 2:
        print(VERIFY_USAGE, file=sys.stderr)
        return 2
    infile = args[0]
    outfile = args[1]
    as_json = False
    i = 2
    while i < len(args):
        if args[i] == "--json":
            as_json = True
            i += 1
        else:
            print(f"unknown or incomplete argument: {args[i]}", file=sys.stderr)
            return 2
    try:
        source = _read(infile)
        generated = _read(outfile)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    report = verify(source, generated, source_name=infile, output_name=outfile)
    if as_json:
        print(json.dumps(report, separators=(",", ":")))
    else:
        print(report["summary"])
    return 0 if report["ok"] else 1


def _cmd_permissions(args):
    if not args:
        print(PERMS_USAGE, file=sys.stderr)
        return 2
    infile = args[0]
    fmt = "claude-settings"
    i = 1
    while i < len(args):
        if args[i] == "--format" and i + 1 < len(args):
            fmt = args[i + 1]
            i += 2
        else:
            print(f"unknown or incomplete argument: {args[i]}", file=sys.stderr)
            return 2
    try:
        source = _read(infile)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    try:
        manifest = render_permissions(source, filename=os.path.basename(infile), fmt=fmt)
    except (PedroSyntaxError, PedroTypeError, PedroCapabilityError) as e:
        loc = f"{e.line}" if e.col is None else f"{e.line}:{e.col}"
        print(f"{infile}:{loc}: error [{e.code}]: {e.message}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(manifest)
    return 0


def _print_human(report):
    print(f"{report['file']}: {report['summary']}")
    for err in report["errors"]:
        loc = f"line {err['line']}" if err.get("col") is None else f"line {err['line']}:{err['col']}"
        print(f"  error [{err['code']}] {loc}: {err['message']}")
        if err.get("hint"):
            print(f"    hint: {err['hint']}")
        if err.get("suggestion"):
            print(f"    did you mean {err['suggestion']!r}?")
        if err.get("snippet"):
            for sl in err["snippet"].split("\n"):
                print(f"    {sl}")
    for hole in report["holes"]:
        print(f"  hole  line {hole['line']}: {hole['message']}")
    for exp in report["expectations"]:
        mark = "PASS" if exp["passed"] else "FAIL"
        line = f"  [{mark}] {exp['text']}"
        if not exp["passed"] and exp["detail"]:
            line += f"   ({exp['detail']})"
        print(line)
    print("  => ok" if report["ok"] else "  => not ok")


def _print_targets_human(report):
    print(f"{report['file']}: {report['summary']}")
    for err in report["errors"]:
        loc = f"line {err['line']}" if err.get("col") is None else f"line {err['line']}:{err['col']}"
        print(f"  error [{err['code']}] {loc}: {err['message']}")
    for hole in report["holes"]:
        print(f"  hole  line {hole['line']}: {hole['message']}")
    for t in report["targets"]:
        r = report["results"][t]
        if not r["ran"]:
            why = r.get("skipped") or r.get("error") or r.get("status") or "not run"
            print(f"  [{t}] not run: {why}")
            continue
        state = "ok" if r["ok"] else (r.get("status") or "fail")
        if r["expectations"]:
            n = len(r["expectations"])
            n_pass = sum(1 for x in r["expectations"] if x["passed"])
            print(f"  [{t}] {n_pass}/{n} passed ({state})")
        else:  # coarse lane: whole-program pass/fail only
            verdict = "ran green" if r["ok"] else f"failed: {r.get('error')}"
            print(f"  [{t}] {verdict} (whole-program)")
    if report["disagreements"]:
        print("  DISAGREEMENTS (a codegen bug — targets must agree):")
        for d in report["disagreements"]:
            if d["kind"] == "expectation-count":
                counts = ", ".join(f"{k}={v}" for k, v in d["counts"].items())
                print(f"    - expectation count differs: {counts}")
            elif d["kind"] == "program":
                print(f"    - {d['detail']}:")
                for t, got in d["results"].items():
                    extra = ""
                    if got.get("failed"):
                        extra = f" failed={got['failed']}"
                    elif got.get("error"):
                        extra = f" error={got['error']!r}"
                    print(f"        {t}: ok={got['ok']}{extra}")
            else:
                print(f"    - #{d['index']} {d['expectation']!r}:")
                for t, got in d["results"].items():
                    detail = f" ({got['detail']})" if got.get("detail") else ""
                    print(f"        {t}: passed={got['passed']}{detail}")
    print("  => ok" if report["ok"] else "  => not ok")


def main(argv):
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print(USAGE, file=sys.stderr)
        return 2
    cmd = argv[0]
    if cmd == "build":
        return _cmd_build(argv[1:])
    if cmd == "check":
        return _cmd_check(argv[1:])
    if cmd == "verify":
        return _cmd_verify(argv[1:])
    if cmd == "permissions":
        return _cmd_permissions(argv[1:])
    print(USAGE, file=sys.stderr)
    return 2


def run():
    """Console-script entry point (the bare `pedroc` command).

    setuptools' generated wrapper calls `sys.exit(run())`, so returning the
    process exit code here is correct. `python -m pedroc` goes through the same
    `main` below, so both invocation paths behave identically.
    """
    return main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(run())
