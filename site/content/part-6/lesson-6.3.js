/* 6.3 — The Severity enum and what orders it
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "6.3",
  "part": 6,
  "part_title": "The five-field contract",
  "title": "The Severity enum and what orders it",
  "order": 603,
  "duration_min": 20,
  "concept_md": "### Four values, no more\n\n```python\nclass Severity(str, Enum):\n    LOW = \"LOW\"\n    MEDIUM = \"MEDIUM\"\n    HIGH = \"HIGH\"\n    CRITICAL = \"CRITICAL\"\n```\n\nIt subclasses `str`, so a finding serialises to `\"HIGH\"` rather than to an enum wrapper — the JSON a client sees is the same text a human reads.\n\n### The order is data, not the alphabet\n\n```python\n_ORDER = (\"LOW\", \"MEDIUM\", \"HIGH\", \"CRITICAL\")\n```\n\nAlphabetically, CRITICAL comes before LOW, which is exactly backwards for a reviewer. `rank` looks the value up in `_ORDER` and returns 0 to 3, and `sort_findings` sorts by `-rank` so the worst finding is first.\n\n### The repr is not the value\n\nNeither `str()` nor `repr()` gives you the bare value: `str()` yields `Severity.HIGH` and `repr()` yields `<Severity.HIGH: 'HIGH'>`. Only `.value` is `HIGH`, which is why the row helper calls it explicitly and why the JSON a client sees is the bare text.\n\n### The verdict uses the same ladder\n\n`verdict_for` blocks on CRITICAL or HIGH, approves with comments on MEDIUM or LOW, and approves on an empty list. Three outcomes, derived from the same four names — no second scale to keep in step.\n\n### Why an enum and not four strings\n\nA string field would accept `\"severe\"`, and the failure would surface at the consumer that renders the severity — after the review had already been posted. The enum moves that failure to the boundary, where the message names the four legal values and nothing has been sent.",
  "code_examples": [
    {
      "id": "6.3-ex-0",
      "lang": "python",
      "caption": "The ladder, the repr, and the order it produces",
      "code": "from app.models import Finding, Severity, sort_findings\n\nprint(str(Severity.HIGH), \"|\", repr(Severity.HIGH), \"|\", Severity.HIGH.rank)\nprint([s.value for s in Severity])\n\nfindings = [\n    Finding(file=\"a.py\", line=\"9\", severity=\"LOW\", issue=\"minor\", suggested_fix=\"x\"),\n    Finding(file=\"a.py\", line=\"2\", severity=\"CRITICAL\", issue=\"urgent\", suggested_fix=\"y\"),\n    Finding(file=\"a.py\", line=\"5\", severity=\"MEDIUM\", issue=\"middle\", suggested_fix=\"z\"),\n]\nprint([f.severity.value for f in sort_findings(findings)])",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "Severity.HIGH | <Severity.HIGH: 'HIGH'> | 2\n['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']\n['CRITICAL', 'MEDIUM', 'LOW']",
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
      "q": "Why does `Severity` subclass `str`?",
      "options": [
        "So Pydantic accepts it as a field type",
        "So it can be compared with integers",
        "So it serialises as its own text rather than an enum wrapper",
        "So the values can be sorted alphabetically in a report column"
      ],
      "answer": 2,
      "why": "A `str` mixin makes the JSON and the display text the same string, which is why no consumer needs an enum encoder."
    },
    {
      "q": "What does `rank` return for CRITICAL?",
      "options": [
        "3, its index in the declared order",
        "1, because it is the worst",
        "0, because ranks start at zero for the worst",
        "The string \"CRITICAL\""
      ],
      "answer": 0,
      "why": "`_ORDER` is LOW, MEDIUM, HIGH, CRITICAL, so CRITICAL sits at index 3 and sorting by `-rank` puts it first."
    },
    {
      "q": "Which severity mix makes `verdict_for` return `block`?",
      "options": [
        "Only CRITICAL, never HIGH",
        "Two or more MEDIUM findings, which is a block in some tools",
        "A single LOW finding",
        "Any CRITICAL or HIGH finding"
      ],
      "answer": 3,
      "why": "The gate is deliberately blunt: one HIGH is enough to block, and the lesser severities approve with comments."
    }
  ],
  "try_it": {
    "prompt": "Print the rank of every severity and check the order is the one a reviewer expects.",
    "starter": "",
    "solution": "```python\nfrom app.models import Severity\n\nfor name in Severity:\n    print(name.value, name.rank)\n```",
    "explanation": "LOW 0, MEDIUM 1, HIGH 2, CRITICAL 3 — ascending, so `-rank` sorts the worst first."
  },
  "exercise": {
    "prompt": "Two findings share a severity and a file. What breaks the tie, and why that field?",
    "hint": "Read the sort key.",
    "solution": "```text\nsort_findings sorts by (-rank, file, int(line.split(\"-\")[0]), issue).\nAfter severity and file, the first line number breaks the tie, then the issue text.\nLine order matters because a reviewer reads a file top to bottom; the issue text\nis the final tiebreak so the output is deterministic.\n```",
    "explanation": "Determinism is the point: two runs over the same findings must produce the same order, or a diff of two reviews would show noise."
  },
  "common_mistakes": [
    "Sorting severities alphabetically, which puts CRITICAL last.",
    "Comparing a `Severity` member to its name with `==` on the enum rather than on `.value`.",
    "Adding a fifth severity, which breaks the rank ladder and the verdict."
  ],
  "project_links": [
    {
      "label": "The enum and its rank",
      "path": "app/models.py",
      "lines": "46-57"
    },
    {
      "label": "The sort that uses it",
      "path": "app/models.py",
      "lines": "133-138"
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
    "enum — a closed set of named values",
    "rank — the position of a severity in the ladder",
    "verdict — block, approve with comments, or approve"
  ]
});
