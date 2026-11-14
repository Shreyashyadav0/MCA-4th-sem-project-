/* 1.1 — Variables, types, and f-strings
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "1.1",
  "part": 1,
  "part_title": "Python fundamentals",
  "title": "Variables, types, and f-strings",
  "order": 101,
  "duration_min": 15,
  "concept_md": "### The types this repository actually leans on\n\nNine built-in types cover almost every line of `app/`. Knowing which one a value is decides what you can do to it, and what a type error will say when you get it wrong.\n\n| Type | Example | Where you meet it in this repo |\n|---|---|---|\n| `str` | `\"HIGH\"` | severities, file paths, diff lines |\n| `int` | `3` | line numbers, counts, `duration_min` |\n| `float` | `1.25` | benchmark metrics |\n| `bool` | `True` | `runnable`, `extra=\"forbid\"` switches |\n| `None` | `None` | \"no provider configured\", missing optional values |\n| `list` | `[\"a\", \"b\"]` | findings, rules, changed lines |\n| `dict` | `{\"file\": \"app/db.py\"}` | one finding before it becomes a model |\n| `set` | `{\"HIGH\", \"LOW\"}` | membership checks |\n| `tuple` | `(\"sarvam\", \"local\", \"mock\")` | fixed order that must not change |\n\n### A finding is a dict before it is a model\n\nEvery finding arrives from a rule, or from a model, as a dictionary with five keys. An f-string is how the rest of the codebase prints one:\n\n```python\nfinding = {\n    \"file\": \"app/db.py\",\n    \"line\": 3,\n    \"severity\": \"CRITICAL\",\n    \"issue\": \"A GitHub token literal is committed here.\",\n}\n\nprint(f\"{finding['severity']}: {finding['issue']}\")\n```\n\nTwo things to notice. The expression inside the braces is ordinary Python, so dictionary access works — and it fails with `KeyError` when the key is missing, which is the behaviour you want at a boundary. And the quotes around the key are single quotes inside double-quoted f-strings; the other way round has been legal since Python 3.12 but reads badly.\n\n### Format specs do the alignment\n\nAfter a colon inside the braces comes a format spec. `{label:<8}` left-aligns in eight columns, `{value:>8}` right-aligns, `{ratio:.2f}` fixes two decimals, `{count:03d}` zero-pads to three digits.\n\n```python\nfor label, count in ((\"high\", 3), (\"medium\", 2), (\"low\", 0)):\n    print(f\"{label:<8}{count}\")\n```\n\n```text\nhigh    3\nmedium  2\nlow     0\n```\n\n### `None` is compared with `is`\n\n`None` is a singleton. `if value is None` asks the question you mean; `if value == None` asks a question the object can answer for itself, because `==` is a method that a class may override. The same holds for `True` and `False`.\n\n### Mutable default arguments are evaluated once\n\n```python\ndef add(finding, findings=[]):      # the same list, on every call\n    findings.append(finding)\n    return findings\n```\n\nThe default is built when the `def` runs, not when the function is called, so every call shares one list and findings leak between reviews. `def add(finding, findings=None)` and a fresh list inside the body is the fix.\n\n### The contract, in the repository's own words\n\nThe module docstring of `app/models.py` says why a finding has exactly five fields. Quoted, not paraphrased:\n\n```text\n* :class:`Finding` — what the reviewer believes. Exactly five fields, nothing\n  else, ``extra=\"forbid\"``. A stray key from a future LLM response fails at the\n  boundary instead of leaking into a PR comment.\n```",
  "code_examples": [
    {
      "lang": "python",
      "caption": "Print a finding-shaped dict with an f-string",
      "code": "finding = {\n    \"file\": \"app/db.py\",\n    \"line\": 3,\n    \"severity\": \"CRITICAL\",\n    \"issue\": \"A GitHub token literal is committed here.\",\n}\n\nprint(f\"{finding['severity']}: {finding['issue']}\")\nprint(f\"{finding['file']}:{finding['line']} — {finding['severity']}\")\n",
      "runnable": true
    },
    {
      "lang": "python",
      "caption": "Alignment with a format spec — the shape the exercise asks for",
      "code": "for label, count in ((\"high\", 3), (\"medium\", 2), (\"low\", 0)):\n    print(f\"{label:<8}{count}\")\n",
      "runnable": true
    }
  ],
  "try_it": {
    "prompt": "Write `summarize(findings)` that takes a list of finding-shaped dicts and returns one line of counts in the order high, medium, low — for example `3 high, 2 medium, 0 low`.\n\nThe data uses the severities the repository uses, in uppercase: `HIGH`, `MEDIUM`, `LOW`. The sentence you return uses lowercase words.",
    "starter": "findings = [\n    {\"severity\": \"HIGH\"},\n    {\"severity\": \"HIGH\"},\n    {\"severity\": \"HIGH\"},\n    {\"severity\": \"MEDIUM\"},\n    {\"severity\": \"MEDIUM\"},\n]\n\n\ndef summarize(findings):\n    # Return a string like \"3 high, 2 medium, 0 low\"\n    ...\n\n\nprint(summarize(findings))\n",
    "solution": "def summarize(findings):\n    counts = {\"high\": 0, \"medium\": 0, \"low\": 0}\n    for finding in findings:\n        key = finding[\"severity\"].lower()\n        if key in counts:\n            counts[key] += 1\n    return f\"{counts['high']} high, {counts['medium']} medium, {counts['low']} low\"\n",
    "explanation": "A dict of three counters is enough because the output order is fixed and small. `key in counts` also makes the function safe against a severity it does not know about — the repository's ladder has a fourth value, `CRITICAL`, which the real `severity_counts` helper in `app/models.py` handles."
  },
  "exercise": {
    "prompt": "Same function, same input, but return three aligned lines instead of one sentence. Left-align the labels to eight columns so the numbers line up:\n\n```text\nhigh    3\nmedium  2\nlow     0\n```",
    "hint": "A format spec goes after a colon inside the braces: `{label:<8}`. Join the three lines with a newline rather than printing inside the function, so the caller decides what to do with them.",
    "solution": "def summarize(findings):\n    counts = {\"high\": 0, \"medium\": 0, \"low\": 0}\n    for finding in findings:\n        key = finding[\"severity\"].lower()\n        if key in counts:\n            counts[key] += 1\n    return \"\\n\".join(f\"{label:<8}{count}\" for label, count in counts.items())\n",
    "explanation": "Dicts keep insertion order, so `counts.items()` already yields high, medium, low. Returning a string instead of printing keeps the function testable: a test can assert on the value, and nothing in it depends on stdout."
  },
  "common_mistakes": [
    "A mutable default argument: `def add(finding, findings=[])` builds the list once, at def time, so findings leak between reviews. Use `findings=None` and create the list inside the body.",
    "`if severity == None` instead of `if severity is None`. `==` is a method a class can override; `is` is the identity test you actually mean, and it is the only correct one for None, True and False.",
    "A format spec outside the braces: `f\"{label} :<8\"` prints a colon and an 8 as text. The spec goes after a colon inside the braces: `f\"{label:<8}\"`.",
    "Treating an f-string as a template. `f\"{value}\"` is evaluated once, where it is written; a string stored for later keeps the old value."
  ],
  "project_links": [
    {
      "label": "The module docstring — why Finding has exactly five fields (quoted in the concept above)",
      "path": "app/models.py",
      "lines": "1-11"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-1-models.md — the full track this lesson opens",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-1-models.md"
    }
  ],
  "glossary_terms": [
    "f-string — a string literal prefixed with f whose {braces} hold expressions evaluated where it is written",
    "format spec — the part after a colon inside an f-string brace: width, alignment, precision",
    "mutable default argument — a default list or dict built once at def time and shared by every call",
    "identity test — `is`, which asks whether two names point at the same object",
    "dict — insertion-ordered mapping; one finding before it is validated into a model"
  ]
});
