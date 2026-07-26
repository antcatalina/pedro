# Pedro

**A small, human-readable language for intent. Claude writes it from your plain-English request; a real compiler (`pedroc`) turns it into the programming language of your choice.**

> **Status:** v0.1. `pedroc` deterministically compiles the scalar/list/map subset — the entire [cookbook](docs/cookbook.md) (22 algorithms) — to Python. Design rationale: [docs/design-for-llms.md](docs/design-for-llms.md). Progress log: [WORKLOG.md](WORKLOG.md).

Pedro is the **verifiable intermediate language between natural-language intent and executable code.** You (or Claude) write clear, keyworded pseudocode and tag a target (`target: python`, …); `pedroc` compiles it to idiomatic code. The design splits one job into two:

- **plain English → Pedro** is fuzzy and creative — that's **Claude's** job (the *authoring layer*).
- **Pedro → code** is exact and mechanical — that's **`pedroc`'s** job (a real, deterministic compiler; **no LLM in the pipeline**).

Putting the LLM where fuzziness is a feature and a real compiler where correctness is non-negotiable is what makes Pedro reliable — and what makes it a good language *for* LLMs: the model emits Pedro, runs `pedroc check`, and self-corrects from structured feedback.

```
   plain English  ─▶  Claude   ─▶  your_app.pedro  ─▶  pedroc   ─▶  your_app.py
   (what you want)   (authoring)   (verifiable IR)    (compiler)   (or .ts, .go, …)
                                          │
                                     expect blocks ─▶ run ─▶ pass / fail  (self-correction)
```

---

## Why Pedro?

- **Write intent once, target any language.** The same `.pedro` source can compile to Python today and TypeScript tomorrow — you change one line.
- **Readable by humans and Claude alike.** A non-programmer can follow a Pedro file; Claude can compile it. Both read the same source of truth.
- **Reproducible, reviewable, versionable.** A `.pedro` file is a stable artifact you can diff, review, and re-compile — unlike a one-off prompt.
- **Leans on Claude's strengths.** Instead of forcing a rigid grammar the model must never trip on, Pedro gives Claude clear structure and an explicit contract, and lets it do what it's good at: turning clear intent into idiomatic code.

---

## Hello, Pedro

```pedro
target: python

task greet(name: text) returns text:
    return "Hello, {name}!"
```

Compiles to:

```python
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

---

## A worked example — one source, two languages

`examples/order_total.pedro`:

```pedro
target: python 3.11

record LineItem:
    name: text
    price: number
    quantity: whole

task order_total(items: list of LineItem, discount_percent: number) returns number:
    let subtotal = 0
    for each item in items:
        increase subtotal by item.price * item.quantity

    when subtotal is greater than 100:
        # free-shipping tier gets an extra 5% off
        increase discount_percent by 5

    let discount = subtotal * discount_percent / 100
    return subtotal - discount

expect:
    order_total([ { name: "pen",  price: 2.5, quantity: 4 } ], 0)  == 10
    order_total([ { name: "desk", price: 120, quantity: 1 } ], 10) == 102
```

Compiled with `target: python 3.11`:

```python
# Generated from order_total.pedro by Pedro v0.1 — target: python 3.11. Do not edit by hand.
from dataclasses import dataclass


@dataclass
class LineItem:
    name: str
    price: float
    quantity: int


def order_total(items: list[LineItem], discount_percent: float) -> float:
    subtotal = 0.0
    for item in items:
        subtotal += item.price * item.quantity

    if subtotal > 100:
        # free-shipping tier gets an extra 5% off
        discount_percent += 5

    discount = subtotal * discount_percent / 100
    return subtotal - discount
```

The *same source* compiled with `target: typescript`:

```typescript
// Generated from order_total.pedro by Pedro v0.1 — target: typescript. Do not edit by hand.
interface LineItem {
  name: string;
  price: number;
  quantity: number;
}

