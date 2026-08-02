"""Content hashing for tamper-evident generated output.

`pedroc` stamps a short hash of the **Pedro source** into the banner of every
generated file. The hash is over the source, not the generated output, so it is
stable across a compiler version (same source -> same hash -> byte-identical
output). `pedroc verify` recomputes it from the current `.pedro` source and
compares it to the banner to detect two distinct kinds of drift:

- the source changed since the file was generated (stale output -- rebuild it), or
- the generated file was hand-edited after the fact (someone bypassed pedroc).

Keep this deterministic and dependency-free: same bytes in, same digest out.
"""
import hashlib
import re

# 12 hex chars (48 bits) of SHA-256: short enough to sit unobtrusively in the
# banner, wide enough that an accidental collision is not a practical concern.
HASH_LEN = 12

# The stamped banner is a compiler contract (README rule 8). It carries the
# source hash so `pedroc verify` can detect drift. Keep this the single source
# of truth for both rendering (codegen) and parsing (verify).
_BANNER_RE = re.compile(
    r"Generated from (?P<filename>.+?) by pedroc \S+ "
    r"\(target: (?P<target>[^)]+)\) source-hash: (?P<hash>[0-9a-f]+|unknown)\."
)


def source_hash(source):
    """Return the short hex content hash of a Pedro *source* string.

    Deterministic and encoding-stable: hashes the UTF-8 bytes of the source.
    """
    if isinstance(source, str):
        source = source.encode("utf-8")
    return hashlib.sha256(source).hexdigest()[:HASH_LEN]


def banner(comment, filename, target, src_hash):
    """Render the 'do not edit by hand' banner as a `comment`-prefixed line.

    `comment` is the target's line-comment token (`#` for Python, `//` for TS).
    `src_hash` is the short source hash from `source_hash`; None is stamped as
    `unknown` (only happens for callers that don't have the source, never the
    real build/`check` paths).
    """
    h = src_hash if src_hash else "unknown"
    return (f"{comment} Generated from {filename} by pedroc v0.1 "
            f"(target: {target}) source-hash: {h}. Do not edit by hand.")


def parse_banner(generated_text):
    """Extract the stamped fields from a generated file's banner.

    Returns a dict `{"filename", "target", "hash"}`, or None if the text has no
    recognizable pedroc banner (not pedroc-generated, or an older compiler that
    predates the source-hash field).
    """
    m = _BANNER_RE.search(generated_text)
    if not m:
        return None
    return {"filename": m.group("filename"),
            "target": m.group("target"),
            "hash": m.group("hash")}
