# Initials

Write a task that returns the initials of a full name: the first character of each
space-separated word, concatenated in order.

## Required signature

    task initials(full_name: text) returns text

## Details

- `initials("Ada Lovelace")` is `"AL"`.
- `initials("Grace Brewster Hopper")` is `"GBH"`.
- A single-word name yields a single character: `initials("Plato")` is `"P"`.
- You may assume words are separated by single spaces and none are empty.

Hint: `split full_name by " "` gives the words, and `characters of word` gives a
word's characters as a list.
