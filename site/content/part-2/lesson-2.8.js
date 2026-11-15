/* 2.8 — Serialization: model_dump and mode='json'
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "2.8",
  "part": 2,
  "part_title": "Typing and data modelling",
  "title": "Serialization: model_dump and mode='json'",
  "order": 208,
  "duration_min": 20,
  "concept_md": "### Two dumps, one difference that matters\n\n```python\nresult.model_dump()              # {\"severity\": <Severity.LOW: 'LOW'>}\nresult.model_dump(mode=\"json\")   # {\"severity\": \"LOW\"}\n```\n\nThe first is Python-shaped: enums stay enums, tuples stay tuples. The second is JSON-shaped: enums become their values, dates become strings, and the result survives `json.dumps`.\n\n### Why the HTTP layer wants json mode\n\nA response model is serialised by FastAPI, which does the JSON conversion for you. The place the distinction bites is anywhere you build the payload yourself — a webhook body, a cached blob, a test fixture. `json.dumps(result.model_dump())` on a model with an enum raises `TypeError`; with `mode=\"json\"` it does not.\n\n### Three useful switches\n\n- `exclude_none=True` drops every field whose value is `None` — the difference between a payload with ten nulls and one with the three fields that matter.\n- `by_alias=True` uses the alias instead of the field name, for APIs that expect camelCase.\n- `exclude={\"findings\"}` drops one field without a second model.\n\n### Computed fields come along\n\n`ReviewResult.verdict` is a `@computed_field` — derived, never settable, and serialised into the JSON. That is why the model needs its `mode=\"before\"` validator to strip `verdict` when reading its own output: the dump contains a key the model never declared.",
  "code_examples": [
    {
      "id": "2.8-ex-0",
      "lang": "python",
      "caption": "Python mode, JSON mode, and the computed field",
      "code": "import json\n\nfrom app.models import ReviewResult\n\nresult = ReviewResult(mode=\"mock\", target=\"a.py\", findings=[\n    {\"file\": \"a.py\", \"line\": \"3\", \"severity\": \"CRITICAL\", \"issue\": \"x\", \"suggested_fix\": \"y\"},\n])\n\npython_mode = result.model_dump()\nprint(\"python mode:\", type(python_mode[\"findings\"][0][\"severity\"]).__name__)\n\njson_mode = result.model_dump(mode=\"json\")\nprint(\"json mode:\", repr(json_mode[\"findings\"][0][\"severity\"]))\nprint(\"computed verdict:\", json_mode[\"verdict\"])\nprint(\"json.dumps works:\", len(json.dumps(json_mode)) > 0)\n",
      "runnable": true,
      "run_tier": "browser",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py"
      ],
      "expected_output": "python mode: Severity\njson mode: 'CRITICAL'\ncomputed verdict: block\njson.dumps works: True"
    }
  ],
  "quiz": [
    {
      "q": "What does `mode=\"json\"` change in `model_dump`?",
      "options": [
        "Because it skips validation for speed",
        "It converts values to JSON-safe primitives",
        "It makes the dump faster by skipping validation",
        "It sorts the keys so two dumps compare equal"
      ],
      "answer": 1,
      "why": "Python mode keeps enum members; JSON mode converts them, which is what makes the result survive `json.dumps`."
    },
    {
      "q": "What does `exclude_none=True` do?",
      "options": [
        "Drops fields whose value is None",
        "Drops empty strings",
        "Drops missing fields",
        "Raises if a field is None"
      ],
      "answer": 0,
      "why": "It removes the nulls only — an empty list and an empty string survive, which is why the flag is for optional fields rather than for trimming a payload."
    },
    {
      "q": "Why does `ReviewResult` need a `mode=\"before\"` validator to drop `verdict`?",
      "options": [
        "Because a computed field is in the dump and the model never declared it",
        "Because the dump contains a key whose value is None",
        "Because the dump contains a computed field the model never declared",
        "Because `extra=\"forbid\"` rejects every field not set explicitly"
      ],
      "answer": 2,
      "why": "The model can read its own JSON only if the computed key is removed before the unknown-key check runs."
    }
  ],
  "try_it": {
    "prompt": "Dump a `ReviewResult` with `exclude_none=True` and with `exclude={\"notes\"}` and compare the keys.",
    "starter": "from app.models import ReviewResult\n\n\nr = ReviewResult(mode=\"mock\", target=\"a.py\")\nprint(sorted(r.model_dump(exclude_none=True)))\n",
    "solution": "from app.models import ReviewResult\n\n\nr = ReviewResult(mode=\"mock\", target=\"a.py\")\nprint(sorted(r.model_dump(exclude_none=True)))\nprint(sorted(r.model_dump(exclude={\"notes\"})))\n",
    "explanation": "Both keep `findings` (empty list, not None). The second drops `notes` entirely; the first keeps it because an empty list is not None."
  },
  "exercise": {
    "prompt": "Dump `list[Finding]` with `exclude_none=True` and show the JSON. Then explain why the output has no nulls even without the flag.",
    "hint": "None of the five fields is optional, so there is nothing to exclude.",
    "solution": "import json\n\nfrom app.models import Finding\n\n\nfindings = [Finding(file=\"a.py\", line=\"3\", severity=\"LOW\", issue=\"x\", suggested_fix=\"y\")]\nprint(json.dumps([f.model_dump(mode=\"json\", exclude_none=True) for f in findings], indent=2))\n",
    "explanation": "The JSON has all five keys and no nulls: `exclude_none` had nothing to remove because no field of `Finding` is optional. The flag earns its place on models that do have optional fields."
  },
  "common_mistakes": [
    "Calling `json.dumps(model.model_dump())` and hitting `TypeError: Object of type Severity is not JSON serializable`.",
    "Expecting `exclude_none` to drop empty lists — it only drops `None`.",
    "Forgetting that a computed field is in the dump, so a round-trip through the model needs a before-validator."
  ],
  "project_links": [
    {
      "label": "The response model FastAPI serialises",
      "path": "app/main.py",
      "lines": "260-301"
    },
    {
      "label": "The computed verdict field",
      "path": "app/models.py",
      "lines": "180-194"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-1-models.md — the models track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-1-models.md"
    }
  ],
  "glossary_terms": [
    "model_dump — a dict of the model's fields",
    "computed field — a derived value serialised like a field",
    "exclude_none — drop fields whose value is None"
  ]
});
