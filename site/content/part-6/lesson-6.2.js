/* 6.2 — file and line, and why line is a string
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "6.2",
  "part": 6,
  "part_title": "The five-field contract",
  "title": "file and line, and why line is a string",
  "order": 602,
  "duration_min": 20,
  "concept_md": "### `line` is a string, and that is deliberate\n\nA finding may concern one line or a range. The model stores both as text:\n\n```text\n\"42\"      one line\n\"42-45\"   four lines\n```\n\nAn `int` could not hold the second, and a tuple would need its own serialisation in every consumer. A string that matches `^\\d+(?:-\\d+)?$` holds both, sorts predictably once split, and survives JSON without a custom encoder.\n\n### The validator is the only gate\n\n```python\n@field_validator(\"line\")\n@classmethod\ndef _check_line(cls, value: str) -> str:\n```\n\nIt rejects anything that is not a number or an ascending range. `\"4-2\"` fails because a range that descends is a caller bug, not a finding, and `\"line 42\"` fails because prose is not a line number. `\"42-42\"` passes: it ascends, and it names one line.\n\n### `file` is a path, or `<snippet>`\n\n`file` is relative to the project root so a comment can be posted against the right file. When the input was pasted code rather than a diff, the tool uses the sentinel `<snippet>`, which is not a path and must never be treated as one.\n\n### Why this matters downstream\n\nThe anchorer calls `_parse_range` on the value to get `(start, end)`, so the format is not decoration: it is the interface between the finding and the diff.",
  "code_examples": [
    {
      "id": "6.2-ex-0",
      "lang": "python",
      "caption": "Both forms are legal; a descending range is not",
      "code": "from app.models import Finding\n\ndef attempt(line):\n    try:\n        Finding(file=\"app/db.py\", line=line, severity=\"LOW\", issue=\"x\", suggested_fix=\"y\")\n        return \"accepted\"\n    except Exception as exc:\n        first = exc.errors()[0]\n        return first[\"type\"] + \" -> \" + first[\"msg\"][:48]\n\nfor value in (\"42\", \"42-45\", \"4-2\", \"line 42\"):\n    print(value, \"->\", attempt(value))",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "42 -> accepted\n42-45 -> accepted\n4-2 -> value_error -> Value error, line range must ascend, got '4-2'\nline 42 -> value_error -> Value error, line must look like \"42\" or \"42-45\"",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py"
      ]
    }
  ],
  "quiz": [
    {
      "q": "Why is `line` a string rather than an int?",
      "options": [
        "Because JSON cannot store integers",
        "A string holds both a number and an ascending range",
        "Because Pydantic cannot validate integers",
        "Because the file names are strings too"
      ],
      "answer": 1,
      "why": "One field has to carry `42` and `42-45`; a string does both without a second type or a custom serialiser."
    },
    {
      "q": "What is `\"4-2\"` to this model?",
      "options": [
        "A legal range of one line",
        "A legal range of two lines",
        "An error: the range must ascend",
        "A line number with a negative part"
      ],
      "answer": 2,
      "why": "The validator compares the two ends and rejects a descending pair, because it can only come from a bug in whatever produced the finding."
    },
    {
      "q": "What is `<snippet>` in the `file` field?",
      "options": [
        "A sentinel for pasted code that is not a path",
        "A placeholder for a file the diff did not name",
        "A filename git generates for new files",
        "The default when `file` is omitted"
      ],
      "answer": 0,
      "why": "It marks input that arrived as code rather than a diff, so downstream code can refuse to post an inline comment against it."
    }
  ],
  "try_it": {
    "prompt": "Find which line values the model accepts.",
    "starter": "",
    "solution": "```python\nfrom app.models import Finding\n\nok = []\nfor value in (\"7\", \"7-9\", \"9-7\", \"\", \"x\"):\n    try:\n        Finding(file=\"f\", line=value, severity=\"LOW\", issue=\"i\", suggested_fix=\"s\")\n        ok.append(value)\n    except Exception:\n        pass\nprint(ok)\n```",
    "explanation": "`['7', '7-9']` — the number and the ascending range. The empty string and the letter fail before the field is stored."
  },
  "exercise": {
    "prompt": "The anchorer needs the first line of a range. Write the expression it uses, and say what it returns for `\"42-45\"` and for `\"42\"`.",
    "hint": "Split on the dash and take the first part.",
    "solution": "```python\nfrom app.parser import _parse_range\n\n_parse_range(\"42-45\")  # (42, 45)\n_parse_range(\"42\")     # (42, 42)\n```",
    "explanation": "One helper handles both forms, which is why the anchorer never splits the string itself."
  },
  "common_mistakes": [
    "Passing an int for `line`, which fails validation rather than being coerced.",
    "Producing a descending range from a loop that walks backwards.",
    "Treating `<snippet>` as a real path and posting a comment against it."
  ],
  "project_links": [
    {
      "label": "The line pattern",
      "path": "app/models.py",
      "lines": "42"
    },
    {
      "label": "The validator that enforces it",
      "path": "app/models.py",
      "lines": "87-95"
    }
  ],
  "learn_more": [
    {
      "label": "app/models.py — the models",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/models.py"
    },
    {
      "label": "docs/learning/track-1-models.md",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-1-models.md"
    }
  ],
  "glossary_terms": [
    "range — two line numbers with a dash, ascending",
    "sentinel — a value that marks a special case, like <snippet>",
    "field validator — a function Pydantic runs on one field"
  ]
});
