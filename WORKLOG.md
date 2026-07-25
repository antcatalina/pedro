# Pedro Work Log

Reverse-chronological log of substantive changes and next steps, so we can
resume cleanly across sessions.

---

## 2026-07-25 — LLM-first tooling: `check`, holes, language card, authoring skill

**Direction:** Pedro = the verifiable IR between natural-language intent and
code. The LLM does NL → Pedro (fuzzy); `pedroc` does Pedro → code
(deterministic). This session made the **generate → check → fix loop** real,
because the loop — not the compiler — is what makes a language good for LLMs.

### Added
- **Typed holes: `todo "<why>"`** — first-class uncertainty. The model flags
  unknowns instead of hallucinating. Parsed (`nodes.Todo`), compiled to a loud
  `raise NotImplementedError(...)`, and reported by `check`.
- **`pedroc check <file> [--json]`** — the machine oracle for the loop
  (`pedroc/check.py`). Reports syntax `errors` (line/code/message/hint),
  `holes`, and per-`expectation` pass/fail by **actually running** the generated
  code; failures carry `detail` = "got X, expected <op> Y". Exit 0 iff `ok`.
- **Structured error codes + hints** (`errors.py`, `lexer.py`, `parser.py`) —
  errors are prompts: `unexpected-token`, `bad-indentation`,
  `unterminated-string`, `unexpected-character`, plus hints for `:` / `returns`.
- **`docs/language-card.md`** — the compact, in-context spec the authoring LLM
  reads. Describes the SUPPORTED subset + the loop protocol. Fits in a prompt.
- **`skills/write-pedro/SKILL.md`** — the Claude Code authoring skill (NL → Pedro
  in the check loop). NOTE: needs registration to auto-load in Claude Code.

### Verified this session (all green)
- `examples/math.pedro` still compiles + runs — no regression.
- Loop demo: buggy `classify` → check flagged `classify(0)`: got 'positive',
  expected == 'zero' → fixed `otherwise` branch → `ok: true`, exit 0.
- Hole demo: `shipping_cost` with a `todo` → check reported the hole at line 6
  and marked the program incomplete.
  (Demo files live in the gitignored `build/`.)

### Decisions made (didn't ask; per "don't compromise")
- **Authoring layer = a Claude Code skill, not an API service.** The "LLM" in the
  loop is Claude-in-the-editor following the language card, so the loop needs no
  API key. An API-driven `pedroc author` CLI stays optional/future.
- **Keep significant-indentation syntax.** LLMs handle Python-style indentation
  very well (heavily represented in training data) and it is token-cheap; we
  invest in precise indentation diagnostics instead. Revisit only if LLM indent
  errors show up in practice.

## Next steps (priority order)
1. **Grow `pedroc` to the cookbook**: lists, maps, records, `for each`, and the
   collection operations. Then make `build/cookbook_check.py` the compiler's
   regression suite (compile each cookbook algorithm, run its expects through
   `check`).
2. **Capabilities + adapter layer in the compiler** (database/http/email/…).
   This is where the "auditable by construction" advantage becomes real —
   `check` should also report the declared capability surface.
3. **Second target: TypeScript codegen** from the same AST, to prove
   retargeting from one source.
4. **Sandbox `check`.** It currently `exec`s generated code in-process — fine for
   trusted local use, unsafe for untrusted input. Sandbox before any hosted use.
5. **Reconcile README** with the new framing (retire "Claude is the compiler" in
   the body) and fold everything into `docs/SPEC.md`.

## Open questions
- Indentation vs. explicit `end`/braces for LLM robustness. Current lean: keep
  indentation + great diagnostics.
- How a table name binds to its `record` type (dict rows vs. typed records) —
  surfaced by the `signup.pedro` compile earlier.
- Cosmetic: negative literals compile with an extra paren (`classify((-3))`);
  harmless, tidy up in codegen later.

## What I need from you (all optional)
- Only if you want an **API-driven** authoring CLI (beyond the in-editor skill):
  an `ANTHROPIC_API_KEY`. The skill-based loop needs nothing.
- A **primary target language** preference beyond Python, for the retargeting
  step (TypeScript is my default guess).
- Any **reference languages** whose feel you want Pedro to match (you mentioned
  you'd share some — Inform 7 / Gherkin / SQL were on my list).
