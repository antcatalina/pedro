"""Error types for the Pedro compiler."""


class PedroSyntaxError(Exception):
    """A syntax/parse error, carrying the 1-based source line for diagnostics."""

    def __init__(self, line, message):
        self.line = line
        self.message = message
        super().__init__(f"line {line}: {message}")
