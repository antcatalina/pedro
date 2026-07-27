"""Name-resolution pass — finds unknown identifiers and unknown task calls.

Runs AFTER a successful parse and produces `undefined-name` / `unknown-task`
diagnostics with a nearest-match "did you mean X?" suggestion. Errors are prompts:
a typo'd variable or task name is one of the most common authoring mistakes, and
the fix is almost always the closest known name.

Scoping is flow-insensitive, like Python function scope: every name bound ANYWHERE
in a task body (params, `let`/`set`/reassign, loop vars, comprehension vars, the
`try ... on failure as <err>` binding) counts as declared for the whole task. This
deliberately never flags a use-before-assign or a name bound only in one branch —
it only flags names that are declared *nowhere*, which is exactly a typo.

The pass is pure and deterministic; it shapes diagnostics only, never output.
"""
from . import nodes as N
from .suggest import nearest

# Names that always resolve (synthesized by the parser, e.g. `is present`/`is
# nothing` emit `Name("None")`; those carry no source position and are skipped
# anyway, but keep the set explicit for safety).
_GLOBALS = {"None", "True", "False"}


def resolve(program):
    """Return a list of PedroNameError for every unresolved reference."""
    from .errors import PedroNameError  # local import avoids a cycle at import time

    task_names = {it.name for it in program.items if isinstance(it, N.Task)}
    errors = []

    def report(node, code, message, candidates):
        sug = nearest(node_value(node), sorted(candidates))
        errors.append(PedroNameError(
            node.line, node.col, message, code=code,
            hint=_HINTS[code], suggestion=sug,
        ))

    def node_value(node):
        return node.value if isinstance(node, N.Name) else node.func

    def check_expr(e, env):
        if isinstance(e, N.Name):
            if e.line is not None and e.value not in env and e.value not in task_names:
                report(e, "undefined-name",
                       f"name {e.value!r} is not defined",
                       env | task_names)
        elif isinstance(e, N.Call):
            if e.line is not None and e.func not in task_names:
                report(e, "unknown-task",
                       f"no task named {e.func!r}",
                       task_names)
            for a in e.args:
                check_expr(a, env)
        elif isinstance(e, N.Attr):
            check_expr(e.obj, env)
        elif isinstance(e, N.Index):
            check_expr(e.obj, env)
            check_expr(e.index, env)
        elif isinstance(e, N.BinOp):
            check_expr(e.left, env)
            check_expr(e.right, env)
        elif isinstance(e, N.Unary):
            check_expr(e.operand, env)
        elif isinstance(e, N.ListLit):
            for i in e.items:
                check_expr(i, env)
        elif isinstance(e, N.MapLit):
            for k, v in e.pairs:
                check_expr(k, env)
                check_expr(v, env)
        elif isinstance(e, N.Convert):
            check_expr(e.expr, env)
        elif isinstance(e, N.Builtin):
            for a in e.args:
                check_expr(a, env)
        elif isinstance(e, N.Comp):
            check_expr(e.coll, env)
            check_expr(e.elem, env)
            if e.cond is not None:
                check_expr(e.cond, env)
        # Num/Str/Bool: leaves, nothing to resolve

    def check_stmts(stmts, env):
        for s in stmts:
            for e in _stmt_exprs(s):
                check_expr(e, env)
            for body in _stmt_bodies(s):
                check_stmts(body, env)

    for it in program.items:
        if isinstance(it, N.Task):
            env = _GLOBALS | {p[0] for p in it.params} | _bound_in(it.body)
            check_stmts(it.body, env)
        elif isinstance(it, N.Expect):
            env = set(_GLOBALS)
            for item in it.items:
                if item[0] == "given":
                    check_expr(item[2], env | task_names)
                    env.add(item[1])
                elif item[0] == "assert":
                    check_expr(item[1], env)
                else:  # fails
                    check_expr(item[1], env)
    return errors


_HINTS = {
    "undefined-name": "declare it first with `let <name> = ...`, or fix the spelling",
    "unknown-task": "define the task, or fix the call to match an existing task name",
}


# --- structural helpers: which sub-expressions / sub-bodies a statement has ---

def _stmt_exprs(s):
    if isinstance(s, N.Assign):
        return [s.value]
    if isinstance(s, N.SetLValue):
        return [s.target, s.value]
    if isinstance(s, N.AugAssign):
        return [s.value]
    if isinstance(s, N.Return):
        return [s.value] if s.value is not None else []
    if isinstance(s, N.If):
        return [c for c, _ in s.branches]
    if isinstance(s, N.While):
        return [s.cond]
    if isinstance(s, N.Repeat):
        return [s.count]
    if isinstance(s, N.For):
        return [s.iterable]
    if isinstance(s, N.Add):
        return [s.value, s.target]
    if isinstance(s, N.Swap):
        return [s.i, s.j, s.target]
    if isinstance(s, N.Match):
        return [s.subject] + [v for v, _ in s.cases if v is not None]
    if isinstance(s, N.Fail):
        return [s.message]
    if isinstance(s, N.ExprStmt):
        return [s.expr]
    return []


def _stmt_bodies(s):
    if isinstance(s, N.If):
        out = [b for _, b in s.branches]
        if s.orelse is not None:
            out.append(s.orelse)
        return out
    if isinstance(s, (N.While, N.Repeat, N.For)):
        return [s.body]
    if isinstance(s, N.Match):
        return [b for _, b in s.cases]
    if isinstance(s, N.Try):
        return [s.body, s.handler]
    return []


def _bound_in(stmts):
    """All names bound anywhere in a statement list (flow-insensitive)."""
    names = set()

    def walk_stmts(ss):
        for s in ss:
            if isinstance(s, N.Assign):
                names.add(s.name)
            elif isinstance(s, N.AugAssign):
                names.add(s.name)
            elif isinstance(s, N.For):
                names.add(s.var)
                if s.index:
                    names.add(s.index)
            elif isinstance(s, N.Try):
                names.add(s.err_name)
            for e in _stmt_exprs(s):
                walk_expr(e)
            for body in _stmt_bodies(s):
                walk_stmts(body)

    def walk_expr(e):
        if isinstance(e, N.Comp):
            names.add(e.var)
            walk_expr(e.coll)
            walk_expr(e.elem)
            if e.cond is not None:
                walk_expr(e.cond)
        elif isinstance(e, N.Call):
            for a in e.args:
                walk_expr(a)
        elif isinstance(e, N.BinOp):
            walk_expr(e.left)
            walk_expr(e.right)
        elif isinstance(e, N.Unary):
            walk_expr(e.operand)
        elif isinstance(e, (N.Attr, N.Convert)):
            walk_expr(e.obj if isinstance(e, N.Attr) else e.expr)
        elif isinstance(e, N.Index):
            walk_expr(e.obj)
            walk_expr(e.index)
        elif isinstance(e, N.ListLit):
            for i in e.items:
                walk_expr(i)
        elif isinstance(e, N.MapLit):
            for k, v in e.pairs:
                walk_expr(k)
                walk_expr(v)
        elif isinstance(e, N.Builtin):
            for a in e.args:
                walk_expr(a)

    walk_stmts(stmts)
    return names
