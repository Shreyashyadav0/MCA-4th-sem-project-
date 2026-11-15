/* 2.3 — Field constraints
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "2.3",
  "part": 2,
  "part_title": "Typing and data modelling",
  "title": "Field constraints",
  "order": 203,
  "duration_min": 25,
  "concept_md": "### Constraints beat validators for simple rules\n\n```python\nfile: str = Field(min_length=1, description=\"Path relative to the project root\")\n```\n\n`min_length`, `max_length`, `ge`, `le`, `pattern` and `gt` are declared on the field and checked by the same machinery that checks the type. They are shorter than a validator, they appear in the JSON schema, and they cannot be forgotten.\n\nReach for a validator (lesson 2.5) only when the rule needs more than one field, or more than one line of logic.\n\n### What the error looks like\n\n```text\nfile\n  String should have at least 1 character [type=string_too_short, ...]\n```\n\nThe first line is the field path, the second the reason. That shape is what makes a Pydantic failure readable in a log, and what `e.errors()` gives you as data.\n\n### A constraint is not a default\n\n`Field(min_length=1)` alone leaves the field **required** — you have constrained it, not made it optional. Adding `= \"\"` would make it optional, and the empty default would *not* be checked: Pydantic validates a default only with `validate_default=True`. That is how a constrained field ends up holding a value its own constraint rejects.\n\n### Where they earn their place here\n\n`Finding.file` and `Finding.issue` both carry `min_length=1`: an empty path or an empty sentence is not a finding, and the check costs nothing. The `line` field cannot use a constraint at all — its rule is \"a number or an ascending range\" — so it gets a validator instead. Knowing which tool fits is most of the skill.",
  "code_examples": [
    {
      "id": "2.3-ex-0",
      "lang": "python",
      "caption": "A constraint on a real field, and the message it produces",
      "code": "from app.models import Finding\n\ntry:\n    Finding(file=\"\", line=\"3\", severity=\"LOW\", issue=\"x\", suggested_fix=\"y\")\nexcept Exception as error:\n    entry = error.errors()[0]\n    print(\"path:\", entry[\"loc\"])\n    print(\"type:\", entry[\"type\"])\n    print(\"msg :\", entry[\"msg\"])\n",
      "runnable": true,
      "run_tier": "browser",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py"
      ],
      "expected_output": "path: ('file',)\ntype: string_too_short\nmsg : String should have at least 1 character"
    }
  ],
  "quiz": [
    {
      "q": "`Field(min_length=1)` on a field — does that make it optional?",
      "options": [
        "Yes, with an empty default",
        "Only when the model is frozen",
        "Yes, if the type is str",
        "No: the field is still required, and must also be long enough"
      ],
      "answer": 3,
      "why": "A constraint narrows what is acceptable; a default is what makes a field optional. Confusing the two produces a field that is optional and always invalid."
    },
    {
      "q": "When should you write a validator instead of a constraint?",
      "options": [
        "When the rule needs more than one field or more than one line",
        "When the rule needs more than one field or more than one line of logic",
        "Always — a validator is clearer than a constraint",
        "When the field happens to be a string type"
      ],
      "answer": 1,
      "why": "`min_length` cannot express \"a number or an ascending range\"; that rule needs code, which is exactly what `Finding.line` uses."
    },
    {
      "q": "What does `error.errors()[0][\"loc\"]` give you?",
      "options": [
        "The path to the failing field, as a tuple",
        "The line of source that failed",
        "The exception class",
        "The model name"
      ],
      "answer": 0,
      "why": "`loc` is the field path — `('findings', 1, 'line')` for a nested failure — which is what lets a caller point at the right item."
    }
  ],
  "try_it": {
    "prompt": "Add a `rule_id: str = Field(pattern=r\"^[a-z]+/[a-z0-9-]+$\")` to a small model and try `\"secret/github-token\"`, then `\"Secret/GitHub\"`.",
    "starter": "from pydantic import BaseModel, Field\n\n\nclass Rule(BaseModel):\n    rule_id: str = Field(pattern=r\"^[a-z]+/[a-z0-9-]+$\")\n\n\nprint(Rule(rule_id=\"secret/github-token\").rule_id)\n",
    "solution": "from pydantic import BaseModel, Field\n\n\nclass Rule(BaseModel):\n    rule_id: str = Field(pattern=r\"^[a-z]+/[a-z0-9-]+$\")\n\n\nprint(Rule(rule_id=\"secret/github-token\").rule_id)\ntry:\n    Rule(rule_id=\"Secret/GitHub\")\nexcept Exception as error:\n    print(\"refused:\", error.errors()[0][\"type\"])\n",
    "explanation": "The first passes; the second fails with `string_pattern_mismatch`. The pattern is the rule ids this repository actually uses — `category/slug`, lower case."
  },
  "exercise": {
    "prompt": "Which fields of `Finding` carry a constraint, and which carry a validator? Read `app/models.py` and list them with the reason.",
    "hint": "One field's rule cannot be written as a single constraint.",
    "solution": "```text\nConstraints: file (min_length=1), issue (min_length=1), suggested_fix (min_length=1) —\n  each is a one-line rule about a single value.\nValidator: line — the rule is \"a number or an ascending range\", which needs a regex plus an\n  ordering comparison, so it is a @field_validator, not a Field(...) argument.\nseverity carries neither: the Severity enum already restricts the value.\n```",
    "explanation": "Three tools, three jobs: a constraint for a simple bound, a validator for logic, an enum for a closed set."
  },
  "common_mistakes": [
    "Writing `Field(min_length=1)` and expecting an optional field — constraints never supply a default.",
    "Giving a constrained field a default that violates its own constraint: the default is not validated, so the bad value is accepted silently until something reads it.",
    "Reaching for a validator where `pattern` would do, and losing the schema entry that comes free with a constraint."
  ],
  "project_links": [
    {
      "label": "The constrained fields, and the one that needs a validator",
      "path": "app/models.py",
      "lines": "68-105"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-1-models.md — the models track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-1-models.md"
    }
  ],
  "glossary_terms": [
    "constraint — a rule declared on a field and checked with the type",
    "pattern — a regex the string must contain a match of; anchor with `^...$` for a full match",
    "loc — the path to a failing field, as a tuple"
  ]
});
