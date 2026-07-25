"""Python code generator: AST -> idiomatic Python source.

Binary expressions are fully parenthesized so the emitted precedence always
matches the parsed AST — deterministic and never wrong, at the cost of a few
extra parens.
"""
from . import nodes as N

TYPE_MAP = {"text": "str", "whole": "int", "number": "float", "flag": "bool", "nothing": "None"}
BINOP_MAP = {"mod": "%", "div": "//"}


def generate(program, filename="<pedro>"):
    lines = [
        f"# Generated from {filename} by pedroc v0.1 (target: {program.target}). Do not edit by hand.",
        "",
    ]
    tasks = [it for it in program.items if isinstance(it, N.Task)]
    expects = [it for it in program.items if isinstance(it, N.Expect)]

    for task in tasks:
        lines.extend(_gen_task(task))
        lines.append("")

    asserts = []
    for ex in expects:
        for a in ex.assertions:
            asserts.append(f"    assert {_gen_expr(a)}")
    if asserts:
        base = filename.replace("\\", "/").split("/")[-1]
        lines.append('if __name__ == "__main__":')
        lines.extend(asserts)
        lines.append(f'    print("{base}: all expectations passed \\u2713")')
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _gen_task(task):
    params = []
    for (pname, ptype, default) in task.params:
        p = f"{pname}: {TYPE_MAP.get(ptype, 'object')}"
        if default is not None:
            p += f" = {_gen_expr(default)}"
        params.append(p)
    ret = TYPE_MAP.get(task.ret_type, "object")
    header = f"def {task.name}({', '.join(params)}) -> {ret}:"
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
    if isinstance(s, N.AugAssign):
        return [f"{pad}{s.name} {s.op}= {_gen_expr(s.value)}"]
    if isinstance(s, N.Return):
        return [f"{pad}return" if s.value is None else f"{pad}return {_gen_expr(s.value)}"]
    if isinstance(s, N.If):
        out = []
        for bi, (cond, body) in enumerate(s.branches):
            kw = "if" if bi == 0 else "elif"
            out.append(f"{pad}{kw} {_gen_expr(cond)}:")
            out.extend(_gen_block(body, indent + 1))
        if s.orelse is not None:
            out.append(f"{pad}else:")
            out.extend(_gen_block(s.orelse, indent + 1))
        return out
    if isinstance(s, N.While):
        return [f"{pad}while {_gen_expr(s.cond)}:"] + _gen_block(s.body, indent + 1)
    if isinstance(s, N.Repeat):
        return [f"{pad}for _ in range({_gen_expr(s.count)}):"] + _gen_block(s.body, indent + 1)
    if isinstance(s, N.ExprStmt):
        return [f"{pad}{_gen_expr(s.expr)}"]
    raise TypeError(f"unknown statement node: {s!r}")


def _gen_expr(e):
    if isinstance(e, N.Num):
        return e.value
    if isinstance(e, N.Str):
        return '"' + e.value + '"'
    if isinstance(e, N.Bool):
        return "True" if e.value else "False"
    if isinstance(e, N.Name):
        return e.value
    if isinstance(e, N.Call):
        return f"{e.func}({', '.join(_gen_expr(a) for a in e.args)})"
    if isinstance(e, N.Attr):
        return f"{_gen_expr(e.obj)}.{e.field}"
    if isinstance(e, N.BinOp):
        op = BINOP_MAP.get(e.op, e.op)
        return f"({_gen_expr(e.left)} {op} {_gen_expr(e.right)})"
    if isinstance(e, N.Unary):
        return f"(not {_gen_expr(e.operand)})" if e.op == "not" else f"(-{_gen_expr(e.operand)})"
    raise TypeError(f"unknown expr node: {e!r}")
