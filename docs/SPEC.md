# Pedro Language Specification (v0.1)

**Normative.** This document defines the Pedro language as the `pedroc` compiler
actually implements it. It is reconciled against the source
(`pedroc/lexer.py`, `parser.py`, `nodes.py`, `annotate.py`, `capabilities.py`,
`codegen_python.py`, `codegen_ts.py`) and against the passing regression corpus
(`examples/**`, run by `tools/regress.py`). **Where any document — this spec,
[`README.md`](../README.md), [`docs/language-card.md`](language-card.md) — and the
compiler disagree, the compiler as exercised by the green corpus is authoritative,
and the document is a bug to be fixed.**

Companion documents:

- [`grammar.md`](grammar.md) — the formal EBNF (this spec references it for shape).
- [`language-card.md`](language-card.md) — the compact, in-context authoring card
  fed to an LLM. It is a *teaching subset* of this spec, not a competing source of
  truth.
- [`cookbook.md`](cookbook.md) — worked, compiled-and-checked examples.

Conventions in this document: **MUST/MUST NOT/MAY** carry their usual normative
force. "Emits" describes generated target code. Code shown as `Pedro` / `Python` /
`TypeScript` is illustrative of the exact translation the compiler performs.

---

## 1. Design invariants

These hold for every conforming implementation of `pedroc`:

1. **Two-stage pipeline.** Natural language → Pedro is the LLM's job and is
   fuzzy. Pedro → code is `pedroc`'s job and is exact. **There is no LLM in the
   Pedro → code pipeline.**
2. **Determinism.** The same source and the same compiler version MUST produce
   **byte-identical** output for a given target. No timestamps, no map/set
   ordering leaks, no randomness.
3. **Purity by default.** A program has no side effects unless it declares a
   capability (§8). Using an effectful verb without its `use capability`
   declaration is a compile error.
4. **Errors are prompts.** Every diagnostic carries a stable machine-readable
   `code`, a 1-based `line`/`col`, and (where useful) a `hint`, a `snippet` with a
   caret, and a nearest-match `suggestion` (§11).
5. **Cross-target agreement.** Every construct that both backends implement MUST
   behave identically at runtime; `pedroc check --targets python,typescript`
   verifies this per expectation (§10).

---

## 2. Lexical structure

Pedro source is UTF-8 text, tokenized line by line (`pedroc/lexer.py`).

- **Comments** run from an unquoted `#` to end of line. A `#` inside a `"…"`
  string is literal.
- **Identifiers** (`NAME`) match `(letter | "_") (letter | digit | "_")*`.
- **Numbers** (`NUMBER`) match `digit (digit | ".")*`. A `whole` literal has no
  `.`; a `number` literal has one.
- **Strings** (`STRING`) are `"…"`, single-line, with **no backslash escape
  sequences** — a `"` always closes the string. (Interpolation `{…}` and the
  literal-brace escapes `\{` `\}` are handled by the parser, §7.6.)
- **Operators** (`OP`): the two-char `==` `!=` `<=` `>=`, and the single
  characters `( ) [ ] { } + - * / < > = : , .`. **No other characters are
  legal outside strings** — notably there is no `?` token, so `optional T` has no
  `T?` shorthand.
- **Layout.** Indentation is significant. A deeper line emits `INDENT`; returning
  to a shallower level emits `DEDENT`(s); each logical line ends with `NEWLINE`.
  Indentation that matches no open level is `bad-indentation`. Blank and
  comment-only lines produce no tokens. Tabs and spaces are both counted as one
  indentation unit each; a file MUST NOT mix them within one indent step.

---

## 3. Program structure

```pedro
target: python            # required first directive

# top-level items, any order:
use capability <name>     # capability declarations (§8)
record <Name>: …          # data types (§5)
enum <Name>: …
table <name>: <Record>    # database table binding (§8)
task <name>(…) returns <T>: …
expect: …                 # checkable expectations (§9)
```

