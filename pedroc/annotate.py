"""Record-literal typing pass — resolves each `{ field: value }` record literal
to the `record` type it constructs, and validates its fields.

A record literal carries no type name in the source (`order_total([ { name: ...,
price: ... } ], 0)`), so this pass figures out which declared `record` each one
is, by propagating an EXPECTED TYPE top-down from the places that know it:

  - a task-call argument   -> the callee's declared parameter type
  - a `return` value       -> the enclosing task's return type
  - a record field value   -> that field's declared type (nested records)
  - a `list`/`map` element  -> the collection's element/value type

When no expected type reaches a literal, it falls back to a UNIQUE field-set
match against the declared records. Anything still unresolved (or an unknown /
missing-required field) is a `PedroTypeError` — a prompt the author can fix.

The pass MUTATES each `RecordLit.type_name` in place and returns the list of
errors. It is pure and deterministic; it shapes annotations + diagnostics only.
"""
from . import nodes as N
from .errors import PedroTypeError
from .suggest import nearest
from .resolve import _stmt_exprs, _stmt_bodies


def annotate(program):
    """Resolve every record literal's `type_name`; return a list of PedroTypeError."""
    records = {it.name: it for it in program.items if isinstance(it, N.Record)}
    tasks = {it.name: it for it in program.items if isinstance(it, N.Task)}
    errors = []

    def unwrap(t):
        # See through `optional T` — a record may sit behind an optional type.
        while t is not None and t[0] == "optional":
            t = t[1]
        return t

    def record_name_of(t):
        t = unwrap(t)
        if t is not None and t[0] == "name" and t[1] in records:
            return t[1]
        return None

    def elem_type_of(t):
        t = unwrap(t)
        return t[1] if t is not None and t[0] == "list" else None

    def value_type_of(t):
        t = unwrap(t)
        return t[2] if t is not None and t[0] == "map" else None

    def infer_by_fields(lit):
        """A record whose declared fields can accept exactly these keys: every
        given key is a valid field and every required field is supplied. Unique
        match -> that record; otherwise None (caller reports the ambiguity)."""
        given = {fn for fn, _ in lit.fields}
        candidates = []
        for rname, rec in records.items():
            declared = {f[0] for f in rec.fields}
            required = {f[0] for f in rec.fields if f[2] is None}
            if given <= declared and required <= given:
                candidates.append(rname)
        return candidates[0] if len(candidates) == 1 else None

    def visit(e, expected):
        if isinstance(e, N.RecordLit):
            rname = record_name_of(expected)
            if rname is None:
                rname = infer_by_fields(e)
            if rname is None:
                errors.append(PedroTypeError(
                    e.line, e.col,
                    "cannot determine which record this `{ ... }` literal builds",
                    code="ambiguous-record",
                    hint="use it where a record type is expected (a typed task "
                         "argument, `return`, or field), or make its fields match "
                         "exactly one declared record",
                    suggestion=nearest(_first_field(e), sorted(records)),
                ))
                return
            e.type_name = rname
            rec = records[rname]
            ftypes = {f[0]: f[1] for f in rec.fields}
            declared = {f[0] for f in rec.fields}
            given = {fn for fn, _ in e.fields}
            for fn, _ in e.fields:
                if fn not in declared:
                    errors.append(PedroTypeError(
                        e.line, e.col, f"record {rname!r} has no field {fn!r}",
                        code="unknown-field",
                        hint=f"{rname} fields are: {', '.join(sorted(declared))}",
                        suggestion=nearest(fn, sorted(declared)),
                    ))
            for f in rec.fields:
                if f[0] not in given and f[2] is None:
                    errors.append(PedroTypeError(
                        e.line, e.col,
                        f"record {rname!r} literal is missing required field {f[0]!r}",
                        code="missing-field",
                        hint=f"add `{f[0]}: <value>` (or give {f[0]} a default in the record)",
                    ))
            for fn, fv in e.fields:
                visit(fv, ftypes.get(fn))
        elif isinstance(e, N.ListLit):
            et = elem_type_of(expected)
            for it in e.items:
                visit(it, et)
        elif isinstance(e, N.MapLit):
            vt = value_type_of(expected)
            for k, v in e.pairs:
                visit(k, None)
                visit(v, vt)
        elif isinstance(e, N.Call):
            callee = tasks.get(e.func)
            ptypes = [p[1] for p in callee.params] if callee else []
            for i, a in enumerate(e.args):
                visit(a, ptypes[i] if i < len(ptypes) else None)
        elif isinstance(e, N.BinOp):
            visit(e.left, None)
            visit(e.right, None)
        elif isinstance(e, N.Unary):
            visit(e.operand, None)
        elif isinstance(e, N.Attr):
            visit(e.obj, None)
        elif isinstance(e, N.Index):
            visit(e.obj, None)
            visit(e.index, None)
        elif isinstance(e, N.Convert):
            visit(e.expr, None)
        elif isinstance(e, N.Builtin):
            for a in e.args:
                visit(a, None)
        elif isinstance(e, N.Comp):
            visit(e.coll, None)
            visit(e.elem, None)
            if e.cond is not None:
                visit(e.cond, None)
        # Num / Str / Bool / Name: leaves, nothing to resolve.

    def visit_stmts(stmts, ret_type):
        for s in stmts:
            if isinstance(s, N.Return):
                if s.value is not None:
                    visit(s.value, ret_type)
            else:
                for e in _stmt_exprs(s):
                    visit(e, None)
            for body in _stmt_bodies(s):
                visit_stmts(body, ret_type)

    for it in program.items:
        if isinstance(it, N.Task):
            visit_stmts(it.body, it.ret_type)
        elif isinstance(it, N.Record):
            for (_, ftype, default) in it.fields:
                if default is not None:
                    visit(default, ftype)
        elif isinstance(it, N.Expect):
            for item in it.items:
                # ("given", name, expr) | ("assert", expr) | ("fails", expr, msg)
                visit(item[2] if item[0] == "given" else item[1], None)

    return errors


def _first_field(lit):
    return lit.fields[0][0] if lit.fields else ""
