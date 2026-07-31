"""TypeScript code generator: AST -> TypeScript source (erasable-types only).

The same Pedro AST the Python backend consumes, retargeted to TypeScript. The
output uses only *erasable* type syntax (annotations, `Record<>`, `as`, `| null`)
so Node (v24+, which strips types) can run it directly with no build step.

The interesting part is bridging Python->JS semantic gaps: Pedro `==` is value
equality (JS `===` is reference-equal for arrays/objects), Pedro `followed by` is
list-or-string concat, `div` floors, membership is by value, and sort must be
numeric-safe. A small runtime preamble of `__`-prefixed helpers carries these.

Binary expressions are fully parenthesized so emitted precedence always matches
the parsed AST — deterministic and never wrong, at the cost of a few parens.
"""
from . import nodes as N
from .capabilities import declared_capabilities

TYPE_MAP = {"text": "string", "whole": "number", "number": "number", "flag": "boolean", "nothing": "void"}
CONVERT_MAP = {"text": "String", "whole": "__whole", "number": "Number"}

# Infix binops emitted as `(l OP r)`. Function-shaped ones (==, in, div, …) are
# handled directly in _gen_expr since JS has no infix form for value-equality etc.
INFIX_MAP = {
    "mod": "%", "and": "&&", "or": "||", "is": "===", "is not": "!==",
    "+": "+", "-": "-", "*": "*", "/": "/", "%": "%",
    "<": "<", "<=": "<=", ">": ">", ">=": ">=",
}

_BUILTINS = {
    "count_of": lambda a: f"__len({a[0]})",
    "first_of": lambda a: f"{a[0]}[0]",
    "last_of": lambda a: f"__last({a[0]})",
    "copy_of": lambda a: f"{a[0]}.slice()",
    "chars_of": lambda a: f"Array.from({a[0]})",
    "take": lambda a: f"{a[1]}.slice(0, {a[0]})",
    "drop": lambda a: f"{a[1]}.slice({a[0]})",
    "item_at": lambda a: f"{a[1]}[{a[0]}]",
    "split": lambda a: f"{a[0]}.split({a[1]})",
    "sort": lambda a: f"__sort({a[0]})",
    "empty_map": lambda a: "{}",
    "range": lambda a: f"__range({a[0]}, {a[1]})",
}

# Emitted once at the top of every file. Deterministic and self-contained.
_PREAMBLE = '''function __eq(a: any, b: any): boolean {
  if (a === b) return true;
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) if (!__eq(a[i], b[i])) return false;
    return true;
  }
  if (a && b && typeof a === "object" && typeof b === "object") {
    const ka = Object.keys(a), kb = Object.keys(b);
    if (ka.length !== kb.length) return false;
    for (const k of ka) if (!__eq(a[k], b[k])) return false;
    return true;
  }
  return false;
}
function __in(x: any, c: any): boolean {
  if (Array.isArray(c) || typeof c === "string") return c.includes(x);
  return x in c;
}
function __len(c: any): number {
  return (typeof c === "string" || Array.isArray(c)) ? c.length : Object.keys(c).length;
}
function __range(a: number, b: number): number[] {
  const r: number[] = [];
  for (let i = a; i <= b; i++) r.push(i);
  return r;
}
function __sort<T>(c: T[]): T[] {
  return c.slice().sort((x: any, y: any) => (x < y ? -1 : x > y ? 1 : 0));
}
function __concat(a: any, b: any): any {
  return typeof a === "string" ? a + b : a.concat(b);
}
function __last(c: any): any { return c[c.length - 1]; }
function __whole(x: any): number { return Math.trunc(Number(x)); }'''


def _pad(indent):
    return "  " * indent


def _gen_type(t):
    if t is None:
        return "void"
    kind = t[0]
    if kind == "name":
        if t[1] in TYPE_MAP:
            return TYPE_MAP[t[1]]
        return t[1] if t[1] in _typenames else "any"
    if kind == "list":
        return f"{_gen_type(t[1])}[]"
    if kind == "map":
        return f"Record<{_gen_type(t[1])}, {_gen_type(t[2])}>"
    if kind == "optional":
        return f"{_gen_type(t[1])} | null"
    return "any"