function orderTotal(items: LineItem[], discountPercent: number): number {
  let subtotal = 0;
  for (const item of items) {
    subtotal += item.price * item.quantity;
  }

  if (subtotal > 100) {
    // free-shipping tier gets an extra 5% off
    discountPercent += 5;
  }

  const discount = (subtotal * discountPercent) / 100;
  return subtotal - discount;
}
```

Notice the compiler converts `snake_case` names to the target's convention (`orderTotal`, `discountPercent`) while preserving meaning.

> **What `pedroc` compiles today:** the scalar/list/map subset — the entire [cookbook](docs/cookbook.md) (22 algorithms across math, strings, search, sorting, recursion, DP, and graphs) to Python, each verified by running (`tools/regress.py`). The `record` type and the TypeScript output shown above are part of the language *design*, not yet in the compiler; [WORKLOG.md](WORKLOG.md) tracks coverage.

---

## Language guide

### Program directives

Every program starts with directives (before the first declaration):

- `target: <language> [version]` — **required.** e.g. `target: python 3.11`, `target: typescript`, `target: go`.
- `module: <name>` — optional module name.
- `use …` — capability and import declarations (see below).

### Comments

```pedro
# This is a line comment.
```

### Primitive types

| Pedro     | Meaning              | Python  | TypeScript |
|-----------|----------------------|---------|------------|
| `text`    | string               | `str`   | `string`   |
| `whole`   | integer              | `int`   | `number`   |
| `number`  | real / decimal       | `float` | `number`   |
| `flag`    | true / false         | `bool`  | `boolean`  |
| `nothing` | absence of a value   | `None`  | `null`     |

### Composite types

- `list of <T>` → `list[T]` / `T[]`
- `map of <K> to <V>` → `dict[K, V]` / `Record<K, V>`
- `optional <T>` (sugar: `<T>?`) → `T | None` / `T | null`
- `record` and `enum` (see below)

### Variables

```pedro
let total = 0        # declare
total = total + 5    # reassign  (or: `increase total by 5`)
```

Pedro identifiers are written in `snake_case`; the compiler converts them to the target language's convention.

### Literals

```pedro
"hello, {name}!"          # text, with {interpolation}; escape braces as \{ \}
42        3.14            # whole, number
true      false           # flag
[1, 2, 3]                 # list
{ id: "u1", age: 36 }     # map / record
nothing                   # the empty value
```

### Operators

- **Arithmetic:** `+ - * /`, `div` (whole-number division), `mod` (remainder)
- **Comparison:** `== != < <= > >=`
- **Logic:** `and`, `or`, `not`
- **Membership:** `x in items`, `x not in items`
- **Presence:** `x is present`, `x is empty`, `x is nothing`

### Readable forms

Many constructs have a plain-English form that compiles **identically** to its symbolic form — write whichever reads better in context:

| Readable form            | Same as        | Meaning                                   |
|--------------------------|----------------|-------------------------------------------|
| `increase x by n`        | `x = x + n`    | add in place                              |
| `decrease x by n`        | `x = x - n`    | subtract in place                         |
| `set x to v`             | `x = v`        | reassign a variable                       |
| `a is b`                 | `a == b`       | equals                                    |
| `a is not b`             | `a != b`       | not equal                                 |
| `a is greater than b`    | `a > b`        |                                           |
| `a is less than b`       | `a < b`        |                                           |
| `a is at least b`        | `a >= b`       |                                           |
| `a is at most b`         | `a <= b`       |                                           |
| `value as text`          | `str(value)`   | convert (also `as whole`, `as number`)    |

Because each form has a single canonical meaning, readability costs nothing in determinism: `increase total by 1` and `total = total + 1` compile to the same code.

### Tasks (functions)

A task declares its return type after `returns`:

```pedro
task discount(price: number, percent: number = 0) returns number:
    return price - price * percent / 100
```

Parameters may have defaults. Return a value with `return <expr>` (or a bare `return`). A task with no `returns` clause returns `nothing` and needn't return a value.

### Records and enums

```pedro
record User:
    id: text
    email: text
    age: whole = 0        # field default

enum Status:
    active
    suspended
    closed
```

Construct a record with a typed map literal, and reference enum values by name:

```pedro
let u = User { id: "u1", email: "a@b.c" }
let s = Status.active
```

### Conditionals

```pedro
when score is at least 90:
    return "A"
when score is at least 80:     # additional branch, like else-if
    return "B"
otherwise:
    return "C"
```

A **contiguous** run of `when` (with an optional final `otherwise`) at the same indentation is **one decision**: the first true branch runs and the rest are skipped. A lone `when` with nothing after it is a simple `if`.

### Loops

```pedro
for each item in items:
    ...

for each index, item in items:   # with 0-based position
    ...

repeat 3 times:
    ...

while remaining is greater than 0:
    ...
```

`stop` exits the nearest loop (break); `skip` jumps to the next iteration (continue).

### Pattern matching

```pedro
match status:
    case Status.active:
        return "ok"
    case Status.suspended:
        return "locked"
    case otherwise:
        return "unknown"
```

### Errors

```pedro
fail with "invalid email"        # raise an idiomatic error with this message

try:
    let data = http get "https://api.example.com/things"
on failure as err:
    fail with "could not reach the API: {err}"
