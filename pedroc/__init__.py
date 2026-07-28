"""pedroc — the deterministic Pedro compiler.

Pipeline: source -> tokenize -> parse -> generate(target).
No LLM involved; the same input always yields the same output.
"""
from .lexer import tokenize
from .parser import Parser
from .annotate import annotate
from .capabilities import check_capabilities
from .codegen_python import generate as generate_python
from .codegen_ts import generate as generate_ts
from .errors import PedroSyntaxError, PedroTypeError, PedroCapabilityError

__all__ = ["compile_source", "PedroSyntaxError", "PedroTypeError", "PedroCapabilityError"]

__version__ = "0.1"

_TARGETS = {"python": generate_python, "typescript": generate_ts}


def compile_source(source, filename="<pedro>", target="python"):
    if target not in _TARGETS:
        raise ValueError(f"unsupported target {target!r}; available: {sorted(_TARGETS)}")
    tokens = tokenize(source)
    program = Parser(tokens, filename).parse()
    type_errors = annotate(program)   # resolves record-literal types; may error
    if type_errors:
        raise type_errors[0]
    _surface, cap_errors = check_capabilities(program)  # undeclared power → compile error
    if cap_errors:
        raise cap_errors[0]
    program.target = target
    return _TARGETS[target](program, filename)
