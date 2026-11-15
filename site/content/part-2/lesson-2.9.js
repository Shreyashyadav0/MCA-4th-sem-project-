/* 2.9 — ValidationError and tolerant parsing
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "2.9",
  "part": 2,
  "part_title": "Typing and data modelling",
  "title": "ValidationError and tolerant parsing",
  "order": 209,
  "duration_min": 25,
  "concept_md": "### A model's reply is not a model\n\nWhen a provider returns JSON, nothing guarantees the shape. The repository's rule is simple: try to parse, and if it fails, return nothing rather than raising. A malformed reply is a reason to fall back, not a reason to fail the review.\n\n### The shape of the failure\n\n`ValidationError.errors()` is a list of dicts, each with `loc`, `msg`, `type` and `input`. That is data, not a string — you can filter it, count it, and log the paths without parsing prose.\n\n```python\nexcept ValidationError as error:\n    for entry in error.errors():\n        print(entry[\"loc\"], entry[\"type\"])\n```\n\n### `model_validate_json` versus `model_validate`\n\n`model_validate_json(raw)` parses the string and validates in one step, which is what a provider's reply needs. Prose that is not JSON raises the same `ValidationError`, with the entry type `json_invalid` — one exception type for both a bad shape and bad syntax, which is why a tolerant parser catches one thing and checks the `type` if it cares which happened.\n\n### Returning None is a decision, not a shrug\n\n`try_parse(raw) -> Finding | None` puts the choice at one call site: the caller decides what a `None` means — skip the item, or count it as a failed parse and note it. The repository's own provider does the harder version: its parser raises, the adapter catches, retries the repair once, and returns an empty list with a WARNING — so a bad reply costs a note, never a bad comment.",
  "code_examples": [
    {
      "id": "2.9-ex-0",
      "lang": "python",
      "caption": "Tolerant parsing: a good reply, a bad shape, and text that is not JSON",
      "code": "from app.models import Finding\n\n\ndef try_parse(raw: str) -> Finding | None:\n    try:\n        return Finding.model_validate_json(raw)\n    except Exception:\n        return None\n\n\ngood = '{\"file\": \"a.py\", \"line\": \"3\", \"severity\": \"LOW\", \"issue\": \"x\", \"suggested_fix\": \"y\"}'\nprint(\"good:\", try_parse(good) is not None)\nprint(\"bad shape:\", try_parse('{\"file\": \"a.py\"}') is None)\nprint(\"not json:\", try_parse(\"sorry, I cannot help with that\") is None)\n\ntry:\n    Finding.model_validate_json('{\"file\": \"a.py\"}')\nexcept Exception as error:\n    print(\"paths:\", [entry[\"loc\"] for entry in error.errors()][:3])\n",
      "runnable": true,
      "run_tier": "browser",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py"
      ],
      "expected_output": "good: True\nbad shape: True\nnot json: True\npaths: [('line',), ('severity',), ('issue',)]"
    }
  ],
  "quiz": [
    {
      "q": "A provider returns prose instead of JSON. What does `model_validate_json` raise?",
      "options": [
        "`ValidationError`, with the entry type `json_invalid`",
        "`json.JSONDecodeError`",
        "`ValueError` from the JSON module",
        "Nothing, it returns None"
      ],
      "answer": 0,
      "why": "Pydantic wraps the parse failure into its own error, so one `except ValidationError` covers bad syntax and bad shape alike."
    },
    {
      "q": "Why return `None` instead of raising from a parse helper?",
      "options": [
        "So the caller decides what a failed parse means",
        "Because exceptions cost more than a returned None does",
        "So the caller decides what a failed parse means — skip it, count it, or fall back",
        "So the error is hidden from whoever reads the log"
      ],
      "answer": 2,
      "why": "The decision belongs to the caller: a failed item in a list is skippable, while a failed whole reply means falling back to the rule engine."
    },
    {
      "q": "What is in one entry of `error.errors()`?",
      "options": [
        "A traceback line",
        "Only a message string",
        "The model's JSON schema",
        "`loc`, `msg`, `type` and `input` — data you can filter"
      ],
      "answer": 3,
      "why": "Entries are dicts, which is what makes \"count the extra-key failures\" a one-liner instead of string parsing."
    }
  ],
  "try_it": {
    "prompt": "Add a `line` and a `severity` to the bad payload so three errors appear, and print each path.",
    "starter": "from app.models import Finding\n\ntry:\n    Finding.model_validate_json('{\"file\": \"a.py\"}')\nexcept Exception as error:\n    for entry in error.errors():\n        print(entry[\"loc\"], entry[\"type\"])\n",
    "solution": "from app.models import Finding\n\ntry:\n    Finding.model_validate_json('{\"file\": \"a.py\", \"line\": \"nope\", \"severity\": \"LOW\"}')\nexcept Exception as error:\n    for entry in error.errors():\n        print(entry[\"loc\"], entry[\"type\"])\n",
    "explanation": "It prints the line validator's failure and the two missing fields — one entry per problem, each with its own path. Note both failure modes are `ValidationError`: Pydantic converts a JSON syntax error into an entry of type `json_invalid`."
  },
  "exercise": {
    "prompt": "Write `try_parse(raw: str) -> Finding | None` and use it on three inputs: valid JSON, JSON of the wrong shape, and plain prose.",
    "hint": "One `except ValidationError` covers both failure modes; check `type` if you need to tell them apart.",
    "solution": "from app.models import Finding\n\n\ndef try_parse(raw: str) -> Finding | None:\n    try:\n        return Finding.model_validate_json(raw)\n    except Exception:\n        return None\n\n\nprint(try_parse('{\"file\": \"a.py\", \"line\": \"3\", \"severity\": \"LOW\", \"issue\": \"x\", \"suggested_fix\": \"y\"}'))\nprint(try_parse('{\"file\": \"a.py\"}'))\nprint(try_parse(\"I could not review that.\"))\n",
    "explanation": "A `Finding` then two `None`s. Catching `Exception` here is deliberate: the caller's contract is \"a finding or nothing\", and both failure modes map to nothing."
  },
  "common_mistakes": [
    "Catching only `json.JSONDecodeError`, which Pydantic never raises from `model_validate_json` — the failure arrives as a `ValidationError`.",
    "Logging `str(error)` instead of the `loc` paths, which is the part you can act on.",
    "Raising from a parse helper and forcing every caller to handle two exception types."
  ],
  "project_links": [
    {
      "label": "The parse that raises, and the catch that degrades",
      "path": "app/openai_compat_provider.py",
      "lines": "540-580"
    },
    {
      "label": "Finding, the model being parsed",
      "path": "app/models.py",
      "lines": "68-105"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-5-providers.md — the providers track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-5-providers.md"
    },
    {
      "label": "ADR 0002 — offline-first fallback",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0002-offline-first-fallback.md"
    }
  ],
  "glossary_terms": [
    "tolerant parsing — returning a value or None instead of raising",
    "model_validate_json — parse a string and validate in one step",
    "loc — the path to a failing field"
  ]
});
