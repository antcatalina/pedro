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


class PedroTypeError(Exception):
    """A type/annotation error found after parsing, e.g. a record literal whose
    `record` type can't be determined, an unknown field, or a missing required
    field. Carries `line`/`col`/`code`/`hint`/`suggestion` like the other
    diagnostics so `check --json` and `build` report it uniformly."""

    def __init__(self, line, col, message, code, hint=None, suggestion=None):
        self.line = line
        self.col = col
        self.message = message
        self.code = code
        self.hint = hint
        self.suggestion = suggestion
        where = f"line {line}" if col is None else f"line {line}:{col}"
        super().__init__(f"{where}: {message}")


class PedroCapabilityError(Exception):
    """A capability/effect error found after parsing: an unknown capability name,
    or a verb used without `use capability …` for it. This is the enforcement that
    makes Pedro auditable — undeclared power is a compile error, not a silent
    import. Carries `line`/`col`/`code`/`hint`/`suggestion` like the others."""

    def __init__(self, line, col, message, code, hint=None, suggestion=None):
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