```

### Collection operations

Readable expressions that compile to the target's idioms (comprehensions, filters, LINQ, …):

```pedro
find one user in users where user.email is email      # first match, or nothing
filter user in users where user.age is at least 18    # list of matches
count user in users where user.active                 # a whole number
collect user.email for each user in users             # map / comprehension → list
sort users by created_at descending
sum of item.price for each item in cart
first of items        last of items
```

A fuller set of list, map, text, and range operations — used throughout the cookbook — is documented in [`docs/cookbook.md`](docs/cookbook.md).

### Capabilities — talking to the outside world

Pedro programs are **pure by default.** Anything with side effects must be unlocked with a capability. This keeps dependencies explicit and the generated code predictable and testable.

```pedro
use capability database
use capability http
use capability email
use capability files
use capability time
use capability crypto
use capability random
```

Capabilities provide verbs:

| Capability | Verbs |
|------------|-------|
| `database` | `find one … in <table>`, `insert into <table> { … }` (returns id), `update <table> set { … } where …`, `delete from <table> where …` |
| `http`     | `http get "<url>"`, `http post "<url>" with <body>` |
| `email`    | `send email to <address> with subject "<s>" body "<b>"` |
| `files`    | `read file "<path>"`, `write <text> to file "<path>"` |
| `time`     | `now`, `today` |
| `crypto`   | `hash <text>`, `verify <text> against <hash>` |
| `random`   | `random whole from <a> to <b>` |

Capability calls compile to a small, pluggable **adapter layer** (one per project) so generated code stays clean and unit-testable, and so the outside world is easy to mock in tests.

### Modules

```pedro
use "lib/money.pedro"                   # import a file's tasks, records, enums
use round_cents from "lib/money.pedro"  # import selectively
```

### Escape hatch — raw target code

For the rare thing Pedro can't express, drop in literal target-language code:

```pedro
raw python:
    result = some_native_library.do_it()
end raw
```

Raw blocks are tagged by language and only emitted when the compile target matches. You may supply several for different targets; variables in scope are shared with the block.

### Verification

State expected behavior. The compiler must produce code that satisfies it, and emits these as tests when the target has a standard test framework.

```pedro
expect:
    given users is empty
    order_total([ { name: "pen", price: 2.5, quantity: 4 } ], 0) == 10
    sign_up("not-an-email", "x") fails with "invalid email"
```

### Known predicates

A small standard library of readable predicates the compiler implements consistently:

- `<text> is a valid email`
- `<text> is a valid url`
- `<x> is empty` / `is present` / `is nothing`
- `<whole> is even` / `is odd`
- `<a> is divisible by <b>`

---

## The compiler contract

> **Note:** now that `pedroc` is a real compiler, this contract has split in two.
> Rules about idiomatic output, canonical translation, and determinism are
> **`pedroc` guarantees**; rules about resolving ambiguity and not inventing
> capabilities are **authoring-layer guidelines** for Claude writing Pedro (see
> [docs/design-for-llms.md](docs/design-for-llms.md)). The rules below describe the
> intended end-to-end behavior.

This is the part that makes Pedro reliable. When a `.pedro` file is compiled, the toolchain **must** honor these rules:

1. **The spec is normative.** `docs/SPEC.md` (and this README) define the language. Compile to match it — don't guess.
2. **Emit idiomatic target code.** Follow the target language's conventions: naming (`snake_case` for Python, `camelCase` for TS, etc.), standard library, and formatting. Convert Pedro identifiers to the target convention while preserving meaning.
3. **Translate construct-by-construct** using the canonical mappings in the spec. Don't restructure or "improve" the logic.
4. **No undeclared powers.** Only use capabilities the program declares with `use capability`. If code needs one that isn't declared, stop and emit `# PEDRO-ERROR: capability <x> not declared` — never invent APIs or import libraries silently.
5. **Resolve ambiguity conservatively.** If a line has one obviously-simplest correct reading, take it and add a `# pedro-note: …` comment. If it's genuinely unclear, emit `# PEDRO-AMBIGUITY: …` and ask the author rather than guessing.
6. **Satisfy every `expect` block.** Generated code must pass all stated expectations; emit them as unit tests when the target has a standard test framework.
7. **Avoid name collisions.** If a capability adapter or import would collide with a user identifier, rename the import (e.g. import the email capability as `mailer`) — never the user's names.
8. **Stamp the output.** Begin each generated file with:
   `Generated from <file>.pedro by Pedro v0.1 — target: <target>. Do not edit by hand.`
9. **Be deterministic.** The same source + same spec version should produce structurally identical output (formatting aside). Don't add logging, caching, comments, or features that weren't written.

---

## Using Pedro today

`pedroc` is a real compiler — run it from the terminal (Python 3.11+, no dependencies):

