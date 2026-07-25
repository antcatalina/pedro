"""Recursive-descent parser: tokens -> AST.

Grammar (v0.1 subset):
  program     := 'target' ':' NAME [NUMBER] (task | expect)*
  task        := 'task' NAME '(' params? ')' 'returns' type ':' block
  expect      := 'expect' ':' INDENT (comparison NEWLINE)+ DEDENT
  statement   := let | set | return | increase | decrease
               | if_chain | while | repeat | reassign | expr
  expr        := or_ ('or' or_)* ... down to primary
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
        return self._expect("NAME")[1]

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
        assertions = []
        while self._type() != "DEDENT":
            assertions.append(self._parse_expr())
            self._expect("NEWLINE")
        self._expect("DEDENT")
        return N.Expect(assertions=assertions)

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
                self._expect("NAME", "to")
                value = self._parse_expr()
                self._expect("NEWLINE")
                return N.Assign(name=name, value=value)
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
            if kw == "todo":
                line = self._line()
                self._advance()
                msg = self._expect("STRING")[1]
                self._expect("NEWLINE")
                return N.Todo(message=msg, line=line)
            if kw == "when":
                return self._parse_if_chain()
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
            nxt = self.toks[self.i + 1]
            if nxt[0] == "OP" and nxt[1] == "=":
                name = self._advance()[1]
                self._expect("OP", "=")
                value = self._parse_expr()
                self._expect("NEWLINE")
                return N.Assign(name=name, value=value)
        # fallback: bare expression statement (e.g. a call)
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
        if self._is_name("is"):
            self._advance()
            if self._is_name("not"):
                self._advance()
                op = "!="
            elif self._is_name("at"):
                self._advance()
                w = self._expect("NAME")[1]
                if w == "least":
                    op = ">="
                elif w == "most":
                    op = "<="
                else:
                    raise PedroSyntaxError(self._line(), f"expected 'least' or 'most' after 'is at', found {w!r}")
            elif self._is_name("greater"):
                self._advance()
                self._expect("NAME", "than")
                op = ">"
            elif self._is_name("less"):
                self._advance()
                self._expect("NAME", "than")
                op = "<"
            elif self._is_name("divisible"):
                self._advance()
                self._expect("NAME", "by")
                right = self._parse_add()
                return N.BinOp(op="==", left=N.BinOp(op="%", left=left, right=right), right=N.Num(value="0"))
            else:
                op = "=="
            return N.BinOp(op=op, left=left, right=self._parse_add())
        return left

    def _parse_add(self):
        left = self._parse_mul()
        while self._is("OP") and self._val() in ("+", "-"):
            op = self._advance()[1]
            left = N.BinOp(op=op, left=left, right=self._parse_mul())
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

    def _parse_primary(self):
        t = self._cur()
        if t[0] == "NUMBER":
            self._advance()
            return N.Num(value=t[1])
        if t[0] == "STRING":
            self._advance()
            return N.Str(value=t[1])
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
            while self._is("OP", "."):
                self._advance()
                node = N.Attr(obj=node, field=self._expect("NAME")[1])
            return node
        if t[0] == "OP" and t[1] == "(":
            self._advance()
            e = self._parse_expr()
            self._expect("OP", ")")
            return e
        raise PedroSyntaxError(t[2], f"unexpected token {t[1]!r}")

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
