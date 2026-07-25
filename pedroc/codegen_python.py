"""Python code generator: AST -> idiomatic Python source.

Binary expressions are fully parenthesized so emitted precedence always matches
the parsed AST — deterministic and never wrong, at the cost of a few parens.
"""
from . import nodes as N

TYPE_MAP = {"text": "str", "whole": "int", "number": "float", "flag": "bool", "nothing": "None"}
BINOP_MAP = {"mod": "%", "div": "//"}
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
        return TYPE_MAP.get(t[1], "object")
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


def generate(program, filename="<pedro>"):
    lines = [
        f"# Generated from {filename} by pedroc v0.1 (target: {program.target}). Do not edit by hand.",
        "",
    ]
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
    if isinstance(s, N.Fail):
        return [f"{pad}raise PedroError({_gen_expr(s.message)})"]
    if isinstance(s, N.ExprStmt):
        return [f"{pad}{_gen_expr(s.expr)}"]
    if isinstance(s, N.Todo):
        msg = s.message.replace("\\", "\\\\").replace('"', '\\"')
        return [f'{pad}raise NotImplementedError("unresolved Pedro hole: {msg}")']
    raise TypeError(f"unknown statement node: {s!r}")


def _gen_str(value):
    if "{" in value or "}" in value:
        body = value.replace("\\{", "{{").replace("\\}", "}}")
        return 'f"' + body + '"'
    return '"' + value + '"'


def _gen_expr(e):
    if isinstance(e, N.Num):
        return e.value
    if isinstance(e, N.Str):
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
