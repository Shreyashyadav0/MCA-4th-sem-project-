/* 6.5 — Pydantic v2 strictness and the unknown field
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "6.5",
  "part": 6,
  "part_title": "The five-field contract",
  "title": "Pydantic v2 strictness and the unknown field",
  "order": 605,
  "duration_min": 25,
  "concept_md": "### The boundary is one line\n\n```python\nmodel_config = ConfigDict(extra=\"forbid\", frozen=True, str_strip_whitespace=True)\n```\n\nThree settings, three jobs. `extra=\"forbid\"` makes an undeclared key an error. `frozen=True` makes the instance immutable. `str_strip_whitespace=True` trims every string before validation, so `\"  app/db.py  \"` and `\"app/db.py\"` are the same finding.\n\n### What \"strict\" does not mean here\n\nPydantic's `strict=True` mode would refuse a JSON number for a `str` field. This model does not use it, because the inputs come from JSON and from a language model, where light coercion helps. The strictness that matters here is about *keys* and *enums*: a finding may not grow a field the contract does not have, and a severity must be one of the four exact spellings — `\"low\"` is rejected, not lowercased.\n\n### Why forbid rather than ignore\n\nIgnoring an extra key is the friendlier default and the more dangerous one. A model that emits `confidence` would be silently stripped, and the caller would believe it had been carried. Forbidding turns that into an error at the boundary, where the cost is a stack trace rather than a wrong review.\n\n### The error names the field\n\n`ValidationError` with `type=\"extra_forbidden\"` and `loc=(\"confidence\",)`. That is enough to fix the producer without reading the model.",
  "code_examples": [
    {
      "id": "6.5-ex-0",
      "lang": "python",
      "caption": "An extra key, refused at the boundary",
      "code": "from app.models import Finding\n\ntry:\n    Finding(file=\"a.py\", line=\"1\", severity=\"LOW\", issue=\"x\",\n            suggested_fix=\"y\", confidence=0.9)\nexcept Exception as exc:\n    first = exc.errors()[0]\n    print(first[\"type\"], first[\"loc\"])\n\nf = Finding(file=\"  app/db.py  \", line=\" 3 \", severity=\"LOW\", issue=\"x\", suggested_fix=\"y\")\nprint(repr(f.file), repr(f.line), f.severity.value)",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "extra_forbidden ('confidence',)\n'app/db.py' '3' LOW",
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
      "q": "What does `extra=\"forbid\"` protect?",
      "options": [
        "The severity ladder from new values that the model has not seen",
        "The database schema",
        "The JSON encoder from cycles",
        "The contract: a finding cannot grow a field no consumer knows"
      ],
      "answer": 3,
      "why": "Without it an undeclared key is dropped silently and the producer believes it was carried; forbidding makes that a named error."
    },
    {
      "q": "What does `str_strip_whitespace=True` change about `\"  app/db.py  \"`?",
      "options": [
        "It is rejected as invalid",
        "It is stored as `app/db.py`",
        "It is stored with the spaces",
        "It is lowercased"
      ],
      "answer": 1,
      "why": "The strings are trimmed before validation, so a padded path from a model's output matches the real file."
    },
    {
      "q": "Why is `strict=True` not used on this model?",
      "options": [
        "Because frozen and strict cannot be combined on the same model",
        "Because strict mode disables validators",
        "Because inputs arrive as JSON and from a model, where coercion helps",
        "Because strict mode is slower"
      ],
      "answer": 2,
      "why": "The strictness that matters is about keys and enum spellings: an extra key and a lowercase severity are both refused, while a JSON string for a string field is accepted."
    }
  ],
  "try_it": {
    "prompt": "Send a padded file name and a padded line, then send a lowercase severity. Print what each does.",
    "starter": "",
    "solution": "```python\nfrom app.models import Finding\n\nf = Finding(file=\"  app/db.py \", line=\" 3 \", severity=\"LOW\",\n            issue=\"x\", suggested_fix=\"y\")\nprint(repr(f.file), repr(f.line), f.severity.value)\n\ntry:\n    Finding(file=\"a.py\", line=\"1\", severity=\"low\", issue=\"x\", suggested_fix=\"y\")\nexcept Exception as exc:\n    print(exc.errors()[0][\"type\"])\n```",
    "explanation": "`'app/db.py' '3' 'LOW'` then `enum` — whitespace is trimmed, but a severity must be one of the four exact spellings."
  },
  "exercise": {
    "prompt": "A model emits a finding with `category=\"secrets\"`. What happens, and what is the smallest change that fixes the producer?",
    "hint": "The error names the key.",
    "solution": "```text\nValidationError, type extra_forbidden, loc (\"category\",).\n\nThe producer drops `category` — or the contract gains it, which would mean changing\nevery consumer. Dropping is the fix that keeps the five-field contract.\n```",
    "explanation": "The error is specific enough to fix the producer without opening the model, which is the point of `loc`."
  },
  "common_mistakes": [
    "Assuming an extra key is silently dropped; with `extra=\"forbid\"` it raises.",
    "Using `strict=True` and then wondering why `\"low\"` is rejected.",
    "Storing a path with trailing whitespace and failing to match the file."
  ],
  "project_links": [
    {
      "label": "The config that sets all three",
      "path": "app/models.py",
      "lines": "68-105"
    },
    {
      "label": "The fields it applies to",
      "path": "app/models.py",
      "lines": "68-83"
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
    "extra=forbid — an undeclared key raises",
    "coercion — converting a compatible value to the declared type",
    "loc — the path to the offending input in an error"
  ]
});
