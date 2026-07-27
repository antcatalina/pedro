"""Deterministic "did you mean X?" suggestions by edit distance.

Errors are prompts: when the author writes an unknown identifier or keyword, the
nearest known name is usually the fix. This module is pure and deterministic —
same inputs always yield the same suggestion — so it never breaks the
Pedro->code contract (it only shapes diagnostics, not output).
"""


def edit_distance(a, b):
    """Levenshtein distance between two strings (insert/delete/substitute)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def nearest(word, candidates, max_distance=None):
    """Return the closest candidate to `word`, or None if nothing is close enough.

    A match must be within `max_distance` edits (default: scales with word length —
    ~1/3 of the letters, at least 1, at most 3), which keeps suggestions relevant
    and avoids proposing an unrelated name. Ties break on the shortest, then
    lexicographically smallest candidate, so the result is fully deterministic.
    """
    if not word:
        return None
    if max_distance is None:
        max_distance = max(1, min(3, len(word) // 3 + 1))
    best = None
    best_key = None
    for cand in candidates:
        if cand == word:
            continue
        d = edit_distance(word, cand)
        if d > max_distance:
            continue
        key = (d, len(cand), cand)
        if best_key is None or key < best_key:
            best, best_key = cand, key
    return best