A program MUST begin with exactly one `target:` directive naming the backend
(`python` or `typescript`). An optional trailing version number is accepted and
currently ignored. After the directive, top-level items appear in any order.

Every generated file starts with a banner (§10.2) and MUST NOT be hand-edited.

---

## 4. Types

| Pedro | Meaning | Python | TypeScript |
|---|---|---|---|
| `text` | string | `str` | `string` |
| `whole` | integer | `int` | `number` |
| `number` | decimal / real | `float` | `number` |
| `flag` | boolean | `bool` | `boolean` |
| `nothing` | absence of a value | `None` | `void` |
| `list of <T>` | ordered list | `list[T]` | `T[]` |
| `map of <K> to <V>` | keyed map | `dict[K, V]` | `Record<K, V>` |
| `optional <T>` | `T` or absent | `T \| None` | `T \| null` |
| *record name* | a declared record | that `@dataclass` | that `interface` |
| *enum name* | a declared enum | that `str, Enum` | that const/union type |

`optional T` MUST be written in full — there is no `T?` shorthand.

---

## 5. Records and enums

```pedro
enum Priority:
    low
    medium
    high

record Ticket:
    title: text
    priority: Priority = Priority.medium    # optional field default
    done: flag = false
```

- A `record` MUST declare at least one field (`<name>: <type> [= <default>]`);
  otherwise `empty-record`. Fields are accessed with `.` (`t.title`).
- An `enum` MUST list at least one variant; otherwise `empty-enum`. A variant is
  referenced as `Name.variant` and **is the string `"variant"` at runtime on both
  backends** (Python via the `str, Enum` mixin, TypeScript via a const object), so
  `==` and `match`/`case` compare enum variants correctly across targets.

**Record literals are typed by context.** A `{ field: value, … }` literal
(bare-identifier keys) carries no type name in the source. The annotate pass
(`pedroc/annotate.py`) assigns its record type from the nearest expected type — a
call argument's parameter type, a `return` type, an enclosing record field, or a
`list of <Record>` / `map` element type. With no expected type, it falls back to
the unique record whose field set matches. Failures are `ambiguous-record`,
`unknown-field`, or `missing-field`. Omitted fields that have defaults are filled
in at codegen time, so both backends emit the identical, complete field set.

A collection binds its element record type **explicitly via the type annotation**
(`items: list of LineItem`), never by naming convention.

### Translation

| Pedro | Python | TypeScript |
|---|---|---|
| `enum E:` with variants `a b` | `class E(str, Enum): a = "a"; b = "b"` | `const E = { a: "a", b: "b" } as const;` + `type E = …` |
| `record R:` with fields | `@dataclass`\n`class R: …` | `interface R { … }` |
| `{ f: v }` (record literal, type `R`) | `R(f=v, …)` | `{ f: v, … }` |

---

## 6. Statements

| Pedro | Python | TypeScript |
|---|---|---|
| `let x = e` | `x = e` | `let x = e;` |
| `x = e` / `set x to e` | `x = e` | `x = e;` |
| `set x[i] to e` | `x[i] = e` | `x[i] = e;` |
| `increase x by e` | `x += e` | `x += e;` |
| `decrease x by e` | `x -= e` | `x -= e;` |
| `return e` / `return` | `return e` / `return` | `return e;` / `return;` |
| `when c:` … `otherwise:` | `if`/`elif`/`else` | braced `if`/`else if`/`else` |
| `while c:` | `while c:` | `while (c) { … }` |
| `repeat n times:` | `for _ in range(n):` | `for (let __r = 0; __r < n; __r++) { … }` |
| `for each x in xs:` | `for x in xs:` | `for (const x of xs) { … }` |
| `for each i, x in xs:` | `for i, x in enumerate(xs):` | `for (const [i, x] of xs.entries()) { … }` |
| `add v to xs` | `xs.append(v)` | `xs.push(v);` |
| `swap items at i and j in xs` | `xs[i], xs[j] = xs[j], xs[i]` | `[xs[i], xs[j]] = [xs[j], xs[i]];` |
| `match s:` `case v:` … | `_subject = s`; `if`/`elif _subject == v` | `const _subject = s;` `if (__eq(_subject, v))` … |
| `try:` … `on failure as e:` … | `try:` / `except PedroError as _err: e = str(_err)` | `try { … } catch (_err) { … const e = _err.message; … }` |
| `fail with m` | `raise PedroError(m)` | `throw new PedroError(m);` |
| `todo "m"` | `raise NotImplementedError("unresolved Pedro hole: m")` | `throw new Error("unresolved Pedro hole: m");` |

