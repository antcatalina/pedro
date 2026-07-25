"""pedroc — the deterministic Pedro compiler.

Pipeline: source -> tokenize -> parse -> generate(target).
No LLM involved; the same input always yields the same output.
"""
from .lexer import tokenize
from .parser import Parser
from .codegen_python import generate
from .errors import PedroSyntaxError

__all__ = ["compile_source", "PedroSyntaxError"]

__version__ = "0.1"

_TARGETS = {"python": generate}


def compile_source(source, filename="<pedro>", target="python"):
    if target not in _TARGETS:
        raise ValueError(f"unsupported target {target!r}; available: {sorted(_TARGETS)}")
    tokens = tokenize(source)
    program = Parser(tokens, filename).parse()
    return _TARGETS[target](program, filename)
