/* 1.3 — Functions, args, kwargs, type hints
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "1.3",
  "part": 1,
  "part_title": "Python fundamentals",
  "title": "Functions, args, kwargs, type hints",
  "order": 103,
  "duration_min": 20,
  "concept_md": "### Four ways to pass arguments\n\n```python\ndef rule(line, severity=\"MEDIUM\"): ...      # positional + default\ndef total(*numbers): ...                    # any number of positionals\ndef make_finding(**fields): ...             # any number of keywords\ndef review(bundle, *, provider=\"auto\"): ...  # keyword-only after the star\n```\n\nThe star is the important one. Everything after `*` must be passed by name, which is how a function with six options stays readable: `review(bundle, provider=\"local\")` says what it means, `review(bundle, \"local\", False)` does not.\n\n### Defaults are evaluated once\n\nA default is built when the `def` runs, not per call. `def add(f, acc=[])` shares one list across every call. Use `None` and build inside.\n\n### Type hints are documentation the tools can check\n\n```python\ndef make_finding(**kw) -> dict[str, str]:\n```\n\nThe return annotation is not decoration: `-> dict[str, str]` tells a reader the values are strings, and `mypy` can prove it. `*args: int` and `**kw: str` annotate the element type, not the tuple or dict.\n\n### On a real signature\n\n`app/engine.py` defines the review entry point with two positional parameters and four keyword-only ones — `provider`, `force_offline`, `min_severity`, `categories` — all defaulted. That is the pattern this lesson teaches, used where it matters: a call site cannot silently pass the wrong option positionally.\n\n### Keyword arguments make boundaries explicit\n\n`make_finding(**kw)` accepts whatever the caller passes, which is convenient and dangerous: an unknown field would sail through. The example below closes that hole by checking the keys against an allow-list — the same discipline `Finding` enforces with `extra=\"forbid\"`, one layer earlier.",
  "code_examples": [
    {
      "id": "1.3-ex-0",
      "lang": "python",
      "caption": "A **kwargs helper with hints, and an allow-list",
      "code": "def make_finding(**kw) -> dict[str, str]:\n    \"\"\"Build a finding-shaped dict, refusing anything that is not a field.\"\"\"\n    allowed = {\"file\", \"line\", \"severity\", \"issue\", \"suggested_fix\"}\n    unknown = set(kw) - allowed\n    if unknown:\n        raise TypeError(f\"unexpected field(s): {sorted(unknown)}\")\n    return {key: str(value) for key, value in kw.items()}\n\n\nfinding = make_finding(file=\"app/db.py\", line=\"3\", severity=\"CRITICAL\", issue=\"Token literal\")\nprint(finding)\nprint(make_finding.__annotations__)\n",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "{'file': 'app/db.py', 'line': '3', 'severity': 'CRITICAL', 'issue': 'Token literal'}\n{'return': dict[str, str]}"
    }
  ],
  "quiz": [
    {
      "q": "What does the `*` in `def review(bundle, *, provider=\"auto\")` change?",
      "options": [
        "Nothing, it is decoration",
        "Every parameter after it must be passed by keyword",
        "It unpacks a tuple",
        "It makes the parameter optional"
      ],
      "answer": 1,
      "why": "A bare star ends the positional parameters, so provider can only be given by name — which is what keeps a six-option call readable."
    },
    {
      "q": "Why is `def add(f, acc=[])` a bug waiting to happen?",
      "options": [
        "Lists cannot be default values",
        "The list is created once, at def time, and shared by every call",
        "It fails on the first call",
        "It copies the list on each call"
      ],
      "answer": 1,
      "why": "Defaults are evaluated when the def runs, so every call appends to the same list and findings leak between reviews."
    },
    {
      "q": "`def make_finding(**kw) -> dict[str, str]` — what does the annotation say?",
      "options": [
        "kw is a dict of str keys and str values",
        "The function returns a dict whose keys and values are strings",
        "The function accepts exactly two arguments",
        "Nothing useful"
      ],
      "answer": 1,
      "why": "The return annotation types the result: str keys, str values. It is what lets a checker catch a caller that expects ints."
    }
  ],
  "try_it": {
    "prompt": "Add a keyword-only `severity` with a default of `\"MEDIUM\"` to `make_finding`, and call it with and without that argument.",
    "starter": "def make_finding(*, severity: str = \"MEDIUM\", **kw) -> dict[str, str]:\n    return {\"severity\": severity, **{k: str(v) for k, v in kw.items()}}\n\nprint(make_finding(file=\"app/db.py\"))\n",
    "solution": "def make_finding(*, severity: str = \"MEDIUM\", **kw) -> dict[str, str]:\n    return {\"severity\": severity, **{k: str(v) for k, v in kw.items()}}\n\nprint(make_finding(file=\"app/db.py\"))\nprint(make_finding(severity=\"CRITICAL\", file=\"app/db.py\"))\n",
    "explanation": "Both calls work; the first gets MEDIUM by default. `severity` is keyword-only, so a positional call would be a TypeError — which is the point of putting it after the star."
  },
  "exercise": {
    "prompt": "Write the signature for `review(diff: str, *, provider: str = \"mock\") -> list[Finding]`, with a docstring that says what the keyword means, and show what happens when someone calls it positionally.",
    "hint": "Import `Finding` from app.models so the annotation resolves, and call it wrong on purpose.",
    "solution": "from app.models import Finding\n\n\ndef review(diff: str, *, provider: str = \"mock\") -> list[Finding]:\n    \"\"\"Review a diff; provider selects mock, local or sarvam.\"\"\"\n    return []\n\n\nprint(review(\"@@\"))\ntry:\n    review(\"@@\", \"local\")\nexcept TypeError as error:\n    print(\"TypeError:\", error)\n",
    "explanation": "The first call returns `[]`; the second raises `TypeError: review() takes 1 positional argument but 2 were given`. That error is the feature: the option cannot be passed in the wrong slot."
  },
  "common_mistakes": [
    "A mutable default argument. `def add(f, acc=[])` builds the list once, so every call shares it.",
    "Dropping the `->` return annotation while annotating every parameter — the return type is the half callers read first.",
    "Annotating `list` where the function only iterates. `Sequence` accepts tuples too, and `Iterable` accepts generators."
  ],
  "project_links": [
    {
      "label": "The real review entry point: two positional, four keyword-only",
      "path": "app/engine.py",
      "lines": "320-345"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-6-engine.md — the engine track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-6-engine.md"
    }
  ],
  "glossary_terms": [
    "keyword-only — a parameter after a bare `*`, callable only by name",
    "**kwargs — a dict of the keyword arguments a function received",
    "annotation — the `: type` and `-> type` hints, checked by tools not by the interpreter",
    "mutable default — a list or dict default evaluated once and shared by every call"
  ]
});
