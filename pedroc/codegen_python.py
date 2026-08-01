"""Python code generator: AST -> idiomatic Python source.

Binary expressions are fully parenthesized so emitted precedence always matches
the parsed AST — deterministic and never wrong, at the cost of a few parens.
"""
from . import nodes as N
from .capabilities import declared_capabilities, adapter_names

TYPE_MAP = {"text": "str", "whole": "int", "number": "float", "flag": "bool", "nothing": "None"}
BINOP_MAP = {"mod": "%", "div": "//", "followed_by": "+"}
CONVERT_MAP = {"text": "str", "whole": "int", "number": "float"}

_BUILTINS = {
    "count_of": lambda a: f"len({a[0]})",
    "first_of": lambda a: f"{a[0]}[0]",
    "last_of": lambda a: f"{a[0]}[-1]",
    "copy_of": lambda a: f"list({a[0]})",
    "chars_of": lambda a: f"list({a[0]})",
    "take": lambda a: f"{a[1]}[:{a[0]}]",
    "drop": lambda a: f"{a[1]}[{a[0]}:]",
    "item_at": lambda a: f"{a[1]}[{a[0]}]",
    "split": lambda a: f"{a[0]}.split({a[1]})",
    "sort": lambda a: f"sorted({a[0]})",
    "empty_map": lambda a: "{}",
    "range": lambda a: f"list(range({a[0]}, {a[1]} + 1))",
}


def _gen_type(t):
    if t is None:
        return "None"
    kind = t[0]
    if kind == "name":
        if t[1] in TYPE_MAP:
            return TYPE_MAP[t[1]]
        return t[1] if t[1] in _typenames else "object"
    if kind == "list":
        return f"list[{_gen_type(t[1])}]"
    if kind == "map":
        return f"dict[{_gen_type(t[1])}, {_gen_type(t[2])}]"
    if kind == "optional":
        return f"{_gen_type(t[1])} | None"
    return "object"


def _uses_pedro_error(program):
    found = [False]

    def walk(stmts):
        for s in stmts:
            if isinstance(s, N.Fail):
                found[0] = True
            elif isinstance(s, N.Try):
                found[0] = True  # the generated `except PedroError` needs it
                walk(s.body)
                walk(s.handler)
            elif isinstance(s, N.Match):
                for _, body in s.cases:
                    walk(body)
            elif isinstance(s, N.If):
                for _, body in s.branches:
                    walk(body)
                if s.orelse:
                    walk(s.orelse)
            elif isinstance(s, (N.While, N.Repeat, N.For)):
                walk(s.body)

    for it in program.items:
        if isinstance(it, N.Task):
            walk(it.body)
        elif isinstance(it, N.Expect):
            if any(kind == "fails" for (kind, *_rest) in it.items):
                found[0] = True
    return found[0]


_match_counter = [0]

# Record definitions for the file currently being generated, so RecordLit codegen
# can look up field order + defaults. Reset per generate() call (deterministic,
# single-threaded), mirroring the _match_counter pattern.
_records = {}
_typenames = set()   # declared record + enum names (rendered by name, not `object`)
_adapters = {}       # {capability: emitted adapter alias} for this file


def _fresh_subject():
    _match_counter[0] += 1
    return f"_subject{_match_counter[0]}"


def _cap_import(caps):
    """`from pedro_capabilities import database, email as mailer, crypto` — one
    swappable per-project module. Aliases dodge collisions with user identifiers
    (contract #7: rename the IMPORT, never the user's names)."""
    specs = []
    for cap in caps:
        alias = _adapters[cap]
        specs.append(cap if alias == cap else f"{cap} as {alias}")
    return f"from pedro_capabilities import {', '.join(specs)}"


