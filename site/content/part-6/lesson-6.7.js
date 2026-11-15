/* 6.7 — Serialising a Finding to JSON and to Markdown
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "6.7",
  "part": 6,
  "part_title": "The five-field contract",
  "title": "Serialising a Finding to JSON and to Markdown",
  "order": 607,
  "duration_min": 25,
  "concept_md": "### One model, three renderings\n\nA finding is serialised three ways, and each is generated from the model rather than hand-written:\n\n- **JSON** — `to_json()` on the container, for the API response and the review record.\n- **A row** — `as_row()`, the five display fields in contract order, for the CLI table.\n- **Markdown** — a table row or an inline comment, built from the same five fields.\n\n### Why `as_row` exists\n\nThe JSON key names are the field names (`suggested_fix`); the display headings are the human ones (`Suggested Fix`). Putting that mapping in one method means the CLI and the Markdown table cannot disagree about what a column is called.\n\n### The computed fields are dropped\n\n`ReviewResult` carries one `computed_field`, `verdict`, which is serialised into the JSON. `counts()` and `sorted_findings` are a method and a property — helpers for a caller, never serialised. On the way back in, `_drop_computed` removes a `verdict` key so a round trip cannot introduce a verdict that disagrees with the findings.\n\n### Round-trip is the test\n\n`ReviewResult.model_validate_json(result.to_json())` must equal the original. If a computed value were stored, that equality would be a coincidence rather than a guarantee.\n\n### Markdown is built from the row, not from the model\n\nThe comment renderer takes `as_row()` and lays the five values into a table, so the Markdown and the CLI table are two layouts of one mapping. A field renamed in the model changes both renderings at once, which is the property a hand-built f-string would lose.",
  "code_examples": [
    {
      "id": "6.7-ex-0",
      "lang": "python",
      "caption": "The row and the JSON, from one model",
      "code": "from app.models import Finding, ReviewResult\n\nf = Finding(file=\"app/db.py\", line=\"3-4\", severity=\"CRITICAL\",\n            issue=\"A token is hardcoded.\", suggested_fix=\"Read it from the environment.\")\nresult = ReviewResult(mode=\"mock\", target=\"app/db.py\", findings=[f])\nprint(f.as_row())\nprint(result.to_json()[:120])\nprint(\"verdict:\", result.verdict, \"| counts:\", result.counts())",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "{'File': 'app/db.py', 'Line': '3-4', 'Severity': 'CRITICAL', 'Issue': 'A token is hardcoded.', 'Suggested Fix': 'Read it from the environment.'}\n{\n  \"mode\": \"mock\",\n  \"target\": \"app/db.py\",\n  \"findings\": [\n    {\n      \"file\": \"app/db.py\",\n      \"line\": \"3-4\",\n     \nverdict: block | counts: {'LOW': 0, 'MEDIUM': 0, 'HIGH': 0, 'CRITICAL': 1}",
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
      "q": "Why is `as_row()` a method rather than a dict built at each call site?",
      "options": [
        "Because a dict cannot hold five keys in a fixed order",
        "Because a dict cannot hold five keys and keep their order",
        "So the column names cannot disagree",
        "So the values can be cached"
      ],
      "answer": 2,
      "why": "One mapping from field names to headings means a rename happens in one place; two call sites would drift."
    },
    {
      "q": "What does `_drop_computed` prevent?",
      "options": [
        "A stored verdict that disagrees with the findings",
        "A JSON payload that is too large to parse in one pass",
        "The findings from being sorted",
        "The mode from being validated"
      ],
      "answer": 0,
      "why": "Verdict and counts are derived; accepting them on input would let a caller assert a verdict its own findings contradict."
    },
    {
      "q": "What makes a round trip trustworthy?",
      "options": [
        "The model is frozen",
        "The JSON is compressed",
        "The fields are sorted alphabetically",
        "Computed values are re-derived"
      ],
      "answer": 3,
      "why": "If the verdict were stored, a round trip would only prove the bytes survived; re-deriving proves the findings still imply the verdict."
    }
  ],
  "try_it": {
    "prompt": "Serialise a result and parse it back; confirm the findings survive.",
    "starter": "",
    "solution": "```python\nfrom app.models import Finding, ReviewResult\n\nf = Finding(file=\"a.py\", line=\"2\", severity=\"HIGH\", issue=\"x\", suggested_fix=\"y\")\nresult = ReviewResult(mode=\"mock\", target=\"a.py\", findings=[f])\nagain = ReviewResult.model_validate_json(result.to_json())\nprint(again.findings == result.findings, again.verdict)\n```",
    "explanation": "`True block` — the findings compare equal and the verdict is derived again from them."
  },
  "exercise": {
    "prompt": "Add a `verdict` key to the JSON by hand and parse it back. What happens, and why is that right?",
    "hint": "Look at `_drop_computed`.",
    "solution": "```text\nThe key is dropped on input: ReviewResult._drop_computed removes computed names\nbefore validation, so a hand-written verdict is ignored and the real one is\nderived from the findings. That is right because a verdict is a conclusion about\nthe findings, not a field a caller may assert.\n```",
    "explanation": "Derived data is refused at the boundary in both directions, which is what makes the JSON a faithful record."
  },
  "common_mistakes": [
    "Building the Markdown table from raw field names, so a rename changes one renderer only.",
    "Storing the verdict and letting it drift from the findings.",
    "Serialising the enum object directly and emitting a wrapper instead of the text."
  ],
  "project_links": [
    {
      "label": "The row helper",
      "path": "app/models.py",
      "lines": "97-105"
    },
    {
      "label": "The JSON serialiser and computed fields",
      "path": "app/models.py",
      "lines": "151-194"
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
    "computed field — a value derived from the model rather than stored",
    "round trip — serialise then parse back",
    "row — the five display fields in contract order"
  ]
});
