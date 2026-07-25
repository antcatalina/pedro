# Pedro

**A human-readable language you write, and Claude compiles into the programming language of your choice.**

> **Status:** v0.1 — draft. The language is *defined by this repository*; Claude reads it and acts as the compiler.

Pedro is a small, structured, easy-to-read language for describing **what a program should do**. You write your intent in clear, keyworded pseudocode, tag a target language (`target: python`, `target: typescript`, …), and Claude reads the Pedro spec plus your source and compiles it into idiomatic code in that language.

The idea that makes Pedro work: **the compiler is Claude, and this repository is the compiler's specification.** There is no separate binary to install (yet). Because Claude learns Pedro from the spec *in-context* every session, the spec has to be precise, example-dense, and written for Claude as its primary reader — which is exactly what this repo is built to be.

```
   your_app.pedro  ─┐
                     ├─▶  Claude  ──▶  your_app.py   (or .ts, .go, .java, …)
   docs/SPEC.md    ─┘   (compiler)
   (the language spec)
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

> **More examples:** [`docs/cookbook.md`](docs/cookbook.md) implements 22 classic algorithms in Pedro — math, strings, searching, sorting, recursion, dynamic programming, and graphs — each with an `expect` block, and every one machine-verified.

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

This is the part that makes Pedro reliable. When Claude compiles a `.pedro` file, it **must** follow these rules:

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

## Using Pedro with Claude today

There's no standalone compiler binary yet — **Claude is the compiler.** The workflow:

1. Keep `docs/SPEC.md` in your project (it's the normative contract).
2. Write your program, e.g. `app.pedro`, with a `target:` line.
3. Ask Claude: *"Compile `app.pedro` to its target, following `docs/SPEC.md`."*

To make this repeatable in Claude Code, we'll ship a **skill** (`skills/compile-pedro/`) that loads the spec and turns Claude into the Pedro compiler on demand. Later, a thin CLI (`pedroc build app.pedro`) can call the Claude API with the spec attached so builds run from the terminal.

---

## Repository layout

```
pedro/
├── README.md              # this file — overview + language guide
├── docs/
│   ├── cookbook.md        # 22 algorithms in Pedro, every one machine-verified
│   ├── SPEC.md            # normative spec / the compiler contract   (planned)
│   └── grammar.md         # formal grammar sketch                    (planned)
├── examples/
│   ├── order_total.pedro  # pure logic, compiled to Python & TypeScript
│   └── signup.pedro       # capabilities: database, email, crypto
├── skills/                # Claude Code skill that compiles Pedro    (planned)
└── pedroc/                # CLI compiler over the Claude API          (planned)
```

## Roadmap

- **v0.1 (now)** — Language design, this README, the algorithm cookbook, first examples.
- **v0.2** — `docs/SPEC.md`: the full normative spec with the canonical translation table for every construct.
- **v0.3** — Claude Code skill that compiles `.pedro` files on command.
- **v0.4** — A test harness that round-trips every example through the compiler and checks its `expect` blocks.
- **v0.5** — `pedroc` CLI wrapping the Claude API.
- **v1.0** — Stable syntax, multi-target coverage (Python, TypeScript, Go, Java, …), a documented adapter layer for capabilities.

## Design principles

1. **The spec is the compiler.** Docs precision beats syntax cleverness.
2. **Determinism over cleverness.** Fewer ways to say a thing means fewer ways to get it wrong.
3. **Explicit over implicit.** Types and capabilities are declared, never conjured.
4. **Readable first.** A non-programmer should be able to follow a Pedro file.
5. **Always an escape hatch.** You're never blocked by the language.
6. **Verify by example.** `expect` blocks turn intent into a checkable contract.

## FAQ

**Is the output really deterministic?** Not bit-for-bit guaranteed — Claude is a probabilistic compiler. But the contract, the structured syntax, and `expect` blocks push variance down hard and catch drift when it happens.

**Why not just prompt Claude to write the code directly?** Pedro gives you a stable, reviewable, version-controllable source of truth that's shorter than code, target-language-independent, and re-compilable — instead of a one-off prompt whose output you can't diff or reproduce.

**Do I need to fine-tune Claude?** No. Pedro is taught entirely in-context via the spec.

**Which languages can it target?** Any language Claude writes well — Python, TypeScript/JavaScript, Go, Java, C#, Ruby, Rust, and more. Start with one; the same source retargets.

**Can Claude read Pedro as well as write it?** Yes — Pedro is designed to be equally clear to humans and to Claude, so you can also hand Claude a `.pedro` file and ask it to explain or extend the program.

---

*Pedro is an experiment in treating Claude as a programmable compiler. Ideas and contributions welcome.*
