# Pedro Language Card (v0.1)

The compact, in-context spec for an **LLM authoring Pedro**. This is the artifact
you inject into the prompt. Keep it small on purpose — the whole language must
fit in context, because the model is taught here, not fine-tuned.

## Your job (as the authoring model)

You turn natural language into **Pedro**, not into Python. A real compiler
(`pedroc`) turns Pedro into code. So produce correct Pedro and let the oracle
check it:

1. Write a `.pedro` program for the request, in the SUPPORTED subset below.
2. **Always** include an `expect:` block with concrete cases capturing intent.
3. If you are unsure of a rule, a value, or a step, **do not guess** — write
   `todo "<what's missing and why>"`. A hole beats a hallucination.
4. Run `python -m pedroc check <file>.pedro --json` and read the JSON:
   - `ok` → `true` when there are no errors, no holes, and every expectation
     passed. That's your goal.
   - `errors[]` → fix these first. Each carries `code` (stable, machine-readable),
     `line` + `col` (1-based; `col` points at the offending token), `message`,
     and often a `hint` (what to do) and a `snippet` (the source line with a `^`
     caret under the spot). When the fix is a spelling mistake you also get a
     `suggestion` — the nearest known name/keyword ("did you mean X?"); if it's
     right, just apply it. Common codes: `unexpected-token`, `expected-expression`,
     `bad-indentation`, `unterminated-string`, `undefined-name`, `unknown-task`,
     `empty-match`, `case-after-otherwise`.
   - `holes[]` → resolve each `todo`, or ask the user for the missing detail.
   - `expectations[].passed == false` → your logic is wrong; `detail` gives
     `got X, expected <op> Y`. Fix and re-check.
   - `capabilities[]` → the program's declared capability surface (reserved;
     empty today).
   - `status` → present only on an abnormal run: `"timeout"` (your program didn't
     terminate — likely an infinite loop; the summary names the stuck expectation)
     or `"error"` (it crashed). Your program is run in a sandboxed subprocess with
     a time budget, so a runaway loop is reported, not hung on. A normal run has no
     `status` key.
   - The JSON is COMPACT: null/empty fields are omitted, so an absent key means
     null (e.g. no `suggestion` key = no suggestion).
5. Loop until `ok: true`, then `python -m pedroc build <file>.pedro -o out.py`.

## Program shape

```pedro
target: python                       # required first line

task <name>(<p>: <type>, ...) returns <type>:
    <statements>

expect:
    <call> == <value>
```

## Types (supported)

`text` · `whole` (integer) · `number` (decimal) · `flag` (true/false)

## Statements

- `let x = <expr>` (declare) · `x = <expr>` or `set x to <expr>` (reassign)
- `increase x by <expr>` · `decrease x by <expr>`
- `return <expr>` · `return`
- `when <cond>:` / `when <cond>:` / `otherwise:`  — first true branch wins
- `match <expr>:` with `case <value>:` arms and a final `case otherwise:` —
  the subject is compared by equality against each case; `otherwise` is the
  default (and must be last)
- `try:` / `on failure as <err>:` — run the body; if a `fail with` fires,
  recover in the handler with `<err>` bound to the failure message (a `text`)
- `while <cond>:` · `repeat <expr> times:`
- `fail with <expr>`  — raise a recoverable failure with a message
- `todo "<message>"`  — an unresolved hole

## Expressions

- arithmetic: `+ - * /`, `mod` (remainder), `div` (whole-number division)
- compare: `is`, `is not`, `is greater than`, `is less than`, `is at least`,
  `is at most`  (symbols `== != < > <= >=` also work)
- `<a> is divisible by <b>`
- logic: `and`, `or`, `not`
- literals: `42`, `3.14`, `true`, `false`, `"text with {interpolation}"`
- calls: `factorial(n - 1)` — recursion is fine

## NOT yet supported — do not use until the compiler catches up

lists, maps, records, enums, `for each`, string methods, capabilities/effects.
If the task needs these: write the task signature and an `expect:` block, and
put a `todo "<what's needed>"` in the body. Ship the hole, don't fake it.

## Canonical example

```pedro
target: python

task is_prime(n: whole) returns flag:
    when n is at most 1:
        return false
    let divisor = 2
    while divisor * divisor is at most n:
        when n is divisible by divisor:
            return false
        increase divisor by 1
    return true

expect:
    is_prime(2) == true
    is_prime(97) == true
    is_prime(100) == false
```

## `match` and `try` (control flow)

```pedro
task next_state(state: text, event: text) returns text:
    match state:
        case "locked":
            when event is "coin":
                return "unlocked"
            return "locked"
        case otherwise:
            fail with "unknown state"

task safe_next(state: text, event: text) returns text:
    try:
        return next_state(state, event)
    on failure as err:
        return "error: {err}"
```
