"""Error types for the Pedro compiler.

Diagnostics carry a machine-readable `code` and an optional `hint` so an LLM
can self-correct from them (errors are prompts).
"""


class PedroSyntaxError(Exception):
    """A syntax/parse error, carrying the 1-based source line for diagnostics."""

    def __init__(self, line, message, code="syntax-error", hint=None):
        self.line = line
        self.message = message
        self.code = code
        self.hint = hint
        super().__init__(f"line {line}: {message}")
