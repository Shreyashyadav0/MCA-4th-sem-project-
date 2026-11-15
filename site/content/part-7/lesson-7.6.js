/* 7.6 — anchor_findings: anchored, file_only, unanchored
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "7.6",
  "part": 7,
  "part_title": "The parser",
  "title": "anchor_findings: anchored, file_only, unanchored",
  "order": 706,
  "duration_min": 30,
  "concept_md": "### The question a comment needs answered\n\nA finding names a line. A pull request comment can only be posted on a line that exists in the diff. `anchor_findings` at **518** decides which of three things is true:\n\n- **anchored** — the file is in the diff and the finding's line touches an added line. An inline comment is possible.\n- **file_only** — the file is in the diff but that line was not changed. The comment must go in the summary.\n- **unanchored** — the file is not in the diff at all. Nothing inline is possible.\n\n### Why three and not two\n\nTwo would force \"file is in the diff but the line is not\" into either the inline case, where GitHub would reject the comment, or the unanchored case, where the file name would be lost. The third state exists so the tool can say something true about a file it did see.\n\n### The comparison\n\nThe finding's range is parsed with `_parse_range` and compared against `added_line_numbers`, a set of integers on the file. A range that contains any added line counts as anchored, which is why a finding on `42-45` anchors when only line 44 changed.\n\n### What it returns\n\n`AnchoredFinding` — the original five fields plus where it landed. Nothing is dropped, so a summary can still show every finding.",
  "code_examples": [
    {
      "id": "7.6-ex-0",
      "lang": "python",
      "caption": "Three findings, three verdicts",
      "code": "from pathlib import Path\nfrom app.models import Finding\nfrom app.parser import anchor_findings, parse_diff\n\nbundle = parse_diff(Path(\"samples/sample.diff\").read_text())\nfindings = [\n    Finding(file=\"app/db.py\", line=\"3\", severity=\"HIGH\", issue=\"added line\", suggested_fix=\"x\"),\n    Finding(file=\"app/db.py\", line=\"20\", severity=\"HIGH\", issue=\"untouched line\", suggested_fix=\"x\"),\n    Finding(file=\"app/other.py\", line=\"1\", severity=\"HIGH\", issue=\"absent file\", suggested_fix=\"x\"),\n]\nfor anchored in anchor_findings(bundle, findings):\n    print(anchored.finding.issue, \"->\", anchored.status.value)",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "added line -> anchored\nuntouched line -> file_only\nabsent file -> unanchored",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py",
        "app/parser.py",
        "samples/sample.diff"
      ]
    }
  ],
  "quiz": [
    {
      "q": "When is a finding `file_only`?",
      "options": [
        "The file is absent from the diff",
        "The file is in the diff but the line is not an added line",
        "The line is in an added span",
        "The finding has no line number"
      ],
      "answer": 1,
      "why": "The file is present so the name is useful, but there is no changed line to attach a comment to, so the summary carries it."
    },
    {
      "q": "A finding covers `42-45` and only line 44 changed. What is its status?",
      "options": [
        "Unanchored, because the range is not a single line",
        "File only, because not every line changed",
        "Anchored, because the range overlaps an added line",
        "Anchored only if line 42 changed"
      ],
      "answer": 2,
      "why": "The comparison is an overlap test, so one changed line inside the range is enough to attach the comment."
    },
    {
      "q": "What does `anchor_findings` return for each finding?",
      "options": [
        "The five fields plus where it landed",
        "Only the anchored ones",
        "A copy with the line rewritten to the diff's numbering",
        "A boolean per finding"
      ],
      "answer": 0,
      "why": "Nothing is filtered or altered; the wrapper records the status so a consumer decides what to post where."
    }
  ],
  "try_it": {
    "prompt": "Anchor a finding on a line the diff does not change and print its status.",
    "starter": "",
    "solution": "```python\nfrom pathlib import Path\nfrom app.models import Finding\nfrom app.parser import anchor_findings, parse_diff\n\nbundle = parse_diff(Path(\"samples/sample.diff\").read_text())\nf = Finding(file=\"app/db.py\", line=\"20\", severity=\"LOW\", issue=\"old line\", suggested_fix=\"x\")\nprint(anchor_findings(bundle, [f])[0].status.value)\n```",
    "explanation": "`file_only` — the file is there, the line was not touched."
  },
  "exercise": {
    "prompt": "Which of the three statuses would a finding against `app/report.py:5` get, and why?",
    "hint": "Look at the spans for that file.",
    "solution": "```text\nanchored. app/report.py is a new file whose added_spans are ['1-5'], so line 5\nis an added line and an inline comment can be posted against it.\n```",
    "explanation": "A new file is entirely added lines, which is why every finding in it anchors."
  },
  "common_mistakes": [
    "Treating `file_only` as unanchored and losing the file name.",
    "Requiring every line of a range to be added before anchoring.",
    "Posting an inline comment for an unanchored finding, which GitHub rejects."
  ],
  "project_links": [
    {
      "label": "anchor_findings",
      "path": "app/parser.py",
      "lines": "518-572"
    },
    {
      "label": "The anchored wrapper",
      "path": "app/models.py",
      "lines": "108-122"
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
    "anchored — the line is an added line, so inline is possible",
    "file_only — the file is present, the line is not changed",
    "unanchored — the file is not in the diff"
  ]
});
