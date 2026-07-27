"""Command-line interface for pedroc.

    python -m pedroc build <file.pedro> [-o <out.py>] [--target python]
    python -m pedroc check <file.pedro> [--json] [--target python]
"""
import json
import os
import sys

from . import compile_source, PedroSyntaxError
from .check import check

BUILD_USAGE = "usage: python -m pedroc build <file.pedro> [-o <out.py>] [--target python]"
CHECK_USAGE = "usage: python -m pedroc check <file.pedro> [--json] [--target python]"
USAGE = BUILD_USAGE + "\n" + CHECK_USAGE


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
    except PedroSyntaxError as e:
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
    i = 1
    while i < len(args):
        if args[i] == "--json":
            as_json = True
            i += 1
        elif args[i] == "--target" and i + 1 < len(args):
            target = args[i + 1]
            i += 2
        else:
            print(f"unknown or incomplete argument: {args[i]}", file=sys.stderr)
            return 2
    try:
        source = _read(infile)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    report = check(source, filename=os.path.basename(infile), target=target)
    if as_json:
        # Compact on purpose: this is read inside a model's context window.
        print(json.dumps(report, separators=(",", ":")))
    else:
        _print_human(report)
    return 0 if report["ok"] else 1


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


def main(argv):
    if not argv:
        print(USAGE, file=sys.stderr)
        return 2
    cmd = argv[0]
    if cmd == "build":
        return _cmd_build(argv[1:])
    if cmd == "check":
        return _cmd_check(argv[1:])
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
