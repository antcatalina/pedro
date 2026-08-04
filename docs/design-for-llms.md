# Designing Pedro for LLMs

This document is the "why" and the "where we're going." It explains the shape of the project and the design rules we hold ourselves to. If you read one doc to understand Pedro's direction, read this one.

## The thesis

**Pedro is the verifiable intermediate language between natural-language intent and executable code.**

There are two very different jobs hiding inside "turn what I want into a program":

| Step | Nature | Who should do it |
|------|--------|------------------|
| **plain English → Pedro** | fuzzy, creative, needs world-knowledge | an **LLM** (Claude) — being fuzzy is a *superpower* here |
| **Pedro → code** | exact, mechanical, must be correct | a **real compiler** (`pedroc`) — being deterministic is a *requirement* |

The classic mistake is making one system do both. An LLM asked to go straight from English to correct code has to be creative *and* exact in the same breath, and it silently guesses when unsure. Splitting the job fixes this: the LLM commits its understanding to **Pedro** — a typed, checkable artifact — and a deterministic compiler takes it the rest of the way.

```
   plain English  ─▶  Claude   ─▶  your_app.pedro  ─▶  pedroc   ─▶  your_app.py
   (what you want)   (authoring)   (verifiable IR)    (compiler)   (or .ts, .go, …)
                                          │
                                     expect blocks ─▶ run ─▶ pass / fail
                                          └──────── self-correction loop ────────┘
```

## Why this makes Pedro a *go-to language for LLMs*

LLMs are unreliable **generators** but excellent **iterators**. Give a model a target it can compile and test, and it converges: emit Pedro → compile → run the `expect` block → read the error → fix → repeat. Pedro's determinism isn't opposed to LLM-friendliness — it's the **ground truth the model bounces off of.** A language with no compiler gives the model nothing to be corrected by; Pedro gives it a fast, exact oracle.

So "fine-tuned for Claude/LLMs" does **not** mean "vague and English-like." It means: **give the model the scaffolding that makes its output trustworthy.**

## Why not just Python or JavaScript?

The honest answer starts with a concession: **readability is not Pedro's advantage.** Python and JS read fine. Pedro's edge shows up only in one specific regime — **when the code is written by a probabilistic generator that you must review, retarget, and regenerate.** In that regime, Python's greatest strengths turn into liabilities:

- **Bounded, closed surface vs. unbounded.** Python can import anything, monkeypatch, `eval`, and touch the network or filesystem from any line. That vastness is exactly *why* LLM-generated Python is hard to trust — the model can hallucinate an API or slip in a side effect you never asked for. Pedro has a small, fixed construct set and no ambient imports: the model cannot wander outside it, and anything undefined is a **compile error, not a silent guess.**
- **Auditable by construction (capabilities).** A Pedro program declares its powers at the top (`use capability database, email`). Its entire blast radius is legible from the header — no hidden network call, no surprise file write. To get the same guarantee from Python you'd have to audit every line *and every transitive dependency*. For code you didn't write and don't fully trust, that's the line between reviewable and not.
- **Whole-program readability, not line readability.** Python reads clearly line by line, but a program's real behavior depends on its imports, dynamic features, and environment. A Pedro program hides nothing, so "what can this do?" is answerable at a glance. That is the kind of readability that scales into *trust*.
- **Retargetable.** One Pedro source compiles to Python, TypeScript, or Go. The artifact you reviewed stays small and stable; the generated code is disposable and language-agnostic.
- **Co-designed with the LLM loop.** Verifiable (`expect`), self-correcting (compiler errors as prompts), and able to admit uncertainty (holes). Python was designed for a trusted human author in 1991; it was never optimized to be the I/O format of a probabilistic generator.

**Where Python/JS honestly win:** ecosystem and libraries (Pedro has none), decades of maturity, and raw expressiveness for the one-off scripts an LLM already writes perfectly. Pedro is not trying to be your general-purpose language. **It competes with "an LLM handing you Python you can't fully trust"** — and against that, boundedness + auditability + verification + retargeting are the upper hand.

> One line: **Python optimizes for a human author who is trusted, targeting one runtime. Pedro optimizes for a machine author who is not trusted, targeting many.**

