# Pedro Grammar (v0.1)

A formal-ish EBNF grammar for Pedro, **derived from the actual compiler**
(`pedroc/lexer.py` + `pedroc/parser.py`) and kept in sync with it. This is the
companion to [`SPEC.md`](SPEC.md), which gives the normative prose semantics and
the per-construct translation tables; here we describe only *shape* — what is a
well-formed program. Where this grammar and the compiler ever disagree, the
compiler (as exercised by the passing regression corpus) is the source of truth,
and this file is the bug.

## Notation

Standard EBNF:

- `=` defines a rule; rules are lower-case.
- `|` alternation, `[ x ]` optional (0 or 1), `{ x }` repetition (0 or more),
  `( … )` grouping.
- `"foo"` is a literal terminal (a keyword or operator token).
- `UPPERCASE` names are lexer tokens (see [Lexical grammar](#lexical-grammar)).
- `(* … *)` is a comment.

Pedro is **indentation-structured** like Python: the lexer turns indentation into
explicit `INDENT` / `DEDENT` / `NEWLINE` tokens, and the grammar below consumes
those tokens directly. A `block` is always one-or-more statements because the
lexer only emits an `INDENT` for a genuinely deeper line.

## Lexical grammar

The tokenizer (`pedroc/lexer.py`) is line-oriented. Each raw line has its
trailing `# comment` stripped (a `#` inside a `"…"` string does not start a
comment), leading indentation measured, and the remainder split into tokens.

```ebnf
NAME    = ( letter | "_" ) , { letter | digit | "_" } ;
NUMBER  = digit , { digit | "." } ;            (* e.g. 42, 3.14 *)
STRING  = '"' , { any-char-except-'"' } , '"' ; (* single line; no escape chars *)
OP      = "==" | "!=" | "<=" | ">="            (* two-char operators *)
        | "(" | ")" | "[" | "]" | "{" | "}"
        | "+" | "-" | "*" | "/" | "<" | ">" | "=" | ":" | "," | "." ;
```

- **Comments** run from an unquoted `#` to end of line.
- **Strings** are double-quoted and single-line; there are **no backslash escape
  sequences** at the lexical level (a `"` always closes the string). The only
  escapes are `\{` and `\}`, recognised later by the parser *inside* string
  interpolation to mean literal braces.
- The only characters the lexer accepts outside strings are letters, digits, `_`,
  whitespace, and the operator characters above. Anything else (`?`, `@`, `!`
  alone, `;`, …) is an `unexpected-character` error. In particular there is **no
  `?` token**, so an `optional T` type has no `T?` shorthand.
- **Layout tokens.** A line indented further than its parent emits one `INDENT`;
  returning to a shallower level emits one `DEDENT` per level closed; every
  non-blank logical line ends with a `NEWLINE`. Indentation that matches no
  enclosing level is a `bad-indentation` error. Blank and comment-only lines
  produce no tokens.

## Program

```ebnf
program    = { NEWLINE } , directive , { NEWLINE } ,
             { item , { NEWLINE } } , EOF ;

directive  = "target" , ":" , NAME , [ NUMBER ] , NEWLINE ;
             (* NAME is "python" or "typescript"; a NUMBER version is accepted
                but currently ignored *)

item       = task | record | enum | use | table | expect ;
```

Every program begins with exactly one `target:` directive, then a sequence of
top-level items in any order (tasks, type declarations, capability declarations,
table bindings, and `expect` blocks).

## Declarations

```ebnf
task    = "task" , NAME , "(" , [ param , { "," , param } ] , ")" ,
          "returns" , type , ":" , NEWLINE , block ;
param   = NAME , ":" , type , [ "=" , expr ] ;

record  = "record" , NAME , ":" , NEWLINE ,
          INDENT , field , { field } , DEDENT ;
field   = NAME , ":" , type , [ "=" , expr ] , NEWLINE ;

enum    = "enum" , NAME , ":" , NEWLINE ,
          INDENT , ( NAME , NEWLINE ) , { NAME , NEWLINE } , DEDENT ;

use     = "use" , "capability" , NAME , NEWLINE ;

table   = "table" , NAME , ":" , NAME , NEWLINE ;
          (* `table <name>: <RecordName>` — needs `use capability database` *)
```

A `record` must have at least one field and an `enum` at least one variant
(otherwise `empty-record` / `empty-enum`).

## Types

```ebnf
type    = "list" , "of" , type
        | "map" , "of" , type , "to" , type
        | "optional" , type
        | NAME ;                 (* a scalar (text/whole/number/flag/nothing)
                                    or a declared record/enum name *)
```

There is no postfix `?` optional shorthand — write `optional T` in full.

## The `expect` block

```ebnf
expect       = "expect" , ":" , NEWLINE ,
               INDENT , { expect_item , NEWLINE } , DEDENT ;

expect_item  = given
             | forall
             | assertion
             | fails ;

given        = "given" , NAME , ( "=" , expr | "is" , "empty" ) ;
forall       = "for" , "all" , NAME , "from" , add , "to" , add , ":" , expr ;
assertion    = expr ;                          (* a flag that must be true *)
fails        = expr , "fails" , "with" , STRING ;
```

## Statements

```ebnf
block       = INDENT , statement , { statement } , DEDENT ;

statement   = let | set | reassign | augassign | return
            | for_each | while_stmt | repeat_stmt
            | when_chain | match_stmt | try_stmt
            | add_stmt | swap_stmt | send_stmt
            | delete_stmt | update_stmt
            | fail_stmt | todo_stmt | expr_stmt ;

let         = "let" , NAME , "=" , expr , NEWLINE ;
set         = "set" , NAME , [ "[" , expr , "]" ] , "to" , expr , NEWLINE ;
reassign    = NAME , "=" , expr , NEWLINE ;
augassign   = ( "increase" | "decrease" ) , NAME , "by" , expr , NEWLINE ;
return      = "return" , [ expr ] , NEWLINE ;

for_each    = "for" , "each" , NAME , [ "," , NAME ] , "in" , expr , ":" ,
              NEWLINE , block ;
              (* one name: the item. two names: `index, item` (index is 0-based) *)
while_stmt  = "while" , expr , ":" , NEWLINE , block ;
repeat_stmt = "repeat" , expr , "times" , ":" , NEWLINE , block ;

when_chain  = when_branch , { when_branch } ,
              [ "otherwise" , ":" , NEWLINE , block ] ;
when_branch = "when" , expr , ":" , NEWLINE , block ;

match_stmt  = "match" , expr , ":" , NEWLINE ,
              INDENT , case , { case } , DEDENT ;
case        = "case" , ( "otherwise" | expr ) , ":" , NEWLINE , block ;
              (* `case otherwise` is the default and must be the last arm *)

try_stmt    = "try" , ":" , NEWLINE , block ,
              "on" , "failure" , "as" , NAME , ":" , NEWLINE , block ;

add_stmt    = "add" , add , "to" , add , NEWLINE ;
swap_stmt   = "swap" , "items" , "at" , add , "and" , add , "in" , add , NEWLINE ;
send_stmt   = "send" , "email" , "to" , expr ,
              "with" , "subject" , expr , "body" , expr , NEWLINE ;
              (* capability: email *)
delete_stmt = "delete" , add , "from" , add , NEWLINE ;   (* capability: database *)
              (* removes the row VALUE (e.g. a `find one`) from the table *)
update_stmt = "update" , add , "in" , add , "set" , NAME , "to" , expr , NEWLINE ;
              (* capability: database — writes one field of the row VALUE *)

fail_stmt   = "fail" , "with" , expr , NEWLINE ;
todo_stmt   = "todo" , STRING , NEWLINE ;
expr_stmt   = expr , NEWLINE ;                 (* e.g. a bare call `f(x)` *)
```

## Expressions

Precedence, lowest to highest binding, exactly mirrors the parser's climbing
functions. Each level is left-associative except `not`/unary `-` (prefix) and the
comparison level (non-associative — at most one comparison per `add` operand).

```ebnf
expr        = or_expr ;
or_expr     = and_expr , { "or" , and_expr } ;
and_expr    = not_expr , { "and" , not_expr } ;
not_expr    = "not" , not_expr | comparison ;

comparison  = add , [ comp_tail ] ;
comp_tail   = comp_op , add
            | "in" , add
            | "not" , "in" , add
            | is_clause ;
comp_op     = "==" | "!=" | "<" | ">" | "<=" | ">=" ;

is_clause   = "is" , [ "not" ] , is_rhs ;
is_rhs      = "empty"
            | "present"
            | "nothing"
            | "divisible" , "by" , add
            | "at" , ( "least" | "most" ) , add
            | "greater" , "than" , add
            | "less" , "than" , add
            | add ;                            (* bare add ⇒ equality (is / is not) *)

add         = mul , { ( "+" | "-" ) , mul | "followed" , "by" , mul } ;
mul         = unary , { ( "*" | "/" | "mod" | "div" ) , unary } ;
unary       = "-" , unary | primary ;

primary     = operation | atom ;
              (* a keyword-led operation binds as a primary; an atom then takes
                 a chain of postfixes *)

atom        = NUMBER
            | STRING
            | "true" | "false"
            | call
            | NAME
            | "(" , expr , ")"
            | list_lit
            | record_or_map ,
              { postfix } ;
postfix     = "." , NAME
            | "[" , expr , "]"
            | "as" , NAME ;                    (* conversion: as text|whole|number *)

call        = NAME , "(" , [ expr , { "," , expr } ] , ")" ;

list_lit    = "[" , [ expr , { "," , expr } ] , "]" ;

record_or_map = "{" , ( record_body | map_body ) , "}" ;
record_body = field_pair , { "," , field_pair } ;  (* chosen when the first token
                                                       is NAME followed by ":" *)
field_pair  = NAME , ":" , expr ;
map_body    = [ pair , { "," , pair } ] ;
pair        = add , ":" , expr ;                   (* string / expression keys *)
```

A `{ … }` literal is a **record literal** when it opens with `NAME :`
(bare-identifier key) and a **map literal** otherwise (string/expression keys, or
empty). This split is purely syntactic — no type inference is needed to classify
it.

### Keyword-led operations

These are dispatched from primary position when the current `NAME` matches; if it
does not form a complete operation the `NAME` is treated as an ordinary
identifier.

```ebnf
operation =
      "count" , "of" , add
    | "count" , NAME , "in" , add , "where" , expr      (* count v in xs where c *)
    | "first" , "of" , add
    | "last" , "of" , add
    | "copy" , "of" , add
    | "characters" , "of" , add
    | "take" , add , "from" , add
    | "drop" , add , "from" , add
    | "item" , "at" , add , "in" , add
    | "split" , add , "by" , add
    | "sort" , unary
    | "numbers" , "from" , add , "to" , add
    | "empty" , "map" , "of" , type , "to" , type
    | "filter" , NAME , "in" , add , "where" , expr
    | "collect" , add , "for" , "each" , NAME , "in" , add , [ "where" , expr ]
    | "sum" , "of" , add , "for" , "each" , NAME , "in" , add , [ "where" , expr ]
    | "find" , "one" , NAME , "in" , add , "where" , expr
    | "insert" , "into" , add , expr                    (* capability: database *)
    | "hash" , unary                                    (* capability: crypto *)
    | "verify" , add , "against" , add ;                (* capability: crypto *)
```

### String interpolation

A `STRING` may contain `{ … }` holes. After lexing, the parser re-scans the
literal: each `{expr}` hole's text is tokenized and parsed as a standalone
`expr` (so each backend can re-emit it in its own syntax), while `\{` and `\}`
denote literal braces. An unterminated or empty hole is a
`unterminated-interpolation` / `empty-interpolation` / `bad-interpolation`
error.

## Reserved words

The following words are keywords in at least one position and should not be used
as ordinary identifiers where they would be ambiguous:

`target`, `task`, `returns`, `record`, `enum`, `use`, `capability`, `table`,
`expect`, `given`, `for`, `all`, `each`, `from`, `to`, `in`, `where`, `of`,
`let`, `set`, `to`, `by`, `increase`, `decrease`, `return`, `when`, `otherwise`,
`match`, `case`, `try`, `on`, `failure`, `as`, `while`, `repeat`, `times`,
`add`, `swap`, `items`, `at`, `and`, `send`, `email`, `subject`, `body`,
`with`, `fail`, `todo`, `not`, `or`, `is`, `empty`, `present`, `nothing`,
`divisible`, `least`, `most`, `greater`, `less`, `than`, `followed`, `mod`,
`div`, `true`, `false`, `list`, `map`, `optional`, `count`, `first`, `last`,
`copy`, `characters`, `take`, `drop`, `item`, `split`, `sort`, `numbers`,
`filter`, `collect`, `sum`, `find`, `one`, `insert`, `into`, `update`, `delete`,
`hash`, `verify`, `against`, `fails`.

The capability verbs `hash`, `insert`, `update`, `delete`, `send`, and `verify` are
reserved in their verb positions — don't name a variable after them.
