/* 7.4 — added_spans and the _spans compaction
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "7.4",
  "part": 7,
  "part_title": "The parser",
  "title": "added_spans and the _spans compaction",
  "order": 704,
  "duration_min": 30,
  "concept_md": "### The problem with a list of numbers\n\nA file with four added lines reports `[3, 4, 7, 8]`. That is accurate and hard to read: a reviewer has to reconstruct that it means two blocks rather than four scattered lines.\n\n`_spans` turns a sorted list into ranges:\n\n```text\n[3, 4, 7, 8]   ->   ['3-4', '7-8']\n[1, 2, 3, 4, 5] ->   ['1-5']\n[9]             ->   ['9']\n```\n\n### Why the shape matters downstream\n\nThe anchorer asks \"does this finding's line fall in an added span?\". With ranges it splits on `-` and compares two integers; with a list it would scan. And the Markdown comment shows the ranges, so the reader sees two blocks at a glance.\n\n### The invariant\n\n`added_spans` covers exactly the added line numbers, no more and no fewer. `added_line_count` is the length of the underlying list, not of the span strings — which is why `['3-4','7-8']` sits beside `4`.\n\n### Where it is computed\n\nIn the builder's `finish()`, from the `DiffLine` objects it collected, so the spans and the lines cannot disagree.\n\n### Why not compute it on demand\n\nEvery consumer wants the spans: the anchorer, the summary, the Markdown table. Computing them once, where the lines are already in hand, is cheaper than four callers each walking the list — and it keeps the invariant in one place.",
  "code_examples": [
    {
      "id": "7.4-ex-0",
      "lang": "python",
      "caption": "The compaction, on four inputs",
      "code": "from app.parser import _spans\n\nfor numbers in ([3, 4, 7, 8], [1, 2, 3, 4, 5], [9], [2, 3, 5]):\n    print(numbers, \"->\", _spans(numbers))",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "[3, 4, 7, 8] -> ['3-4', '7-8']\n[1, 2, 3, 4, 5] -> ['1-5']\n[9] -> ['9']\n[2, 3, 5] -> ['2-3', '5']",
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
      "q": "What does `_spans([2, 3, 5])` return?",
      "options": [
        "`['2-3', '5']`",
        "`['2-5']`",
        "`['2', '3', '5']`",
        "`['2-3-5']`"
      ],
      "answer": 0,
      "why": "A run becomes a range and a lone number stays bare, so a gap always produces a new element."
    },
    {
      "q": "What is `added_line_count` when `added_spans` is `['3-4', '7-8']`?",
      "options": [
        "8, the last line touched",
        "2, the number of spans",
        "7, the highest line number",
        "4, the number of added lines"
      ],
      "answer": 3,
      "why": "The count is of lines, not of span strings — which is why the two fields sit beside each other rather than being derived from one."
    },
    {
      "q": "Why does the anchorer prefer ranges over a list?",
      "options": [
        "Because ranges use less JSON",
        "A range is two comparisons rather than a scan",
        "Because a list cannot be serialised",
        "Because ranges preserve order"
      ],
      "answer": 1,
      "why": "Testing containment in a range is arithmetic; testing membership in a list is a loop, and the anchorer does it for every finding."
    }
  ],
  "try_it": {
    "prompt": "Produce spans for the sample's first file and count the added lines from the spans.",
    "starter": "",
    "solution": "```python\nfrom pathlib import Path\nfrom app.parser import parse_diff\n\nf = parse_diff(Path(\"samples/sample.diff\").read_text()).files[0]\nprint(f.added_spans, f.added_line_count)\ntotal = sum(int(s.split(\"-\")[-1]) - int(s.split(\"-\")[0]) + 1 for s in f.added_spans)\nprint(\"from the spans:\", total)\n```",
    "explanation": "`['3-4', '7-8'] 4` and then `4` again — the spans and the count agree, which is the invariant."
  },
  "exercise": {
    "prompt": "A file adds lines 5 through 12 with no gaps, then line 20. Write the `added_spans` and the count.",
    "hint": "One run, then a single line.",
    "solution": "```text\nadded_spans      ['5-12', '20']\nadded_line_count 9        (8 lines in the run, plus 1)\n```",
    "explanation": "Eight consecutive lines collapse to one range; the isolated line stays bare because a range of one reads worse than the number."
  },
  "common_mistakes": [
    "Computing the count from the span strings rather than from the lines.",
    "Sorting the numbers after compacting, which breaks the runs.",
    "Assuming adjacent spans merge across a gap of one line."
  ],
  "project_links": [
    {
      "label": "_spans, the compaction",
      "path": "app/parser.py",
      "lines": "89-105"
    },
    {
      "label": "Where added_spans is built",
      "path": "app/parser.py",
      "lines": "305-342"
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
    "span — a compact range of added lines",
    "compaction — collapsing a sorted list into ranges",
    "invariant — a property that must hold for the data to be correct"
  ]
});
