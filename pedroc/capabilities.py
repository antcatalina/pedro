"""Capabilities + the adapter layer — Pedro's "auditable by construction" core.

Pedro programs are pure by default. Anything effectful (a database write, an
email, a hash) must be unlocked with `use capability <name>`. The full set of
declared capabilities is the program's *auditable blast radius*: `pedroc check
--json` reports it as a field, and using a verb whose capability wasn't declared
is a COMPILE ERROR — never a silent import.

This module owns:
  - the capability/verb METADATA (canonical order, adapter names, which verb
    belongs to which capability),
  - `adapter_names(program)`: the emitted import alias per declared capability,
    renamed to dodge a collision with a user identifier (contract #7 — rename the
    IMPORT, never the user's names),
  - `check_capabilities(program)`: the enforcement pass, returning the declared
    surface plus a list of `PedroCapabilityError`.

Codegen (Python/TS) turns each `CapCall` into a call on the adapter object named
here; the reference in-memory adapters live in `pedroc/adapters.py`.
"""
from . import nodes as N
from .suggest import nearest

# Canonical capability order (import order, surface order) — deterministic.
CAPABILITY_ORDER = ["database", "http", "email", "files", "time", "crypto", "random"]

# Per-capability: the default adapter identifier, and a fallback used when the
# default collides with a user identifier (contract #7).
_ADAPTER_DEFAULT = {
    "database": "database", "http": "http", "email": "email", "files": "files",
    "time": "clock", "crypto": "crypto", "random": "random",
}
_ADAPTER_FALLBACK = {
    "database": "db", "http": "web", "email": "mailer", "files": "filesystem",
    "time": "clock_", "crypto": "hasher", "random": "rng",
}

# Verb -> owning capability. Only the verbs the compiler emits today are listed;
# the rest of the README's verb table is pending (see WORKLOG).
VERB_OWNER = {
    "insert": "database",
    "delete": "database",
    "update": "database",
    "send": "email",
    "read": "files",
    "write": "files",
    "hash": "crypto",
    "verify": "crypto",
}

# A human label per verb for diagnostics ("the verb `send email` needs …").
VERB_LABEL = {
    "insert": "insert into",
    "delete": "delete from",
    "update": "update in",
    "send": "send email",
    "read": "read file",
    "write": "write to file",
    "hash": "hash",
    "verify": "verify",
}


def declared_capabilities(program):
    """The capabilities the program declares, deduped, in canonical order."""
    seen = {u.capability for u in program.items if isinstance(u, N.Use)}
    return [c for c in CAPABILITY_ORDER if c in seen]


def adapter_names(program):
    """{capability: emitted import alias} for each DECLARED capability, choosing a
    non-colliding name. Deterministic: default, else fallback, else default + '_'*n."""
    taken = user_identifiers(program)
    names = {}
    chosen = set()
    for cap in declared_capabilities(program):
        for candidate in (_ADAPTER_DEFAULT[cap], _ADAPTER_FALLBACK[cap]):
            if candidate not in taken and candidate not in chosen:
                break
        else:
            candidate = _ADAPTER_DEFAULT[cap]
            while candidate in taken or candidate in chosen:
                candidate += "_"
        names[cap] = candidate
        chosen.add(candidate)
    return names


def user_identifiers(program):
    """Every top-level/param/local identifier a capability import could shadow —
    used to pick a non-colliding adapter alias. `email` (a param in signup) is the
    canonical case that forces the email adapter to import as `mailer`."""
    from .resolve import _bound_in  # reuse the flow-insensitive binder
    names = set()
    for it in program.items:
        if isinstance(it, N.Task):
            names.add(it.name)
            names.update(p[0] for p in it.params)
            names.update(_bound_in(it.body))
        elif isinstance(it, (N.Record, N.Enum)):
            names.add(it.name)
        elif isinstance(it, N.Table):
            names.add(it.name)
    return names


def _walk_capcalls(program, fn):
    """Call `fn(node)` for every CapCall expression anywhere in the program."""
    from .resolve import _stmt_exprs, _stmt_bodies

    def expr(e):
        if e is None:
            return
        if isinstance(e, N.CapCall):
            fn(e)
            for a in e.args:
                expr(a)
        elif isinstance(e, N.BinOp):
            expr(e.left); expr(e.right)
        elif isinstance(e, N.Unary):
            expr(e.operand)
        elif isinstance(e, N.Attr):
            expr(e.obj)
        elif isinstance(e, N.Index):
            expr(e.obj); expr(e.index)
        elif isinstance(e, N.Convert):
            expr(e.expr)
        elif isinstance(e, N.Call):
            for a in e.args:
                expr(a)
        elif isinstance(e, N.Builtin):
            for a in e.args:
                expr(a)
        elif isinstance(e, N.ListLit):
            for i in e.items:
                expr(i)
        elif isinstance(e, N.MapLit):
            for k, v in e.pairs:
                expr(k); expr(v)
        elif isinstance(e, N.RecordLit):
            for _fn, fv in e.fields:
                expr(fv)
        elif isinstance(e, N.Comp):
            expr(e.coll); expr(e.elem); expr(e.cond)

    def stmts(ss):
        for s in ss:
            for e in _stmt_exprs(s):
                expr(e)
            for body in _stmt_bodies(s):
                stmts(body)

    for it in program.items:
        if isinstance(it, N.Task):
            stmts(it.body)
        elif isinstance(it, N.Expect):
            for item in it.items:
                if item[0] == "given":
                    expr(item[2])
                elif item[0] in ("assert", "fails"):
                    expr(item[1])
                elif item[0] == "forall":
                    expr(item[2]); expr(item[3]); expr(item[4])


def check_capabilities(program):
    """Return (surface, errors): the declared capability surface, and a list of
    PedroCapabilityError for unknown declarations, undeclared verb use, and bad
    `table` declarations. Pure — shapes diagnostics only."""
    from .errors import PedroCapabilityError

    errors = []
    declared_set = set()
    for u in [it for it in program.items if isinstance(it, N.Use)]:
        if u.capability not in _ADAPTER_DEFAULT:
            errors.append(PedroCapabilityError(
                u.line, u.col, f"unknown capability {u.capability!r}",
                code="unknown-capability",
                hint="capabilities are: " + ", ".join(CAPABILITY_ORDER),
                suggestion=nearest(u.capability, CAPABILITY_ORDER),
            ))
        else:
            declared_set.add(u.capability)

    records = {it.name for it in program.items if isinstance(it, N.Record)}
    for t in [it for it in program.items if isinstance(it, N.Table)]:
        if "database" not in declared_set:
            errors.append(PedroCapabilityError(
                t.line, t.col,
                f"table {t.name!r} needs the database capability",
                code="undeclared-capability",
                hint="add `use capability database` before declaring a table",
            ))
        if t.row_type not in records:
            errors.append(PedroCapabilityError(
                t.line, t.col,
                f"table {t.name!r} has unknown row type {t.row_type!r}",
                code="unknown-record",
                hint="a table's row type must be a declared `record`",
                suggestion=nearest(t.row_type, sorted(records)),
            ))

    def check_call(node):
        owner = VERB_OWNER.get(node.verb)
        if owner is not None and owner not in declared_set:
            errors.append(PedroCapabilityError(
                node.line, node.col,
                f"the verb {VERB_LABEL.get(node.verb, node.verb)!r} needs the "
                f"{owner} capability, which is not declared",
                code="undeclared-capability",
                hint=f"add `use capability {owner}` at the top of the program",
            ))

    _walk_capcalls(program, check_call)

    surface = [c for c in CAPABILITY_ORDER if c in declared_set]
    return surface, errors
