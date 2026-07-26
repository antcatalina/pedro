"""Recursive-descent parser: tokens -> AST.

Covers the cookbook subset: tasks; whole/number/text/flag/list/map types;
let/set/reassign, increase/decrease, return, when/otherwise, while, repeat,
for-each, add, swap, fail, todo; arithmetic, readable comparisons, membership,
`followed by`, calls, indexing, list/map literals, conversions, and the
keyword-led collection operations (`count of`, `item at .. in ..`,
`numbers from .. to ..`, filter/collect/sum/count/find, ...).
"""
from .errors import PedroSyntaxError
from . import nodes as N


class Parser:
    def __init__(self, tokens, filename="<pedro>"):
        self.toks = tokens
        self.i = 0
        self.filename = filename

    # --- token helpers ---
    def _cur(self):
        return self.toks[self.i]

    def _type(self):
        return self.toks[self.i][0]

    def _val(self):
        return self.toks[self.i][1]

    def _line(self):
        return self.toks[self.i][2]

    def _peek(self, n=1):
        return self.toks[self.i + n]

    def _advance(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def _is(self, ttype, val=None):
        t = self.toks[self.i]
        return t[0] == ttype and (val is None or t[1] == val)

    def _is_name(self, val):
        return self._is("NAME", val)

    def _expect(self, ttype, val=None):
        t = self.toks[self.i]
        if t[0] != ttype or (val is not None and t[1] != val):
            want = repr(val) if val is not None else ttype
            found = repr(t[1]) if t[1] != "" else t[0]
            hint = None
            if val == ":":
                hint = "a block header ends with ':' followed by an indented body"
            elif val == "returns":
                hint = "declare a task's result type after ')': `task f(...) returns <type>:`"
            raise PedroSyntaxError(t[2], f"expected {want}, found {found}", code="unexpected-token", hint=hint)
        return self._advance()

    def _skip_newlines(self):
        while self._type() == "NEWLINE":
            self._advance()

    # --- top level ---
    def parse(self):
        self._skip_newlines()
        target = self._parse_directives()
        items = []
        self._skip_newlines()
        while self._type() != "EOF":
            if self._is_name("task"):
                items.append(self._parse_task())
            elif self._is_name("expect"):
                items.append(self._parse_expect())
            else:
                t = self._cur()
                raise PedroSyntaxError(t[2], f"expected 'task' or 'expect', found {t[1]!r}")
            self._skip_newlines()
        return N.Program(target=target, items=items)

    def _parse_directives(self):
        self._expect("NAME", "target")
        self._expect("OP", ":")
        lang = self._expect("NAME")[1]
        if self._type() == "NUMBER":
            self._advance()  # optional version, currently informational
        self._expect("NEWLINE")
        return lang

    def _parse_type(self):
        if self._is_name("list"):
            self._advance()
            self._expect("NAME", "of")
            return ("list", self._parse_type())
        if self._is_name("map"):
            self._advance()
            self._expect("NAME", "of")
            k = self._parse_type()
            self._expect("NAME", "to")
            v = self._parse_type()
            return ("map", k, v)
        if self._is_name("optional"):
            self._advance()
            return ("optional", self._parse_type())
        return ("name", self._expect("NAME")[1])

    # --- declarations ---
    def _parse_task(self):
        self._expect("NAME", "task")
        name = self._expect("NAME")[1]
        self._expect("OP", "(")
        params = []
        if not self._is("OP", ")"):
            params.append(self._parse_param())
            while self._is("OP", ","):
                self._advance()
                params.append(self._parse_param())
        self._expect("OP", ")")
        self._expect("NAME", "returns")
        ret_type = self._parse_type()
        self._expect("OP", ":")
        self._expect("NEWLINE")
        body = self._parse_block()
        return N.Task(name=name, params=params, ret_type=ret_type, body=body)

    def _parse_param(self):
        pname = self._expect("NAME")[1]
        self._expect("OP", ":")
        ptype = self._parse_type()
        default = None
        if self._is("OP", "="):
            self._advance()
            default = self._parse_expr()
        return (pname, ptype, default)

    def _parse_expect(self):
        self._expect("NAME", "expect")
        self._expect("OP", ":")
        self._expect("NEWLINE")
        self._expect("INDENT")
        items = []
        while self._type() != "DEDENT":
            if self._is_name("given"):
                self._advance()
                name = self._expect("NAME")[1]
                self._expect("OP", "=")
                items.append(("given", name, self._parse_expr()))
            else:
                expr = self._parse_expr()
                if self._is_name("fails"):
                    self._advance()
                    self._expect("NAME", "with")
                    msg = self._expect("STRING")[1]
                    items.append(("fails", expr, msg))
                else:
                    items.append(("assert", expr))
            self._expect("NEWLINE")
        self._expect("DEDENT")
        return N.Expect(items=items)

    # --- statements ---
    def _parse_block(self):
        self._expect("INDENT")
        stmts = []
        while self._type() != "DEDENT":
            stmts.append(self._parse_statement())
        self._expect("DEDENT")
        return stmts

    def _parse_statement(self):
        if self._type() == "NAME":
            kw = self._val()
            if kw == "let":
                self._advance()
                name = self._expect("NAME")[1]
                self._expect("OP", "=")
                value = self._parse_expr()
                self._expect("NEWLINE")
                return N.Assign(name=name, value=value)
            if kw == "set":
                self._advance()
                name = self._expect("NAME")[1]
                target = N.Name(value=name)
                if self._is("OP", "["):
                    self._advance()
                    idx = self._parse_expr()
                    self._expect("OP", "]")
                    target = N.Index(obj=N.Name(value=name), index=idx)
                self._expect("NAME", "to")
                value = self._parse_expr()
                self._expect("NEWLINE")
                if isinstance(target, N.Name):
                    return N.Assign(name=name, value=value)
                return N.SetLValue(target=target, value=value)
            if kw == "return":
                self._advance()
                value = None
                if self._type() != "NEWLINE":
                    value = self._parse_expr()
                self._expect("NEWLINE")
                return N.Return(value=value)
            if kw in ("increase", "decrease"):
                self._advance()
                name = self._expect("NAME")[1]
                self._expect("NAME", "by")
                value = self._parse_expr()
                self._expect("NEWLINE")
                return N.AugAssign(name=name, op="+" if kw == "increase" else "-", value=value)
            if kw == "for":
                self._advance()
                self._expect("NAME", "each")
                first = self._expect("NAME")[1]
                index = None
                var = first
                if self._is("OP", ","):
                    self._advance()
                    var = self._expect("NAME")[1]
                    index = first
                self._expect("NAME", "in")
                iterable = self._parse_expr()
                self._expect("OP", ":")
                self._expect("NEWLINE")
                body = self._parse_block()
                return N.For(var=var, index=index, iterable=iterable, body=body)
            if kw == "add":
                self._advance()
                value = self._parse_add()
                self._expect("NAME", "to")
                target = self._parse_add()
                self._expect("NEWLINE")
                return N.Add(value=value, target=target)
            if kw == "swap":
                self._advance()
                self._expect("NAME", "items")
                self._expect("NAME", "at")
                i = self._parse_add()
                self._expect("NAME", "and")
                j = self._parse_add()
                self._expect("NAME", "in")
                target = self._parse_add()
                self._expect("NEWLINE")
                return N.Swap(i=i, j=j, target=target)
            if kw == "fail":
                self._advance()
                self._expect("NAME", "with")
                msg = self._parse_expr()
                self._expect("NEWLINE")
                return N.Fail(message=msg)
            if kw == "todo":
                line = self._line()
                self._advance()
                msg = self._expect("STRING")[1]
                self._expect("NEWLINE")
                return N.Todo(message=msg, line=line)
            if kw == "when":
                return self._parse_if_chain()
            if kw == "match":
                return self._parse_match()
            if kw == "try":
                return self._parse_try()
            if kw == "while":
                self._advance()
                cond = self._parse_expr()
                self._expect("OP", ":")
                self._expect("NEWLINE")
                body = self._parse_block()
                return N.While(cond=cond, body=body)
            if kw == "repeat":
                self._advance()
                count = self._parse_expr()
                self._expect("NAME", "times")
                self._expect("OP", ":")
                self._expect("NEWLINE")
                body = self._parse_block()
                return N.Repeat(count=count, body=body)
            # reassignment: NAME = expr
            nxt = self._peek()
            if nxt[0] == "OP" and nxt[1] == "=":
                name = self._advance()[1]
                self._expect("OP", "=")
                value = self._parse_expr()
                self._expect("NEWLINE")
                return N.Assign(name=name, value=value)
        expr = self._parse_expr()
        self._expect("NEWLINE")
        return N.ExprStmt(expr=expr)

    def _parse_if_chain(self):
        branches = []
        while self._is_name("when"):
            self._advance()
            cond = self._parse_expr()
            self._expect("OP", ":")
            self._expect("NEWLINE")
            body = self._parse_block()
            branches.append((cond, body))
        orelse = None
        if self._is_name("otherwise"):
            self._advance()
            self._expect("OP", ":")
            self._expect("NEWLINE")
            orelse = self._parse_block()
        return N.If(branches=branches, orelse=orelse)

    def _parse_match(self):
        self._advance()  # 'match'
        subject = self._parse_expr()
        self._expect("OP", ":")
        self._expect("NEWLINE")
        self._expect("INDENT")
        cases = []
        saw_otherwise = False
        while self._is_name("case"):
            if saw_otherwise:
                raise PedroSyntaxError(
                    self._line(), "no case may follow 'case otherwise'",
                    code="case-after-otherwise",
                    hint="'case otherwise:' is the default and must be the last arm",
                )
            self._advance()  # 'case'
            if self._is_name("otherwise"):
                self._advance()
                value = None
                saw_otherwise = True
            else:
                value = self._parse_expr()
            self._expect("OP", ":")
            self._expect("NEWLINE")
            cases.append((value, self._parse_block()))
        if not cases:
            raise PedroSyntaxError(
                self._line(), "a 'match' needs at least one 'case'",
                code="empty-match", hint="add `case <value>:` arms under the match",
            )
        self._expect("DEDENT")
        return N.Match(subject=subject, cases=cases)

    def _parse_try(self):
        self._advance()  # 'try'
        self._expect("OP", ":")
        self._expect("NEWLINE")
        body = self._parse_block()
        self._expect("NAME", "on")
        self._expect("NAME", "failure")
        self._expect("NAME", "as")
        err_name = self._expect("NAME")[1]
        self._expect("OP", ":")
        self._expect("NEWLINE")
        handler = self._parse_block()
        return N.Try(body=body, err_name=err_name, handler=handler)

    # --- expressions (precedence climbing) ---
    def _parse_expr(self):
        return self._parse_or()

    def _parse_or(self):
        left = self._parse_and()
        while self._is_name("or"):
            self._advance()
            left = N.BinOp(op="or", left=left, right=self._parse_and())
        return left

    def _parse_and(self):
        left = self._parse_not()
        while self._is_name("and"):
            self._advance()
            left = N.BinOp(op="and", left=left, right=self._parse_not())
        return left

    def _parse_not(self):
        if self._is_name("not"):
            self._advance()
            return N.Unary(op="not", operand=self._parse_not())
        return self._parse_comparison()

    def _parse_comparison(self):
        left = self._parse_add()
        if self._is("OP") and self._val() in ("==", "!=", "<", ">", "<=", ">="):
            op = self._advance()[1]
            return N.BinOp(op=op, left=left, right=self._parse_add())
        if self._is_name("in"):
            self._advance()
            return N.BinOp(op="in", left=left, right=self._parse_add())
        if self._is_name("not") and self._peek()[0] == "NAME" and self._peek()[1] == "in":
            self._advance()
            self._advance()
            return N.BinOp(op="not in", left=left, right=self._parse_add())
        if self._is_name("is"):
            return self._parse_is(left)
        return left

    def _parse_is(self, left):
        self._advance()  # 'is'
        negate = False
        if self._is_name("not"):
            self._advance()
            negate = True
        if self._is_name("empty"):
            self._advance()
            op = "!=" if negate else "=="
            return N.BinOp(op=op, left=N.Builtin(name="count_of", args=[left]), right=N.Num(value="0"))
        if self._is_name("present"):
            self._advance()
            return N.BinOp(op="is" if negate else "is not", left=left, right=N.Name(value="None"))
        if self._is_name("nothing"):
            self._advance()
            return N.BinOp(op="is not" if negate else "is", left=left, right=N.Name(value="None"))
        if self._is_name("divisible"):
            self._advance()
            self._expect("NAME", "by")
            node = N.BinOp(op="==", left=N.BinOp(op="%", left=left, right=self._parse_add()), right=N.Num(value="0"))
            return N.Unary(op="not", operand=node) if negate else node
        if self._is_name("at"):
            self._advance()
            w = self._expect("NAME")[1]
            if w == "least":
                op = ">="
            elif w == "most":
                op = "<="
            else:
                raise PedroSyntaxError(self._line(), f"expected 'least' or 'most' after 'is at', found {w!r}")
            if negate:
                op = "<" if op == ">=" else ">"
            return N.BinOp(op=op, left=left, right=self._parse_add())
        if self._is_name("greater"):
            self._advance()
            self._expect("NAME", "than")
            return N.BinOp(op="<=" if negate else ">", left=left, right=self._parse_add())
        if self._is_name("less"):
            self._advance()
            self._expect("NAME", "than")
            return N.BinOp(op=">=" if negate else "<", left=left, right=self._parse_add())
        return N.BinOp(op="!=" if negate else "==", left=left, right=self._parse_add())

    def _parse_add(self):
        left = self._parse_mul()
        while True:
            if self._is("OP") and self._val() in ("+", "-"):
                op = self._advance()[1]
                left = N.BinOp(op=op, left=left, right=self._parse_mul())
            elif self._is_name("followed"):
                self._advance()
                self._expect("NAME", "by")
                left = N.BinOp(op="+", left=left, right=self._parse_mul())
            else:
                return left

    def _parse_mul(self):
        left = self._parse_unary()
        while (self._is("OP") and self._val() in ("*", "/")) or self._is_name("mod") or self._is_name("div"):
            op = self._advance()[1]
            left = N.BinOp(op=op, left=left, right=self._parse_unary())
        return left

    def _parse_unary(self):
        if self._is("OP", "-"):
            self._advance()
            return N.Unary(op="-", operand=self._parse_unary())
        return self._parse_primary()

    # keyword-led operations dispatched from primary position
    def _parse_primary(self):
        t = self._cur()
        if t[0] == "NAME":
            op = self._parse_operation()
            if op is not None:
                return op

        if t[0] == "NUMBER":
            self._advance()
            return self._parse_postfix(N.Num(value=t[1]))
        if t[0] == "STRING":
            self._advance()
            return self._parse_postfix(N.Str(value=t[1]))
        if t[0] == "NAME":
            val = t[1]
            self._advance()
            if val == "true":
                node = N.Bool(value=True)
            elif val == "false":
                node = N.Bool(value=False)
            elif self._is("OP", "("):
                node = N.Call(func=val, args=self._parse_args())
            else:
                node = N.Name(value=val)
            return self._parse_postfix(node)
        if t[0] == "OP" and t[1] == "(":
            self._advance()
            e = self._parse_expr()
            self._expect("OP", ")")
            return self._parse_postfix(e)
        if t[0] == "OP" and t[1] == "[":
            self._advance()
            items = []
            if not self._is("OP", "]"):
                items.append(self._parse_expr())
                while self._is("OP", ","):
                    self._advance()
                    items.append(self._parse_expr())
            self._expect("OP", "]")
            return self._parse_postfix(N.ListLit(items=items))
        if t[0] == "OP" and t[1] == "{":
            self._advance()
            pairs = []
            if not self._is("OP", "}"):
                pairs.append(self._parse_pair())
                while self._is("OP", ","):
                    self._advance()
                    pairs.append(self._parse_pair())
            self._expect("OP", "}")
            return self._parse_postfix(N.MapLit(pairs=pairs))
        raise PedroSyntaxError(t[2], f"unexpected token {t[1]!r}")

    def _parse_pair(self):
        key = self._parse_add()
        self._expect("OP", ":")
        value = self._parse_expr()
        return (key, value)

    def _parse_postfix(self, node):
        while True:
            if self._is("OP", "."):
                self._advance()
                node = N.Attr(obj=node, field=self._expect("NAME")[1])
            elif self._is("OP", "["):
                self._advance()
                idx = self._parse_expr()
                self._expect("OP", "]")
                node = N.Index(obj=node, index=idx)
            elif self._is_name("as"):
                self._advance()
                node = N.Convert(expr=node, to=self._expect("NAME")[1])
            else:
                return node

    def _parse_operation(self):
        """Keyword-led collection/text/range operations. Returns None if the
        current NAME is not one (so it's treated as an identifier)."""
        kw = self._val()
        if kw == "count":
            if self._peek()[1] == "of":
                self._advance()
                self._advance()
                return N.Builtin(name="count_of", args=[self._parse_add()])
            if self._peek()[1] not in ("in",) and self._peek()[0] == "NAME":
                # count <var> in <coll> where <cond>
                self._advance()
                var = self._expect("NAME")[1]
                self._expect("NAME", "in")
                coll = self._parse_add()
                self._expect("NAME", "where")
                return N.Comp(kind="count", elem=N.Name(value=var), var=var, coll=coll, cond=self._parse_expr())
            return None
        if kw == "first" and self._peek()[1] == "of":
            self._advance()
            self._advance()
            return N.Builtin(name="first_of", args=[self._parse_add()])
        if kw == "last" and self._peek()[1] == "of":
            self._advance()
            self._advance()
            return N.Builtin(name="last_of", args=[self._parse_add()])
        if kw == "copy" and self._peek()[1] == "of":
            self._advance()
            self._advance()
            return N.Builtin(name="copy_of", args=[self._parse_add()])
        if kw == "characters" and self._peek()[1] == "of":
            self._advance()
            self._advance()
            return N.Builtin(name="chars_of", args=[self._parse_add()])
        if kw == "take":
            self._advance()
            n = self._parse_add()
            self._expect("NAME", "from")
            return N.Builtin(name="take", args=[n, self._parse_add()])
        if kw == "drop":
            self._advance()
            n = self._parse_add()
            self._expect("NAME", "from")
            return N.Builtin(name="drop", args=[n, self._parse_add()])
        if kw == "item" and self._peek()[1] == "at":
            self._advance()
            self._advance()
            i = self._parse_add()
            self._expect("NAME", "in")
            return N.Builtin(name="item_at", args=[i, self._parse_add()])
        if kw == "split":
            self._advance()
            s = self._parse_add()
            self._expect("NAME", "by")
            return N.Builtin(name="split", args=[s, self._parse_add()])
        if kw == "sort":
            self._advance()
            return N.Builtin(name="sort", args=[self._parse_unary()])
        if kw == "numbers" and self._peek()[1] == "from":
            self._advance()
            self._advance()
            a = self._parse_add()
            self._expect("NAME", "to")
            return N.Builtin(name="range", args=[a, self._parse_add()])
        if kw == "empty" and self._peek()[1] == "map":
            self._advance()
            self._advance()
            self._expect("NAME", "of")
            self._parse_type()
            self._expect("NAME", "to")
            self._parse_type()
            return N.Builtin(name="empty_map", args=[])
        if kw == "filter":
            self._advance()
            var = self._expect("NAME")[1]
            self._expect("NAME", "in")
            coll = self._parse_add()
            self._expect("NAME", "where")
            return N.Comp(kind="filter", elem=N.Name(value=var), var=var, coll=coll, cond=self._parse_expr())
        if kw == "collect":
            self._advance()
            elem = self._parse_add()
            self._expect("NAME", "for")
            self._expect("NAME", "each")
            var = self._expect("NAME")[1]
            self._expect("NAME", "in")
            coll = self._parse_add()
            cond = None
            if self._is_name("where"):
                self._advance()
                cond = self._parse_expr()
            return N.Comp(kind="collect", elem=elem, var=var, coll=coll, cond=cond)
        if kw == "sum" and self._peek()[1] == "of":
            self._advance()
            self._advance()
            elem = self._parse_add()
            self._expect("NAME", "for")
            self._expect("NAME", "each")
            var = self._expect("NAME")[1]
            self._expect("NAME", "in")
            coll = self._parse_add()
            cond = None
            if self._is_name("where"):
                self._advance()
                cond = self._parse_expr()
            return N.Comp(kind="sum", elem=elem, var=var, coll=coll, cond=cond)
        if kw == "find" and self._peek()[1] == "one":
            self._advance()
            self._advance()
            var = self._expect("NAME")[1]
            self._expect("NAME", "in")
            coll = self._parse_add()
            self._expect("NAME", "where")
            return N.Comp(kind="find", elem=N.Name(value=var), var=var, coll=coll, cond=self._parse_expr())
        return None

    def _parse_args(self):
        self._expect("OP", "(")
        args = []
        if not self._is("OP", ")"):
            args.append(self._parse_expr())
            while self._is("OP", ","):
                self._advance()
                args.append(self._parse_expr())
        self._expect("OP", ")")
        return args
