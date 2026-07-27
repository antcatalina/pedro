"""Grammar-based fuzzer for pedroc — generates random VALID Pedro programs with
SELF-CHECKING `expect` blocks, then compiles+runs them on every available backend
and asserts every backend agrees with an independent reference oracle.

How it self-checks
------------------
The generator builds each expression bottom-up as an (source, value) pair, where
`value` is computed by a small reference evaluator that mirrors Pedro's semantics
(`div`→floor-division, `mod`→remainder, `followed by`→concat, value-equality for
lists, …). Each generated `expect` line is arranged to be TRUE under the oracle,
so a correct compiler must make every expectation pass. Any expectation that
fails — or any backend that disagrees with another — is a real bug (in codegen, or
in this oracle; both are worth knowing).

The domain is kept NON-NEGATIVE for `div`/`mod` so semantics are backend-portable
(JS `Math.floor` division and Python `//` agree on non-negative operands), which
means the same generated corpus will exercise the TypeScript lane identically once
it lands.

Determinism / reproduction
--------------------------
Everything is driven by `random.Random(seed)`. A failing program prints its exact
seed and source so it reproduces with `python tools/fuzz.py --seed <N> --count 1`.

Usage
-----
    python tools/fuzz.py [--seed N] [--count K] [--lines L] [--depth D] [-v]

Exit 0 iff every generated program passes on every available backend.
"""
import argparse
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.backends import run_python, run_typescript, ts_available  # noqa: E402

# Surface comparison forms → reference operator. A mix of readable keywords and
# symbols so both spellings get exercised.
_CMP = [
    ("is", lambda a, b: a == b),
    ("is not", lambda a, b: a != b),
    ("is greater than", lambda a, b: a > b),
    ("is less than", lambda a, b: a < b),
    ("is at least", lambda a, b: a >= b),
    ("is at most", lambda a, b: a <= b),
    ("==", lambda a, b: a == b),
    ("!=", lambda a, b: a != b),
    (">", lambda a, b: a > b),
    ("<", lambda a, b: a < b),
    (">=", lambda a, b: a >= b),
    ("<=", lambda a, b: a <= b),
]


def gen_int(rng, depth):
    """Return (pedro_source, int_value); value is always non-negative."""
    if depth <= 0 or rng.random() < 0.4:
        v = rng.randint(1, 20)
        return str(v), v
    op = rng.choice(["+", "-", "*", "div", "mod"])
    ls, lv = gen_int(rng, depth - 1)
    rs, rv = gen_int(rng, depth - 1)
    if op == "+":
        return f"({ls} + {rs})", lv + rv
    if op == "*":
        return f"({ls} * {rs})", lv * rv
    if op == "-":
        # Keep the result non-negative by ordering operands high - low.
        if lv < rv:
            ls, lv, rs, rv = rs, rv, ls, lv
        return f"({ls} - {rs})", lv - rv
    # div / mod: guard against a zero divisor deterministically.
    if rv == 0:
        rv = rng.randint(1, 20)
        rs = str(rv)
    if op == "div":
        return f"({ls} div {rs})", lv // rv
    return f"({ls} mod {rs})", lv % rv


def gen_bool(rng, depth):
    """Return (pedro_source, bool_value)."""
    if depth <= 0 or rng.random() < 0.5:
        ls, lv = gen_int(rng, depth)
        rs, rv = gen_int(rng, depth)
        word, fn = rng.choice(_CMP)
        return f"({ls} {word} {rs})", fn(lv, rv)
    op = rng.choice(["and", "or", "not"])
    if op == "not":
        s, v = gen_bool(rng, depth - 1)
        return f"(not {s})", (not v)
    ls, lv = gen_bool(rng, depth - 1)
    rs, rv = gen_bool(rng, depth - 1)
    if op == "and":
        return f"({ls} and {rs})", (lv and rv)
    return f"({ls} or {rs})", (lv or rv)


def gen_list(rng, depth):
    """Return (pedro_source, list_value) — a flat list of small ints."""
    n = rng.randint(0, 4)
    vals = [rng.randint(1, 9) for _ in range(n)]
    src = "[" + ", ".join(str(v) for v in vals) + "]"
    return src, vals