def generate(program, filename="<pedro>"):
    global _records, _typenames, _adapters
    _match_counter[0] = 0  # reset per call → deterministic temp names
    records = [it for it in program.items if isinstance(it, N.Record)]
    enums = [it for it in program.items if isinstance(it, N.Enum)]
    tables = [it for it in program.items if isinstance(it, N.Table)]
    caps = declared_capabilities(program)
    _records = {r.name: r for r in records}
    _typenames = {r.name for r in records} | {en.name for en in enums}
    _adapters = adapter_names(program)

    lines = [
        f"# Generated from {filename} by pedroc v0.1 (target: {program.target}). Do not edit by hand.",
        "",
    ]
    # `from __future__ import annotations` makes dataclass field annotations lazy
    # strings, so a record may reference another record/enum declared later.
    future = ["from __future__ import annotations", ""] if records else []
    imports = []
    if records:
        imports.append("from dataclasses import dataclass")
    if enums:
        imports.append("from enum import Enum")
    if caps:
        imports.append(_cap_import(caps))
    lines += future
    if imports:
        lines += imports + [""]

    for en in enums:
        lines.extend(_gen_enum(en))
        lines.append("")
    for rec in records:
        lines.extend(_gen_record(rec))
        lines.append("")

    # Table bindings come after the record classes they reference.
    for tbl in tables:
        lines.append(f'{tbl.name} = {_adapters["database"]}.table("{tbl.name}", {tbl.row_type})')
    if tables:
        lines.append("")

    if _uses_pedro_error(program):
        lines += ["class PedroError(Exception):", "    pass", "", ""]

    tasks = [it for it in program.items if isinstance(it, N.Task)]
    expects = [it for it in program.items if isinstance(it, N.Expect)]

    for task in tasks:
        lines.extend(_gen_task(task))
        lines.append("")

    main = []
    for ex in expects:
        for item in ex.items:
            main.extend(_gen_expect_item(item))
    if main:
        base = filename.replace("\\", "/").split("/")[-1]
        lines.append('if __name__ == "__main__":')
        lines.extend(main)
        lines.append(f'    print("{base}: all expectations passed \\u2713")')
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _gen_expect_item(item):
    kind = item[0]
    if kind == "given":
        return [f"    {item[1]} = {_gen_expr(item[2])}"]
    if kind == "given-empty":
        return [f"    {item[1]}.clear()"]
    if kind == "forall":
        name, lo, hi, body = item[1], item[2], item[3], item[4]
        return [
            f"    for {name} in range({_gen_expr(lo)}, ({_gen_expr(hi)}) + 1):",
            f"        assert ({_gen_expr(body)}), "
            f'f"counterexample: {name}={{{name}}}, got false"',
        ]
    if kind == "assert":
        return [f"    assert {_gen_expr(item[1])}"]
    if kind == "fails":
        call = _gen_expr(item[1])
        msg = item[2].replace("\\", "\\\\").replace('"', '\\"')
        return [
            "    try:",
            f"        {call}",
            f'        raise AssertionError("expected failure: {msg}")',
            "    except PedroError as _e:",
            f'        assert str(_e) == "{msg}"',
        ]
    raise TypeError(f"unknown expect item: {item!r}")


def _gen_enum(en):
    # `str, Enum` mixin so `Color.red == "red"` — matches the TypeScript backend,
    # where the enum is a plain string, keeping the two backends in agreement.
    lines = [f"class {en.name}(str, Enum):"]
    for v in en.variants:
        lines.append(f'    {v} = "{v}"')
    return lines


def _gen_record(rec):
    lines = ["@dataclass", f"class {rec.name}:"]
    for (fname, ftype, default) in rec.fields:
        decl = f"    {fname}: {_gen_type(ftype)}"
        if default is not None:
            decl += f" = {_gen_expr(default)}"
        lines.append(decl)
    return lines


def _gen_task(task):
    params = []
    for (pname, ptype, default) in task.params:
        p = f"{pname}: {_gen_type(ptype)}"
        if default is not None:
            p += f" = {_gen_expr(default)}"
        params.append(p)
    header = f"def {task.name}({', '.join(params)}) -> {_gen_type(task.ret_type)}:"
    return [header] + _gen_block(task.body, 1)


def _gen_block(stmts, indent):
    out = []
    for s in stmts:
        out.extend(_gen_stmt(s, indent))
    if not out:
        out.append("    " * indent + "pass")
    return out


