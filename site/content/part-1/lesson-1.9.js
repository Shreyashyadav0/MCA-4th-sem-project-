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
  "concept_md": "### Iterable, iterator, generator\n\nAn **iterable** is something you can loop over. An **iterator** is the object that walks it, with `__next__`. A **generator** is the easy way to write an iterator: any function containing `yield` returns one.\n\n```python\ndef added_lines(diff):\n    for line in diff.splitlines():\n        if line.startswith(\"+\"):\n            yield line[1:]\n```\n\nNothing runs when you call it. The body runs one step at a time, each time the consumer asks for the next value, and stops when the function returns.\n\n### Lazy is the point\n\nA diff can be thousands of lines, and `added_lines` never holds more than one of them. The parser in `app/parser.py` is the eager counterpart: `parse_diff` splits the raw text once, builds a `FileDiff` per file, and returns the whole bundle. Eager is the right choice there because anchoring needs the complete structure; generators are the right choice when a consumer only needs one item at a time.\n\n### A generator is consumed once\n\n```python\nlines = added_lines(DIFF)\nlist(lines)   # ['added one', 'added two']\nlist(lines)   # []\n```\n\nThe second call is empty, because the generator is exhausted. When you need to loop twice, materialise it once: `lines = list(added_lines(DIFF))`.\n\n### Generator expressions\n\nThis is the lazy cousin of the comprehension in lesson 1.2: same shape, one item at a time.\n\n`sum(len(line) for line in lines)` is a generator expression: same laziness, no function. It is the right tool when the loop exists only to feed a single call.\n\n### Reading the parser with this in mind\n\n`parse_diff` returns a `DiffBundle` of `FileDiff` objects, each with `hunks`, each with `lines`. Derived values are computed on demand rather than stored: `added_line_count` and `added_line_numbers` are `@property` on `FileDiff`, and `Hunk.added_lines` is a property listing one hunk's new line numbers. None of them caches, so none of them can go stale.",
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
        "When the function is called, all at once, like any other call, not when it is decorated",
        "When the module is imported, before anything calls it",
        "When the generator object is finally garbage collected",
        "One step at a time, each time the consumer asks for the next value"
      ],
      "answer": 3,
      "why": "Calling it only builds the generator; the body advances on each `next()`, which is what keeps memory proportional to one item."
    },
    {
      "q": "You loop over the same generator twice and the second loop is empty. Why?",
      "options": [
        "A bug in Python",
        "A generator is consumed once",
        "The loop variable was reused",
        "The generator needs to be restarted manually"
      ],
      "answer": 1,
      "why": "It is an iterator, not a collection: once exhausted it stays exhausted, so a second pass needs `list(...)` first."
    },
    {
      "q": "`parse_diff` returns the whole `DiffBundle` at once rather than yielding files. Why is that the right choice here?",
      "options": [
        "Because anchoring needs the complete bundle",
        "Because Python cannot yield from inside a recursive parser",
        "Because generators are slower than lists for inputs this small",
        "Because the diff is always small enough to fit in memory"
      ],
      "answer": 0,
      "why": "A finding is anchored by looking up a line across the finished bundle, so the bundle has to exist before anchoring starts — laziness would buy nothing and cost a second pass."
    }
  ],
  "try_it": {
    "prompt": "Change `added_lines` to yield only the added lines that are not blank, then count them. Print the generator's type first, before consuming it.",
    "starter": "def added_lines(diff):\n    for line in diff.splitlines():\n        if line.startswith(\"+\"):\n            yield line[1:]\n",
    "solution": "DIFF = \"@@ -1,3 +1,4 @@\\n context\\n+added one\\n+\\n+added two\\n\"\n\n\ndef added_lines(diff):\n    for line in diff.splitlines():\n        if line.startswith(\"+\"):\n            text = line[1:]\n            if text.strip():\n                yield text\n\n\nstream = added_lines(DIFF)\nprint(type(stream).__name__)\nprint(list(stream))\n",
    "explanation": "It prints `generator` then `['added one', 'added two']`: the blank added line is skipped. Note the `+` of the diff marker is stripped before the blank check, which is the order that matters."
  },
  "exercise": {
    "prompt": "Predict the output before you run it: an outer generator that yields an INNER generator for each starting number, each inner one yielding two values.",
    "hint": "The outer loop hands you generators, so you need an inner loop before you see numbers.",
    "solution": "def pairs():\n    for start in (1, 3):\n        yield (start, start + 1)\n\n\ndef streams():\n    for start in (1, 3):\n        yield (value for value in (start, start + 1))\n\n\nfor inner in pairs():\n    print(inner)\n\nfor inner in streams():\n    print([value for value in inner])\n",
    "explanation": "The first loop prints `(1, 2)` and `(3, 4)` — tuples, so no inner loop is needed. The second yields generator objects, which print as `<generator object ...>` unless you iterate them; the list comprehension is what makes the numbers visible. Two generators nested is a shape you have to unwrap deliberately."
  },
  "common_mistakes": [
    "Looping over an exhausted generator and concluding it is empty rather than spent.",
    "Returning a list from a function that should stream, when the caller only needs one pass.",
    "Assuming a generator's body has run by the time the call returns — it has not."
  ],
  "project_links": [
    {
      "label": "Hunk and FileDiff: derived values as properties that recompute",
      "path": "app/parser.py",
      "lines": "123-190"
    },
    {
      "label": "parse_diff — the entry point that walks the diff once",
      "path": "app/parser.py",
      "lines": "343-500"
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
