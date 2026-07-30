# Pedro

[![regress](https://github.com/antcatalina/pedro/actions/workflows/regress.yml/badge.svg)](https://github.com/antcatalina/pedro/actions/workflows/regress.yml)

**The goal: the easiest language to pick up for LLM-driven development.** Small enough to fit in a single prompt, precise enough for a real compiler to check your work against. Claude writes Pedro from your plain-English request; a real, deterministic compiler (`pedroc`) — **not an LLM** — turns it into the programming language of your choice.

> **Status:** v0.1. `pedroc` deterministically compiles a real, growing subset of the language — scalars, lists, maps, `record`/`enum` types, control flow (including `match`/`case` and `try`/`on failure`), recursion, and the collection operations — to **both Python and TypeScript**, verified by running the entire [cookbook](docs/cookbook.md) on *each* backend and asserting they agree. **Capabilities/effects** are implemented on the Python backend (database/email/crypto verbs, enforced and surface-reported); the TypeScript adapter path and modules are designed and next up — see [WORKLOG.md](WORKLOG.md) for exactly what's real today vs. still ahead. This README marks every not-yet-compiled construct with 🧭.

Pedro is the **verifiable intermediate language between natural-language intent and executable code.** You (or Claude) write clear, keyworded pseudocode and tag a target (`target: python`); `pedroc` compiles it to idiomatic code. The design splits one job into two:

- **plain English → Pedro** is fuzzy and creative — that's **Claude's** job (the *authoring layer*).
- **Pedro → code** is exact and mechanical — that's **`pedroc`'s** job (a real, deterministic compiler; **no LLM in the pipeline**).

Putting the LLM where fuzziness is a feature and a real compiler where correctness is non-negotiable is what makes Pedro reliable — and what makes it a good language *for* LLMs: the model emits Pedro, runs `pedroc check`, and self-corrects from structured feedback.

```
   plain English  ─▶  Claude   ─▶  your_app.pedro  ─▶  pedroc   ─▶  your_app.py
   (what you want)   (authoring)   (verifiable IR)    (compiler)   (Python & TypeScript; 🧭 more next)
                                          │
                                     expect blocks ─▶ run ─▶ pass / fail  (self-correction)
```

---

## Why Pedro?

- **Write intent once, target any language.** The same `.pedro` source compiles to **Python and TypeScript** today; the AST is target-agnostic on purpose, so each backend is just a codegen module, not a rewrite — and the [differential tester](tools/differential.py) runs the whole corpus on both and asserts they agree.
- **Readable by humans and Claude alike.** A non-programmer can follow a Pedro file; Claude can read, write, and extend it — `pedroc` is what actually compiles it. Both read the same source of truth.
- **Reproducible, reviewable, versionable.** A `.pedro` file is a stable artifact you can diff, review, and re-compile — unlike a one-off prompt. The same source always produces byte-identical output.
- **Leans on Claude's strengths.** Instead of forcing a rigid grammar the model must never trip on, Pedro gives Claude clear structure and an explicit contract, and lets it do what it's good at: turning clear intent into idiomatic code.

## Built for agent-heavy teams

If you're already driving most of your codebase through Claude Code, Cursor, or your own agent harness, Pedro is aimed squarely at you — not at replacing your agent, but at giving it a better substrate to work in:

- **The compiler is a real oracle, not a second opinion.** `pedroc check --json` doesn't grade style — it *runs* the generated code against your `expect` blocks and reports `code`, `line`, `col`, a `hint`, and (for typos) a nearest-match `suggestion`. An agent can loop on that JSON directly; it's built to be read by a model, not a human squinting at a stack trace.
- **Typed holes instead of hallucination.** When Claude doesn't know a value or a rule, it writes `todo "<what's missing and why>"` instead of guessing. A hole is visible and blocks `ok: true`; a guess silently ships a bug. This matters far more once an agent is making hundreds of these calls unattended.
- **Determinism is a safety property, not just tidiness.** Same source, same compiler version → byte-identical output, every time. When multiple agent runs (possibly days apart, possibly different sessions) touch the same `.pedro` file, you get the same code back — no drift, no "which run generated this."
- **Sandboxed by default.** `check` runs generated code in an isolated subprocess with a wall-clock timeout, so an agent-authored infinite loop is reported as `status: "timeout"` instead of hanging your CI or your laptop.
- **A capability surface you can read before you run anything.** Every effectful action — database, network, filesystem, email — has to be declared with `use capability`, and using an undeclared one is a compile error. `pedroc check --json` reports the program's entire declared capability surface as a `capabilities` field: the full blast radius of what an agent-authored program can *do*, visible before a single line executes. That's the kind of manifest an agent governance layer (or a human reviewing 50 agent-authored programs) actually wants.
- **That surface compiles to a harness permission manifest.** `pedroc permissions <file>.pedro` derives a ready-to-use permission block from the declared capabilities — by default a Claude Code `settings.json`-shaped `permissions.allow` list you can drop straight into a config, or `--format json` for an auditable per-capability breakdown. The manifest is *derived, never hand-maintained*: regenerating it from the same source is byte-identical, and an **undeclared** capability can never appear in the output (a pure program emits an empty, no-op manifest). The mapping is deliberately small and documented — a starting bridge, not a policy engine:

  | capability | grants (`allow` rules) |
  |---|---|
  | `http` | `WebFetch`, `Bash(curl:*)`, `Bash(wget:*)` |
  | `database` | `Bash(psql:*)` |
  | `email` | `Bash(sendmail:*)` |
  | `files` | `Read`, `Write`, `Edit` |
  | `time` / `crypto` / `random` | *(local-only — no external permission)* |

  For `examples/signup.pedro` (which declares `database` + `email` + `crypto`), that's exactly `["Bash(psql:*)", "Bash(sendmail:*)"]` — `crypto` is local so it grants nothing, and `http`/`files` never appear because they were never declared.
- **The language card fits in one prompt.** [`docs/language-card.md`](docs/language-card.md) is the entire in-context spec — no fine-tuning, no RAG over scattered docs. Every model call gets the complete, current language.
- **We dogfood this exact loop.** Pedro's own compiler is developed largely by autonomous Claude Code agents running on a schedule against this same `pedroc check` loop (see [`CLAUDE.md`](CLAUDE.md)) — if the authoring loop weren't reliable, the compiler wouldn't be either.

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

## A worked example — real, today, verified by `pedroc check`

`examples/cookbook/recover.pedro` — wrapping a failing operation in `try:` / `on failure as err:` and recovering two different ways:

```pedro
target: python

task checked_divide(a: whole, b: whole) returns whole:
    when b is 0:
        fail with "division by zero"
    return a div b

task safe_divide(a: whole, b: whole) returns whole:
    try:
        return checked_divide(a, b)
    on failure as err:
        return 0

task describe_divide(a: whole, b: whole) returns text:
    try:
        let result = checked_divide(a, b)
        return "result is {result}"
    on failure as err:
        return "failed: {err}"

expect:
    checked_divide(6, 3) == 2
    checked_divide(1, 0) fails with "division by zero"
    safe_divide(10, 2) == 5
    safe_divide(10, 0) == 0
    describe_divide(10, 2) == "result is 5"
    describe_divide(10, 0) == "failed: division by zero"
```

This is the **actual output** of `pedroc build examples/cookbook/recover.pedro`:

```python
# Generated from recover.pedro by pedroc v0.1 (target: python). Do not edit by hand.

class PedroError(Exception):
    pass


def checked_divide(a: int, b: int) -> int:
    if (b == 0):
        raise PedroError("division by zero")
    return (a // b)

def safe_divide(a: int, b: int) -> int:
    try:
        return checked_divide(a, b)
    except PedroError as _pedro_err:
        err = str(_pedro_err)
        return 0

def describe_divide(a: int, b: int) -> str:
    try:
        result = checked_divide(a, b)
        return f"result is {result}"
    except PedroError as _pedro_err:
        err = str(_pedro_err)
        return f"failed: {err}"

if __name__ == "__main__":
    assert (checked_divide(6, 3) == 2)
    # ... one generated assertion per `expect` line, then:
    print("recover.pedro: all expectations passed ✓")
```

`pedroc check examples/cookbook/recover.pedro --json` runs that file and reports `{"ok": true, ...}` — this isn't a mockup, it's what the compiler does right now. Run it yourself:

```
PYTHONPATH=. python -m pedroc check examples/cookbook/recover.pedro --json
```

---

## One source, two targets, with data modeling — real today

`record` and `enum` types are **implemented** and compile on both backends.
`examples/order_total.pedro` is a corpus program — it passes `pedroc check` and
runs green on Python *and* TypeScript:

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

A `{ ... }` literal with bare field names (`{ name: "pen", ... }`) is a **record
literal**, typed by context: where a `LineItem` is expected, it becomes one. The
real Python output (`pedroc build examples/order_total.pedro`) — record → `@dataclass`:

```python
# Generated from order_total.pedro by pedroc v0.1 (target: python). Do not edit by hand.

from __future__ import annotations

from dataclasses import dataclass

@dataclass
class LineItem:
    name: str
    price: float
    quantity: int

def order_total(items: list[LineItem], discount_percent: float) -> float:
    subtotal = 0
    for item in items:
        subtotal += (item.price * item.quantity)
    if (subtotal > 100):
        discount_percent += 5
    discount = ((subtotal * discount_percent) / 100)
    return (subtotal - discount)
```

…and the real TypeScript output (`--target typescript`) — record → `interface` + object literal:

```typescript
// Generated from order_total.pedro by pedroc v0.1 (target: typescript). Do not edit by hand.
// ... __eq / __in / __sort / __concat runtime-helper preamble (see the note above) ...
interface LineItem {
  name: string;
  price: number;
  quantity: number;
}

function order_total(items: LineItem[], discount_percent: number): number {
  let subtotal = 0;
  for (const item of items) {
    subtotal += (item.price * item.quantity);
  }
  if ((subtotal > 100)) {
    discount_percent += 5;
  }
  let discount = ((subtotal * discount_percent) / 100);
  return (subtotal - discount);
}
```

`pedroc` preserves your identifiers verbatim across targets (no case conversion) — the same names appear in the Python and TypeScript output, so a Pedro file reads the same whichever backend you compile it to. `examples/cookbook/tickets.pedro` models an issue tracker with both a `record` and an `enum` if you want a second, matcher-heavy example.

The rest of this README documents the **complete language design**, including pieces `pedroc` doesn't compile yet. Every such section is marked 🧭 — check [WORKLOG.md](WORKLOG.md) for the live, authoritative list, or run `pedroc check` and let the compiler tell you.

---

## Language guide

Sections below are the **full language design**. Anything not yet in the compiler is marked 🧭 — check [WORKLOG.md](WORKLOG.md) for the live, authoritative list, or run `pedroc check` and let the compiler tell you.

### Program directives

Every program starts with directives (before the first declaration):

- `target: <language> [version]` — **required; implemented.** e.g. `target: python 3.11`, `target: python`, `target: typescript`. **Both `python` and `typescript` are real targets today** (`pedroc build file.pedro --target typescript` → runnable `.ts`); the version suffix parses but has no effect on output yet. 🧭 other languages.
- `module: <name>` 🧭 — optional module name. Not yet parsed.
- `use "<file>.pedro"` / `use <name> from "<file>.pedro"` 🧭 — imports. Not yet parsed.
- `use capability …` — **implemented.** Capability declarations (see [below](#capabilities--talking-to-the-outside-world--implemented)); a top-level declaration of one effectful power the program is allowed to reach.

### Comments

```pedro
# This is a line comment.
```

### Primitive types — implemented

| Pedro     | Meaning              | Python  | TypeScript |
|-----------|----------------------|---------|------------|
| `text`    | string               | `str`   | `string`   |
| `whole`   | integer              | `int`   | `number`   |
| `number`  | real / decimal       | `float` | `number`   |
| `flag`    | true / false         | `bool`  | `boolean`  |
| `nothing` | absence of a value   | `None`  | `void`     |

Composite types map too: `list of T` → `T[]`, `map of K to V` → `Record<K, V>`, `optional T` → `T | null`. (JS has no value-equality or floor-division built in, so the TypeScript backend emits a tiny runtime preamble of `__eq`/`__in`/`__sort`/`__concat`/… helpers to keep `==`, membership, `sort`, and `followed by` value-correct.)

### Composite types

- `list of <T>` → `list[T]` — **implemented**
- `map of <K> to <V>` → `dict[K, V]` — **implemented**
- `optional <T>` (sugar: `<T>?`) → `T | None` — **implemented**
- `record` and `enum` (see below) — **implemented** (record → `@dataclass` / `interface`; enum → `str, Enum` / const object)

### Variables — implemented

```pedro
let total = 0        # declare
total = total + 5    # reassign  (or: `increase total by 5`)
```

Pedro identifiers are written in `snake_case`; the compiler converts them to the target language's convention.

### Literals — implemented

```pedro
"hello, {name}!"          # text, with {interpolation}; escape braces as \{ \}
42        3.14            # whole, number
true      false           # flag
[1, 2, 3]                 # list
{ "id": "u1", "n": 36 }   # map literal (string/expression keys)
{ id: "u1", age: 36 }     # record literal (bare field-name keys; typed by context)
nothing                   # the empty value
```

### Operators — implemented

- **Arithmetic:** `+ - * /`, `div` (whole-number division), `mod` (remainder)
- **Comparison:** `== != < <= > >=`
- **Logic:** `and`, `or`, `not`
- **Membership:** `x in items`, `x not in items`
- **Presence:** `x is present`, `x is empty`, `x is nothing`

### Readable forms — implemented

Many constructs have a plain-English form that compiles **identically** to its symbolic form — write whichever reads better in context:

| Readable form            | Same as        | Meaning                                   |
|---------------------------|----------------|-------------------------------------------|
| `increase x by n`        | `x = x + n`    | add in place                              |
| `decrease x by n`        | `x = x - n`    | subtract in place                         |
| `set x to v`             | `x = v`        | reassign a variable                       |
| `a is b`                 | `a == b`       | equals                                    |
| `a is not b`              | `a != b`       | not equal                                 |
| `a is greater than b`    | `a > b`        |                                            |
| `a is less than b`       | `a < b`        |                                            |
| `a is at least b`        | `a >= b`       |                                            |
| `a is at most b`         | `a <= b`       |                                            |
| `value as text`          | `str(value)`   | convert (also `as whole`, `as number`)    |

Because each form has a single canonical meaning, readability costs nothing in determinism: `increase total by 1` and `total = total + 1` compile to the same code.

### Tasks (functions) — implemented

A task declares its return type after `returns`:

```pedro
task discount(price: number, percent: number = 0) returns number:
    return price - price * percent / 100
```

Parameters may have defaults. Return a value with `return <expr>` (or a bare `return`). A task with no `returns` clause returns `nothing` and needn't return a value.

### Records and enums — implemented

Records and enums are top-level declarations. A `record` becomes a Python
`@dataclass` (attribute access, `u.email`) / a TypeScript `interface`; an `enum`
becomes a Python `str, Enum` / a TypeScript const object, so `Status.active` is
the string `"active"` at runtime on both backends (they agree).

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

Construct a record with a **record literal** — a `{ ... }` with bare field-name
keys — and reference enum variants by name:

```pedro
let s = Status.active
some_task({ id: "u1", email: "a@b.c" })   # { age } omitted → its default (0) is filled in
```

A record literal has no type name written on it; `pedroc` types it **by
context** — where a `User` is expected (a typed task argument, a `return`, a
record field, or a `list of User` element), the `{ ... }` becomes a `User`. If no
expected type reaches it, `pedroc` falls back to a unique field-set match, and
reports `ambiguous-record` / `unknown-field` / `missing-field` otherwise.

**How a collection binds to its record type:** explicitly, through the type
annotation — `items: list of LineItem` says the rows are `LineItem`s. Pedro never
infers a row type from a collection's *name* (no `users` → `User` pluralization).
The same rule will govern the future `database` capability: a table declares its
record type. (See `examples/order_total.pedro` and `examples/signup.pedro` for the
`# pedro-note` where this applies.)

### Conditionals — implemented

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

All of the above are **implemented**. 🧭 There is no `break`/`continue` yet (no `stop`/`skip` keywords) — structure loops (e.g. a guard condition, or `find one … where …` instead of a hand-rolled search loop) to avoid needing early exit for now.

### Pattern matching — implemented (over values *and* enum variants)

```pedro
match status:
    case "active":
        return "ok"
    case "suspended":
        return "locked"
    case otherwise:
        return "unknown"
```

`match`/`case`/`case otherwise` work today, comparing the subject by equality against each case — over plain values *or* `Enum.variant` values (`case Status.active:`), as in `examples/cookbook/tickets.pedro`.

### Errors — implemented

```pedro
fail with "invalid email"        # raise an idiomatic error with this message

try:
    let result = checked_divide(a, b)
on failure as err:
    fail with "could not complete: {err}"
```

(`try`/`on failure` catches a Pedro-raised `fail with`, as in the [worked example](#a-worked-example--real-today-verified-by-pedroc-check) above. An adapter that raises a Pedro failure is caught the same way.)

### Collection operations — implemented

Readable expressions that compile to the target's idioms (comprehensions, generator expressions, …):

```pedro
find one user in users where user.email is email      # first match, or nothing
filter user in users where user.age is at least 18    # list of matches
count of users                                        # a whole number
collect user.email for each user in users              # list comprehension
sort scores                                            # ascending; 🧭 no `by <key>` / `descending` yet
sum of item.price for each item in cart
first of items        last of items
numbers from 1 to 10                                   # inclusive range
```

A fuller set of list, map, text, and range operations — used throughout the cookbook — is documented in [`docs/cookbook.md`](docs/cookbook.md). 🧭 Keyed/descending sort (`sort users by created_at descending`) is designed but not yet implemented — `sort` today takes a single collection and sorts it in ascending natural order.

### Capabilities — talking to the outside world — **implemented**

Pedro programs are **pure by default.** Anything with side effects must be unlocked with a capability. This is the core differentiator — **auditable by construction**: the set of declared capabilities is the program's entire blast radius, and using a verb whose capability isn't declared is a **compile error**, never a silent import.

```pedro
use capability database
use capability http
use capability email
use capability files
use capability time
use capability crypto
use capability random
```

All seven **declarations** parse, are enforced, and are reported by `pedroc check --json` as a `capabilities` field. Capabilities provide verbs:

| Capability | Verbs | Status |
|------------|-------|--------|
| `database` | `insert into <table> { … }` (returns id) | **implemented** |
| `database` | `update <table> set { … } where …`, `delete from <table> where …` | 🧭 pending |
| `email`    | `send email to <address> with subject "<s>" body "<b>"` | **implemented** |
| `crypto`   | `hash <text>`, `verify <text> against <hash>` | **implemented** |
| `http`     | `http get "<url>"`, `http post "<url>" with <body>` | 🧭 pending |
| `files`    | `read file "<path>"`, `write <text> to file "<path>"` | 🧭 pending |
| `time`     | `now`, `today` | 🧭 pending |
| `random`   | `random whole from <a> to <b>` | 🧭 pending |

Reading a table (`find one user in users where …`, `count of users`, `for each user in users`) needs no new verb — a `table` handle is an ordinary iterable, so the existing collection operations work on it directly.

**The adapter layer.** Capability calls compile through a small, swappable module — `pedro_capabilities` — with one adapter object per capability (`database`, `crypto`, `email`, …). Generated code stays clean (`crypto.hash(password)`, `users.insert(...)`, `mailer.send(...)`) and the outside world is trivial to mock: a project ships its own `pedro_capabilities.py` wired to a real database / SMTP server, and `pedroc`'s in-memory reference adapters ([`pedroc/adapters.py`](pedroc/adapters.py)) make `pedroc check` run an effectful program with no real I/O. `examples/signup.pedro` (validate → dedupe → hash → store → email) and `examples/cookbook/credentials.pedro` (register → login) both compile and pass `pedroc check` against those mocks.

**Tables.** A database table binds its row type explicitly — `table users: User` — and is referenced by name:

```pedro
use capability database
use capability email
use capability crypto

record User:
    email: text
    password: text
    id: text = ""            # assigned by the database on insert

table users: User

task sign_up(email: text, password: text) returns text:
    when "@" not in email:
        fail with "invalid email"
    let existing = find one user in users where user.email is email
    when existing is present:
        fail with "email already registered"
    let hashed = hash password
    let new_id = insert into users { email: email, password: hashed }
    send email to email with subject "Welcome!" body "Thanks for signing up."
    return new_id
```

Here `email` is both a parameter and a capability, so `pedroc` imports the email adapter under a **non-colliding alias** (`from pedro_capabilities import ... , email as mailer`) — the *import* is renamed, never your identifier (contract rule #7). `pedroc check examples/signup.pedro --json` reports `"capabilities":["database","email","crypto"]`.

### Modules 🧭 — designed, not yet parsed

```pedro
use "lib/money.pedro"                   # import a file's tasks, records, enums
use round_cents from "lib/money.pedro"  # import selectively
```

### Escape hatch — raw target code 🧭 — designed, not yet parsed

For the rare thing Pedro can't express, the intent is a literal target-language escape hatch:

```pedro
raw python:
    result = some_native_library.do_it()
end raw
```

Raw blocks would be tagged by language and only emitted when the compile target matches, sharing in-scope variables with the block. Not yet implemented — today, if a task needs something Pedro can't express, write the signature and an `expect:` block and leave a `todo "<what's needed>"` hole instead.

### Verification — implemented

State expected behavior. The compiler must produce code that satisfies it, and emits these as runnable assertions.

```pedro
expect:
    given users is empty
    order_total([ { name: "pen", price: 2.5, quantity: 4 } ], 0) == 10
    sign_up("not-an-email", "x") fails with "invalid email"
```

### Known predicates

A small standard library of readable predicates:

| Predicate | Status |
|-----------|--------|
| `<x> is empty` / `is present` / `is nothing` | **implemented** |
| `<a> is divisible by <b>` | **implemented** |
| `<whole> is even` / `is odd` | 🧭 designed, not yet parsed |
| `<text> is a valid email` | 🧭 designed, not yet parsed |
| `<text> is a valid url` | 🧭 designed, not yet parsed |

---

## The compiler contract

> **Note:** now that `pedroc` is a real compiler, this contract has split in two.
> Rules about idiomatic output, canonical translation, and determinism are
> **`pedroc` guarantees**; rules about resolving ambiguity and not inventing
> capabilities are **authoring-layer guidelines** for Claude writing Pedro (see
> [docs/design-for-llms.md](docs/design-for-llms.md)). The rules below describe the
> intended end-to-end behavior; today's `pedroc` implements them for the
> constructs it supports (unmarked 🧭 above).

This is the part that makes Pedro reliable. When a `.pedro` file is compiled, the toolchain **must** honor these rules:

1. **The spec is normative.** `docs/SPEC.md` 🧭 (planned) and [`docs/language-card.md`](docs/language-card.md) define the language. Compile to match it — don't guess.
2. **Emit idiomatic target code.** Follow the target language's conventions: naming (`snake_case` for Python, `camelCase` for TS, etc.), standard library, and formatting. Convert Pedro identifiers to the target convention while preserving meaning.
3. **Translate construct-by-construct** using the canonical mappings in the spec. Don't restructure or "improve" the logic.
4. **No undeclared powers.** — **implemented.** Only capabilities the program declares with `use capability` may be used. A verb whose capability isn't declared is a **compile error** (`undeclared-capability`) — `pedroc` never invents APIs or imports libraries silently.
5. **Resolve ambiguity conservatively.** If a line has one obviously-simplest correct reading, take it and add a `# pedro-note: …` comment. If it's genuinely unclear, emit `# PEDRO-AMBIGUITY: …` and ask the author rather than guessing.
6. **Satisfy every `expect` block.** Generated code must pass all stated expectations; today they're emitted as runnable assertions with a pass/fail summary line.
7. **Avoid name collisions.** — **implemented.** If a capability adapter import would collide with a user identifier, `pedroc` renames the *import* (e.g. the email capability imports as `mailer`) — never the user's names.
8. **Stamp the output.** Every generated file begins with:
   `# Generated from <file>.pedro by pedroc v0.1 (target: <target>). Do not edit by hand.`
9. **Be deterministic.** The same source + same compiler version produces byte-identical output. Don't add logging, caching, comments, or features that weren't written.

---

## Using Pedro today

`pedroc` is a real compiler — run it from the terminal (Python 3.11+, no dependencies):

```
# compile Pedro to Python
PYTHONPATH=. python -m pedroc build examples/cookbook/numbers.pedro -o build/numbers.py

# ...or to TypeScript, and run it straight away (Node v24+ strips types — no build step)
PYTHONPATH=. python -m pedroc build examples/cookbook/numbers.pedro -o build/numbers.ts --target typescript
node build/numbers.ts

# check it: compile, run its expect blocks, report per-assertion pass/fail
PYTHONPATH=. python -m pedroc check examples/cookbook/numbers.pedro --json
```

`check` is the oracle for the authoring loop: emit Pedro → `check` → read the JSON (`errors`, `holes`, and failing `expectations` with `got X, expected Y`) → fix. Diagnostics are built to be *read by a model*: each error carries a stable `code`, `line` **and `col`**, an actionable `hint`, a source `snippet` with a `^` caret, and — for a misspelled identifier, task, or keyword — a nearest-match `suggestion` ("did you mean X?"). The JSON is compact (null fields omitted). The generated program is run in a **sandboxed subprocess** with a wall-clock timeout and a restricted environment, so a non-terminating or hostile program is reported as a structured `status:"timeout"`/`"error"` instead of hanging or compromising the compiler. The **authoring layer** — turning a plain-English request into Pedro and driving that loop — is the Claude Code skill in `skills/write-pedro/`; the compact spec it reads is [docs/language-card.md](docs/language-card.md).

**Coverage today:** the whole cookbook (scalars, lists, maps, control flow — including `match`/`case` and `try`/`on failure as err` — recursion, and the collection operations), targeting **Python and TypeScript** — every corpus program runs green on both, and the differential tester asserts the two backends agree expectation-for-expectation. **Capabilities + the adapter layer** are live on the Python backend (database/email/crypto verbs, enforced, surface-reported). Every 🧭 in this README is not yet in the compiler — [WORKLOG.md](WORKLOG.md) has the live, prioritized list of what's next.

---

## Repository layout

```
pedro/
├── README.md              # overview + language guide
├── CLAUDE.md               # standing guidance for Claude / automated agents
├── WORKLOG.md              # dated change log + next steps
├── pedroc/                 # the real compiler: lexer, parser, codegen_python + codegen_ts, capabilities, adapters, check, CLI
├── docs/
│   ├── design-for-llms.md  # why Pedro is shaped this way (the strategy)
│   ├── language-card.md    # compact in-context spec for the authoring LLM
│   ├── cookbook.md         # 22 algorithms, all compiled + checked by pedroc
│   └── SPEC.md              # normative spec                            (planned)
├── examples/
│   ├── math.pedro          # integer algorithms
│   ├── cookbook/            # the cookbook algorithms as .pedro (regression corpus; incl. tickets.pedro — record + enum)
│   ├── order_total.pedro   # uses a record       (compiles + runs on both backends; in the corpus)
│   └── signup.pedro        # uses capabilities   (compiles + passes check against mock adapters)
├── skills/write-pedro/     # the Claude Code authoring skill (NL -> Pedro)
└── tools/
    ├── regress.py           # compiles + checks the whole corpus (CI; run on GitHub Actions + AntMac cron)
    ├── backends.py           # per-backend "run + report expectations" adapter
    ├── differential.py       # runs each corpus program on every backend, asserts agreement
    ├── fuzz.py               # seedable grammar fuzzer with a reference oracle
    └── check_docs.py         # doc-drift backstop: compiler's real construct surface vs. doc claims
```

The correctness harness is kept off the default fast path: `python tools/regress.py`
runs both backends over the corpus plus a tiny fuzz smoke, while `--fuzz`, `--diff`,
and `--slow` run the full sweeps. The differential lane compares backends against
each other; now that the TypeScript backend has landed, it runs a live cross-backend
diff (the TS corpus lane runs automatically whenever `node` is on PATH).

**Docs can't silently drift.** `tools/check_docs.py` is the mechanical backstop for
[`CLAUDE.md`](CLAUDE.md) ground rule 6: it extracts `pedroc`'s *real* construct surface
straight from source (every `kw == "…"` / `_is_name("…")` / `_expect(…, "…")` literal in
`pedroc/parser.py`, plus the `BINOP_MAP` / builtin-dispatch keys in
`pedroc/codegen_python.py`) and cross-references it against the docs. It flags, **HIGH
confidence**, any construct the compiler implements that a doc still marks "NOT yet
supported"/🧭 — the exact bug the 2026-07-28 audit found (`for each` listed as unsupported
weeks after it shipped) — and, **LOW confidence**, a construct a doc presents as supported
with no matching keyword anywhere in `pedroc/*.py`. It runs as a labelled, **non-fatal
warning** inside `tools/regress.py` (new heuristic — false positives possible); run it on
its own with `python tools/check_docs.py`, and use `python tools/regress.py --strict-docs`
(or `python tools/check_docs.py --strict-docs`) to make HIGH findings fail.

**CI is machine-independent.** The [`regress` GitHub Actions workflow](.github/workflows/regress.yml)
runs `PYTHONPATH=. python tools/regress.py` — the exact command below — on every push
to `agent/dev`/`master` and on every PR, so the badge at the top of this README is the
authoritative green/red signal. AntMac's cron runs the same command as a convenience and
build engine on top of it, not the source of truth.

## Working on Pedro (humans and agents)

Repo-specific conventions and guardrails for anyone — or any Claude agent — making changes live in **[`CLAUDE.md`](CLAUDE.md)**; read it first. Automated Claude Code agents run unattended, round-robin, on a schedule against the shared **`agent/dev`** branch, following the prioritized roadmap in [`WORKLOG.md`](WORKLOG.md) and self-correcting against the same `pedroc check` loop described above; their work is reviewed and merged to `master` by a human.

## Roadmap

Live status and next steps live in [WORKLOG.md](WORKLOG.md). In brief:

- **Done** — the language design; a real deterministic compiler (`pedroc`) for the scalar/list/map/`record`/`enum`/control-flow subset → **Python and TypeScript**; **capabilities + the swappable adapter layer** (Python; database/email/crypto verbs, undeclared-use is a compile error, the declared surface reported by `check --json`); the **capability → agent-permission bridge** (`pedroc permissions`, see above); the `pedroc check` loop, typed holes, and structured diagnostics, sandboxed in a subprocess; the [cookbook](docs/cookbook.md) as a passing regression suite (`tools/regress.py`) on both backends; a differential tester + seedable grammar fuzzer running live over both backends (`tools/differential.py`, `tools/fuzz.py`); and a mechanical doc-drift backstop (`tools/check_docs.py`) wired into CI.
- **Next (highest priority first)** — the remaining capability verbs (db `update`/`delete`, `http`/`files`/`time`/`random`) + the TypeScript adapter path; promoting the differential check into a `pedroc check --targets` guarantee; then `docs/SPEC.md`.

### Committed: bets that make Pedro distinctly agent-native 🧭

Approved 2026-07-28, queued on AntMac, not built yet — each depends on a "Next" item above landing first:

- ~~**Capability manifest → agent permission bridge** (`capability-permission-bridge`)~~ — **LANDED.** `pedroc permissions <file>.pedro` derives the manifest from the declared capability surface; see the "Built for agent-heavy teams" section above for the mapping table.
- **Cross-target consistency as a CLI guarantee** (`cross-target-check-cli`, depends on the TypeScript backend). Promotes `tools/differential.py`'s cross-backend agreement check into `pedroc check <file>.pedro --targets python,typescript` — "this program behaves identically everywhere" becomes something any user's own code can assert, not just the compiler's own test suite.
- **Property-based `expect` blocks** (`property-based-expect`). Extends `expect:` with a bounded quantified form (`for all n from 0 to 100: is_prime(n) implies n > 1`), enumerated and checked — a strict superset of today's example-based syntax, and a much higher correctness bar for agent-authored logic than a handful of examples.
- **Tamper-evident generated output** (`verify-drift-detection`). Embeds a source content-hash in the "do not edit by hand" banner; `pedroc verify <file>.pedro <output>` detects drift — catches the common failure mode where a human hand-patches generated code and an agent later regenerates over it (or vice versa).

### Keeping the docs honest — mechanically, not just by reminder

This same session found `docs/language-card.md` — the actual in-context spec fed to the authoring LLM — telling the model that lists, maps, and `for each` were unsupported, weeks after they shipped. Two new AntMac jobs address the root cause instead of the symptom:

- **`docs-alignment-audit`** (recurring) — periodically re-runs the README/WORKLOG/CLAUDE.md/language-card.md-vs-actual-compiler cross-check this session did by hand, and fixes drift as it's found.
- ~~**`docs-consistency-checker`**~~ — **LANDED** (2026-07-30). `tools/check_docs.py` extracts pedroc's real construct surface from source and cross-references it against the "NOT yet supported"/🧭 claims in the docs, wired into `tools/regress.py` as a non-fatal warning (with `--strict-docs` to enforce), so a shipped feature whose docs didn't catch up gets flagged mechanically. See the "Docs can't silently drift" note in the tooling section above. The same "verify by running" principle Pedro applies to your programs, applied to its own documentation.

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

**How do I know what actually works today vs. what's still vision?** Every construct in this README that isn't compiled yet is marked 🧭. When in doubt, `pedroc check` is the final word — if it parses and runs, it's real.

**Do I need to fine-tune Claude?** No. Pedro is taught entirely in-context via [docs/language-card.md](docs/language-card.md).

**Which languages can it target?** `pedroc` emits **Python and TypeScript** today (the AST is target-agnostic, so each backend is just a codegen module, not a rewrite) — every corpus program runs green on both and the [differential tester](tools/differential.py) asserts they agree. The design supports any language a backend is written for.

**Can Claude read Pedro as well as write it?** Yes — Pedro is designed to be equally clear to humans and to Claude, so you can also hand Claude a `.pedro` file and ask it to explain or extend the program.

---

*Pedro's bet: the easiest language to pick up for LLM-driven development isn't the one with the most features — it's the one small enough for an agent to hold entirely in context, precise enough for a real compiler to check every claim it makes, and readable enough that you never have to wonder what it built. Ideas and contributions welcome.*
