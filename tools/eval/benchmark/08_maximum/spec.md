# Maximum of a list

Write a task that returns the largest number in a list. If the list is EMPTY, the
task must `fail with "empty list"` (there is no maximum to return).

## Required signature

    task maximum(xs: list of whole) returns whole

## Details

- `maximum([3, 1, 4, 1, 5, 9, 2, 6])` is `9`.
- `maximum([42])` is `42`.
- `maximum([])` must fail with the exact message `"empty list"`.
