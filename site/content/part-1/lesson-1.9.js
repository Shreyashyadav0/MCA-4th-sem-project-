/* 1.9 — Iterators and generators, enough to read the parser
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "1.9",
  "part": 1,
  "part_title": "Python fundamentals",
  "title": "Iterators and generators, enough to read the parser",
  "order": 109,
  "duration_min": 20,
  "concept_md": "### Iterable, iterator, generator\n\nAn **iterable** is something you can loop over. An **iterator** is the object that walks it, with `__next__`. A **generator** is the easy way to write an iterator: any function containing `yield` returns one.\n\n```python\ndef added_lines(diff):\n    for line in diff.splitlines():\n        if line.startswith(\"+\"):\n            yield line[1:]\n```\n\nNothing runs when you call it. The body runs one step at a time, each time the consumer asks for the next value, and stops when the function returns.\n\n### Lazy is the point\n\nA diff can be thousands of lines. `added_lines` holds one line at a time, not a list of all of them. The parser in `app/parser.py` walks hunks the same way: it reads a line, decides what kind it is, appends it to the current hunk, and moves on — memory proportional to the diff, not to the file count.\n\n### A generator is consumed once\n\n```python\nlines = added_lines(DIFF)\nlist(lines)   # ['added one', 'added two']\nlist(lines)   # []\n```\n\nThe second call is empty, because the generator is exhausted. When you need to loop twice, materialise it once: `lines = list(added_lines(DIFF))`.\n\n### Generator expressions\n\n`sum(len(line) for line in lines)` is a generator expression: same laziness, no function. It is the right tool when the loop exists only to feed a single call.\n\n### Reading the parser with this in mind\n\n`parse_diff` returns a `DiffBundle` of `FileDiff` objects, each with `hunks`, each with `lines`. Derived values are computed on demand rather than stored: `added_line_count` is a `@property`, and `added_lines()` is a method that walks the hunks and returns the numbers.",
  "code_examples": [
    {
      "id": "1.9-ex-0",
      "lang": "python",
      "caption": "A generator over a diff, and the fact that it is exhausted",
      "code": "DIFF = \"\"\"@@ -1,3 +1,4 @@\n context line\n+added one\n-removed one\n+added two\n\"\"\"\n\n\ndef added_lines(diff: str):\n    for line in diff.splitlines():\n        if line.startswith(\"+\"):\n            yield line[1:]\n\n\nlines = list(added_lines(DIFF))\nprint(len(lines), \"added lines:\", lines)\nprint(\"lazy:\", added_lines(DIFF).__class__.__name__)\n",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "2 added lines: ['added one', 'added two']\nlazy: generator"
    }
  ],
  "quiz": [
    {
      "q": "When does the body of a generator function run?",
      "options": [
        "When the function is called",
        "One step at a time, each time the consumer asks for the next value",
        "When the module is imported",
        "All at once, then cached"
      ],
      "answer": 1,
      "why": "Calling it only builds the generator; the body advances on each `next()`, which is what keeps memory proportional to one item."
    },
    {
      "q": "You loop over the same generator twice and the second loop is empty. Why?",
      "options": [
        "A bug in Python",
        "A generator is consumed once; the second loop has nothing left",
        "The loop variable was reused",
        "The generator needs to be restarted manually"
      ],
      "answer": 1,
      "why": "It is an iterator, not a collection: once exhausted it stays exhausted, so a second pass needs `list(...)` first."
    },
    {
      "q": "Why does a parser walk hunks lazily?",
      "options": [
        "Because yield is faster to type",
        "Because a diff can be large and one line at a time is enough",
        "Because Python forbids lists of lines",
        "Because hunks are immutable"
      ],
      "answer": 1,
      "why": "The parser needs each line once, in order; holding the whole file in memory would cost more and buy nothing."
    }
  ],
  "try_it": {
    "prompt": "Change `added_lines` to yield only the added lines that are not blank, then count them. Print the generator's type first, before consuming it.",
    "starter": "def added_lines(diff):\n    for line in diff.splitlines():\n        if line.startswith(\"+\"):\n            yield line[1:]\n",
    "solution": "DIFF = \"@@ -1,3 +1,4 @@\\n context\\n+added one\\n+\\n+added two\\n\"\n\n\ndef added_lines(diff):\n    for line in diff.splitlines():\n        if line.startswith(\"+\"):\n            text = line[1:]\n            if text.strip():\n                yield text\n\n\nstream = added_lines(DIFF)\nprint(type(stream).__name__)\nprint(list(stream))\n",
    "explanation": "It prints `generator` then `['added one', 'added two']`: the blank added line is skipped. Note the `+` of the diff marker is stripped before the blank check, which is the order that matters."
  },
  "exercise": {
    "prompt": "Predict the output of two nested generators before you run it: an outer generator that yields inner generators, each yielding two numbers.",
    "hint": "The outer loop gives you generators, not numbers, unless you iterate them.",
    "solution": "def pairs():\n    for start in (1, 3):\n        yield (start, start + 1)\n\n\nfor inner in pairs():\n    print(inner)\n",
    "explanation": "It prints `(1, 2)` then `(3, 4)` — the outer generator yields tuples here, so each loop body receives one. If it yielded generators instead, printing would show `<generator object ...>` and you would need an inner loop to see the numbers."
  },
  "common_mistakes": [
    "Looping over an exhausted generator and concluding it is empty rather than spent.",
    "Returning a list from a function that should stream, when the caller only needs one pass.",
    "Assuming a generator's body has run by the time the call returns — it has not."
  ],
  "project_links": [
    {
      "label": "Hunk and FileDiff: derived counts computed on demand",
      "path": "app/parser.py",
      "lines": "160-190"
    },
    {
      "label": "parse_diff — the entry point that walks the diff once",
      "path": "app/parser.py",
      "lines": "343-370"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-2-parser.md — the parser track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-2-parser.md"
    }
  ],
  "glossary_terms": [
    "iterable — anything a `for` loop can walk",
    "iterator — the object with `__next__` that tracks position",
    "generator — a function with `yield`, which returns an iterator",
    "exhausted — a generator that has yielded its last value; further calls give nothing"
  ]
});
