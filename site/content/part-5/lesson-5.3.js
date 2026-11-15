/* 5.3 — Counting lines to get new-file numbers
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "5.3",
  "part": 5,
  "part_title": "Unified diffs",
  "title": "Counting lines to get new-file numbers",
  "order": 503,
  "duration_min": 30,
  "concept_md": "### The question a review has to answer\n\nA finding says \"line 42 is unsafe\". In which file, and which numbering? A diff has two numbering systems at once: the old file's and the new file's. A comment on a pull request must point at the **new** file, because that is what the reviewer sees.\n\n### Two counters, three line kinds\n\nThe model records three kinds — `added`, `removed`, `context` — and the parser keeps two counters while walking a hunk's body:\n\n| Line kind | Old counter | New counter |\n|---|---|---|\n| `-` removed | advances | stays |\n| `+` added | stays | advances |\n| space context | advances | advances |\n\nSo an added line's new-file number is the new counter *before* it advances. Get the order wrong by one and every finding lands a line early or late — which is why this is the one piece of arithmetic in the parser that is worth reading twice.\n\n### What the model stores\n\n`DiffLine` carries both numbers, each optional, because a removed line has no new-file position and an added line has no old-file one:\n\n```python\nclass DiffLine(BaseModel):\n    kind: LineKind\n    text: str\n    old_lineno: int | None = None\n    new_lineno: int | None = None\n```\n\n`kind` is one of `added`, `removed` or `context` — the model's names, not the\n`+` / `-` / space characters, which are the text form.\n\n### The compaction\n\nContiguous added lines become a span. `[3, 4, 7, 8]` is stored as `['3-4', '7-8']` by `_spans`, which is what `added_spans` holds and what a reviewer reads at a glance.",
  "code_examples": [
    {
      "id": "5.3-ex-0",
      "lang": "python",
      "caption": "The spans the sample diff produces",
      "code": "from app.parser import parse_diff\n\nwith open(\"samples/sample.diff\", encoding=\"utf-8\") as handle:\n    bundle = parse_diff(handle.read())\n\nfor file in bundle.files:\n    print(file.path, file.change, file.added_line_count, file.added_spans)",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "app/db.py modified 4 ['3-4', '7-8']\napp/report.py added 5 ['1-5']",
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
      "q": "Which counter tells you the new-file line number of an added line?",
      "options": [
        "The hunk's start line",
        "The old counter, read before it advances",
        "The sum of both counters",
        "The new counter, read before it advances"
      ],
      "answer": 3,
      "why": "An added line exists only in the new file, so its position comes from the new counter — and the number belongs to the line itself, so it is read before the increment."
    },
    {
      "q": "A removed line has `new_lineno=None`. Why?",
      "options": [
        "Because the parser has not reached it yet",
        "Because the line does not exist in the new file",
        "Because the line is context",
        "Because the new counter overflowed"
      ],
      "answer": 1,
      "why": "`new_lineno` is set only on `added` and `context` lines; on a `-` line the new counter is left untouched, so there is no number to record."
    },
    {
      "q": "`added_spans` is `['3-4', '7-8']`, not `[3, 4, 7, 8]`. What does the compaction buy?",
      "options": [
        "It reduces the size of the JSON payload",
        "It sorts the numbers into order",
        "A contiguous run becomes one span",
        "It records which lines were removed"
      ],
      "answer": 2,
      "why": "Two runs read as two spans; the ranges carry the same information as the list but show at a glance that the additions are in two blocks, not four scattered lines."
    }
  ],
  "try_it": {
    "prompt": "Print the new-file numbers of every added line in the sample's first file.",
    "starter": "",
    "solution": "```console\n$ python -c \"from pathlib import Path; from app.parser import parse_diff; b = parse_diff(Path('samples/sample.diff').read_text()); print([(l.new_lineno, l.text) for h in b.files[0].hunks for l in h.lines if l.kind == 'added'])\"\n[(3, 'API_TOKEN = \"ghp_exampleTokenValue1234567890\"'), (4, ''), (7, '    query = f\"SELECT * FROM users WHERE id = {uid}\"'), (8, '    return sqlite3.connect(\"app.db\").execute(query).fetchone()')]\n```",
    "explanation": "Lines 3, 4, 7 and 8 of the new file — which is exactly the `['3-4', '7-8']` span, now expanded."
  },
  "exercise": {
    "prompt": "In the first file's hunk, why is the added token on new line 3 rather than line 2?",
    "hint": "Look at what precedes it: a context line and a blank context line.",
    "solution": "```text\nThe hunk starts at new line 1. Two context lines come first — `import sqlite3`\n(new 1) and the blank line (new 2) — so the first `+` is new line 3.\nThe new counter advances on both `+` and space lines, which is why context\nconsumes new-file numbers too.\n```",
    "explanation": "Context lines occupy numbers in the new file even though they are unchanged; skipping them is the classic off-by-N error."
  },
  "common_mistakes": [
    "Advancing only on `+` and ignoring that context lines also consume new-file numbers.",
    "Using the old counter for a comment on a pull request, so every finding lands on the wrong line.",
    "Treating `added_spans` as a list of numbers when it is a list of ranges."
  ],
  "project_links": [
    {
      "label": "The line model with both numbers",
      "path": "app/parser.py",
      "lines": "112-120"
    },
    {
      "label": "The hunk model",
      "path": "app/parser.py",
      "lines": "123-149"
    },
    {
      "label": "The body walk where the counters move",
      "path": "app/parser.py",
      "lines": "375-500"
    }
  ],
  "learn_more": [
    {
      "label": "app/parser.py — the parser",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/parser.py"
    },
    {
      "label": "docs/learning/track-2-parser.md — the parser track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-2-parser.md"
    }
  ],
  "glossary_terms": [
    "new counter — the running line number in the new file",
    "old counter — the running line number in the old file",
    "span — a compact range such as 3-4 covering contiguous added lines"
  ]
});
