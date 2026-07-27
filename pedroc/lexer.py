"""Indentation-aware tokenizer for Pedro.

Emits a flat token stream with explicit INDENT / DEDENT / NEWLINE tokens
(like Python's tokenizer), which keeps the parser simple.

Token = (type, value, line, col). `col` is the 1-based column of the token's
first character in the original source line (before indentation is stripped),
so diagnostics can point a caret at the exact spot. Types:
  NAME NUMBER STRING OP NEWLINE INDENT DEDENT EOF
"""
from .errors import PedroSyntaxError

TWO_CHAR_OPS = {"==", "!=", "<=", ">="}
SINGLE_OPS = set("()[]{}+-*/<>=:,.")


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


def _tokenize_line(s, lineno, col_offset):
    """Tokenize one already-dedented line. `col_offset` is the number of leading
    indentation characters stripped, so `col_offset + i + 1` is the 1-based column
    of position `i` in the ORIGINAL source line."""
    toks = []
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        col = col_offset + i + 1
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
                raise PedroSyntaxError(
                    lineno, "unterminated string literal", code="unterminated-string",
                    col=col, hint='close the string with a matching \'"\' on the same line',
                )
            toks.append(("STRING", "".join(buf), lineno, col))
            i = j + 1
            continue
        if ch.isdigit():
            j = i
            while j < n and (s[j].isdigit() or s[j] == "."):
                j += 1
            toks.append(("NUMBER", s[i:j], lineno, col))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            toks.append(("NAME", s[i:j], lineno, col))
            i = j
            continue
        two = s[i:i + 2]
        if two in TWO_CHAR_OPS:
            toks.append(("OP", two, lineno, col))
            i += 2
            continue
        if ch in SINGLE_OPS:
            toks.append(("OP", ch, lineno, col))
            i += 1
            continue
        raise PedroSyntaxError(
            lineno, f"unexpected character {ch!r}", code="unexpected-character", col=col,
            hint="Pedro uses letters, digits, strings, and the operators ()[]{}+-*/<>=:,. — remove this character",
        )
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
            tokens.append(("INDENT", "", lineno, indent + 1))
        else:
            while indent < indent_stack[-1]:
                indent_stack.pop()
                tokens.append(("DEDENT", "", lineno, indent + 1))
            if indent != indent_stack[-1]:
                raise PedroSyntaxError(
                    lineno,
                    "inconsistent indentation",
                    code="bad-indentation",
                    col=indent + 1,
                    hint="a nested block must be indented further than its header; sibling statements share indentation",
                )
        tokens.extend(_tokenize_line(stripped, lineno, indent))
        # NEWLINE sits just past the last character of the source line.
        tokens.append(("NEWLINE", "", lineno, len(line) + 1))
    while len(indent_stack) > 1:
        indent_stack.pop()
        tokens.append(("DEDENT", "", lineno, 1))
    tokens.append(("EOF", "", lineno, 1))
    return tokens
