/* 7.1 — parse_diff's contract: text in, model out
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "7.1",
  "part": 7,
  "part_title": "The parser",
  "title": "parse_diff's contract: text in, model out",
  "order": 701,
  "duration_min": 20,
  "concept_md": "### The signature is the contract\n\n```python\ndef parse_diff(raw: str, *, source: str = \"<diff>\") -> DiffBundle:\n```\n\nText in, a model out. No path, no file handle, no configuration object. `source` is a label that rides along with the result, so a bundle can say where it came from without the parser knowing what a file is.\n\n### Why purity is worth the extra wrapper\n\nBecause the function touches nothing, a test can call it with a string literal — no fixture on disk, no temporary directory, no cleanup. That is why this part's examples run in a browser: `parse_diff` needs only the module and the text.\n\nThe cost is one thin wrapper, `parse_diff_file`, which reads the path and calls the pure function.\n\n### Three things it refuses\n\nAn empty or whitespace-only input raises `DiffParseError(\"diff is empty\")`. Text with no file headers raises `DiffParseError(\"no file headers found…\")`. A file it cannot read, in the wrapper, raises the same type. Everything else is data — including a diff whose hunks are short, which is tolerated rather than raised.\n\n### What \"no I/O\" buys downstream\n\nThe engine, the CLI and the API all parse the same way, because there is only one way. Nothing can parse a diff with different rules because it happens to have a file open.",
  "code_examples": [
    {
      "id": "7.1-ex-0",
      "lang": "python",
      "caption": "A string literal is the whole input",
      "code": "from app.parser import parse_diff\n\nbundle = parse_diff(\"diff --git a/x.py b/x.py\\n--- a/x.py\\n+++ b/x.py\\n@@ -1,2 +1,2 @@\\n-a\\n+b\\n c\\n\")\nprint(\"files:\", len(bundle.files))\nprint(\"source:\", bundle.source)\nprint(\"kind:\", bundle.files[0].change, \"| hunks:\", len(bundle.files[0].hunks))",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "files: 1\nsource: <diff>\nkind: modified | hunks: 1",
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
      "q": "What does `parse_diff` take as its first argument?",
      "options": [
        "A bundle to fill in",
        "A path to a diff file",
        "An open file handle",
        "The diff text itself"
      ],
      "answer": 3,
      "why": "The text, which is what makes the function testable with a literal and runnable in the browser; reading a path is `parse_diff_file`'s job."
    },
    {
      "q": "What is `source` for?",
      "options": [
        "The path used to read the file",
        "A label recording where the text came from",
        "A switch between git and plain diffs",
        "The name of the module that called it, which the parser never records"
      ],
      "answer": 1,
      "why": "It travels with the bundle so a downstream message can say which input produced it; the parser never acts on it."
    },
    {
      "q": "Which input does the parser tolerate rather than reject?",
      "options": [
        "An empty string",
        "A diff with no file headers, which raises rather than returning empty",
        "A hunk whose body is shorter than its header claims",
        "A file it cannot read"
      ],
      "answer": 2,
      "why": "A short hunk is closed and the next line is re-read as a header, so a truncated patch still yields a bundle; the other three raise."
    }
  ],
  "try_it": {
    "prompt": "Parse a one-file diff written inline and print the change kind and the added span.",
    "starter": "",
    "solution": "```python\nfrom app.parser import parse_diff\n\ntext = \"diff --git a/x.py b/x.py\\n--- a/x.py\\n+++ b/x.py\\n@@ -1,1 +1,2 @@\\n a\\n+b\\n\"\nbundle = parse_diff(text)\nprint(bundle.files[0].change, bundle.files[0].added_spans)\n```",
    "explanation": "`modified ['2']` — one file, one added line, found without any file on disk."
  },
  "exercise": {
    "prompt": "Write the two-line test that proves an empty diff is rejected, and say which call you would write to prove a file on disk is read.",
    "hint": "One is pure, the other is the wrapper.",
    "solution": "```python\nimport pytest\nfrom app.parser import DiffParseError, parse_diff\n\ndef test_empty_is_rejected() -> None:\n    with pytest.raises(DiffParseError):\n        parse_diff(\"   \\n\")\n\n# and the wrapper, for a real file:\n# parse_diff_file(Path(\"samples/sample.diff\"))\n```",
    "explanation": "The pure case needs no fixture, which is the practical difference between the two entry points."
  },
  "common_mistakes": [
    "Passing a `Path` to `parse_diff` and wondering why every diff is empty.",
    "Assuming a truncated hunk raises; it is tolerated by design.",
    "Treating `source` as a filename the parser will open."
  ],
  "project_links": [
    {
      "label": "parse_diff, signature to return",
      "path": "app/parser.py",
      "lines": "343-500"
    },
    {
      "label": "The I/O wrapper",
      "path": "app/parser.py",
      "lines": "503-515"
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
    "pure function — depends only on its arguments",
    "wrapper — a thin function that performs I/O then delegates",
    "bundle — the parse result"
  ]
});
