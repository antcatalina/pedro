# The Pedro Cookbook

A growing library of classic algorithms written in Pedro. It has two jobs:

1. **Teach the language by example** — humans and Claude both learn Pedro faster from worked programs than from a grammar.
2. **Anchor the compiler** — the more idiomatic patterns Claude has seen in-context, the more consistently it compiles.

> **Every algorithm here is machine-verified.** Each one is compiled and run against its `expect` block as part of the corpus regression, `python tools/regress.py` (Python plus the TypeScript backend via the differential lane — capability programs included). At the time of writing all **36 algorithms pass ✓** on every available backend.

All examples target `python`, but the same source retargets — change the `target:` line and recompile.

## Contents

- [Constructs used in this cookbook](#constructs-used-in-this-cookbook)
- [Numbers & math](#numbers--math) — factorial, fibonacci, gcd, is_prime, sum_of_digits, fizzbuzz
- [Text](#text) — reverse_text, is_palindrome, count_vowels, word_count, is_anagram
- [Searching](#searching) — index_of, binary_search
- [Sorting](#sorting) — bubble_sort, quicksort, merge_sort, selection_sort, insertion_sort
- [Collections](#collections) — maximum, average, unique
- [Arrays & matrices](#arrays--matrices) — transpose, sliding_window_max
- [Recursion & dynamic programming](#recursion--dynamic-programming) — fibonacci_fast, min_coins, lcs_length, knapsack
- [Graphs](#graphs) — shortest_hops (BFS), depth_first (DFS), topological_sort, dijkstra
- [Codecs](#codecs) — rle_encode/decode, caesar cipher
- [Data modeling](#data-modeling) — tickets (record + enum), inventory (database CRUD), journal (files capability)
- [Property-based checks](#property-based-checks) — `for all n from a to b: …`

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

### selection_sort — repeatedly select the smallest remaining ✓

Scan the unsorted tail for its minimum and swap it into place. The `for all`
property checks the result keeps its length for every input size up to 40.

```pedro
task selection_sort(items: list of whole) returns list of whole:
    let result = copy of items
    let n = count of result
    for each i in numbers from 0 to n - 1:
        let min_index = i
        for each j in numbers from i + 1 to n - 1:
            when (item at j in result) is less than (item at min_index in result):
                min_index = j
        swap items at i and min_index in result
    return result

expect:
    selection_sort([5, 4, 3, 2, 1]) == [1, 2, 3, 4, 5]
    selection_sort([]) == []
    for all n from 0 to 40: count of selection_sort(numbers from 0 to n) == n + 1
```

### insertion_sort — grow a sorted prefix, swapping each new item down ✓

```pedro
task insertion_sort(items: list of whole) returns list of whole:
    let result = copy of items
    let n = count of result
    for each i in numbers from 1 to n - 1:
        let j = i
        while j is greater than 0 and (item at j - 1 in result) is greater than (item at j in result):
            swap items at j - 1 and j in result
            decrease j by 1
    return result

expect:
    insertion_sort([9, 7, 8, 6, 5]) == [5, 6, 7, 8, 9]
    insertion_sort([42]) == [42]
```

The full file is `examples/cookbook/sorting_more.pedro`.

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

## Arrays & matrices

### transpose — turn a matrix's rows into columns ✓

A matrix is a `list of list of whole`. Read cell `(i, j)` by nesting the indexer:
`item at j in (item at i in matrix)`.

```pedro
task transpose(matrix: list of list of whole) returns list of list of whole:
    when matrix is empty:
        return []
    let rows = count of matrix
    let cols = count of (first of matrix)
    let result = []
    for each j in numbers from 0 to cols - 1:
        let new_row = []
        for each i in numbers from 0 to rows - 1:
            add (item at j in (item at i in matrix)) to new_row
        add new_row to result
    return result

expect:
    transpose([[1, 2, 3], [4, 5, 6]]) == [[1, 4], [2, 5], [3, 6]]
    transpose([[1], [2], [3]]) == [[1, 2, 3]]
    transpose([]) == []
```

### sliding_window_max — the maximum of every window of size k ✓

```pedro
task sliding_window_max(items: list of whole, k: whole) returns list of whole:
    let n = count of items
    let result = []
    when k is at most 0 or k is greater than n:
        return result
    for each start in numbers from 0 to n - k:
        let window_max = item at start in items
        for each offset in numbers from 1 to k - 1:
            let value = item at start + offset in items
            when value is greater than window_max:
                window_max = value
        add window_max to result
    return result

expect:
    sliding_window_max([1, 3, -1, -3, 5, 3, 6, 7], 3) == [3, 3, 5, 5, 6, 7]
    sliding_window_max([9, 8, 7], 1) == [9, 8, 7]
    sliding_window_max([1, 2], 5) == []
```

The full file is `examples/cookbook/arrays.pedro`.

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

### lcs_length — longest common subsequence (length) ✓

A 2-D DP. Pedro's `set map[key] to` takes a single index, not `table[i][j]`, so we
key a flat map by an interpolated `"row,col"` string and fill every cell before it
is read.

```pedro
task lcs_length(a: text, b: text) returns whole:
    let ca = characters of a
    let cb = characters of b
    let m = count of ca
    let n = count of cb
    let dp = empty map of text to whole
    for each i in numbers from 0 to m:
        for each j in numbers from 0 to n:
            when i is 0 or j is 0:
                set dp["{i},{j}"] to 0
            otherwise:
                when (item at i - 1 in ca) is (item at j - 1 in cb):
                    set dp["{i},{j}"] to dp["{i - 1},{j - 1}"] + 1
                otherwise:
                    let up = dp["{i - 1},{j}"]
                    let left = dp["{i},{j - 1}"]
                    when up is at least left:
                        set dp["{i},{j}"] to up
                    otherwise:
                        set dp["{i},{j}"] to left
    return dp["{m},{n}"]

expect:
    lcs_length("ABCBDAB", "BDCAB") == 4
    lcs_length("abc", "xyz") == 0
```

### knapsack — 0/1 knapsack, maximum value within a capacity ✓

Same flat-map DP over `(item index, remaining capacity)`.

```pedro
task knapsack(weights: list of whole, values: list of whole, capacity: whole) returns whole:
    let n = count of weights
    let dp = empty map of text to whole
    for each c in numbers from 0 to capacity:
        set dp["0,{c}"] to 0
    for each i in numbers from 1 to n:
        let w = item at i - 1 in weights
        let v = item at i - 1 in values
        for each c in numbers from 0 to capacity:
            let without = dp["{i - 1},{c}"]
            when w is at most c:
                let with_item = v + dp["{i - 1},{c - w}"]
                when with_item is greater than without:
                    set dp["{i},{c}"] to with_item
                otherwise:
                    set dp["{i},{c}"] to without
            otherwise:
                set dp["{i},{c}"] to without
    return dp["{n},{capacity}"]

expect:
    knapsack([1, 3, 4, 5], [1, 4, 5, 7], 7) == 9
    knapsack([], [], 10) == 0
```

Both are in `examples/cookbook/dp_more.pedro`.

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

### depth_first — pre-order DFS visit sequence ✓

Written purely functionally: each visit *returns* the extended visited list rather
than mutating shared state, so it behaves identically on every backend.

```pedro
task depth_first(graph: map of text to list of text, start: text) returns list of text:
    return dfs_visit(graph, start, [])

task dfs_visit(graph: map of text to list of text, node: text, visited: list of text) returns list of text:
    when node in visited:
        return visited
    let result = visited followed by [node]
    for each neighbor in graph[node]:
        result = dfs_visit(graph, neighbor, result)
    return result

expect:
    given g = { "a": ["b", "c"], "b": ["d"], "c": [], "d": [] }
    depth_first(g, "a") == ["a", "b", "d", "c"]
```

### topological_sort — order a DAG by dependencies (Kahn) ✓

Count each node's in-degree, start from the zero-in-degree nodes, and peel them off,
decrementing successors as you go.

```pedro
task topological_sort(graph: map of text to list of text, nodes: list of text) returns list of text:
    let indegree = empty map of text to whole
    for each node in nodes:
        set indegree[node] to 0
    for each node in nodes:
        for each neighbor in graph[node]:
            set indegree[neighbor] to indegree[neighbor] + 1
    let ready = filter node in nodes where indegree[node] is 0
    let order = []
    while ready is not empty:
        let node = first of ready
        ready = drop 1 from ready
        add node to order
        for each neighbor in graph[node]:
            set indegree[neighbor] to indegree[neighbor] - 1
            when indegree[neighbor] is 0:
                add neighbor to ready
    return order

expect:
    given d = { "shirt": ["tie", "belt"], "tie": ["jacket"], "belt": ["jacket"], "jacket": [] }
    topological_sort(d, ["shirt", "tie", "belt", "jacket"]) == ["shirt", "tie", "belt", "jacket"]
```

### dijkstra — shortest paths with non-negative weights ✓

Weighted edges are modelled with a small `record Edge`; the map-literal value
`{ to: "b", weight: 1 }` is a record literal typed by the `list of Edge` it lands in.
Each round picks the closest unvisited node and relaxes its edges.

```pedro
record Edge:
    to: text
    weight: whole

task dijkstra(graph: map of text to list of Edge, nodes: list of text, start: text) returns map of text to whole:
    let infinity = 1000000
    let dist = empty map of text to whole
    for each node in nodes:
        set dist[node] to infinity
    set dist[start] to 0
    let visited = []
    repeat count of nodes times:
        let current = ""
        let best = infinity
        for each node in nodes:
            when node not in visited and dist[node] is at most best:
                current = node
                best = dist[node]
        add current to visited
        for each edge in graph[current]:
            let candidate = dist[current] + edge.weight
            when candidate is less than dist[edge.to]:
                set dist[edge.to] to candidate
    return dist

expect:
    given w = { "a": [{ to: "b", weight: 1 }, { to: "c", weight: 4 }], "b": [{ to: "c", weight: 2 }, { to: "d", weight: 5 }], "c": [{ to: "d", weight: 1 }], "d": [] }
    dijkstra(w, ["a", "b", "c", "d"], "a") == { "a": 0, "b": 1, "c": 3, "d": 4 }
```

`depth_first`, `topological_sort`, and `dijkstra` all live in
`examples/cookbook/graphs.pedro`.

---

## Codecs

### rle_encode / rle_decode — run-length encoding ✓

```pedro
task rle_encode(input: text) returns text:
    let chars = characters of input
    when chars is empty:
        return ""
    let result = ""
    let current = first of chars
    let run = 0
    for each ch in chars:
        when ch is current:
            increase run by 1
        otherwise:
            result = "{result}{run}{current}"
            current = ch
            run = 1
    result = "{result}{run}{current}"
    return result

task rle_decode(input: text) returns text:
    let result = ""
    let run = 0
    for each ch in characters of input:
        when ch in "0123456789":
            run = run * 10 + (ch as whole)
        otherwise:
            repeat run times:
                result = "{result}{ch}"
            run = 0
    return result

expect:
    rle_encode("aaabbc") == "3a2b1c"
    rle_decode("3a2b1c") == "aaabbc"
    rle_decode("12x") == "xxxxxxxxxxxx"
```

### caesar cipher — rotate letters by a fixed shift ✓

Pedro has no character-code arithmetic, so we look each letter up in the alphabet
and rotate its index; non-letters pass through. Decrypting is encrypting with the
complementary (non-negative) shift, and a `for all` property proves the round trip.

```pedro
task letter_index(letters: list of text, target: text) returns whole:
    for each i, ch in letters:
        when ch is target:
            return i
    return -1

task caesar_encrypt(input: text, shift: whole) returns text:
    let letters = characters of "abcdefghijklmnopqrstuvwxyz"
    let result = ""
    for each ch in characters of input:
        let idx = letter_index(letters, ch)
        when idx is -1:
            result = "{result}{ch}"
        otherwise:
            let rotated = (idx + shift) mod 26
            result = "{result}{item at rotated in letters}"
    return result

task caesar_decrypt(input: text, shift: whole) returns text:
    return caesar_encrypt(input, 26 - (shift mod 26))

expect:
    caesar_encrypt("hello, world", 3) == "khoor, zruog"
    caesar_decrypt("khoor, zruog", 3) == "hello, world"
    for all n from 0 to 25: caesar_decrypt(caesar_encrypt("pedro", n), n) is "pedro"
```

Both codecs are in `examples/cookbook/codecs.pedro`.

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

### inventory — persistent CRUD over a `record` + `enum` (database capability) ✓

The `database` capability gives a table the full CRUD surface. `insert into t { … }`
stores a row; reads reuse the ordinary collection ops (`find one … in t`); **`update
r in t set f to v`** writes one field of a row you already hold (typically a `find
one` result); **`delete r from t`** removes it. Both `update` and `delete` act on the
row VALUE, not a `where` clause — you look the row up first, then act on it. The
row's `status` field is an `enum`, and `pedroc check` runs the whole round-trip
against the in-memory reference adapters (no real I/O).

```pedro
use capability database

enum Status:
    in_stock
    low
    out

record Item:
    name: text
    quantity: whole
    status: Status
    id: text = ""

table items: Item

task classify(quantity: whole) returns Status:
    when quantity is 0:
        return Status.out
    when quantity is at most 3:
        return Status.low
    return Status.in_stock

task restock(name: text, amount: whole) returns whole:
    let it = find one it in items where it.name is name
    let new_qty = it.quantity + amount
    update it in items set quantity to new_qty
    update it in items set status to classify(new_qty)
    return new_qty

task discard_out(name: text) returns whole:
    let it = find one it in items where it.name is name and it.status is Status.out
    when it is present:
        delete it from items
    return count of items

expect:
    given items is empty
    insert into items { name: "apple", quantity: 5, status: classify(5) } is present
    restock("apple", 3) == 8
    discard_out("apple") == 1
```

The full example (`examples/cookbook/inventory.pedro`) also proves `sell` driving an
item to `Status.out` and `discard_out` then deleting it. Because `update`/`delete`
route through the declared capability, the effect stays part of the program's
auditable surface — `pedroc check --json` reports `"capabilities":["database"]`.

### journal — a persisted key/value store (files capability) ✓

The `files` capability adds `write <text> to file <path>` and `read file <path>`.
In `pedroc check` these run against an in-memory reference filesystem (no real I/O);
a project's own adapter would hit the real disk behind the same names. A write is
visible to a later read, so a save/load round-trip — including an overwrite — works
end to end.

```pedro
target: python

use capability files

task save(path: text, value: text) returns text:
    write value to file path
    return value

task load(path: text) returns text:
    return read file path

expect:
    save("motd.txt", "be excellent") == "be excellent"
    load("motd.txt") == "be excellent"
    given overwrite = save("motd.txt", "party on")
    load("motd.txt") == "party on"
```

`pedroc check --json` reports `"capabilities":["files"]` — the whole blast radius,
visible before the program runs. (`examples/cookbook/journal.pedro`.)

---

## Property-based checks

`expect:` blocks aren't limited to hand-picked examples. A **property** —
`for all <name> from <a> to <b>: <flag expression>` — asserts that something holds
for *every* integer in an inclusive range. `pedroc check` proves it by brute force:
it enumerates the range, evaluates the property at each value, and reports the first
failure as `counterexample: <name>=<v>, got false`. Pedro is not a theorem prover,
so ranges stay bounded (over **10000** values is refused — raise it with
`pedroc check --forall-cap N`). Properties and examples mix freely in one block, and
each property is checked identically on both the Python and TypeScript backends.

```pedro
target: python

task is_even(n: whole) returns flag:
    return n mod 2 == 0

task double(n: whole) returns whole:
    return n + n

task is_prime(n: whole) returns flag:
    when n is at most 1:
        return false
    let d = 2
    while d * d is at most n:
        when n mod d is 0:
            return false
        d = d + 1
    return true

expect:
    is_prime(7)                                          # ordinary example
    is_prime(8) == false

    for all n from 0 to 200: is_even(double(n))          # doubling → even
    for all n from 0 to 50: count of sort numbers from 1 to n == n   # sort keeps length
    for all n from 3 to 100: not is_prime(n) or not is_even(n)       # primes > 2 are odd
```

The full program is `examples/cookbook/properties.pedro`. A deliberately wrong
predicate is caught with the exact offending value — a far stronger correctness
signal for agent-authored logic than a few examples. Good properties to reach for:
a round-trip (`decode(encode(x)) == x`), an invariant (`count of sort(xs) == count of xs`,
`f(x) is at least 0`), or a known relationship (`double(n) == n + n`).

---

## Contributing an algorithm

This cookbook is designed to grow. To add one:

1. Write the algorithm in Pedro with an `expect` block.
2. Add its compiled form + assertions to `build/cookbook_check.py` and run it.
3. Only mark it verified (✓) once the harness passes.

Good candidates still to add: selection/insertion sort, two-pointer problems, sliding-window,
depth-first search, topological sort, Dijkstra, longest-common-subsequence, knapsack,
run-length encoding, matrix transpose, Roman-numeral conversion, and Caesar cipher.
