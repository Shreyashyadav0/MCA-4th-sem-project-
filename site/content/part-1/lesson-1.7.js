/* 1.7 — Context managers (with)
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "1.7",
  "part": 1,
  "part_title": "Python fundamentals",
  "title": "Context managers (with)",
  "order": 107,
  "duration_min": 15,
  "concept_md": "### What `with` buys you\n\n```python\nwith open(\"notes.txt\", encoding=\"utf-8\") as handle:\n    data = handle.read()\n```\n\nThe file is closed when the block ends — including when it ends by an exception. Written without `with`, the close has to happen in a `finally`, and every early `return` is a chance to forget it.\n\n### The protocol, in two methods\n\nA context manager is anything with `__enter__` and `__exit__`. `__enter__` returns the value bound by `as`; `__exit__` is called on the way out, with the exception details if there was one, and returning a truthy value swallows the exception. Files, database connections and locks all implement it.\n\n### Writing one without a class\n\n`@contextlib.contextmanager` turns a generator into a context manager: everything before `yield` is `__enter__`, everything after is `__exit__`, and the value you `yield` is what `as` binds.\n\n```python\n@contextmanager\ndef timed(label):\n    print(\"enter\", label)\n    try:\n        yield label.upper()\n    finally:\n        print(\"exit\", label)\n```\n\nThe `try/finally` around the `yield` is not optional — it is how cleanup survives an exception inside the block.\n\n### This repository's own style\n\nYou will not find `with open(` in `app/`. It reads files with `pathlib`: `path.read_text(encoding=\"utf-8\")` in `app/cli.py`, which closes the file for you. That is the same discipline one level up — the resource is managed, not remembered. The one place the pattern is written out is a rule's suggested fix in `app/rules.py`, which recommends `with open(...)` to anyone reviewing code that does not use it.",
  "code_examples": [
    {
      "id": "1.7-ex-0",
      "lang": "python",
      "caption": "A file round-trip, then a @contextmanager",
      "code": "from contextlib import contextmanager\n\nwith open(\"notes.txt\", \"w\", encoding=\"utf-8\") as handle:\n    handle.write(\"line one\\n\")\n\nwith open(\"notes.txt\", encoding=\"utf-8\") as handle:\n    print(\"read back:\", repr(handle.read()))\n\n\n@contextmanager\ndef timed(label: str):\n    print(\"enter\", label)\n    try:\n        yield label.upper()\n    finally:\n        print(\"exit\", label)\n\n\nwith timed(\"block\") as name:\n    print(\"inside\", name)\n",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "read back: 'line one\\n'\nenter block\ninside BLOCK\nexit block"
    }
  ],
  "quiz": [
    {
      "q": "What closes the file in `with open(...) as handle:`?",
      "options": [
        "The garbage collector, eventually",
        "The context manager's `__exit__`, on the way out of the block",
        "A call to `handle.close()` you must write",
        "Nothing; the OS does it"
      ],
      "answer": 1,
      "why": "`__exit__` runs when the block ends, including on an exception, which is exactly what a bare open cannot promise."
    },
    {
      "q": "In a `@contextmanager` function, what is the value bound by `as`?",
      "options": [
        "The function itself",
        "Whatever is yielded",
        "The exception, if any",
        "None, always"
      ],
      "answer": 1,
      "why": "The `yield` splits the function into enter and exit, and its value is what `as` receives — here the upper-cased label."
    },
    {
      "q": "Why does the example wrap the `yield` in `try/finally`?",
      "options": [
        "Style",
        "So the cleanup runs even when the block raises",
        "Because yield is illegal otherwise",
        "To return a value"
      ],
      "answer": 1,
      "why": "Without it, an exception inside the `with` block skips the code after the yield and the cleanup never happens."
    }
  ],
  "try_it": {
    "prompt": "Make `timed` print the elapsed time in milliseconds between enter and exit. Use `time.perf_counter()`.",
    "starter": "from contextlib import contextmanager\nimport time\n\n\n@contextmanager\ndef timed(label: str):\n    start = time.perf_counter()\n    yield label\n    print(label, \"took\", round((time.perf_counter() - start) * 1000, 2), \"ms\")\n",
    "solution": "from contextlib import contextmanager\nimport time\n\n\n@contextmanager\ndef timed(label: str):\n    start = time.perf_counter()\n    try:\n        yield label\n    finally:\n        elapsed = (time.perf_counter() - start) * 1000\n        print(label, \"took\", round(elapsed, 2), \"ms\")\n\n\nwith timed(\"sum\"):\n    sum(range(100000))\n",
    "explanation": "The number varies by machine — never quote it as a fact. The `finally` is what makes the timing survive an exception, which is the part worth keeping."
  },
  "exercise": {
    "prompt": "Explain what breaks when a `@contextmanager` function returns instead of yielding exactly once. Try it and read the error.",
    "hint": "A generator that never yields is not a context manager; contextlib checks.",
    "solution": "Returning before any `yield` raises `RuntimeError: generator didn't yield` when the `with` block is entered — `__enter__` calls `next()` and finds nothing. Yielding twice raises `RuntimeError: generator didn't stop` on exit, because the manager must produce exactly one value.",
    "explanation": "The protocol is exactly one yield: the first `next()` is the enter, the second is the exit, and a third has nowhere to go."
  },
  "common_mistakes": [
    "Opening a file without `with`, so an early return leaks the handle.",
    "Returning from inside the `with` block believing the file stays open — it is closed on the way out, which is the point.",
    "Writing `@contextmanager` around a function that yields twice, or not at all."
  ],
  "project_links": [
    {
      "label": "read_source — the repository's pathlib habit instead of `with open`",
      "path": "app/cli.py",
      "lines": "142-168"
    },
    {
      "label": "The rule that recommends `with open(...)` to other people's code",
      "path": "app/rules.py",
      "lines": "1225-1245"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-4-offline-and-config.md — config and file handling",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-4-offline-and-config.md"
    }
  ],
  "glossary_terms": [
    "__enter__ / __exit__ — the two methods the `with` statement calls",
    "@contextmanager — turns a one-yield generator into a context manager",
    "yield — the point where enter ends and exit begins",
    "pathlib — the module this repository reads files with; read_text closes for you"
  ]
});