(Note: capability-gating and holes are language-design guarantees we are building toward; today's `pedroc` compiles the pure logic core. The point is the *shape* of the language, which is what determines these properties.)

## Design principles

1. **A real compiler + verifier is the core.** The single biggest reliability lever. Everything else supports the generate → check → fix loop. *(Built: `pedroc`, deterministic, for the integer-algorithm subset.)*

2. **The spec must fit in context.** We cannot fine-tune Claude on Pedro, so the entire language has to be learnable from a short doc + examples that fit in a prompt. This is a hard budget, and it argues *against* cleverness: **keep Pedro small and regular.** Every construct we add costs context tokens on every compile.

3. **Regularity over synonyms.** LLMs latch onto patterns; irregular languages induce hallucination. We allow a *small* set of readable aliases (each mapping to one canonical form), but we resist proliferating them. The model is taught to emit the **canonical form**; humans may use the sugar.

4. **Errors are prompts.** Compiler diagnostics are consumed by the model, not just humans. `pedroc` offers a structured error mode (line, code, message, hint, suggestion) via `pedroc check --json` so a model can self-correct mechanically instead of re-reasoning from scratch.

5. **First-class uncertainty (typed holes).** When the model doesn't know something, it should be able to say so instead of guessing. A `todo "<why>"` hole compiles to an "unresolved intent" report rather than fake code — making hallucination *visible and safe*, and giving the human (or the authoring LLM) an exact list of what to fill in.

6. **`expect` blocks are the model's built-in grader.** They turn intent into an executable contract. The standard authoring loop *requires* the model to write expectations, which are then run automatically. This is a self-test the model designs and the compiler enforces.

7. **Determinism unlocks evaluation and (later) fine-tuning.** Because Pedro → code is exact and `expect` blocks are runnable, we can auto-generate and auto-grade training/eval data. A language with an executable ground truth is ideal for building datasets, benchmarks, and RL loops down the road.

## What this changes about earlier framing

- **"Claude is the compiler" is retired.** Claude is now the **authoring layer** (English → Pedro, error explanation, filling holes). `pedroc` is the compiler.
- **The 9-rule "compiler contract"** in the README is re-scoped: rules about idiomatic output, canonical translation, and determinism are **`pedroc` guarantees**; rules about resolving ambiguity and not inventing capabilities are **authoring-layer guidelines** for Claude writing Pedro. This is reconciled in `docs/SPEC.md`.

## Roadmap

**Done (v0.1)**
- Language design, README language guide, `docs/cookbook.md` (22 verified algorithms).
- `pedroc`: a real, deterministic compiler (lexer → parser → codegen) for the integer subset — `task`, types, `let`/reassign, `increase/decrease`, `when`/`otherwise`, `while`, `repeat`, arithmetic + readable comparisons, recursion, and `expect` → runnable Python tests. Output proven deterministic (byte-identical across runs) and correct (passes its expectations).

**Shipped since v0.1** (all of the original "Next" list has landed — see [WORKLOG.md](../WORKLOG.md) for dates)
1. **Compiler coverage** grew to the whole cookbook: lists, maps, `record`/`enum`, `for each`, string ops, and the collection operations. `tools/regress.py` compiles *and runs* the corpus as the regression suite.
2. **`pedroc check --json`** — structured diagnostics for the agent loop (line/col, stable codes, hints, `did you mean X?`, unresolved holes, per-expectation results).
3. **Typed holes** (`todo "<why>"`) — first-class uncertainty; compiles to an unresolved-intent report.
4. **Capabilities + the adapter layer** in the compiler (`database`/`email`/`crypto`/`files`), enforced and surface-reported, on **both** backends via swappable reference adapters.
5. **A second target** (TypeScript) — one source, two backends, cross-checked by `check --targets` and `tools/differential.py`.
6. **The authoring skill** — `skills/write-pedro/`, a Claude Code skill for English → Pedro that runs `pedroc` in the loop and self-corrects from its errors.

**Next** (see WORKLOG.md roadmap for the authoritative, prioritized list)
- The remaining capability verbs — `http` (`http get`/`http post`), `time` (`now`/`today`), `random` (`random whole from … to …`); `time`/`random` must be built deterministic (fixed clock / seeded RNG) to preserve `check` reproducibility.
- Modules (`use "file.pedro"`).
7. **`docs/SPEC.md`** — the normative spec, reconciled with everything above.

## The one-line summary

> Put the LLM where fuzziness is a feature (understanding intent) and a real compiler where correctness is non-negotiable (generating code). Pedro is the verifiable contract in between — and the compiler is what makes the LLM reliable.