def _uses_pedro_error(program):
    found = [False]

    def walk(stmts):
        for s in stmts:
            if isinstance(s, N.Fail):
                found[0] = True
            elif isinstance(s, N.Try):
                found[0] = True  # the generated `catch` re-checks `instanceof PedroError`
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


_subject_counter = [0]
_repeat_counter = [0]

# Record definitions for the file being generated (reset per generate() call), so
# RecordLit codegen can fill in defaulted fields — mirrors the Python backend.
_records = {}
_typenames = set()   # declared record + enum names (rendered by name, not `any`)


def _fresh_subject():
    _subject_counter[0] += 1
    return f"_subject{_subject_counter[0]}"


def _fresh_repeat():
    _repeat_counter[0] += 1
    return f"__r{_repeat_counter[0]}"


def generate(program, filename="<pedro>"):
    global _records, _typenames
    # Capabilities/adapters are Python-only for now (no JS reference adapter +
    # injection yet) — see WORKLOG. Fail loudly so the differential/corpus lanes
    # SKIP capability programs rather than emitting broken TypeScript.
    if declared_capabilities(program):
        raise NotImplementedError(
            "the TypeScript backend does not support capabilities yet (Python-only)")
    _subject_counter[0] = 0  # reset per call → deterministic temp names
    _repeat_counter[0] = 0
    records = [it for it in program.items if isinstance(it, N.Record)]
    enums = [it for it in program.items if isinstance(it, N.Enum)]
    _records = {r.name: r for r in records}
    _typenames = {r.name for r in records} | {en.name for en in enums}

    lines = [
        f"// Generated from {filename} by pedroc v0.1 (target: {program.target}). Do not edit by hand.",
        "",
        _PREAMBLE,
        "",
    ]
    for en in enums:
        lines.extend(_gen_enum(en))
        lines.append("")
    for rec in records:
        lines.extend(_gen_record(rec))
        lines.append("")
    if _uses_pedro_error(program):
        lines += ["class PedroError extends Error {}", ""]

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
        lines.append("(() => {")
        lines.extend(main)
        lines.append(f'  console.log("{base}: all expectations passed \\u2713");')
        lines.append("})();")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _gen_expect_item(item):
    kind = item[0]
    if kind == "given":
        return [f"  const {item[1]} = {_gen_expr(item[2])};"]
    if kind == "assert":
        expr = _gen_expr(item[1])
        msg = _js_string(f"expectation failed: {expr}")
        return [f"  if (!({expr})) throw new Error({msg});"]
    if kind == "fails":
        call = _gen_expr(item[1])
        msg = _js_string(item[2])
        return [
            "  {",
            "    let __threw = false;",
            f"    try {{ {call}; }} catch (e) {{ __threw = true;"
            f" if (!(e instanceof PedroError) || (e as PedroError).message !== {msg}) throw e; }}",
            f"    if (!__threw) throw new Error({_js_string('expected failure: ' + item[2])});",
            "  }",
        ]
    raise TypeError(f"unknown expect item: {item!r}")


def _gen_enum(en):
    # A const object + a string-literal union type — the erasable-TS stand-in for
    # `enum` (which Node's type-stripping can't run). The value and type share the
    # name (declaration merging); `Color.red` is the string "red" at runtime, which
    # matches the Python `str, Enum` backend so the two agree.
    entries = ", ".join(f'{v}: "{v}"' for v in en.variants)
    return [
        f"const {en.name} = {{ {entries} }} as const;",
        f"type {en.name} = typeof {en.name}[keyof typeof {en.name}];",
    ]


def _gen_record(rec):
    lines = [f"interface {rec.name} {{"]
    for (fname, ftype, _default) in rec.fields:
        # Fields are always required in the interface: RecordLit codegen fills in
        # defaulted fields explicitly, so every emitted literal is complete.
        lines.append(f"  {fname}: {_gen_type(ftype)};")
    lines.append("}")
    return lines


def _gen_task(task):
    params = []
    for (pname, ptype, default) in task.params:
        p = f"{pname}: {_gen_type(ptype)}"
        if default is not None:
            p += f" = {_gen_expr(default)}"
        params.append(p)
    header = f"function {task.name}({', '.join(params)}): {_gen_type(task.ret_type)} {{"
    return [header] + _gen_block(task.body, 1) + ["}"]


def _gen_block(stmts, indent):
    out = []
    for s in stmts:
        out.extend(_gen_stmt(s, indent))
    return out


