"""Indentation-aware tokenizer for Pedro.

Emits a flat token stream with explicit INDENT / DEDENT / NEWLINE tokens
(like Python's tokenizer), which keeps the parser simple.

Token = (type, value, line). Types:
  NAME NUMBER STRING OP NEWLINE INDENT DEDENT EOF
"""
from .errors import PedroSyntaxError

TWO_CHAR_OPS = {"==", "!=", "<=", ">="}
SINGLE_OPS = set("()+-*/<>=:,.")


def _strip_comment(line):
    """Drop a trailing `# comment`, but not a `#` inside a string literal."""
    out = []
    in_str = False
    for ch in line:
        if ch == '"':
            in_str = not in_str
            out.append(ch)
        elif ch == '#' and not in_str:
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def _tokenize_line(s, lineno):
    toks = []
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if ch in " \t":
            i += 1
            continue
        if ch == '"':
            j = i + 1
            buf = []
            while j < n and s[j] != '"':
                buf.append(s[j])
                j += 1
            if j >= n:
                raise PedroSyntaxError(lineno, "unterminated string literal", code="unterminated-string")
            toks.append(("STRING", "".join(buf), lineno))
            i = j + 1
            continue
        if ch.isdigit():
            j = i
            while j < n and (s[j].isdigit() or s[j] == "."):
                j += 1
            toks.append(("NUMBER", s[i:j], lineno))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            toks.append(("NAME", s[i:j], lineno))
            i = j
            continue
        two = s[i:i + 2]
        if two in TWO_CHAR_OPS:
            toks.append(("OP", two, lineno))
            i += 2
            continue
        if ch in SINGLE_OPS:
            toks.append(("OP", ch, lineno))
            i += 1
            continue
        raise PedroSyntaxError(lineno, f"unexpected character {ch!r}", code="unexpected-character")
    return toks


def tokenize(source):
    tokens = []
    indent_stack = [0]
    lineno = 0
    for lineno, raw in enumerate(source.split("\n"), 1):
        line = _strip_comment(raw)
        if line.strip() == "":
            continue  # blank / comment-only line produces no tokens
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if indent > indent_stack[-1]:
            indent_stack.append(indent)
            tokens.append(("INDENT", "", lineno))
        else:
            while indent < indent_stack[-1]:
                indent_stack.pop()
                tokens.append(("DEDENT", "", lineno))
            if indent != indent_stack[-1]:
                raise PedroSyntaxError(
                    lineno,
                    "inconsistent indentation",
                    code="bad-indentation",
                    hint="a nested block must be indented further than its header; sibling statements share indentation",
                )
        tokens.extend(_tokenize_line(stripped, lineno))
        tokens.append(("NEWLINE", "", lineno))
    while len(indent_stack) > 1:
        indent_stack.pop()
        tokens.append(("DEDENT", "", lineno))
    tokens.append(("EOF", "", lineno))
    return tokens