def _gen_stmt(s, indent):
    pad = "    " * indent
    if isinstance(s, N.Assign):
        return [f"{pad}{s.name} = {_gen_expr(s.value)}"]
    if isinstance(s, N.SetLValue):
        return [f"{pad}{_gen_expr(s.target)} = {_gen_expr(s.value)}"]
    if isinstance(s, N.AugAssign):
        return [f"{pad}{s.name} {s.op}= {_gen_expr(s.value)}"]
    if isinstance(s, N.Return):
        return [f"{pad}return" if s.value is None else f"{pad}return {_gen_expr(s.value)}"]
    if isinstance(s, N.If):
        out = []
        for bi, (cond, body) in enumerate(s.branches):
            out.append(f"{pad}{'if' if bi == 0 else 'elif'} {_gen_expr(cond)}:")
            out.extend(_gen_block(body, indent + 1))
        if s.orelse is not None:
            out.append(f"{pad}else:")
            out.extend(_gen_block(s.orelse, indent + 1))
        return out
    if isinstance(s, N.While):
        return [f"{pad}while {_gen_expr(s.cond)}:"] + _gen_block(s.body, indent + 1)
    if isinstance(s, N.Repeat):
        return [f"{pad}for _ in range({_gen_expr(s.count)}):"] + _gen_block(s.body, indent + 1)
    if isinstance(s, N.For):
        if s.index:
            head = f"{pad}for {s.index}, {s.var} in enumerate({_gen_expr(s.iterable)}):"
        else:
            head = f"{pad}for {s.var} in {_gen_expr(s.iterable)}:"
        return [head] + _gen_block(s.body, indent + 1)
    if isinstance(s, N.Add):
        return [f"{pad}{_gen_expr(s.target)}.append({_gen_expr(s.value)})"]
    if isinstance(s, N.Swap):
        t, i, j = _gen_expr(s.target), _gen_expr(s.i), _gen_expr(s.j)
        return [f"{pad}{t}[{i}], {t}[{j}] = {t}[{j}], {t}[{i}]"]
    if isinstance(s, N.Match):
        tmp = _fresh_subject()
        out = [f"{pad}{tmp} = {_gen_expr(s.subject)}"]
        emitted = False
        for (value, body) in s.cases:
            if value is None:  # otherwise
                if emitted:
                    out.append(f"{pad}else:")
                    out.extend(_gen_block(body, indent + 1))
                else:  # match with only an otherwise arm → unconditional
                    out.extend(_gen_block(body, indent))
            else:
                kw = "if" if not emitted else "elif"
                out.append(f"{pad}{kw} {tmp} == {_gen_expr(value)}:")
                out.extend(_gen_block(body, indent + 1))
                emitted = True
        return out
    if isinstance(s, N.Try):
        pad_in = "    " * (indent + 1)
        out = [f"{pad}try:"]
        out.extend(_gen_block(s.body, indent + 1))
        out.append(f"{pad}except PedroError as _pedro_err:")
        out.append(f"{pad_in}{s.err_name} = str(_pedro_err)")
        out.extend(_gen_block(s.handler, indent + 1))
        return out
    if isinstance(s, N.Fail):
        return [f"{pad}raise PedroError({_gen_expr(s.message)})"]
    if isinstance(s, N.ExprStmt):
        return [f"{pad}{_gen_expr(s.expr)}"]
    if isinstance(s, N.Todo):
        msg = s.message.replace("\\", "\\\\").replace('"', '\\"')
        return [f'{pad}raise NotImplementedError("unresolved Pedro hole: {msg}")']
    raise TypeError(f"unknown statement node: {s!r}")


def _gen_record_lit(e):
    """`RecordLit` -> `TypeName(field=value, ...)`. Missing defaulted fields are
    filled in explicitly (so Python and TypeScript emit the identical field set),
    in the record's declared field order for deterministic output."""
    given = {fn: fv for fn, fv in e.fields}
    rec = _records[e.type_name]
    args = []
    for (fname, _ftype, default) in rec.fields:
        if fname in given:
            args.append(f"{fname}={_gen_expr(given[fname])}")
        elif default is not None:
            args.append(f"{fname}={_gen_expr(default)}")
    return f"{e.type_name}({', '.join(args)})"


def _gen_capcall(e):
    """A capability verb -> a call on its adapter (from `pedro_capabilities`).
    Table verbs (`insert`) go through the table handle; the rest through the
    capability's adapter alias."""
    if e.verb == "insert":
        table, record = e.args
        return f"{_gen_expr(table)}.insert({_gen_expr(record)})"
    if e.verb == "hash":
        return f"{_adapters['crypto']}.hash({_gen_expr(e.args[0])})"
    if e.verb == "verify":
        return f"{_adapters['crypto']}.verify({_gen_expr(e.args[0])}, {_gen_expr(e.args[1])})"
    if e.verb == "send":
        to, subject, body = e.args
        return (f"{_adapters['email']}.send(to={_gen_expr(to)}, "
                f"subject={_gen_expr(subject)}, body={_gen_expr(body)})")
    raise TypeError(f"unknown capability verb: {e.verb!r}")