Notes:

- **`let` vs reassignment.** `let x = e` is a *declaration* (`is_decl=True`), which
  matters only for TypeScript (`let x = …` vs a bare `x = …` reassignment). `set x
  to e` and `x = e` are reassignments. Python ignores the distinction.
- **`set` targets.** `set` accepts a name or a single indexed element
  (`set x[i] to e`); it does not target attributes.
- **`when` chain semantics.** A contiguous run of `when` branches (with an optional
  final `otherwise`) at the same indentation is **one decision**: the first true
  branch runs, the rest are skipped. A lone `when` is a simple `if`.
- **`match` semantics.** The subject is compared by **equality** against each
  `case` value (Python `==`, TypeScript `__eq`); `case otherwise` is the default
  and MUST be the last arm (`case-after-otherwise` otherwise). A `match` MUST have
  at least one `case` (`empty-match`). Cases match plain values *or* `Enum.variant`
  values.
- **`try`/`on failure`.** Only Pedro failures (`fail with`, raised as
  `PedroError`) are caught; the handler binds `<err>` to the failure message
  (a `text`). A `try:` without an `on failure as <err>:` handler is
  `missing-on-failure`. On TypeScript, a non-`PedroError` exception is re-thrown.
- **`todo`** compiles to a runtime raise, and is *also* reported statically by
  `check` as a `holes[]` entry — an unresolved hole means `ok: false`.
- **No `break`/`continue`.** There are no loop `stop`/`skip` keywords; restructure
  the loop (e.g. with `find one … where …`).

---

## 7. Expressions

### 7.1 Precedence

Lowest-binding to highest: `or` → `and` → `not` → comparison → additive
(`+ - followed by`) → multiplicative (`* / mod div`) → unary `-` → primary
(atoms, calls, keyword-led operations, and postfixes `.field` / `[i]` / `as T`).
The comparison level is **non-associative** (at most one comparison between two
additive operands). All binary operators are emitted **fully parenthesized**, so
the generated precedence always matches the parsed AST.

### 7.2 Arithmetic and concatenation

| Pedro | Python | TypeScript |
|---|---|---|
| `a + b`, `a - b`, `a * b`, `a / b` | same | `(a + b)`, … |
| `a mod b` | `(a % b)` | `(a % b)` |
| `a div b` | `(a // b)` | `Math.floor(a / b)` |
| `a followed by b` | `(a + b)` | `__concat(a, b)` |
| `-a` | `(-a)` | `(-a)` |

