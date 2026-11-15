/* 6.6 — Field validators and constraints
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "6.6",
  "part": 6,
  "part_title": "The five-field contract",
  "title": "Field validators and constraints",
  "order": 606,
  "duration_min": 25,
  "concept_md": "### Two kinds of rule\n\nA **constraint** is declared on the field: `min_length=1` on `issue`, `min_length=1` on `file`. Pydantic applies it without any code of yours.\n\nA **validator** is a function that runs after the type check, for rules a constraint cannot express:\n\n```python\n@field_validator(\"line\")\n@classmethod\ndef _check_line(cls, value: str) -> str:\n```\n\n### What the line validator adds\n\nThe pattern `^\\d+(?:-\\d+)?$` could be a constraint, but the *ascending* check cannot: it needs to compare two halves of the same string. So the validator does both, and raises `ValueError` with a message a human can act on.\n\n### Validators run in declaration order\n\nPydantic runs every field's validation and collects all the errors, so one bad input can report several problems at once — an empty `file`, a descending `line` and an empty `suggested_fix` in the same `ValidationError`. That is why `errors()` returns a list rather than a single entry.\n\n### The null-byte rule lives elsewhere\n\n`ReviewRequest` in the API validates that a pasted code body carries no null bytes, because a null byte in a diff is a request the parser should never see. Same technique, different boundary: the model that receives untrusted input owns the check.\n\n### What a validator may not do\n\nIt may not reach outside the value it was given. A validator that read a file, called a service or looked at another field would make construction depend on the world, and every test would need that world to exist. These validators are pure functions of one string, which is why the models can be exercised in the browser runner.",
  "code_examples": [
    {
      "id": "6.6-ex-0",
      "lang": "python",
      "caption": "A constraint and a validator, side by side",
      "code": "from app.models import Finding\n\ndef attempt(**kwargs):\n    base = dict(file=\"a.py\", line=\"1\", severity=\"LOW\", issue=\"x\", suggested_fix=\"y\")\n    base.update(kwargs)\n    try:\n        Finding(**base)\n        return \"accepted\"\n    except Exception as exc:\n        first = exc.errors()[0]\n        return first[\"loc\"][0] + \": \" + first[\"type\"]\n\nprint(\"empty file   ->\", attempt(file=\"\"))\nprint(\"bad range    ->\", attempt(line=\"9-4\"))\nprint(\"empty fix    ->\", attempt(suggested_fix=\"\"))",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "empty file   -> file: string_too_short\nbad range    -> line: value_error\nempty fix    -> suggested_fix: string_too_short",
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
      "q": "Why can the ascending check not be a plain constraint?",
      "options": [
        "Because constraints only apply to numbers",
        "It compares two halves of the same string",
        "Because the field is a string",
        "Because constraints run before parsing"
      ],
      "answer": 1,
      "why": "`min_length` looks at one value; deciding that 9-4 descends means splitting the value and comparing, which needs code."
    },
    {
      "q": "Two fields are invalid at once. What does `errors()` return?",
      "options": [
        "Both errors, one per field",
        "Only the first error",
        "A single error naming the model",
        "Nothing until `model_validate` is called"
      ],
      "answer": 0,
      "why": "Pydantic validates every field and collects the failures, so a caller can fix several problems in one pass rather than one per run."
    },
    {
      "q": "Where is the null-byte check made, and why there?",
      "options": [
        "On the request model",
        "On `Finding`, because findings are untrusted",
        "In the parser, after the diff is split",
        "In the GitHub client before posting"
      ],
      "answer": 0,
      "why": "The model that first touches a client's bytes owns the check, so nothing downstream has to defend against a null byte."
    }
  ],
  "try_it": {
    "prompt": "Find three ways to make `Finding` raise, and print the field and error type for each.",
    "starter": "",
    "solution": "```python\nfrom app.models import Finding\n\ndef attempt(**kw):\n    base = dict(file=\"a.py\", line=\"1\", severity=\"LOW\", issue=\"x\", suggested_fix=\"y\")\n    base.update(kw)\n    try:\n        Finding(**base)\n        return \"accepted\"\n    except Exception as exc:\n        first = exc.errors()[0]\n        return first[\"loc\"][0] + \": \" + first[\"type\"]\n\nfor kw in ({\"file\": \"\"}, {\"line\": \"9-4\"}, {\"severity\": \"SEVERE\"}):\n    print(kw, \"->\", attempt(**kw))\n```",
    "explanation": "Each failure names its own field, so a producer can be fixed from the error alone."
  },
  "exercise": {
    "prompt": "Add a rule that `issue` may not contain a newline, without changing any other field. Say where the code goes and what it raises.",
    "hint": "It is a rule about one field's content, not about its type.",
    "solution": "```python\n@field_validator(\"issue\")\n@classmethod\ndef _single_line(cls, value: str) -> str:\n    if \"\\n\" in value:\n        raise ValueError(\"issue must be one line\")\n    return value\n\nIt goes on `Finding`, below the existing `line` validator, and it raises\nValueError, which Pydantic reports as a value_error on the issue field.\n```",
    "explanation": "A validator is the right tool when the rule is about content rather than presence or length."
  },
  "common_mistakes": [
    "Raising a bare `Exception` in a validator, which Pydantic reports without a location.",
    "Putting a comparison rule in a constraint and finding it cannot be expressed.",
    "Adding the check to the consumer instead of the model, so each consumer repeats it."
  ],
  "project_links": [
    {
      "label": "The line validator",
      "path": "app/models.py",
      "lines": "87-95"
    },
    {
      "label": "The constraints on file, issue and fix",
      "path": "app/models.py",
      "lines": "73-86"
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
    "constraint — a rule declared on the field itself",
    "validator — a function run after the type check",
    "null byte — a zero byte that can truncate C-level strings"
  ]
});
