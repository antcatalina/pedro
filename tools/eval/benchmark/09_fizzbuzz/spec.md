# FizzBuzz

Write a task that maps a whole number to its FizzBuzz text:

- `"FizzBuzz"` when it is divisible by both 3 and 5,
- `"Fizz"` when it is divisible by 3 (only),
- `"Buzz"` when it is divisible by 5 (only),
- otherwise the number itself, as text.

## Required signature

    task fizzbuzz(n: whole) returns text

## Details

- `fizzbuzz(3)` is `"Fizz"`, `fizzbuzz(5)` is `"Buzz"`, `fizzbuzz(15)` is `"FizzBuzz"`.
- `fizzbuzz(7)` is `"7"` (the number converted to text).

Hint: convert a whole number to text with `n as text`.
