/* 2.5 — field_validator and model_validator
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "2.5",
  "part": 2,
  "part_title": "Typing and data modelling",
  "title": "field_validator and model_validator",
  "order": 205,
  "duration_min": 30,
  "concept_md": "### Two hooks, two jobs\n\nA `@field_validator` sees **one field** after its type has been checked. A `@model_validator` sees **the whole model**, either before or after field validation.\n\n```python\n@field_validator(\"line\")\n@classmethod\ndef _check_line(cls, value: str) -> str:\n    if not _LINE_RE.match(value):\n        raise ValueError(f'line must look like \"42\" or \"42-45\", got {value!r}')\n    if \"-\" in value:            # … then the ascending-range check\n        start, _, end = value.partition(\"-\")\n        if int(end) < int(start):\n            raise ValueError(f\"line range must ascend, got {value!r}\")\n    return value\n```\n\nThat is the real validator on `Finding.line`, quoted from `app/models.py`. It runs after the string type check, so `value` is already a `str`; raising `ValueError` is how a validator refuses, and Pydantic wraps it into a `ValidationError` entry whose message begins \"Value error, \".\n\n### Before or after\n\n`mode=\"before\"` runs on the raw input — the right place to reshape a payload. `mode=\"after\"` (the default) runs once the fields are valid — the right place to check a relationship between fields. A cross-field rule (\"end must not precede start\") has to be a model validator: no single field validator can see both values.\n\n### `ReviewResult` uses both\n\nIts `_check_mode` field validator rejects anything but `\"live\"` and `\"mock\"`, and its `_drop_computed` model validator (mode `\"before\"`) removes a serialised `verdict` key before validation — so the model can read its own JSON output, which contains a computed field it never declared.\n\n### The rule of thumb\n\nConstraint for one value, field validator for one field's logic, model validator for a relationship. Reach for the later one only when the earlier cannot express the rule.",
  "code_examples": [
    {
      "id": "2.5-ex-0",
      "lang": "python",
      "caption": "The real line validator, and a whole-model rule it cannot express",
      "code": "from app.models import Finding\n\nok = Finding(file=\"a.py\", line=\"42-45\", severity=\"LOW\", issue=\"x\", suggested_fix=\"y\")\nprint(\"accepted:\", ok.line)\n\nfor bad in (\"abc\", \"45-42\"):\n    try:\n        Finding(file=\"a.py\", line=bad, severity=\"LOW\", issue=\"x\", suggested_fix=\"y\")\n    except Exception as error:\n        print(\"rejected:\", error.errors()[0][\"msg\"].split(\",\")[0])\n",
      "runnable": true,
      "run_tier": "browser",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py"
      ],
      "expected_output": "accepted: 42-45\nrejected: Value error\nrejected: Value error"
    }
  ],
  "quiz": [
    {
      "q": "A rule that compares two fields of the same model belongs where?",
      "options": [
        "A `@model_validator`, which can see both",
        "TypeError, which aborts validation before any field is checked",
        "A `Field(...)` constraint",
        "A separate function called by the caller"
      ],
      "answer": 0,
      "why": "A field validator only ever sees its own value, so any rule about a relationship has to be a model validator."
    },
    {
      "q": "What should a validator raise to reject a value?",
      "options": [
        "`ValueError`, which Pydantic wraps into a validation entry",
        "`SystemExit`, which stops the run at once",
        "`ValueError`, which Pydantic wraps into a ValidationError entry",
        "`AssertionError`, which pytest reports as a failure"
      ],
      "answer": 2,
      "why": "`ValueError` is the documented signal; the entry's message then begins \"Value error, \" followed by your text."
    },
    {
      "q": "`ReviewResult._drop_computed` runs with `mode=\"before\"`. Why before?",
      "options": [
        "Because it is faster",
        "Because `after` does not exist for models",
        "Because computed fields are not validated",
        "Because it must reshape the raw input before any field is validated"
      ],
      "answer": 3,
      "why": "It removes a key the model never declared, and that has to happen before validation looks at the keys at all."
    }
  ],
  "try_it": {
    "prompt": "Reject a finding whose `file` does not end in `.py`, using a `@field_validator`. Then try `app/db.py` and `README.md`.",
    "starter": "from pydantic import BaseModel, field_validator\n\n\nclass Finding(BaseModel):\n    file: str\n\n    @field_validator(\"file\")\n    @classmethod\n    def _py_only(cls, value: str) -> str:\n        return value\n",
    "solution": "from pydantic import BaseModel, field_validator\n\n\nclass Finding(BaseModel):\n    file: str\n\n    @field_validator(\"file\")\n    @classmethod\n    def _py_only(cls, value: str) -> str:\n        if not value.endswith(\".py\"):\n            raise ValueError(f\"not a Python file: {value!r}\")\n        return value\n\n\nprint(Finding(file=\"app/db.py\").file)\ntry:\n    Finding(file=\"README.md\")\nexcept Exception as error:\n    print(\"rejected:\", error.errors()[0][\"msg\"])\n",
    "explanation": "The first passes; the second prints `Value error, not a Python file: 'README.md'`. Note this repository does not enforce that rule — a finding may legitimately point at a snippet — which is why the real validator checks the line, not the extension."
  },
  "exercise": {
    "prompt": "Read `_check_line` in `app/models.py` and explain, in three lines, why it checks the regex first and the ordering second.",
    "hint": "One check can make the other impossible to run.",
    "solution": "```text\n1. The regex proves the value has the shape number or number-number, so the later split is safe.\n2. Only then does it partition on \"-\" and compare the two halves as ints.\n3. Reversed, int(\"abc\") would raise a bare ValueError with a confusing message instead of the\n   field-shaped one the validator is there to give.\n```",
    "explanation": "Order of checks inside a validator is what decides which message a caller reads — the specific one, or an accident."
  },
  "common_mistakes": [
    "Raising `AssertionError` or returning `False` from a validator, so the failure is not reported as a validation error.",
    "Putting a cross-field rule in a field validator and discovering it can only see one value.",
    "Forgetting `@classmethod` under `@field_validator`, which fails at class definition time."
  ],
  "project_links": [
    {
      "label": "The field validator on line",
      "path": "app/models.py",
      "lines": "82-100"
    },
    {
      "label": "The before-mode model validator",
      "path": "app/models.py",
      "lines": "168-180"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-1-models.md — the models track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-1-models.md"
    }
  ],
  "glossary_terms": [
    "field validator — a check on one field after its type",
    "model validator — a check on the whole model, before or after fields",
    "mode — when a validator runs relative to field validation"
  ]
});
