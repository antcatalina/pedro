"""Command-line interface for pedroc.

    python -m pedroc build <file.pedro> [-o <out.py>] [--target python]
"""
import os
import sys

from . import compile_source, PedroSyntaxError

USAGE = "usage: python -m pedroc build <file.pedro> [-o <out.py>] [--target python]"


def main(argv):
    if len(argv) < 2 or argv[0] != "build":
        print(USAGE, file=sys.stderr)
        return 2

    infile = argv[1]
    out = None
    target = "python"
    i = 2
    while i < len(argv):
        if argv[i] == "-o" and i + 1 < len(argv):
            out = argv[i + 1]
            i += 2
        elif argv[i] == "--target" and i + 1 < len(argv):
            target = argv[i + 1]
            i += 2
        else:
            print(f"unknown or incomplete argument: {argv[i]}", file=sys.stderr)
            return 2

    try:
        with open(infile, "r", encoding="utf-8") as f:
            source = f.read()
        code = compile_source(source, filename=os.path.basename(infile), target=target)
    except PedroSyntaxError as e:
        print(f"{infile}:{e.line}: error: {e.message}", file=sys.stderr)
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


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
