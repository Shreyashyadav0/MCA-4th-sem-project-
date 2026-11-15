/* 6.8 — Guided read of app/models.py
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "6.8",
  "part": 6,
  "part_title": "The five-field contract",
  "title": "Guided read of app/models.py",
  "order": 608,
  "duration_min": 30,
  "concept_md": "### 194 lines, in four blocks\n\n**1. The patterns** — `_LINE_RE` at **42** and `_ORDER` at **43**. Two module constants that the rest of the file leans on.\n\n**2. The enums** — `Severity` at **46** with its `rank` at **55**, and `AnchorStatus` at **60**. Both are `str` subclasses so they serialise as text.\n\n**3. The finding** — `Finding` at **68**, its three-field config, its five fields, the line validator at **87** and `as_row` at **97**. Then `AnchoredFinding` at **108**, which wraps a finding and adds where it landed.\n\n**4. The helpers and the result** — `severity_counts` at **125**, `sort_findings` at **133**, `verdict_for` at **141**, then `ReviewResult` at **151** with its computed verdict, counts and JSON.\n\n### Read it in that order and it is short\n\nThe file is a contract, then the values it can take, then the atom, then the container. Nothing in it knows about HTTP, diffs or GitHub — which is why the whole review pipeline can be tested without any of them.\n\n### The two things to carry away\n\n`Finding` is frozen and forbids extras, so a finding is a record rather than a bag. And `verdict_for` is four lines of tally, so the gate decision is reproducible from the findings alone.",
  "code_examples": [
    {
      "id": "6.8-ex-0",
      "lang": "console",
      "caption": "The file's own index, from grep",
      "code": "grep -n '^class \\|^def \\|^_' app/models.py",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "the browser runner has Python but no shell, so this command cannot run there; it needs a checkout on disk.",
      "expected_output": "28:__all__ = [\n42:_LINE_RE = re.compile(r\"^\\d+(?:-\\d+)?$\")\n43:_ORDER: tuple[str, ...] = (\"LOW\", \"MEDIUM\", \"HIGH\", \"CRITICAL\")\n46:class Severity(str, Enum):\n60:class AnchorStatus(str, Enum):\n68:class Finding(BaseModel):\n108:class AnchoredFinding(BaseModel):\n125:def severity_counts(findings: Iterable[Finding]) -> dict[str, int]:\n133:def sort_findings(findings: Iterable[Finding]) -> list[Finding]:\n141:def verdict_for(findings: Iterable[Finding]) -> str:\n151:class ReviewResult(BaseModel):"
    }
  ],
  "quiz": [
    {
      "q": "Which block would you read to learn what values a severity may take?",
      "options": [
        "The enums, at lines 46 and 60",
        "The helpers, from 125",
        "The result, from 151",
        "The patterns, at line 42"
      ],
      "answer": 0,
      "why": "`Severity` is the closed set, and `AnchorStatus` beside it is the other enum; both are declared before anything uses them."
    },
    {
      "q": "What does `AnchoredFinding` add to a `Finding`?",
      "options": [
        "The verdict",
        "A sixth severity",
        "The suggested fix",
        "Where the finding landed relative to the diff"
      ],
      "answer": 3,
      "why": "It wraps a finding and carries the anchor status and the line it matched, which is a property of the review rather than of the finding."
    },
    {
      "q": "Why can the review pipeline be tested without HTTP or a diff?",
      "options": [
        "Because the models are frozen",
        "Because nothing in models.py knows about either",
        "Because the file is under 200 lines",
        "Because Pydantic mocks the network"
      ],
      "answer": 1,
      "why": "The contract file depends only on pydantic, so a test can build findings and assert a verdict with no server and no diff."
    }
  ],
  "try_it": {
    "prompt": "Print every class and function in the file with its line number, and count them.",
    "starter": "",
    "solution": "```python\nimport subprocess\n\nout = subprocess.run([\"grep\", \"-n\", \"^class \\\\|^def \", \"app/models.py\"],\n                     capture_output=True, text=True).stdout\nprint(out.strip())\nprint(\"count:\", len(out.strip().splitlines()))\n```",
    "explanation": "Eight definitions in 194 lines — the file is small because it holds a contract, not behaviour."
  },
  "exercise": {
    "prompt": "Give the line range of `ReviewResult` and name three things it computes rather than stores.",
    "hint": "The computed fields are decorated.",
    "solution": "```text\nReviewResult spans 151-194.\n\nIt computes: sorted_findings (180), counts (183) and verdict (188) — each derived\nfrom the findings it holds, and each dropped from input by _drop_computed.\n```",
    "explanation": "Three derived values and one serialiser, which is why the class is 44 lines rather than a data bag with a stored verdict."
  },
  "common_mistakes": [
    "Reading `ReviewResult` first; it assumes the finding contract you have not met yet.",
    "Assuming `AnchorStatus` is a severity — it describes placement, not seriousness.",
    "Looking for HTTP or GitHub knowledge in this file; it has none."
  ],
  "project_links": [
    {
      "label": "The patterns and the severity ladder",
      "path": "app/models.py",
      "lines": "42-58"
    },
    {
      "label": "The finding and its anchored wrapper",
      "path": "app/models.py",
      "lines": "68-124"
    },
    {
      "label": "The result and its computed values",
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
      "label": "docs/decisions/0001-five-field-finding.md",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0001-five-field-finding.md"
    }
  ],
  "glossary_terms": [
    "contract file — a module that declares shapes and no behaviour",
    "anchor status — anchored, file_only or unanchored",
    "derived value — computed from the model rather than stored"
  ]
});
