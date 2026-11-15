/* 7.8 — Guided read of app/parser.py
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "7.8",
  "part": 7,
  "part_title": "The parser",
  "title": "Guided read of app/parser.py",
  "order": 708,
  "duration_min": 30,
  "concept_md": "### 614 lines, in five blocks\n\n**1. Errors and path helpers** — `DiffParseError` at **69**, `normalize_path` at **73**, `_spans` at **89**, `_parse_range` at **106**. Small, pure, and used by everything below.\n\n**2. The models** — `DiffLine` at **112**, `Hunk` at **123**, `FileDiff` at **152**, `FileSummary` at **193**, `DiffBundle` at **206**, `DiffReviewResult` at **248**. The shapes the parser produces.\n\n**3. The builder** — `_Builder` at **305**. State that accumulates across lines, with `finish()` deciding what the collected lines mean.\n\n**4. The entry points** — `parse_diff` at **343**, `parse_diff_file` at **503**, `anchor_findings` at **518**, `bundle_from_source` at **575**.\n\n**5. That is the whole file** — fifteen definitions, no renderer. The Markdown comment is built in `app/main.py` from `as_row()`, which is why the parser stays a pure text-to-model module.\n\n### The order is the design\n\nModels before builder before entry points, because each layer uses only what is above it. Reading top to bottom means never meeting a name before it is defined — the same property that makes the module importable without side effects.\n\n### The two functions worth memorising\n\n`parse_diff` at **343** is where text becomes models, and `anchor_findings` at **518** is where models meet a diff. Everything else in the file exists to serve one of those two.",
  "code_examples": [
    {
      "id": "7.8-ex-0",
      "lang": "console",
      "caption": "The file's index",
      "code": "grep -n '^class \\|^def ' app/parser.py",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "the browser runner has Python but no shell, so this command cannot run there; it needs a checkout on disk.",
      "expected_output": "69:class DiffParseError(ValueError):\n73:def normalize_path(raw: str) -> str:\n89:def _spans(numbers: Sequence[int]) -> list[str]:\n106:def _parse_range(value: str) -> tuple[int, int]:\n112:class DiffLine(BaseModel):\n123:class Hunk(BaseModel):\n152:class FileDiff(BaseModel):\n193:class FileSummary(BaseModel):\n206:class DiffBundle(BaseModel):\n248:class DiffReviewResult(BaseModel):\n305:class _Builder:\n343:def parse_diff(raw: str, *, source: str = \"<diff>\") -> DiffBundle:\n503:def parse_diff_file(path: Path) -> DiffBundle:\n518:def anchor_findings(bundle: DiffBundle, findings: Iterable[Finding]) -> list[AnchoredFinding]:\n575:def bundle_from_source(path: Path | str, source: str) -> DiffBundle:"
    }
  ],
  "quiz": [
    {
      "q": "Which block would you read to learn how a hunk's lines are collected?",
      "options": [
        "The builder, from line 305",
        "The models, from line 112",
        "The entry points, from 343",
        "The path helpers, from 69"
      ],
      "answer": 0,
      "why": "`_Builder` owns the accumulation; the models only describe the result and the entry points call the builder."
    },
    {
      "q": "What does `parse_diff_file` add to `parse_diff`?",
      "options": [
        "Validation of the paths inside the diff",
        "A second parsing strategy",
        "Its own error type",
        "Reading the path, and nothing else"
      ],
      "answer": 3,
      "why": "It reads the file and delegates; every parsing rule lives in the pure function."
    },
    {
      "q": "Why is the module importable without side effects?",
      "options": [
        "Because it has no module docstring",
        "Definitions only",
        "Because pydantic defers validation",
        "Because it opens files lazily"
      ],
      "answer": 1,
      "why": "Nothing in the file runs on import beyond building classes and regexes, which is why a test can import it and call one function."
    }
  ],
  "try_it": {
    "prompt": "Print every top-level definition with its line number and count them.",
    "starter": "",
    "solution": "```python\nimport subprocess\n\nout = subprocess.run([\"grep\", \"-n\", \"^class \\\\|^def \", \"app/parser.py\"],\n                     capture_output=True, text=True).stdout\nprint(out.strip())\nprint(\"count:\", len(out.strip().splitlines()))\n```",
    "explanation": "Fifteen definitions across 614 lines — the module is mostly docstrings and the builder's logic."
  },
  "exercise": {
    "prompt": "Give the range of `anchor_findings` and say which two models it consumes.",
    "hint": "It takes a bundle and findings, and returns anchored ones.",
    "solution": "```text\nanchor_findings spans 518-574.\n\nIt consumes a DiffBundle (for the spans per file) and Finding objects (from\napp/models.py), and returns AnchoredFinding objects.\n```",
    "explanation": "It is the one function in the parser that imports from `models`, which is why the two modules are read together."
  },
  "common_mistakes": [
    "Reading `parse_diff` first; it assumes the models you have not met.",
    "Looking for the Markdown renderer here; it is built in `app/main.py` and `app/github_client.py` from `as_row()`.",
    "Assuming the file reads something at import time; it does not."
  ],
  "project_links": [
    {
      "label": "Errors and path helpers",
      "path": "app/parser.py",
      "lines": "69-109"
    },
    {
      "label": "The models",
      "path": "app/parser.py",
      "lines": "112-302"
    },
    {
      "label": "The entry points",
      "path": "app/parser.py",
      "lines": "343-614"
    }
  ],
  "learn_more": [
    {
      "label": "app/parser.py — the parser",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/parser.py"
    },
    {
      "label": "docs/learning/track-2-parser.md",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-2-parser.md"
    }
  ],
  "glossary_terms": [
    "layer — a block that uses only the blocks above it",
    "side effect — work done at import time",
    "entry point — a public function a caller uses"
  ]
});
