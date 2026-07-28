"""AST node definitions for Pedro.

Small and regular — one node per construct — so the language stays easy to
reason about (and easy to describe to an LLM in-context).
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
    ret_type: object     # structured type (see parser._parse_type)
    body: list


@dataclass
class Record:
    """`record Name:` with typed fields and optional defaults.
    Python -> @dataclass; TypeScript -> interface."""
    name: str
    fields: list         # list of (field_name, type, default_expr_or_None)


@dataclass
class Enum:
    """`enum Name:` with named variants, referenced as `Name.variant`.
    Python -> `class Name(str, Enum)`; TypeScript -> a const object + type."""
    name: str
    variants: list       # list of variant names (str)


@dataclass
class Use:
    """`use capability <name>` — declares one effectful capability the program is
    allowed to reach (database/http/email/files/time/crypto/random). The set of
    these is the program's auditable blast radius; using a verb whose capability
    isn't declared is a compile error."""
    capability: str
    line: Optional[int] = None
    col: Optional[int] = None


@dataclass
class Table:
    """`table <name>: <RecordType>` — a database table binding. Requires the
    `database` capability. Compiles to `<name> = database.table("<name>", Row)`;
    the handle is iterable, so `find one … in <name>` reuses the comprehension path."""
    name: str
    row_type: str
    line: Optional[int] = None
    col: Optional[int] = None


@dataclass
class Expect:
    items: list          # ("given", name, expr) | ("given-empty", table) | ("assert", expr) | ("fails", expr, msg)


# --- statements ---

@dataclass
class Assign:
    name: str
    value: object
    is_decl: bool = False   # True for `let x = ...` (a fresh binding)


@dataclass
class SetLValue:
    target: object       # an Index (or Attr) expression
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
class For:
    var: str
    index: Optional[str]  # loop-position variable, or None
    iterable: object
    body: list


@dataclass
class Add:
    value: object
    target: object       # list expression to append to


@dataclass
class Swap:
    i: object
    j: object
    target: object       # list expression


@dataclass
class Match:
    """`match <subject>:` with `case <value>:` arms and an optional
    `case otherwise:` default (stored as a case whose value is None)."""
    subject: object
    cases: list          # list of (value_expr_or_None, body)


@dataclass
class Try:
    """`try:` / `on failure as <err>:` — run body, and on a `fail with` recover
    in the handler with `err` bound to the failure message text."""
    body: list
    err_name: str
    handler: list


@dataclass
class Fail:
    message: object


@dataclass
class Todo:
    """A typed hole: `todo "<why>"`. First-class uncertainty for the author."""
    message: str
    line: int


@dataclass
class ExprStmt:
    expr: object


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
    line: Optional[int] = None   # source position, for resolver diagnostics
    col: Optional[int] = None


@dataclass
class Call:
    func: str
    args: list
    line: Optional[int] = None   # source position, for resolver diagnostics
    col: Optional[int] = None


@dataclass
class Attr:
    obj: object
    field: str


@dataclass
class Index:
    obj: object
    index: object


@dataclass
class BinOp:
    op: str
    left: object
    right: object


@dataclass
class Unary:
    op: str
    operand: object


@dataclass
class ListLit:
    items: list


@dataclass
class MapLit:
    pairs: list          # list of (key_expr, value_expr)


@dataclass
class RecordLit:
    """A record literal `{ field: value, ... }` (bare-identifier keys). Which
    `record` type it constructs is resolved by the annotate pass, which fills in
    `type_name` from the expected type (call arg, return, field, list/map element)
    or a unique field-set match."""
    fields: list         # list of (field_name, value_expr)
    line: Optional[int] = None
    col: Optional[int] = None
    type_name: Optional[str] = None   # filled in by annotate.py


@dataclass
class CapCall:
    """A capability verb call, e.g. `hash password`, `insert into users { … }`,
    `send email to a with subject s body b`. Always an EXPRESSION (a bare verb
    statement is wrapped in `ExprStmt`); it compiles to a call on the capability's
    adapter. `args` order is verb-specific (see codegen)."""
    cap: str             # owning capability, e.g. "crypto"
    verb: str            # e.g. "hash", "insert", "send", "verify"
    args: list           # list of expressions
    line: Optional[int] = None
    col: Optional[int] = None


@dataclass
class Convert:
    expr: object
    to: str              # 'text' | 'whole' | 'number'


@dataclass
class Builtin:
    """A keyword-led operation, e.g. `count of X`, `item at I in X`, `numbers from A to B`."""
    name: str
    args: list


@dataclass
class Comp:
    """A comprehension: filter / collect / count / sum / find."""
    kind: str
    elem: object
    var: str
    coll: object
    cond: Optional[object]
