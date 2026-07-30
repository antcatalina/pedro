#!/usr/bin/env python3
"""Mechanical backstop against doc drift (CLAUDE.md ground rule 6).

Pedro's discipline is "verify by running" — a language feature isn't real until a
`.pedro` program exercises it and passes `pedroc check`. This tool applies the same
discipline to Pedro's *own documentation*: it introspects the compiler's actual
construct surface programmatically and cross-references it against what the docs
claim is (un)supported, so the class of bug found on 2026-07-28 — `docs/language-card.md`
listing `for each` (which shipped weeks earlier) under "NOT yet supported" — is caught
mechanically instead of by a human re-reading prose.

Two checks:

  HIGH confidence — a construct the code IMPLEMENTS that a doc marks UNSUPPORTED/🧭.
    This is the exact 2026-07-28 bug. We extract the real keyword surface from
    pedroc/parser.py (every `kw == "..."`, `_is_name("...")`, `_expect(..., "...")`
    literal) plus pedroc/codegen_python.py's BINOP_MAP / builtin-dispatch keys, then
    look inside doc "unsupported" regions for a code span whose keywords are an
    *adjacent run of two or more implemented keywords* — i.e. an implemented
    multi-word construct being declared not-yet-real. (Requiring an adjacent run of
    length >= 2 is what keeps this quiet: base-with-unimplemented-variant lines like
    keyed/descending `sort` or module `use <name> from "..."` never form such a run.)

  LOW confidence — a doc presents a keyword-shaped construct as supported/plain but
    that word never appears as a string literal ANYWHERE in pedroc/*.py. This is the
    reverse drift; it is heuristic and noisier, so it is reported separately and
    labelled LOW.

Usage:
    python tools/check_docs.py            # print findings; always exit 0 (advisory)
    python tools/check_docs.py --strict-docs   # exit nonzero if any HIGH finding
    python tools/check_docs.py --quiet    # only print if there are findings

Wired into tools/regress.py as a clearly-labelled, non-fatal step (see WORKLOG
2026-07-30). Once it has proven itself over a few runs with no false positives, a
future job should flip the default to strict.
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PEDROC = os.path.join(ROOT, "pedroc")

# ---------------------------------------------------------------------------
# Extract the compiler's real construct surface from source (no imports; a
# careful regex over the files, exactly as CLAUDE.md's ground rule 6 suggests).
# ---------------------------------------------------------------------------

# `kw == "let"`, `_is_name("record")`, `_expect("NAME", "each")`
_KW_RE = re.compile(r'kw\s*==\s*"([a-z_]+)"')
_ISNAME_RE = re.compile(r'_is_name\("([a-z_]+)"\)')
_EXPECT_RE = re.compile(r'_expect\([^,]+,\s*"([a-z_]+)"\)')
# any single-quoted/double-quoted lowercase-word literal (for the reverse check's
# "appears anywhere in pedroc/*.py" test)
_LITERAL_RE = re.compile(r'''["']([a-z][a-z_]*)["']''')
# dict keys in BINOP_MAP / _BUILTINS blocks
_DICT_KEY_RE = re.compile(r'"([a-z_]+)"\s*:')


def implemented_keywords() -> set[str]:
    """The real keyword/construct surface pedroc parses + dispatches on."""
    kws: set[str] = set()
    with open(os.path.join(PEDROC, "parser.py"), encoding="utf-8") as f:
        src = f.read()
    for rx in (_KW_RE, _ISNAME_RE, _EXPECT_RE):
        kws.update(rx.findall(src))

    with open(os.path.join(PEDROC, "codegen_python.py"), encoding="utf-8") as f:
        cg_lines = f.read().splitlines()
    # BINOP_MAP + _BUILTINS keys — the operator/builtin *dispatch* surface. We must
    # pick out exactly these two dicts' keys (not the neighbouring TYPE_MAP /
    # CONVERT_MAP, whose type-name keys would leak in and cause false positives).
    for i, line in enumerate(cg_lines):
        stripped = line.lstrip()
        if stripped.startswith("BINOP_MAP"):
            # single-line dict: scan just this line for "key":
            for key in _DICT_KEY_RE.findall(line):
                kws.update(key.split("_"))
        elif stripped.startswith("_BUILTINS"):
            # multi-line dict: keys are indented `"key": ...` until a bare `}`.
            for j in range(i + 1, len(cg_lines)):
                if cg_lines[j].strip() == "}":
                    break
                m = re.match(r'\s*"([a-z_]+)"\s*:', cg_lines[j])
                if m:
                    # split "count_of"/"followed_by" so doc words ("count","of",
                    # "followed","by") match.
                    kws.update(m.group(1).split("_"))
    # drop the empty string / one-letter noise
    return {k for k in kws if len(k) >= 2}


def all_pedro_literals() -> set[str]:
    """Every lowercase-word string literal in pedroc/*.py (reverse-check corpus)."""
    lits: set[str] = set()
    for name in sorted(os.listdir(PEDROC)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(PEDROC, name), encoding="utf-8") as f:
            lits.update(_LITERAL_RE.findall(f.read()))
    return lits


# ---------------------------------------------------------------------------
# Doc scanning
# ---------------------------------------------------------------------------

GUIDE = "\U0001f9ed"  # 🧭
# code span, minus quoted strings and <placeholders> which are metavariables
_SPAN_RE = re.compile(r"`([^`]+)`")
_QUOTED_RE = re.compile(r'"[^"]*"|\'[^\']*\'')
_PLACEHOLDER_RE = re.compile(r"<[^>]*>")
_WORD_RE = re.compile(r"[a-z]+")
# meta-lines that talk *about* the 🧭 convention rather than marking a construct
_META_RE = re.compile(r"mark(s|ed)?\b|🧭 (above|more|check)|not-yet-compiled", re.I)


def _span_tokens(span: str) -> list[str | None]:
    """Word tokens of a code span; metavars/quoted strings become None (breakers)."""
    # replace quoted strings and <placeholders> with a breaker sentinel
    tmp = _QUOTED_RE.sub(" \x00 ", span)
    tmp = _PLACEHOLDER_RE.sub(" \x00 ", tmp)
    out: list[str | None] = []
    for chunk in tmp.split():
        if chunk == "\x00":
            out.append(None)
            continue
        words = _WORD_RE.findall(chunk.lower())
        if not words:
            out.append(None)  # punctuation/number → breaker
        else:
            out.extend(words)
    return out


def _max_implemented_run(span: str, impl: set[str]) -> tuple[int, list[str]]:
    """Longest run of ADJACENT implemented-keyword word tokens in the span."""
    best: list[str] = []
    cur: list[str] = []
    for tok in _span_tokens(span):
        if tok is not None and tok in impl:
            cur.append(tok)
            if len(cur) > len(best):
                best = list(cur)
        else:
            cur = []
    return len(best), best


def _unsupported_regions() -> list[tuple[str, int, str]]:
    """(file, lineno, span-source-text) for every doc code span in an unsupported
    context: the language-card 'NOT yet supported' section, and 🧭-marked spans."""
    regions: list[tuple[str, int, str]] = []

    # 1) language-card "## NOT yet supported ..." section body.
    card = os.path.join(ROOT, "docs", "language-card.md")
    with open(card, encoding="utf-8") as f:
        lines = f.readlines()
    in_section = False
    for i, line in enumerate(lines, 1):
        if line.startswith("## "):
            in_section = line.lower().startswith("## not yet supported")
            continue
        if in_section:
            for span in _SPAN_RE.findall(line):
                regions.append((card, i, span))

    # 2) 🧭-marked spans across README + language-card: a code span is "marked
    #    unsupported" when a 🧭 follows it within a short distance on the same line
    #    (per-construct marker), and the line is not a meta-line about the convention.
    for rel in ("README.md", os.path.join("docs", "language-card.md")):
        path = os.path.join(ROOT, rel)
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if GUIDE not in line or _META_RE.search(line):
                    continue
                for m in _SPAN_RE.finditer(line):
                    tail = line[m.end():]
                    g = tail.find(GUIDE)
                    if 0 <= g <= 30:
                        regions.append((path, i, m.group(1)))
    return regions


# words that signal a line is describing the ABSENCE of a construct, so a keyword
# named there is not being "presented as supported" (reverse check must skip it).
_NEGATION_RE = re.compile(
    r"\b(no|not|never|without|lacks?|missing|instead|only|yet)\b|🧭"
)


def _supported_spans() -> list[tuple[str, int, str]]:
    """Bare single-word code spans from language-card '(supported)'/Statements/
    Expressions BULLET lines — conservative reverse-check candidates. We restrict
    to bullet ('- ...') lines with no negation cue and skip fenced code, so prose
    mentions of host-language/output words and example identifiers don't leak in."""
    card = os.path.join(ROOT, "docs", "language-card.md")
    out: list[tuple[str, int, str]] = []
    with open(card, encoding="utf-8") as f:
        lines = f.readlines()
    in_supported = False
    in_fence = False
    for i, line in enumerate(lines, 1):
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.startswith("## "):
            low = line.lower()
            in_supported = "(supported)" in low or low.startswith("## statements") \
                or low.startswith("## expressions")
            continue
        if not in_supported or not line.lstrip().startswith("-"):
            continue
        if _NEGATION_RE.search(line):
            continue
        for span in _SPAN_RE.findall(line):
            words = _WORD_RE.findall(span.lower())
            # only bare single-word keyword-shaped spans
            if len(words) == 1 and len(words[0]) >= 3 and span.strip() == words[0]:
                out.append((card, i, words[0]))
    return out


# reverse-check stoplist: ordinary English / host-language / output words that
# legitimately appear as single-word code spans in supported prose but aren't
# parser keywords.
_REVERSE_STOP = {
    "true", "false", "value", "values", "name", "field", "fields", "type",
    "types", "key", "keys", "item", "items", "element", "line", "block",
    "otherwise", "variant", "variants",
    # host-language / codegen-output words
    "python", "typescript", "interface", "dataclass", "class", "object",
    "str", "int", "float", "bool", "none", "null", "pedroc", "pedro",
}


def find(strict: bool = False):
    impl = implemented_keywords()
    high: list[str] = []
    for path, lineno, span in _unsupported_regions():
        n, run = _max_implemented_run(span, impl)
        if n >= 2:
            rel = os.path.relpath(path, ROOT)
            high.append(
                f"{rel}:{lineno}: marks `{span.strip()}` as unsupported/🧭, but "
                f"`{' '.join(run)}` is an implemented construct (parser/codegen surface)."
            )

    lits = all_pedro_literals()
    low: list[str] = []
    seen: set[str] = set()
    for path, lineno, word in _supported_spans():
        if word in _REVERSE_STOP or word in lits or word in seen:
            continue
        seen.add(word)
        rel = os.path.relpath(path, ROOT)
        low.append(
            f"{rel}:{lineno}: `{word}` is presented as supported, but no such keyword "
            f"literal appears anywhere in pedroc/*.py."
        )
    return high, low


def main(argv: list[str]) -> int:
    strict = "--strict-docs" in argv
    quiet = "--quiet" in argv
    high, low = find(strict)

    if not high and not low:
        if not quiet:
            print("check_docs: OK — no doc/compiler drift detected.")
        return 0

    bar = "=" * 72
    print(bar)
    print("!!! DOC DRIFT CHECK (tools/check_docs.py) — FINDINGS !!!")
    print(bar)
    if high:
        print(f"\n  HIGH confidence ({len(high)}) — implemented construct marked "
              f"unsupported (the 2026-07-28 bug class):")
        for msg in high:
            print(f"    ✗ {msg}")
    if low:
        print(f"\n  LOW confidence ({len(low)}) — doc claims support but compiler "
              f"has no matching keyword (heuristic; verify before acting):")
        for msg in low:
            print(f"    ? {msg}")
    print(f"\n{bar}")

    if strict and high:
        print("check_docs: --strict-docs and HIGH findings present → failing.")
        return 1
    if not strict:
        print("check_docs: advisory only (non-fatal). Re-run with --strict-docs to "
              "make HIGH findings fail CI.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
