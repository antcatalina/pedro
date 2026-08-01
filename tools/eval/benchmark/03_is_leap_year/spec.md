# Leap year

Write a task that decides whether a Gregorian calendar year is a leap year.

A year is a leap year when it is divisible by 4, EXCEPT that years divisible by 100
are not leap years UNLESS they are also divisible by 400.

## Required signature

    task is_leap_year(year: whole) returns flag

## Details

- `2000` is a leap year (divisible by 400).
- `1900` is not (divisible by 100 but not 400).
- `2024` is a leap year (divisible by 4, not by 100).
- `2023` is not.