def _emit_chain(branches, indent):
    """Emit a braced if / else-if / else chain from (cond_or_None, body) pairs.
    A None cond is the `else` (must be last); a lone None branch → unconditional."""
    pad = _pad(indent)
    out = []
    started = False
    for (cond, body) in branches:
        if cond is None:
            if not started:  # only an `otherwise`/`else` → unconditional block
                out.extend(_gen_block(body, indent))
            else:
                out.append(f"{pad}}} else {{")
                out.extend(_gen_block(body, indent + 1))
        else:
            out.append(f"{pad}if ({cond}) {{" if not started else f"{pad}}} else if ({cond}) {{")
            out.extend(_gen_block(body, indent + 1))
            started = True
    if started:
        out.append(f"{pad}}}")
    return out


def _gen_stmt(s, indent):
    pad = _pad(indent)
    if isinstance(s, N.Assign):
        kw = "let " if s.is_decl else ""
        return [f"{pad}{kw}{s.name} = {_gen_expr(s.value)};"]
    if isinstance(s, N.SetLValue):
        return [f"{pad}{_gen_expr(s.target)} = {_gen_expr(s.value)};"]
    if isinstance(s, N.AugAssign):
        return [f"{pad}{s.name} {s.op}= {_gen_expr(s.value)};"]
    if isinstance(s, N.Return):
        return [f"{pad}return;" if s.value is None else f"{pad}return {_gen_expr(s.value)};"]
    if isinstance(s, N.If):
        branches = list(s.branches)
        if s.orelse is not None:
            branches = branches + [(None, s.orelse)]
        return _emit_chain([(_gen_expr(c) if c is not None else None, b) for (c, b) in branches], indent)
    if isinstance(s, N.While):
        return [f"{pad}while ({_gen_expr(s.cond)}) {{"] + _gen_block(s.body, indent + 1) + [f"{pad}}}"]
    if isinstance(s, N.Repeat):
        v = _fresh_repeat()
        n = _gen_expr(s.count)
        head = f"{pad}for (let {v} = 0; {v} < {n}; {v}++) {{"
        return [head] + _gen_block(s.body, indent + 1) + [f"{pad}}}"]
    if isinstance(s, N.For):
        if s.index:
            head = f"{pad}for (const [{s.index}, {s.var}] of {_gen_expr(s.iterable)}.entries()) {{"
        else:
            head = f"{pad}for (const {s.var} of {_gen_expr(s.iterable)}) {{"
        return [head] + _gen_block(s.body, indent + 1) + [f"{pad}}}"]
    if isinstance(s, N.Add):
        return [f"{pad}{_gen_expr(s.target)}.push({_gen_expr(s.value)});"]
    if isinstance(s, N.Swap):
        t, i, j = _gen_expr(s.target), _gen_expr(s.i), _gen_expr(s.j)
        return [f"{pad}[{t}[{i}], {t}[{j}]] = [{t}[{j}], {t}[{i}]];"]
    if isinstance(s, N.Match):
        tmp = _fresh_subject()
        out = [f"{pad}const {tmp} = {_gen_expr(s.subject)};"]
        branches = []
        for (value, body) in s.cases:
            cond = None if value is None else f"__eq({tmp}, {_gen_expr(value)})"
            branches.append((cond, body))
        out.extend(_emit_chain(branches, indent))
        return out
    if isinstance(s, N.Try):
        pad_in = _pad(indent + 1)
        out = [f"{pad}try {{"]
        out.extend(_gen_block(s.body, indent + 1))
        out.append(f"{pad}}} catch (_pedro_err) {{")
        out.append(f"{pad_in}if (!(_pedro_err instanceof PedroError)) throw _pedro_err;")
        out.append(f"{pad_in}const {s.err_name} = (_pedro_err as PedroError).message;")
        out.extend(_gen_block(s.handler, indent + 1))
        out.append(f"{pad}}}")
        return out
    if isinstance(s, N.Fail):
        return [f"{pad}throw new PedroError({_gen_expr(s.message)});"]
    if isinstance(s, N.ExprStmt):
        return [f"{pad}{_gen_expr(s.expr)};"]
    if isinstance(s, N.Todo):
        return [f"{pad}throw new Error({_js_string('unresolved Pedro hole: ' + s.message)});"]
    raise TypeError(f"unknown statement node: {s!r}")