def _gen_str(value):
    if "{" in value or "}" in value:
        body = value.replace("\\{", "{{").replace("\\}", "}}")
        return 'f"' + body + '"'
    return '"' + value + '"'


def _gen_interpolation(parts):
    """A `Str` with structured interpolation → a Python f-string, with each hole's
    expression re-generated through codegen (so `div`→`//`, etc.)."""
    out = []
    for kind, val in parts:
        if kind == "text":
            out.append(val.replace("{", "{{").replace("}", "}}"))
        else:  # expr — render through codegen, guard braces from f-string parsing
            code = _gen_expr(val)
            if "{" in code or "}" in code or "\\" in code:
                # A hole whose generated code itself contains braces/backslashes
                # can't sit in an f-string; concatenate via str() instead.
                return _gen_interpolation_concat(parts)
            out.append("{" + code + "}")
    return 'f"' + "".join(out) + '"'


def _gen_interpolation_concat(parts):
    """Fallback for holes whose codegen contains braces: `("t" + str(expr) + ...)`."""
    pieces = []
    for kind, val in parts:
        if kind == "text":
            pieces.append('"' + val.replace("\\", "\\\\").replace('"', '\\"') + '"')
        else:
            pieces.append(f"str({_gen_expr(val)})")
    return "(" + " + ".join(pieces) + ")" if pieces else '""'


def _gen_expr(e):
    if isinstance(e, N.Num):
        return e.value
    if isinstance(e, N.Str):
        if e.parts is not None:
            return _gen_interpolation(e.parts)
        return _gen_str(e.value)
    if isinstance(e, N.Bool):
        return "True" if e.value else "False"
    if isinstance(e, N.Name):
        return e.value
    if isinstance(e, N.Call):
        return f"{e.func}({', '.join(_gen_expr(a) for a in e.args)})"
    if isinstance(e, N.Attr):
        return f"{_gen_expr(e.obj)}.{e.field}"
    if isinstance(e, N.Index):
        return f"{_gen_expr(e.obj)}[{_gen_expr(e.index)}]"
    if isinstance(e, N.BinOp):
        op = BINOP_MAP.get(e.op, e.op)
        return f"({_gen_expr(e.left)} {op} {_gen_expr(e.right)})"
    if isinstance(e, N.Unary):
        return f"(not {_gen_expr(e.operand)})" if e.op == "not" else f"(-{_gen_expr(e.operand)})"
    if isinstance(e, N.ListLit):
        return f"[{', '.join(_gen_expr(i) for i in e.items)}]"
    if isinstance(e, N.MapLit):
        return "{" + ", ".join(f"{_gen_expr(k)}: {_gen_expr(v)}" for k, v in e.pairs) + "}"
    if isinstance(e, N.RecordLit):
        return _gen_record_lit(e)
    if isinstance(e, N.CapCall):
        return _gen_capcall(e)
    if isinstance(e, N.Convert):
        fn = CONVERT_MAP.get(e.to)
        if fn is None:
            raise TypeError(f"cannot convert to {e.to!r}")
        return f"{fn}({_gen_expr(e.expr)})"
    if isinstance(e, N.Builtin):
        args = [_gen_expr(a) for a in e.args]
        return _BUILTINS[e.name](args)
    if isinstance(e, N.Comp):
        elem = _gen_expr(e.elem)
        coll = _gen_expr(e.coll)
        cond = f" if {_gen_expr(e.cond)}" if e.cond is not None else ""
        if e.kind in ("filter", "collect"):
            return f"[{elem} for {e.var} in {coll}{cond}]"
        if e.kind == "count":
            return f"sum(1 for {e.var} in {coll}{cond})"
        if e.kind == "sum":
            return f"sum({elem} for {e.var} in {coll}{cond})"
        if e.kind == "find":
            return f"next(({elem} for {e.var} in {coll}{cond}), None)"
        raise TypeError(f"unknown comprehension kind: {e.kind!r}")
    raise TypeError(f"unknown expr node: {e!r}")
