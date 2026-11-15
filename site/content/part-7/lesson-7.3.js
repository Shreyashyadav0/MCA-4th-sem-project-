/* 7.3 — FileDiff versus FileSummary
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "7.3",
  "part": 7,
  "part_title": "The parser",
  "title": "FileDiff versus FileSummary",
  "order": 703,
  "duration_min": 25,
  "concept_md": "### Two shapes for two questions\n\n`FileDiff` answers \"what changed in this file?\" — it holds the hunks, every body line, and the spans of added lines.\n\n`FileSummary` answers \"which files changed, and how much?\" — it holds the path, the change kind, the counts, the spans and the binary flag, and no lines at all.\n\n### Why not one model with an optional list\n\nBecause the line list is large and the summary is what most callers want. A review comment needs the summary; the anchorer needs the spans; only a deep inspection needs the lines. Keeping them apart means the common path carries kilobytes rather than megabytes.\n\n`DiffBundle.summaries()` at **234** builds them on demand from the diffs it holds, so the two shapes cannot disagree — the summary is derived, not stored twice.\n\n### The overlap is deliberate\n\nBoth carry `path`, `change`, `added_spans`, `added_line_count`, `hunk_count` and `binary`. That duplication is the point: a summary is a self-contained answer, not a view that needs the diff to be readable.\n\n### What follows for tests\n\nA test about counts can build a summary; a test about line numbers needs a diff. The split makes the cheap test cheap.\n\n### What the API returns\n\n`GET /reviews/{id}` returns summaries, not diffs, because a list of reviews does not need every line of every file. The detail view builds one `FileDiff` at a time. The two shapes exist because two endpoints ask two different questions.",
  "code_examples": [
    {
      "id": "7.3-ex-0",
      "lang": "python",
      "caption": "The same file in both shapes",
      "code": "from pathlib import Path\nfrom app.parser import parse_diff\n\nbundle = parse_diff(Path(\"samples/sample.diff\").read_text())\nfile = bundle.files[0]\nsummary = bundle.summaries()[0]\nprint(\"diff    :\", file.path, len(file.hunks), \"hunk(s),\", sum(len(h.lines) for h in file.hunks), \"lines\")\nprint(\"summary :\", summary.path, summary.change, summary.added_line_count, summary.added_spans)",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "diff    : app/db.py 1 hunk(s), 9 lines\nsummary : app/db.py modified 4 ['3-4', '7-8']",
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
      "q": "Which model carries the body lines?",
      "options": [
        "`DiffBundle`, which holds both",
        "`FileSummary`, which holds the counts",
        "`FileDiff`, which holds hunks and their lines",
        "`DiffReviewResult`, which holds the review"
      ],
      "answer": 2,
      "why": "The lines live in `FileDiff`'s hunks; the summary carries only the numbers derived from them."
    },
    {
      "q": "Why is the summary derived rather than stored alongside?",
      "options": [
        "So the two cannot disagree about the same file",
        "Because storage is expensive",
        "Because `FileSummary` is frozen",
        "Because the bundle is immutable"
      ],
      "answer": 0,
      "why": "`summaries()` computes from the diffs, so a change to the diff cannot leave a stale summary behind."
    },
    {
      "q": "A test needs only the added span of one file. Which shape?",
      "options": [
        "Neither; spans are computed separately",
        "The diff, because spans live in the hunks",
        "The bundle, because it holds everything",
        "The summary, which carries `added_spans` without the lines"
      ],
      "answer": 3,
      "why": "The span is on both, so the cheaper shape is enough — that is the reason the two exist."
    }
  ],
  "try_it": {
    "prompt": "Print the summary for each file in the sample, then print how many body lines the diff holds.",
    "starter": "",
    "solution": "```python\nfrom pathlib import Path\nfrom app.parser import parse_diff\n\nbundle = parse_diff(Path(\"samples/sample.diff\").read_text())\nfor s in bundle.summaries():\n    print(s.path, s.change, s.added_line_count)\nprint(\"body lines:\", sum(len(h.lines) for f in bundle.files for h in f.hunks))\n```",
    "explanation": "Two summaries and thirteen body lines — the numbers a reviewer reads, and the data only a deep pass needs."
  },
  "exercise": {
    "prompt": "Name three fields the two models share and one only `FileDiff` has.",
    "hint": "The shared ones are the summary's whole content.",
    "solution": "```text\nShared: path, change, added_spans (also added_line_count, hunk_count, binary).\nOnly FileDiff: hunks (and therefore lines, old_path, new_path).\n```",
    "explanation": "The summary is the diff minus the hunks — which is exactly why it can be derived from it."
  },
  "common_mistakes": [
    "Trying to read body lines off a `FileSummary`; it has none.",
    "Storing a summary next to the diff and letting the two drift.",
    "Assuming the summary is a different parse; it is derived from the same one."
  ],
  "project_links": [
    {
      "label": "FileDiff, with the hunks",
      "path": "app/parser.py",
      "lines": "152-192"
    },
    {
      "label": "FileSummary, without them",
      "path": "app/parser.py",
      "lines": "193-205"
    },
    {
      "label": "summaries(), which derives them",
      "path": "app/parser.py",
      "lines": "234-245"
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
    "FileDiff — a file with its hunks and lines",
    "FileSummary — a file with counts and no lines",
    "derive — compute from something already held"
  ]
});
