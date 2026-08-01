# Absolute difference

Write a task that returns the absolute (non-negative) difference between two whole
numbers — how far apart they are, regardless of which is larger.

## Required signature

    task abs_diff(a: whole, b: whole) returns whole

## Details

- `abs_diff(7, 3)` and `abs_diff(3, 7)` are both `4`.
- `abs_diff(n, n)` is `0` for every `n`.
- The result is never negative.