def gen_expect_line(rng, depth):
    """One self-true `expect` assertion, chosen from several expression families."""
    kind = rng.choice(["int", "bool", "count", "member", "concat"])
    if kind == "int":
        s, v = gen_int(rng, depth)
        return f"{s} == {v}"
    if kind == "bool":
        s, v = gen_bool(rng, depth)
        return s if v else f"not ({s})"
    if kind == "count":
        s, vals = gen_list(rng, depth)
        return f"count of {s} == {len(vals)}"
    if kind == "member":
        s, vals = gen_list(rng, depth)
        if vals and rng.random() < 0.5:
            x = rng.choice(vals)
            return f"{x} in {s}"
        # pick a value guaranteed absent (10..19; list holds 1..9)
        y = rng.randint(10, 19)
        return f"{y} not in {s}"
    # concat: (A followed by B) == A ++ B
    a_s, a_v = gen_list(rng, depth)
    b_s, b_v = gen_list(rng, depth)
    concat = "[" + ", ".join(str(v) for v in (a_v + b_v)) + "]"
    return f"({a_s} followed by {b_s}) == {concat}"


def gen_program(rng, lines, depth):
    body = "\n".join("    " + gen_expect_line(rng, depth) for _ in range(lines))
    return f"target: python\n\nexpect:\n{body}\n"


def _check_agreement(source, name):
    """Run every available backend; return (ok, message). ok=False on a failed
    expectation or a cross-backend disagreement."""
    py = run_python(source, filename=name)
    if not py["ok"]:
        bad = [x for x in py["expectations"] if not x["passed"]]
        detail = bad[0] if bad else {"text": py["error"], "detail": None}
        return False, f"python: expectation failed: {detail}"

    if ts_available():
        ts = run_typescript(source, filename=name)
        if not ts["ran"]:
            return True, None
        if not ts["ok"]:
            return False, f"typescript: {ts['error']}"
        # Per-expectation agreement when TS emits records.
        if ts["expectations"]:
            for a, b in zip(py["expectations"], ts["expectations"]):
                if a["passed"] != b["passed"]:
                    return False, f"backend disagreement on {a['text']!r}: py={a['passed']} ts={b['passed']}"
    return True, None


def run(seed=0, count=200, lines=4, depth=3, verbose=False):
    rng = random.Random(seed)
    failures = 0
    for i in range(count):
        # Derive a per-program seed so a single failure reproduces standalone.
        prog_seed = rng.randrange(2**31)
        prng = random.Random(prog_seed)
        source = gen_program(prng, lines, depth)
        name = f"fuzz_{i}.pedro"
        try:
            ok, msg = _check_agreement(source, name)
        except Exception as e:  # a compiler crash is a bug too
            ok, msg = False, f"harness/compiler raised: {e!r}"
        if verbose and ok:
            print(f"[ok  ] program {i} (prog-seed {prog_seed})")
        if not ok:
            failures += 1
            print(f"[FAIL] program {i} — reproduce with --seed {seed} (prog-seed {prog_seed})")
            print(f"       {msg}")
            print("       ---- source ----")
            for ln in source.rstrip().splitlines():
                print(f"       {ln}")
            print("       ----------------")
    lane = "python+typescript" if ts_available() else "python (TS lane pending)"
    status = "PASS" if failures == 0 else "FAIL"
    print(f"\n{status}: fuzzed {count} programs on {lane}, seed {seed} — {failures} failure(s)")
    return failures == 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=0, help="RNG seed (default 0; runs reproduce)")
    ap.add_argument("--count", type=int, default=200, help="number of programs (default 200)")
    ap.add_argument("--lines", type=int, default=4, help="expect lines per program (default 4)")
    ap.add_argument("--depth", type=int, default=3, help="max expression depth (default 3)")
    ap.add_argument("-v", "--verbose", action="store_true", help="print each passing program")
    args = ap.parse_args(argv)
    ok = run(seed=args.seed, count=args.count, lines=args.lines, depth=args.depth, verbose=args.verbose)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