`div` is whole-number (floor) division and `followed by` is list-or-string
concatenation on both backends — the TypeScript helpers exist precisely to keep
these value-correct (JS `/` doesn't floor; JS `+` on arrays stringifies).

### 7.3 Comparison and predicates

| Pedro | Python | TypeScript |
|---|---|---|
| `a is b` / `a == b` | `(a == b)` | `__eq(a, b)` |
| `a is not b` / `a != b` | `(a != b)` | `!__eq(a, b)` |
| `a is greater than b` / `a > b` | `(a > b)` | `(a > b)` |
| `a is less than b` / `a < b` | `(a < b)` | `(a < b)` |
| `a is at least b` / `a >= b` | `(a >= b)` | `(a >= b)` |
| `a is at most b` / `a <= b` | `(a <= b)` | `(a <= b)` |
| `a is divisible by b` | `((a % b) == 0)` | `__eq((a % b), 0)` |
| `x is empty` | `(len(x) == 0)` | `__eq(__len(x), 0)` |
| `x is present` | `(x is not None)` | `(x !== null)` |
| `x is nothing` | `(x is None)` | `(x === null)` |

Every `is <predicate>` form accepts an inserted `not` that negates it
(`is not empty`, `is not divisible by`, `is not greater than` → `<=`, etc.). A
bare `is <expr>` / `is not <expr>` is equality / inequality. Value-equality
(`==`, `is`) is **structural** — deep equality on lists/maps/records on both
backends (Python native, TypeScript via `__eq`).

### 7.4 Logic and membership

| Pedro | Python | TypeScript |
|---|---|---|
| `not a` | `(not a)` | `(!a)` |
| `a and b` | `(a and b)` | `(a && b)` |
| `a or b` | `(a or b)` | `(a \|\| b)` |
| `x in xs` | `(x in xs)` | `__in(x, xs)` |
| `x not in xs` | `(x not in xs)` | `!__in(x, xs)` |

`in` tests list/string element membership and map-key membership.

### 7.5 Conversions

| Pedro | Python | TypeScript |
|---|---|---|
| `e as text` | `str(e)` | `String(e)` |
| `e as whole` | `int(e)` | `__whole(e)` (`Math.trunc(Number(e))`) |
| `e as number` | `float(e)` | `Number(e)` |

### 7.6 Literals and interpolation

| Pedro | Python | TypeScript |
|---|---|---|
| `42`, `3.14` | `42`, `3.14` | `42`, `3.14` |
| `true` / `false` | `True` / `False` | `true` / `false` |
| `"plain"` | `"plain"` | `"plain"` |
| `"avg {total div count}"` | `f"avg {total // count}"` | `` `avg ${Math.floor(total / count)}` `` |
| `[a, b]` | `[a, b]` | `[a, b]` |
| `{ "k": v }` (map) | `{"k": v}` | `{["k"]: v}` |
| `{ f: v }` (record) | `Type(f=v)` (§5) | `{ f: v }` (§5) |

A string is a **record vs map** disambiguator only for `{ … }`: bare-identifier
keys → record literal, string/expression keys (or empty) → map. In interpolation,
each `{expr}` hole is a full Pedro expression re-generated through the target's
own codegen (so operators translate); `\{` and `\}` are literal braces.

There is **no bare `nothing` value literal**: `nothing` is a *type* keyword (§4)
and part of the `is nothing` / `is present` predicates (§7.3) — writing `return
nothing` or `let x = nothing` is an `undefined-name` error. An absent value is
produced by operations that can miss, e.g. `find one v in xs where c` (which
yields `None` / `null` when nothing matches), and tested with `is nothing` /
`is present`.

### 7.7 Collection and range operations

| Pedro | Python | TypeScript |
|---|---|---|
| `count of x` | `len(x)` | `__len(x)` |
| `first of x` | `x[0]` | `x[0]` |
| `last of x` | `x[-1]` | `__last(x)` |
| `copy of x` | `list(x)` | `x.slice()` |
| `characters of x` | `list(x)` | `Array.from(x)` |
| `take n from x` | `x[:n]` | `x.slice(0, n)` |
| `drop n from x` | `x[n:]` | `x.slice(n)` |
| `item at i in x` | `x[i]` | `x[i]` |
| `split x by sep` | `x.split(sep)` | `x.split(sep)` |
| `sort x` | `sorted(x)` | `__sort(x)` |
| `numbers from a to b` | `list(range(a, b + 1))` | `__range(a, b)` |
| `empty map of K to V` | `{}` | `{}` |

`sort` is ascending natural order only (no `by <key>` / `descending`).
`numbers from a to b` is the **inclusive** range `[a, b]`.

### 7.8 Comprehensions

| Pedro | Python | TypeScript |
|---|---|---|
| `filter v in x where c` | `[v for v in x if c]` | `x.filter(v => c)` |
| `collect e for each v in x [where c]` | `[e for v in x if c]` | `x[.filter(v=>c)].map(v => e)` |
| `count v in x where c` | `sum(1 for v in x if c)` | `x.filter(v => c).length` |
| `sum of e for each v in x [where c]` | `sum(e for v in x if c)` | `x[.filter].reduce((acc, v) => acc + (e), 0)` |
| `find one v in x where c` | `next((v for v in x if c), None)` | `(x.find(v => c) ?? null)` |

The binder `v` is lexically scoped to the comprehension's element/condition (not
to the iterated collection).

