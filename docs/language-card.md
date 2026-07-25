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
   - `errors[]` → fix the syntax at `line`; follow `hint`.
   - `holes[]` → resolve it, or ask the user for the missing detail.
   - `expectations[].passed == false` → your logic is wrong; `detail` gives
     `got X, expected <op> Y`. Fix and re-check.
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
- `while <cond>:` · `repeat <expr> times:`
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
