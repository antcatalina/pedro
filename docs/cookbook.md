# The Pedro Cookbook

A growing library of classic algorithms written in Pedro. It has two jobs:

1. **Teach the language by example** — humans and Claude both learn Pedro faster from worked programs than from a grammar.
2. **Anchor the compiler** — the more idiomatic patterns Claude has seen in-context, the more consistently it compiles.

> **Every algorithm here is machine-verified.** Each one was compiled (to Python) and run against its `expect` block. The verification harness lives in `build/cookbook_check.py`; at the time of writing all **22 algorithms pass ✓**.

All examples target `python`, but the same source retargets — change the `target:` line and recompile.

## Contents

- [Constructs used in this cookbook](#constructs-used-in-this-cookbook)
- [Numbers & math](#numbers--math) — factorial, fibonacci, gcd, is_prime, sum_of_digits, fizzbuzz
- [Text](#text) — reverse_text, is_palindrome, count_vowels, word_count, is_anagram
- [Searching](#searching) — index_of, binary_search
- [Sorting](#sorting) — bubble_sort, quicksort, merge_sort
- [Collections](#collections) — maximum, average, unique
- [Recursion & dynamic programming](#recursion--dynamic-programming) — fibonacci_fast, min_coins
- [Graphs](#graphs) — shortest_hops (BFS)
- [Data modeling](#data-modeling) — tickets (record + enum)

---

## Constructs used in this cookbook

Beyond the core language guide in the [README](../README.md), the algorithms below use these forms. Each has a single canonical meaning, so they stay deterministic.

### Ranges

| Form | Meaning |
|---|---|
| `numbers from a to b` | inclusive list of wholes `[a, … , b]`; empty when `a > b` |

### List operations

| Form | Meaning |
|---|---|
| `count of list` | number of items (length) |
| `item at i in list` | element at 0-based index `i` |
| `first of list` / `last of list` | first / last element |
| `take n from list` | the first `n` items |
| `drop n from list` | everything except the first `n` items |
| `add x to list` | append `x` (in place) |
| `a followed by b` | concatenation (of lists or of text) |
| `copy of list` | a shallow copy |
| `swap items at i and j in list` | exchange two elements (in place) |
| `sort list` | ascending natural order (for lists of scalars) |
| `characters of text` | list of single-character texts |
| `filter x in list where cond` | list of matches |
| `count x in list where cond` | number of matches |
| `collect expr for each x in list` | build a new list (map / comprehension) |
| `sum of expr for each x in list` | total |
| `x in list` / `x not in list` | membership |

### Text operations

| Form | Meaning |
|---|---|
| `for each letter in text` | iterate characters |
| `char in text` | character / substring membership |
| `split text by sep` | list of text pieces |
| `"{x} and {y}"` | interpolation |

### Map operations

| Form | Meaning |
|---|---|
| `empty map of K to V` | a new empty map |
| `m[k]` | value at key `k` |
| `set m[k] to v` | assign |
| `k in m` | key membership |

---

## Numbers & math

### factorial — `n!` recursively ✓

```pedro
task factorial(n: whole) returns whole:
    when n is at most 1:
        return 1
    return n * factorial(n - 1)

expect:
    factorial(0) == 1
    factorial(5) == 120
```

### fibonacci — the nth Fibonacci number, iteratively ✓

```pedro
task fibonacci(n: whole) returns whole:
    let previous = 0
    let current = 1
    repeat n times:
        let next = previous + current
        previous = current
        current = next
    return previous

expect:
    fibonacci(0) == 0
    fibonacci(1) == 1
    fibonacci(10) == 55
```

### gcd — greatest common divisor (Euclid) ✓

```pedro
task gcd(a: whole, b: whole) returns whole:
    while b is not 0:
        let temp = b
        b = a mod b
        a = temp
    return a

expect:
    gcd(48, 18) == 6
    gcd(17, 5) == 1
```

### is_prime — primality test up to √n ✓

```pedro
task is_prime(n: whole) returns flag:
    when n is at most 1:
        return false
    let divisor = 2
    while divisor * divisor is at most n:
        when n is divisible by divisor:
            return false
        increase divisor by 1
    return true

expect:
    is_prime(1) == false
    is_prime(2) == true
    is_prime(97) == true
    is_prime(100) == false
```

### sum_of_digits — add up a number's digits ✓

```pedro
task sum_of_digits(n: whole) returns whole:
    let total = 0
    let remaining = n
    while remaining is greater than 0:
        increase total by remaining mod 10
        remaining = remaining div 10
    return total

expect:
    sum_of_digits(0) == 0
    sum_of_digits(1234) == 10
```

### fizzbuzz — the classic, as a list ✓

```pedro
task fizzbuzz(n: whole) returns list of text:
    let result = []
    for each i in numbers from 1 to n:
        when i is divisible by 15:
            add "FizzBuzz" to result
        when i is divisible by 3:
            add "Fizz" to result
        when i is divisible by 5:
            add "Buzz" to result
        otherwise:
            add (i as text) to result
    return result

expect:
    fizzbuzz(5) == ["1", "2", "Fizz", "4", "Buzz"]
```

---

## Text

### reverse_text — reverse a string ✓

```pedro
task reverse_text(input: text) returns text:
    let result = ""
    for each letter in input:
        result = "{letter}{result}"
    return result

expect:
    reverse_text("abc") == "cba"
```

### is_palindrome — reads the same forwards and back ✓

```pedro
task is_palindrome(input: text) returns flag:
    return input is reverse_text(input)

expect:
    is_palindrome("racecar") == true
    is_palindrome("hello") == false
```

### count_vowels — count the vowels in a string ✓

```pedro
task count_vowels(input: text) returns whole:
    let vowels = "aeiou"
    let total = 0
    for each letter in input:
        when letter in vowels:
            increase total by 1
    return total

expect:
    count_vowels("hello") == 2
```

### word_count — count non-empty words ✓

```pedro
task word_count(sentence: text) returns whole:
    let words = split sentence by " "
    return count of (filter word in words where word is not "")

expect:
    word_count("the quick brown fox") == 4
```

### is_anagram — same letters, rearranged ✓

```pedro
task is_anagram(first: text, second: text) returns flag:
    let a = sort characters of first
    let b = sort characters of second
    return a == b

expect:
    is_anagram("listen", "silent") == true
    is_anagram("apple", "pale") == false
```

---

## Searching

### index_of — linear search, returning an index or -1 ✓

```pedro
task index_of(target: whole, items: list of whole) returns whole:
    for each index, item in items:
        when item is target:
            return index
    return -1

expect:
    index_of(30, [10, 20, 30, 40]) == 2
    index_of(99, [10, 20, 30, 40]) == -1
```

### binary_search — search a sorted list in O(log n) ✓

```pedro
task binary_search(target: whole, sorted_items: list of whole) returns whole:
    let low = 0
    let high = (count of sorted_items) - 1
    while low is at most high:
        let mid = (low + high) div 2
        let value = item at mid in sorted_items
        when value is target:
            return mid
        when value is less than target:
            low = mid + 1
        otherwise:
            high = mid - 1
    return -1

expect:
    binary_search(30, [10, 20, 30, 40, 50]) == 2
    binary_search(35, [10, 20, 30, 40, 50]) == -1
```

---

## Sorting

### bubble_sort — the simple imperative sort ✓

```pedro
task bubble_sort(items: list of whole) returns list of whole:
    let result = copy of items
    let n = count of result
    repeat n times:
        for each i in numbers from 0 to n - 2:
            when (item at i in result) is greater than (item at i + 1 in result):
                swap items at i and i + 1 in result
    return result

expect:
    bubble_sort([3, 1, 2]) == [1, 2, 3]
```

### quicksort — divide and conquer, functional style ✓

```pedro
task quicksort(items: list of whole) returns list of whole:
    when count of items is at most 1:
        return items
    let pivot = first of items
    let rest = drop 1 from items
    let smaller = filter x in rest where x is at most pivot
    let larger = filter x in rest where x is greater than pivot
    return quicksort(smaller) followed by [pivot] followed by quicksort(larger)

expect:
    quicksort([3, 1, 4, 1, 5, 9, 2, 6]) == [1, 1, 2, 3, 4, 5, 6, 9]
```

### merge_sort — split, sort halves, merge ✓

```pedro
task merge_sort(items: list of whole) returns list of whole:
    when count of items is at most 1:
        return items
    let middle = (count of items) div 2
    let left = merge_sort(take middle from items)
    let right = merge_sort(drop middle from items)
    return merge(left, right)

task merge(left: list of whole, right: list of whole) returns list of whole:
    let result = []
    let i = 0
    let j = 0
    while i is less than (count of left) and j is less than (count of right):
        let a = item at i in left
        let b = item at j in right
        when a is at most b:
            add a to result
            increase i by 1
        otherwise:
            add b to result
            increase j by 1
    return result followed by (drop i from left) followed by (drop j from right)

expect:
    merge_sort([5, 2, 4, 1, 3]) == [1, 2, 3, 4, 5]
```

---

## Collections

### maximum — largest element, failing on empty ✓

```pedro
task maximum(items: list of whole) returns whole:
    when items is empty:
        fail with "cannot take the maximum of an empty list"
    let best = first of items
    for each item in items:
        when item is greater than best:
            best = item
    return best

expect:
    maximum([3, 7, 2, 9, 4]) == 9
    maximum([]) fails with "cannot take the maximum of an empty list"
```

### average — mean of a list of numbers ✓

```pedro
task average(items: list of number) returns number:
    when items is empty:
        return 0
    return (sum of item for each item in items) / (count of items)

expect:
    average([2, 4, 6]) == 4
```

### unique — drop duplicates, keep order ✓

```pedro
task unique(items: list of whole) returns list of whole:
    let seen = []
    for each item in items:
        when item not in seen:
            add item to seen
    return seen

expect:
    unique([1, 2, 2, 3, 3, 3]) == [1, 2, 3]
```

---

## Recursion & dynamic programming

### fibonacci_fast — memoized Fibonacci with a map ✓

```pedro
task fibonacci_fast(n: whole) returns whole:
    let cache = empty map of whole to whole
    return fib_helper(n, cache)

task fib_helper(n: whole, cache: map of whole to whole) returns whole:
    when n is at most 1:
        return n
    when n in cache:
        return cache[n]
    let value = fib_helper(n - 1, cache) + fib_helper(n - 2, cache)
    set cache[n] to value
    return value

expect:
    fibonacci_fast(30) == 832040
```

### min_coins — fewest coins to make an amount (DP), or -1 ✓

```pedro
task min_coins(amount: whole, coins: list of whole) returns whole:
    let unreachable = amount + 1
    let best = [0]                    # best[value] = fewest coins to make `value`
    for each value in numbers from 1 to amount:
        let fewest = unreachable
        for each coin in coins:
            when coin is at most value:
                let candidate = 1 + (item at (value - coin) in best)
                when candidate is less than fewest:
                    fewest = candidate
        add fewest to best
    let answer = item at amount in best
    when answer is greater than amount:
        return -1
    return answer

expect:
    min_coins(11, [1, 2, 5]) == 3
    min_coins(3, [2]) == -1
```

---

## Graphs

### shortest_hops — fewest edges between two nodes (BFS) ✓

```pedro
task shortest_hops(graph: map of text to list of text, start: text, goal: text) returns whole:
    let frontier = [start]
    let visited = [start]
    let distance = 0
    while frontier is not empty:
        let next_frontier = []
        for each node in frontier:
            when node is goal:
                return distance
            for each neighbor in graph[node]:
                when neighbor not in visited:
                    add neighbor to visited
                    add neighbor to next_frontier
        frontier = next_frontier
        increase distance by 1
    return -1

expect:
    given g = { "a": ["b", "c"], "b": ["d"], "c": ["d"], "d": [] }
    shortest_hops(g, "a", "d") == 2
    shortest_hops(g, "a", "a") == 0
```

---

## Data modeling

### tickets — a `record` and an `enum`, with `match` over variants ✓

Records give you typed, dotted fields (`t.priority`); enums give you named
variants (`Priority.high`). A record literal `{ ... }` is typed by context —
where a `Ticket` is expected it becomes one, and omitted fields fall back to the
record's declared defaults.

```pedro
enum Priority:
    low
    medium
    high

record Ticket:
    title: text
    priority: Priority = Priority.medium
    done: flag = false

task is_urgent(t: Ticket) returns flag:
    return t.priority is Priority.high and not t.done

task open_count(tickets: list of Ticket) returns whole:
    return count t in tickets where not t.done

task promote(t: Ticket) returns Priority:
    match t.priority:
        case Priority.low:
            return Priority.medium
        case Priority.medium:
            return Priority.high
        case otherwise:
            return Priority.high

expect:
    given a = { title: "deploy", priority: Priority.high, done: false }
    given b = { title: "write docs", priority: Priority.low, done: true }
    given c = { title: "triage inbox" }
    is_urgent(a) == true
    is_urgent(c) == false
    open_count([a, b, c]) == 2
    promote(c) is Priority.high
    promote(b) is Priority.medium
```

See also `examples/order_total.pedro` — a `record LineItem` priced over a
`list of LineItem`.

---

## Contributing an algorithm

This cookbook is designed to grow. To add one:

1. Write the algorithm in Pedro with an `expect` block.
2. Add its compiled form + assertions to `build/cookbook_check.py` and run it.
3. Only mark it verified (✓) once the harness passes.

Good candidates still to add: selection/insertion sort, two-pointer problems, sliding-window,
depth-first search, topological sort, Dijkstra, longest-common-subsequence, knapsack,
run-length encoding, matrix transpose, Roman-numeral conversion, and Caesar cipher.
