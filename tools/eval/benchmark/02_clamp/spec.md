# Clamp a value to a range

Write a task that constrains a whole number to an inclusive range `[low, high]`:
values below `low` become `low`, values above `high` become `high`, and values
already inside the range are returned unchanged.

## Required signature

    task clamp(x: whole, low: whole, high: whole) returns whole

## Details

- `clamp(5, 0, 10)` is `5` (already in range).
- `clamp(1, 3, 10)` is `3` (raised to the lower bound).
- `clamp(15, 0, 10)` is `10` (lowered to the upper bound).
- You may assume `low` is at most `high`.