### 7.9 Calls

`f(a, b)` calls task `f`. Recursion is permitted. An unknown callee is
`unknown-task`; an unknown identifier is `undefined-name` (each with a
nearest-match `suggestion`).

---

## 8. Capabilities and effects

A program is pure until it declares `use capability <name>`. The set of
declarations is the program's auditable **blast radius**, reported by
`check --json` as `capabilities[]`. Using a verb whose capability is not declared
is `undeclared-capability`; an unknown capability name is `unknown-capability`.

**Declarable capabilities:** `database`, `http`, `email`, `files`, `time`,
`crypto`, `random`.

**Verbs implemented today** (on BOTH backends; the TypeScript backend emits the
same adapter calls against the reference `pedro_capabilities.ts`):

| Pedro | Capability | Python | TypeScript |
|---|---|---|---|
| `table t: Row` | database | `t = database.table("t", Row)` | `const t = database.table("t")` |
| `insert into t { … }` | database | `t.insert({ … })` → returns new id | `t.insert({ … })` |
| `update r in t set f to v` | database | `t.update(r, "f", v)` | `t.update(r, "f", v)` |
| `delete r from t` | database | `t.delete(r)` | `t.delete(r)` |
| `hash x` | crypto | `crypto.hash(x)` | `crypto.hash(x)` |
| `verify x against h` | crypto | `crypto.verify(x, h)` → `flag` | `crypto.verify(x, h)` |
| `send email to a with subject s body b` | email | `mailer.send(to=a, subject=s, body=b)` | `mailer.send(a, s, b)` |
| `given t is empty` (expect only) | database | `t.clear()` |

A `table` handle is iterable, so reads reuse the ordinary collection path
(`find one … in t`, `count of t`, `for each … in t`) with no new verb.

Capability calls compile through a swappable `pedro_capabilities` adapter module
(one adapter object per capability). `pedroc check` injects in-memory reference
adapters (`pedroc/adapters.py`), so effectful programs run with no real I/O. When
a default adapter name would collide with a user identifier (e.g. an `email`
parameter), the **import** is aliased (`email as mailer`) — never the user's name.

The declared surface also drives `pedroc permissions <file>.pedro
[--format claude-settings|json]`, which derives an agent-harness permission
manifest from exactly the declared capabilities.

---

## 9. The `expect` block and checking

An `expect:` block states checkable expectations that `pedroc check` runs against
the compiled program.

| Pedro | Meaning |
|---|---|
| `<flag expr>` | MUST evaluate `true` (e.g. `factorial(5) == 120`). |
| `<call> fails with "<msg>"` | The call MUST raise a `fail with` of exactly that message. |
| `given <name> = <expr>` | Bind a value visible to later expectations. |
| `given <table> is empty` | Reset a table before the expectations run (effectful test isolation). |
| `for all <name> from <a> to <b>: <flag>` | A **property**: the flag MUST hold for every integer in `[a, b]`. |

Property expectations are checked by **honest enumeration**: `check` binds
`<name>` to each integer in the inclusive range and evaluates the body; the first
value that is not `true` fails with `counterexample: <name>=<v>, got false`. This
is not a theorem prover, so ranges are bounded — a range wider than **10000**
values (`FORALL_CAP`) is refused as a failed expectation; `check --forall-cap N`
raises the cap.

Translation of expect items:

