"""Error types for the Pedro compiler.

Diagnostics carry a machine-readable `code`, an optional actionable `hint`, and
an optional nearest-match `suggestion` ("did you mean X?") so an LLM can
self-correct from them (errors are prompts). They also carry the 1-based source
`line` and `col` of the offending token, so the oracle can point a caret at it.
"""


class PedroSyntaxError(Exception):
    """A syntax/parse error, carrying 1-based source `line`/`col` for diagnostics."""

    def __init__(self, line, message, code="syntax-error", hint=None, col=None, suggestion=None):
        self.line = line
        self.col = col
        self.message = message
        self.code = code
        self.hint = hint
        self.suggestion = suggestion
        where = f"line {line}" if col is None else f"line {line}:{col}"
        super().__init__(f"{where}: {message}")


class PedroNameError(Exception):
    """A name-resolution error (unknown identifier / task), found by the resolver
    pass after a successful parse. Carries `line`/`col`/`suggestion` like a syntax
    error so `check --json` can report it uniformly."""

    def __init__(self, line, col, message, code, hint=None, suggestion=None):
        self.line = line
        self.col = col
        self.message = message
        self.code = code
        self.hint = hint
        self.suggestion = suggestion
        super().__init__(f"line {line}:{col}: {message}")
