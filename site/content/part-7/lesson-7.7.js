/* 7.7 — bundle_from_source: reviewing a whole file
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "7.7",
  "part": 7,
  "part_title": "The parser",
  "title": "bundle_from_source: reviewing a whole file",
  "order": 707,
  "duration_min": 25,
  "concept_md": "### Not every review starts from a diff\n\nSometimes you want the rules run over a file that was never in a pull request — a pasted snippet, a file from disk, the output of `POST /review` with `code` rather than `diff`.\n\n`bundle_from_source(path, source)` at **575** manufactures a one-file diff in which every line is an added line, then hands it to the same pipeline.\n\n### Why fake a diff rather than write a second path\n\nEvery rule, every anchor, every renderer already speaks the diff vocabulary. A second entry point with its own model would duplicate all of it and drift. Synthesising the diff means there is one pipeline, and a finding from a pasted snippet behaves exactly like one from a pull request.\n\n### The consequence\n\nEverything anchors. A whole file is an added span from line 1, so `anchor_findings` returns `anchored` for every finding in it — which is correct, since there is no \"unchanged line\" in a file that has no previous version.\n\n### What it does not do\n\nIt does not read the file; the caller passes the text. The name says \"from source\" because `source` is the content, not a path to read.\n\n### Where it is called\n\n`POST /review` uses it when the request carries `code` instead of `diff`, and the CLI uses it for a single file argument. Both then run the same rules and the same renderer, which is the point: a pasted snippet and a pull request produce findings of the same shape.",
  "code_examples": [
    {
      "id": "7.7-ex-0",
      "lang": "python",
      "caption": "A whole file as a one-file diff",
      "code": "from app.parser import bundle_from_source\n\ntext = \"API_TOKEN = \\\"ghp_example\\\"\\ndef get(uid):\\n    return uid\\n\"\nbundle = bundle_from_source(\"snippet.py\", text)\nprint(\"files:\", len(bundle.files), \"| kind:\", bundle.files[0].change)\nprint(\"spans:\", bundle.files[0].added_spans, \"| count:\", bundle.files[0].added_line_count)\nprint(\"source:\", bundle.source)",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "files: 1 | kind: added\nspans: ['1-3'] | count: 3\nsource: snippet.py",
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
      "q": "What does `bundle_from_source` produce?",
      "options": [
        "A diff with the file marked modified, which still has a hunk",
        "A parsed file with no hunks",
        "A one-file diff in which every line is added",
        "A bundle with zero files"
      ],
      "answer": 2,
      "why": "It synthesises an all-added diff so the existing pipeline can run unchanged on a file that has no previous version."
    },
    {
      "q": "Why synthesise rather than add a second review path?",
      "options": [
        "Every rule and renderer already speaks the diff vocabulary",
        "Because diffs are cheaper to store",
        "Because the parser cannot read files and needs the text instead",
        "Because GitHub requires a diff"
      ],
      "answer": 0,
      "why": "A second model would duplicate the rules, the anchoring and the rendering, and the two would drift apart."
    },
    {
      "q": "Does `bundle_from_source` read the file at `path`?",
      "options": [
        "It downloads it from GitHub",
        "Yes, it opens the path and reads it",
        "It reads the path only if the file already exists on disk",
        "No — `source` is the content and `path` is only the label"
      ],
      "answer": 3,
      "why": "The caller supplies the text; the path is used as the file's name in findings, which is why the API can review a pasted snippet."
    }
  ],
  "try_it": {
    "prompt": "Wrap three lines of code as a bundle and print the file's span.",
    "starter": "",
    "solution": "```python\nfrom app.parser import bundle_from_source\n\nbundle = bundle_from_source(\"x.py\", \"a = 1\\nb = 2\\nc = 3\\n\")\nprint(bundle.files[0].added_spans, bundle.files[0].added_line_count)\n```",
    "explanation": "`['1-3'] 3` — one span covering the whole file, because every line is new."
  },
  "exercise": {
    "prompt": "Why does every finding in a `bundle_from_source` result anchor?",
    "hint": "What does the span cover?",
    "solution": "```text\nBecause the whole file is one added span from line 1, so every finding's line\nfalls inside it. There is no unchanged line to be file_only against.\n```",
    "explanation": "Anchoring asks whether the line was added; in a file with no previous version, every line was."
  },
  "common_mistakes": [
    "Passing a path expecting the function to read it.",
    "Expecting some findings to be `file_only` in a whole-file review.",
    "Writing a second pipeline for pasted code instead of reusing this one."
  ],
  "project_links": [
    {
      "label": "bundle_from_source",
      "path": "app/parser.py",
      "lines": "575-614"
    },
    {
      "label": "The endpoint that uses it",
      "path": "app/main.py",
      "lines": "666-668"
    }
  ],
  "learn_more": [
    {
      "label": "app/parser.py — the parser",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/parser.py"
    },
    {
      "label": "app/main.py — the review endpoint",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/main.py"
    }
  ],
  "glossary_terms": [
    "synthesise — build a diff from something that is not one",
    "whole-file review — rules run over code with no previous version",
    "label — a name that is not read"
  ]
});