| Pedro | Python | TypeScript |
|---|---|---|
| `e` | `assert e` | `if (!(e)) throw new Error(…);` |
| `e fails with "m"` | `try: … except PedroError: assert str(e)=="m"` | `try/catch` on `PedroError.message` |
| `given x = e` | `x = e` | `const x = e;` |
| `given t is empty` | `t.clear()` | `t.clear();` |
| `for all n from a to b: e` | `for n in range(a, (b)+1): assert (e), "counterexample: …"` | counted `for` loop throwing on first counterexample |

`check --json` reports `ok` (no errors, no holes, all expectations passed),
`errors[]`, `holes[]`, `expectations[]` (with `passed` and `detail`),
`capabilities[]`, and — only on an abnormal run — `status` (`"timeout"` /
`"error"`). The JSON is compact: null/empty fields are omitted.

The generated program is run in a **sandboxed subprocess**
(`pedroc/_expect_runner.py`) with a wall-clock timeout, a POSIX `RLIMIT_CPU`
backstop, and a restricted environment, so a non-terminating or crashing program
is reported as a structured `status`, never a hang.

---

## 10. Targets, determinism, and tamper-evidence

### 10.1 Targets

`pedroc build <file>.pedro -o out.py [--target python|typescript]` emits runnable
code. Node v24+ strips TypeScript types at runtime, so the `.ts` output runs with
no build step. `pedroc check <file>.pedro --targets python,typescript` compiles
and runs each target's expect suite and reports whether all targets agree on every
expectation; a disagreement is a compiler bug and names which target lost which
expectation.

### 10.2 The banner

Every generated file's first line is a `Do not edit by hand` banner
(`pedroc/hashing.py`), which is a compiler contract:

```
# Generated from <file>.pedro by pedroc v0.1 (target: <target>) source-hash: <12-hex>. Do not edit by hand.
```

(`//` prefix for TypeScript.) The `source-hash` is 12 hex chars of SHA-256 of the
**source** bytes — not the output — so it stays as deterministic as codegen: same
source + compiler version → same hash → byte-identical file.

`pedroc verify <file>.pedro <output> [--json]` recomputes the hash and reports
**match** (hash + a fresh compile both agree), **stale** (source changed —
rebuild), **drift** (hash matches but the output was hand-edited), or
**no-banner**.

---

## 11. Diagnostics

Each diagnostic carries a stable `code`, a 1-based `line`/`col`, a `message`, and
often a `hint`, a `snippet` with a `^` caret, and a nearest-match `suggestion`.
The current codes:

`unexpected-token`, `expected-expression`, `unexpected-character`,
`unterminated-string`, `bad-indentation`, `empty-record`, `empty-enum`,
`empty-match`, `case-after-otherwise`, `missing-on-failure`, `unknown-keyword`,
`undefined-name`, `unknown-task`, `ambiguous-record`, `unknown-field`,
`missing-field`, `unknown-record`, `undeclared-capability`, `unknown-capability`,
`bad-interpolation`, `empty-interpolation`, `unterminated-interpolation`,
`codegen-error`.

---

## 12. Not yet implemented

Declared-but-not-yet-emitted or purely designed surface (see
[WORKLOG.md](../WORKLOG.md) for the prioritized roadmap). Programs MUST NOT rely
on these; write the signature plus an `expect:` block and leave a
`todo "<what's needed>"` in the body instead of faking it.

- **Capability verbs:** `http get`/`http post`; files `read file`/`write … to
  file`; time `now`/`today`; random `random whole from … to …`. (The implemented
  verbs — database `insert`/`update`/`delete`, email `send`, crypto `hash`/`verify`
  — emit on **both** backends.)
- **Language surface:** modules (`use "file.pedro"`), the `raw <lang>: … end raw`
  escape hatch, loop `stop`/`skip`, keyed/descending `sort`
  (`sort xs by key descending`), the `<T>?` optional shorthand, and the predicates
  `is a valid email` / `is a valid url` / `is even` / `is odd`.
