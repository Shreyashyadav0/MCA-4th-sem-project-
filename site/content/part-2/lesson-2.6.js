/* 2.6 — Nested models and list[Model]
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "2.6",
  "part": 2,
  "part_title": "Typing and data modelling",
  "title": "Nested models and list[Model]",
  "order": 206,
  "duration_min": 25,
  "concept_md": "### A model inside a model\n\n```python\nclass ReviewResult(BaseModel):\n    mode: str\n    target: str\n    findings: list[Finding] = Field(default_factory=list)\n```\n\n`list[Finding]` means every element is validated as a `Finding`, and the error path tells you which one: `('findings', 1, 'line')` is the second finding's line field. That path is the difference between \"something in the payload is wrong\" and \"the second finding has a bad line\".\n\n### The error cascades\n\nTen findings, one bad line, one entry — with a path. Pydantic does not stop at the first problem, so a payload with three mistakes reports three entries, each pointing at its own place.\n\n### Why the list needs a factory\n\n`= Field(default_factory=list)` gives each instance its own empty list. Pydantic v2 deep-copies a mutable default per instance anyway, so `= []` is safe here — but `default_factory` is the documented spelling, and it is the one this repository uses.\n\n### What the repository nests\n\n`ReviewResult` holds `list[Finding]` and `list[str]` for the notes. `AnchoredFinding` wraps a `Finding` with the anchor metadata, because anchoring is review metadata rather than part of the finding contract — a distinction that shows up as one extra level in the payload, not one extra field on the finding.\n\n### Reading the path\n\n```python\nfor entry in error.errors():\n    print(\" -> \".join(str(part) for part in entry[\"loc\"]))\n```\n\n`findings -> 1 -> line` reads as an instruction: go to findings, take index 1, look at line.",
  "code_examples": [
    {
      "id": "2.6-ex-0",
      "lang": "python",
      "caption": "A nested list, and the path that points at the bad element",
      "code": "from app.models import ReviewResult\n\ngood = {\"file\": \"a.py\", \"line\": \"3\", \"severity\": \"LOW\", \"issue\": \"x\", \"suggested_fix\": \"y\"}\nbad = {\"file\": \"b.py\", \"line\": \"nope\", \"severity\": \"LOW\", \"issue\": \"x\", \"suggested_fix\": \"y\"}\n\nresult = ReviewResult(mode=\"mock\", target=\"a.py\", findings=[good])\nprint(\"findings:\", len(result.findings), \"| type:\", type(result.findings[0]).__name__)\n\ntry:\n    ReviewResult.model_validate({\"mode\": \"mock\", \"target\": \"a.py\", \"findings\": [good, bad]})\nexcept Exception as error:\n    loc = error.errors()[0][\"loc\"]\n    print(\"path:\", \" -> \".join(str(part) for part in loc))\n",
      "runnable": true,
      "run_tier": "browser",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py"
      ],
      "expected_output": "findings: 1 | type: Finding\npath: findings -> 1 -> line"
    }
  ],
  "quiz": [
    {
      "q": "`findings: list[Finding]` — what does the annotation validate?",
      "options": [
        "Because a bare [] default raises a TypeError at import",
        "That the list is not empty",
        "That it is a list and that every element is a Finding",
        "Nothing until the list is read"
      ],
      "answer": 2,
      "why": "The element type is part of the annotation, so each item is validated as a model and the error names its index."
    },
    {
      "q": "Why does this repository write `Field(default_factory=list)` rather than `= []`?",
      "options": [
        "Because a bare default is rejected for a mutable list field",
        "Because a bare `= []` default is shared by every instance that is built",
        "Because a bare default is rejected for a mutable list field",
        "Because it is the documented spelling for a fresh list"
      ],
      "answer": 3,
      "why": "`Field(default_factory=list)` is the documented spelling, and it also avoids the sharing that a bare `= []` would cause in a plain dataclass — though Pydantic deep-copies a bare default per instance anyway."
    },
    {
      "q": "What does an error path of `('findings', 1, 'line')` tell you?",
      "options": [
        "The first finding has a bad line",
        "The second finding's line field failed validation",
        "There are two findings",
        "The model has one error"
      ],
      "answer": 1,
      "why": "Index 1 is the second element; the path is what lets a caller report the mistake against the right item."
    }
  ],
  "try_it": {
    "prompt": "Add a second valid finding and dump the result with `model_dump()`. How many entries does `findings` have?",
    "starter": "from app.models import ReviewResult\n\n\nr = ReviewResult(mode=\"mock\", target=\"a.py\", findings=[\n    {\"file\": \"a.py\", \"line\": \"3\", \"severity\": \"LOW\", \"issue\": \"x\", \"suggested_fix\": \"y\"},\n])\nprint(len(r.model_dump()[\"findings\"]))\n",
    "solution": "from app.models import ReviewResult\n\n\nr = ReviewResult(mode=\"mock\", target=\"a.py\", findings=[\n    {\"file\": \"a.py\", \"line\": \"3\", \"severity\": \"LOW\", \"issue\": \"x\", \"suggested_fix\": \"y\"},\n    {\"file\": \"b.py\", \"line\": \"7\", \"severity\": \"HIGH\", \"issue\": \"z\", \"suggested_fix\": \"w\"},\n])\nprint(len(r.model_dump()[\"findings\"]))\nprint([f.file for f in r.findings])\n",
    "explanation": "It prints `2` then `['a.py', 'b.py']`: dicts in, `Finding` objects out, in order."
  },
  "exercise": {
    "prompt": "Write the shape of a review payload: a model with a mode, a target and a list of findings, then show what a bad second finding reports.",
    "hint": "Copy the shape of `ReviewResult`, and give the second finding a line of `nope`.",
    "solution": "from pydantic import BaseModel, Field, field_validator\n\n\nclass Finding(BaseModel):\n    file: str\n    line: str\n\n    @field_validator(\"line\")\n    @classmethod\n    def _check_line(cls, value: str) -> str:\n        if not value.isdigit():\n            raise ValueError(f\"not a line number: {value!r}\")\n        return value\n\n\nclass Review(BaseModel):\n    mode: str\n    target: str\n    findings: list[Finding] = Field(default_factory=list)\n\n\ntry:\n    Review.model_validate({\"mode\": \"mock\", \"target\": \"a.py\", \"findings\": [\n        {\"file\": \"a.py\", \"line\": \"3\"},\n        {\"file\": \"b.py\", \"line\": \"nope\"},\n    ]})\nexcept Exception as error:\n    print(error.errors()[0][\"loc\"])\n",
    "explanation": "It prints `('findings', 1, 'line')` — the same path shape the repository's own model produces. The validator is what makes the second finding fail: without it, `\"nope\"` is a perfectly good str."
  },
  "common_mistakes": [
    "Assuming a bare `= []` default is shared between Pydantic instances — it is deep-copied, unlike a plain function default.",
    "Catching `ValidationError` and printing only `str(error)`, losing the paths that say which element failed.",
    "Flattening a nested payload by hand before validating, so the index that would have pointed at the bad item is gone."
  ],
  "project_links": [
    {
      "label": "ReviewResult: a model holding list[Finding]",
      "path": "app/models.py",
      "lines": "151-194"
    },
    {
      "label": "AnchoredFinding: a model wrapping another model",
      "path": "app/models.py",
      "lines": "108-122"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-1-models.md — the models track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-1-models.md"
    }
  ],
  "glossary_terms": [
    "nested model — a model used as a field type",
    "loc — the tuple path to a failing element",
    "default_factory — builds a fresh default per instance"
  ]
});
