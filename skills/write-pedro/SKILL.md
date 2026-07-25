---
name: write-pedro
description: Turn a natural-language request into a verified Pedro program by authoring Pedro and iterating against `pedroc check` until it passes. Use when the user asks to build logic "in Pedro", or to write/compile a .pedro program.
---

# Writing Pedro (the authoring loop)

You are the **authoring layer**: natural language → Pedro. A real compiler
(`pedroc`) handles Pedro → code, so your job is correct **Pedro**, not correct
Python.

## Steps

1. Read `docs/language-card.md` (the compact spec). Stay strictly within its
   SUPPORTED subset.
2. Write a `.pedro` file for the request. **Always** include an `expect:` block
   with concrete cases capturing the intended behavior.
3. For anything you are unsure of, write `todo "<why>"` — never guess.
4. Run the oracle:
   `PYTHONPATH=<repo-root> python -m pedroc check <file>.pedro --json`
5. Read the JSON and fix:
   - `errors` → syntax; fix at `line`, follow `hint`.
   - `holes` → ask the user for the missing detail, or resolve it.
   - failing `expectations` → your logic is wrong; `detail` gives
     `got X, expected <op> Y`.
6. Loop until `ok: true`. Then compile:
   `python -m pedroc build <file>.pedro -o <out>.py`
7. Show the user the Pedro source and the final check result. **Never** hand-edit
   the generated code — change the Pedro and recompile.

## Rules

- A hole is always better than a hallucination.
- Keep programs in the supported subset. If the request needs unsupported
  features, deliver the signature + `expect:` + a `todo`, and say so plainly.
- The Pedro file is the artifact of record; the generated code is disposable.
