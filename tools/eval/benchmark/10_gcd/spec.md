# Greatest common divisor

Write a task that returns the greatest common divisor (GCD) of two whole numbers
using the Euclidean algorithm.

## Required signature

    task gcd(a: whole, b: whole) returns whole

## Details

- `gcd(48, 18)` is `6`.
- `gcd(17, 5)` is `1` (coprime).
- `gcd(0, 5)` is `5` (the GCD with 0 is the other number).
