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
  "concept_md": "### The types this repository actually leans on\n\nThese nine built-in types are the ones you meet most often in `app/`. Knowing which one a value is decides what you can do to it, and what a type error will say when you get it wrong.\n\n| Type | Example | Where you meet it in this repo |\n|---|---|---|\n| `str` | `\"HIGH\"` | severities, file paths, diff lines |\n| `int` | `3` | counts, rule totals, `duration_min` in this site's schema |\n| `float` | `1.25` | benchmark metrics |\n| `bool` | `True` | `frozen=True`, `str_strip_whitespace=True` on the model config |\n| `None` | `None` | \"no provider selected\", missing optional values |\n| `list` | `[\"a\", \"b\"]` | findings, rules, changed lines |\n| `dict` | `{\"file\": \"app/db.py\"}` | one finding before it becomes a model |\n| `set` | `{\"HIGH\", \"LOW\"}` | membership checks |\n| `tuple` | `(\"sarvam\", \"local\", \"mock\")` | fixed order that must not change |\n\n### A finding is a dict before it is a model\n\nEvery finding arrives from a rule, or from a model, as a dictionary with five keys — `file`, `line`, `severity`, `issue`, `suggested_fix`. `line` is a **string** in `app/models.py`, because a finding can also cover a range like `\"42-45\"`. An f-string is how the rest of the codebase prints one:\n\n```python\nfinding = {\n    \"file\": \"app/db.py\",\n    \"line\": \"3\",\n    \"severity\": \"CRITICAL\",\n    \"issue\": \"A GitHub token literal is committed here.\",\n    \"suggested_fix\": \"Revoke the token, then read it at runtime.\",\n}\n\nprint(f\"{finding['severity']}: {finding['issue']}\")\n```\n\nTwo things to notice. The expression inside the braces is ordinary Python, so dictionary access works — and it fails with `KeyError` when the key is missing, which is the behaviour you want at a boundary. And the quotes around the key are single quotes inside double-quoted f-strings; the other way round has been legal since Python 3.12 but reads badly.\n\n### Format specs do the alignment\n\nAfter a colon inside the braces comes a format spec. `{label:<8}` left-aligns in eight columns, `{value:>8}` right-aligns, `{ratio:.2f}` fixes two decimals, `{count:03d}` zero-pads to three digits.\n\n```python\nfor label, count in ((\"high\", 3), (\"medium\", 2), (\"low\", 0)):\n    print(f\"{label:<8}{count}\")\n```\n\n```text\nhigh    3\nmedium  2\nlow     0\n```\n\n### `None` is compared with `is`\n\n`None` is a singleton. `if value is None` asks the question you mean; `if value == None` asks a question the object can answer for itself, because `==` is a method that a class may override. The same holds for `True` and `False`.\n\n### Mutable default arguments are evaluated once\n\n```python\ndef add(finding, findings=[]):      # the same list, on every call\n    findings.append(finding)\n    return findings\n```\n\nThe default is built when the `def` runs, not when the function is called, so every call shares one list and findings leak between reviews. `def add(finding, findings=None)` and a fresh list inside the body is the fix.\n\n### The contract, in the repository's own words\n\nThe module docstring of `app/models.py` says why a finding has exactly five fields. Quoted, not paraphrased:\n\n```text\n* :class:`Finding` — what the reviewer believes. Exactly five fields, nothing\n  else, ``extra=\"forbid\"``. A stray key from a future LLM response fails at the\n  boundary instead of leaking into a PR comment.\n```",
  "code_examples": [
    {
      "id": "1.1-ex-0",
      "lang": "python",
      "caption": "A real Finding, imported from app/models.py — press Run",
      "code": "from app.models import Finding, verdict_for\n\nfinding = Finding(\n    file=\"app/db.py\",\n    line=\"3\",\n    severity=\"CRITICAL\",\n    issue=\"A GitHub token literal is committed here.\",\n    suggested_fix=\"Revoke the token, then read it at runtime.\",\n)\n\nprint(f\"{finding.severity.value} {finding.file}:{finding.line}\")\nprint(finding.issue)\nprint(\"verdict:\", verdict_for([finding]))\n",
      "runnable": true,
      "run_tier": "browser",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py"
      ],
      "expected_output": "CRITICAL app/db.py:3\nA GitHub token literal is committed here.\nverdict: block"
    },
    {
      "id": "1.1-ex-1",
      "lang": "python",
      "caption": "Alignment with a format spec, over two validated Finding objects",
      "code": "from app.models import Finding\n\nfindings = [\n    Finding(\n        file=\"app/db.py\",\n        line=\"3\",\n        severity=\"CRITICAL\",\n        issue=\"A GitHub token literal is committed here.\",\n        suggested_fix=\"Revoke the token.\",\n    ),\n    Finding(\n        file=\"app/report.py\",\n        line=\"1\",\n        severity=\"MEDIUM\",\n        issue=\"A public function without full annotations.\",\n        suggested_fix=\"Annotate the parameters and the return type.\",\n    ),\n]\n\nfor finding in findings:\n    print(f\"{finding.severity.value:<10}{finding.file}:{finding.line}\")\n",
      "runnable": true,
      "run_tier": "browser",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py"
      ],
      "expected_output": "CRITICAL  app/db.py:3\nMEDIUM    app/report.py:1"
    }
  ],
  "try_it": {
    "prompt": "Press Run on the first example. Then change the severity to `\"HIGH\"`, press Run again, and then try `\"LOW\"`. The verdict changes; explain the three answers before you read the solution.\n\nThe severities the repository accepts are `LOW`, `MEDIUM`, `HIGH` and `CRITICAL` — anything else is a `ValidationError`, which is the next thing to try.",
    "starter": "from app.models import Finding, verdict_for\n\nfinding = Finding(\n    file=\"app/db.py\",\n    line=\"3\",\n    severity=\"CRITICAL\",        # try \"HIGH\", then \"LOW\", then \"SEVERE\"\n    issue=\"A GitHub token literal is committed here.\",\n    suggested_fix=\"Revoke the token.\",\n)\nprint(f\"{finding.severity.value:<10}{verdict_for([finding])}\")\n",
    "solution": "from app.models import Finding, verdict_for\n\nfor severity in (\"CRITICAL\", \"HIGH\", \"MEDIUM\", \"LOW\"):\n    finding = Finding(\n        file=\"app/db.py\",\n        line=\"3\",\n        severity=severity,\n        issue=\"A GitHub token literal is committed here.\",\n        suggested_fix=\"Revoke the token.\",\n    )\n    print(f\"{severity:<10}{verdict_for([finding])}\")\n",
    "explanation": "`verdict_for` in `app/models.py` blocks on CRITICAL or HIGH, and returns `approve with comments` for MEDIUM or LOW — a LOW finding still produces a comment, which is the difference between `approve` and `approve with comments`. Passing `\"SEVERE\"` raises `ValidationError` instead: `Severity` is an enum with four legal values and the model validates at the boundary."
  },
  "exercise": {
    "prompt": "Print one aligned line per finding — the severity left-aligned to ten columns, then `file:line` — for the two findings in the second example:\n\n```text\nCRITICAL  app/db.py:3\nMEDIUM    app/report.py:1\n```\n\nRun it, do not copy it: the alignment must come out of your own format spec.",
    "hint": "A format spec goes after a colon inside the braces: `{value:<10}`. `severity` is an enum, so print `finding.severity.value` — printing the enum itself gives you `Severity.CRITICAL`.",
    "solution": "from app.models import Finding\n\nfindings = [\n    Finding(\n        file=\"app/db.py\",\n        line=\"3\",\n        severity=\"CRITICAL\",\n        issue=\"A GitHub token literal is committed here.\",\n        suggested_fix=\"Revoke the token.\",\n    ),\n    Finding(\n        file=\"app/report.py\",\n        line=\"1\",\n        severity=\"MEDIUM\",\n        issue=\"A public function without full annotations.\",\n        suggested_fix=\"Annotate the parameters and the return type.\",\n    ),\n]\n\nfor finding in findings:\n    print(f\"{finding.severity.value:<10}{finding.file}:{finding.line}\")\n",
    "explanation": "`<10` pads on the right to ten columns, so `CRITICAL` (8 characters) takes two spaces and `MEDIUM` (6) takes four, which is what lines the columns up. Returning or printing a value instead of assembling a sentence keeps it testable: a test can assert on the string, and nothing depends on stdout."
  },
  "quiz": [
    {
      "q": "What does verdict_for return for a single MEDIUM finding?",
      "options": [
        "block",
        "approve",
        "approve with comments",
        "It raises before the value is ever stored on the model"
      ],
      "answer": 2,
      "why": "Only CRITICAL or HIGH blocks; MEDIUM and LOW still produce a comment, which is the difference between approve and approve with comments."
    },
    {
      "q": "Finding.line is typed as which Python type?",
      "options": [
        "int",
        "str",
        "float",
        "int or str"
      ],
      "answer": 1,
      "why": "str, because a finding may cover a range such as \"42-45\" and one type has to hold both shapes."
    },
    {
      "q": "Which is the correct test for None?",
      "options": [
        "x == None",
        "x is None",
        "not x",
        "x === None"
      ],
      "answer": 1,
      "why": "== is a method a class can override, so only `is` asks the identity question you mean. `not x` is also true for 0, \"\" and []."
    }
  ],
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