```
# compile Pedro to Python
PYTHONPATH=. python -m pedroc build examples/cookbook/numbers.pedro -o build/numbers.py

# check it: compile, run its expect blocks, report per-assertion pass/fail
PYTHONPATH=. python -m pedroc check examples/cookbook/numbers.pedro --json
```

`check` is the oracle for the authoring loop: emit Pedro → `check` → read the JSON (`errors`, `holes`, and failing `expectations` with `got X, expected Y`) → fix. The **authoring layer** — turning a plain-English request into Pedro and driving that loop — is the Claude Code skill in `skills/write-pedro/`; the compact spec it reads is [docs/language-card.md](docs/language-card.md).

**Coverage today:** the whole cookbook (scalars, lists, maps, control flow — including `match`/`case` and `try`/`on failure as err` — recursion, and the collection operations). `record`/`enum` types and capabilities are designed (see the language guide) but not yet in the compiler, so `match` currently switches over plain values rather than enum variants — see [WORKLOG.md](WORKLOG.md).

---

## Repository layout

```
pedro/
├── README.md              # overview + language guide
├── CLAUDE.md              # standing guidance for Claude / automated agents
├── WORKLOG.md             # dated change log + next steps
├── pedroc/                # the real compiler: lexer, parser, codegen, check, CLI
├── docs/
│   ├── design-for-llms.md # why Pedro is shaped this way (the strategy)
│   ├── language-card.md   # compact in-context spec for the authoring LLM
│   ├── cookbook.md        # 22 algorithms, all compiled + checked by pedroc
│   └── SPEC.md            # normative spec                            (planned)
├── examples/
│   ├── math.pedro         # integer algorithms
│   ├── cookbook/          # the 22 cookbook algorithms as .pedro (regression corpus)
│   ├── order_total.pedro  # uses records       (language-designed; not yet compiled)
│   └── signup.pedro       # uses capabilities   (language-designed; not yet compiled)
├── skills/write-pedro/    # the Claude Code authoring skill (NL -> Pedro)
└── tools/regress.py       # compiles + checks the whole corpus
```

## Working on Pedro (humans and agents)

Repo-specific conventions and guardrails for anyone — or any Claude agent — making changes live in **[`CLAUDE.md`](CLAUDE.md)**; read it first. Automated agents run on the shared **`agent/dev`** branch and follow the prioritized roadmap in [`WORKLOG.md`](WORKLOG.md); their work is reviewed and merged to `master`.

## Roadmap

Live status and next steps live in [WORKLOG.md](WORKLOG.md). In brief:

- **Done** — the language design; a real deterministic compiler (`pedroc`) for the scalar/list/map subset → Python; the `pedroc check` loop, typed holes, and structured diagnostics; the [cookbook](docs/cookbook.md) (22 algorithms) as a passing regression suite (`tools/regress.py`).
- **Next** — `record` types; capabilities + the adapter layer (unlocks "auditable by construction"); a TypeScript backend; sandboxing `check`; then `docs/SPEC.md`.

## Design principles

1. **The spec is the compiler.** Docs precision beats syntax cleverness.
2. **Determinism over cleverness.** Fewer ways to say a thing means fewer ways to get it wrong.
3. **Explicit over implicit.** Types and capabilities are declared, never conjured.
4. **Readable first.** A non-programmer should be able to follow a Pedro file.
5. **Always an escape hatch.** You're never blocked by the language.
6. **Verify by example.** `expect` blocks turn intent into a checkable contract.

## FAQ

**Is the output really deterministic?** Yes for `pedroc` — the same source yields byte-identical output every run; it's an ordinary compiler. The probabilistic step is *authoring* (English → Pedro, done by Claude), which is exactly why the `pedroc check` loop and `expect` blocks exist: to catch and correct authoring mistakes against a real oracle.

**Why not just prompt Claude to write the code directly?** Pedro gives you a stable, reviewable, version-controllable source of truth that's shorter than code, target-language-independent, and re-compilable — instead of a one-off prompt whose output you can't diff or reproduce.

**Do I need to fine-tune Claude?** No. Pedro is taught entirely in-context via the spec.

**Which languages can it target?** `pedroc` emits **Python** today; TypeScript is the next backend (the AST is target-agnostic, so retargeting is a codegen module, not a rewrite). The design supports any language a backend is written for.

**Can Claude read Pedro as well as write it?** Yes — Pedro is designed to be equally clear to humans and to Claude, so you can also hand Claude a `.pedro` file and ask it to explain or extend the program.

---

*Pedro is an experiment in treating Claude as a programmable compiler. Ideas and contributions welcome.*
