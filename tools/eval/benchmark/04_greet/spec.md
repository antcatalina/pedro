# Greeting

Write a task that builds a greeting for a name: the text `Hello, ` followed by the
name, followed by a `!`.

## Required signature

    task greet(name: text) returns text

## Details

- `greet("Ada")` is `"Hello, Ada!"`.
- `greet("World")` is `"Hello, World!"`.
- The name is inserted verbatim (no trimming or capitalization).
