"""pedroc permissions — derive an agent-harness permission manifest from a Pedro
program's DECLARED capability surface.

A Pedro program is pure until it declares `use capability <name>`; that set of
declarations is its auditable blast radius (see `pedroc/capabilities.py`). This
module turns that surface into a ready-to-use permission block for an agent
harness — today, a Claude Code `settings.json`-shaped `permissions.allow` list.

The manifest is DERIVED, never hand-maintained: it is a pure function of the
program's declarations, so regenerating it from the same source is byte-identical
(the same determinism guarantee as codegen). A program that declares NO
capabilities emits an empty, no-op manifest.

The mapping is deliberately SIMPLE and documented (README + docs/language-card.md)
— a starting bridge between Pedro's effect surface and a harness's tool policy,
not an exhaustive policy engine. Local-only capabilities (crypto/time/random) do
no external I/O, so they justify no permission rule and map to nothing.
"""
import json

from .lexer import tokenize
from .parser import Parser
from .annotate import annotate
from .capabilities import check_capabilities

# The mapping table. Each declared capability -> the Claude Code permission rules
# it justifies, as `settings.json` permission entries ("Tool" or "Tool(scope)").
# Canonical (matches CAPABILITY_ORDER); local-only capabilities map to [].
CAPABILITY_RULES = {
    # outbound network: fetch tools + common HTTP CLIs
    "http": ["WebFetch", "Bash(curl:*)", "Bash(wget:*)"],
    # a database client, scoped to the adapter's configured connection when set
    "database": ["Bash(psql:*)"],
    # sending mail via the mail transfer agent
    "email": ["Bash(sendmail:*)"],
    # filesystem access (the `files` verb reads/writes paths at runtime, so the
    # grant is not statically path-scoped — a real policy could tighten this)
    "files": ["Read", "Write", "Edit"],
    # local-only computation — no external permission needed
    "time": [],
    "crypto": [],
    "random": [],
}


def _parse(source, filename):
    tokens = tokenize(source)
    program = Parser(tokens, filename).parse()
    annotate(program)  # sets record-literal types; permissions only need the surface
    return program


def permission_manifest(source, filename="<pedro>"):
    """Return (surface, rules): the program's declared capabilities in canonical
    order, and the flat, deduped, canonical list of permission rules they justify.
    An undeclared capability contributes nothing — the rules are a pure function of
    the declared surface."""
    program = _parse(source, filename)
    surface, _errors = check_capabilities(program)  # surface = declared & known
    rules = []
    for cap in surface:
        for rule in CAPABILITY_RULES.get(cap, []):
            if rule not in rules:
                rules.append(rule)
    return surface, rules


def render(source, filename="<pedro>", fmt="claude-settings"):
    """Render the permission manifest as pretty-printed JSON. `claude-settings`
    emits a settings.json-shaped `{"permissions": {"allow": [...]}}` block droppable
    straight into a Claude Code config; `json` emits an auditable breakdown that
    shows which capability justified which rule. Deterministic: same source -> same
    bytes."""
    surface, rules = permission_manifest(source, filename)
    if fmt == "claude-settings":
        doc = {"permissions": {"allow": rules}}
    elif fmt == "json":
        doc = {
            "capabilities": surface,
            "allow": rules,
            "byCapability": {c: CAPABILITY_RULES.get(c, []) for c in surface},
        }
    else:
        raise ValueError(
            f"unknown format {fmt!r}; available: claude-settings, json"
        )
    return json.dumps(doc, indent=2)
