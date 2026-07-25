"""AST node definitions for Pedro.

Deliberately small and regular — one node per construct — so the language
stays easy to reason about (and easy to describe to an LLM in-context).
"""
from dataclasses import dataclass
from typing import Optional


# --- top level ---

@dataclass
class Program:
    target: str
    items: list          # list of Task | Expect


@dataclass
class Task:
    name: str
    params: list         # list of (name, type, default_expr_or_None)
    ret_type: Optional[str]
    body: list           # list of statements


@dataclass
class Expect:
    assertions: list     # list of expression nodes (each a comparison)


# --- statements ---

@dataclass
class Assign:
    name: str
    value: object


@dataclass
class AugAssign:
    name: str
    op: str              # '+' or '-'
    value: object


@dataclass
class Return:
    value: object        # or None


@dataclass
class If:
    branches: list       # list of (cond, body)
    orelse: Optional[list]


@dataclass
class While:
    cond: object
    body: list


@dataclass
class Repeat:
    count: object
    body: list


@dataclass
class ExprStmt:
    expr: object


@dataclass
class Todo:
    """A typed hole: `todo "<why>"`. First-class uncertainty for the author."""
    message: str
    line: int


# --- expressions ---

@dataclass
class Num:
    value: str


@dataclass
class Str:
    value: str


@dataclass
class Bool:
    value: bool


@dataclass
class Name:
    value: str


@dataclass
class Call:
    func: str
    args: list


@dataclass
class Attr:
    obj: object
    field: str


@dataclass
class BinOp:
    op: str
    left: object
    right: object


@dataclass
class Unary:
    op: str
    operand: object