def _js_string(value):
    """A plain double-quoted JS string literal (no interpolation)."""
    out = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return '"' + out + '"'


def _gen_str(value):
    """A Pedro string literal. `{x}` → template `${x}`; `\\{` → literal `{`."""
    if "{" in value or "}" in value:
        out = []
        i = 0
        while i < len(value):
            c = value[i]
            if c == "\\" and i + 1 < len(value) and value[i + 1] in "{}":
                out.append(value[i + 1])
                i += 2
                continue
            if c == "`":
                out.append("\\`")
            elif c == "\\":
                out.append("\\\\")
            elif c == "{":
                out.append("${")
            else:
                out.append(c)
            i += 1
        return "`" + "".join(out) + "`"
    return _js_string(value)


def _gen_interpolation(parts):
    """A `Str` with structured interpolation → a JS template literal, with each
    hole's expression re-generated through codegen (so `div` floors, etc.)."""
    out = []
    for kind, val in parts:
        if kind == "text":
            # Literal text: escape backslash and backtick; `${` would start an
            # interpolation, so escape a literal `$` that precedes a `{`.
            esc = val.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
            out.append(esc)
        else:
            out.append("${" + _gen_expr(val) + "}")
    return "`" + "".join(out) + "`"


def _gen_expr(e):
    if isinstance(e, N.Num):
        return e.value
    if isinstance(e, N.Str):
        if e.parts is not None:
            return _gen_interpolation(e.parts)
        return _gen_str(e.value)
    if isinstance(e, N.Bool):
        return "true" if e.value else "false"
    if isinstance(e, N.Name):
        return "null" if e.value == "None" else e.value
    if isinstance(e, N.Call):
        return f"{e.func}({', '.join(_gen_expr(a) for a in e.args)})"
    if isinstance(e, N.Attr):
        return f"{_gen_expr(e.obj)}.{e.field}"
    if isinstance(e, N.Index):
        return f"{_gen_expr(e.obj)}[{_gen_expr(e.index)}]"
    if isinstance(e, N.BinOp):
        l, r = _gen_expr(e.left), _gen_expr(e.right)
        op = e.op
        if op == "==":
            return f"__eq({l}, {r})"
        if op == "!=":
            return f"!__eq({l}, {r})"
        if op == "div":
            return f"Math.floor({l} / {r})"
        if op == "followed_by":
            return f"__concat({l}, {r})"
        if op == "in":
            return f"__in({l}, {r})"
        if op == "not in":
            return f"!__in({l}, {r})"
        return f"({l} {INFIX_MAP[op]} {r})"
    if isinstance(e, N.Unary):
        return f"(!{_gen_expr(e.operand)})" if e.op == "not" else f"(-{_gen_expr(e.operand)})"
    if isinstance(e, N.ListLit):
        return f"[{', '.join(_gen_expr(i) for i in e.items)}]"
    if isinstance(e, N.MapLit):
        return "{" + ", ".join(f"[{_gen_expr(k)}]: {_gen_expr(v)}" for k, v in e.pairs) + "}"
    if isinstance(e, N.RecordLit):
        given = {fn: fv for fn, fv in e.fields}
        rec = _records[e.type_name]
        parts = []
        for (fname, _ftype, default) in rec.fields:
            if fname in given:
                parts.append(f"{fname}: {_gen_expr(given[fname])}")
            elif default is not None:
                parts.append(f"{fname}: {_gen_expr(default)}")
        return "{ " + ", ".join(parts) + " }"
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
        var = e.var
        flt = f".filter(({var}: any) => {_gen_expr(e.cond)})" if e.cond is not None else ""
        if e.kind == "filter":
            return f"{coll}{flt}"
        if e.kind == "collect":
            return f"{coll}{flt}.map(({var}: any) => {elem})"
        if e.kind == "count":
            return f"{coll}{flt}.length"
        if e.kind == "sum":
            return f"{coll}{flt}.reduce((__acc: any, {var}: any) => __acc + ({elem}), 0)"
        if e.kind == "find":
            return f"({coll}.find(({var}: any) => {_gen_expr(e.cond)}) ?? null)"
        raise TypeError(f"unknown comprehension kind: {e.kind!r}")
    raise TypeError(f"unknown expr node: {e!r}")
