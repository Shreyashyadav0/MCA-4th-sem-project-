/* 5.7 — Parsing in code: parse_diff and DiffBundle
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "5.7",
  "part": 5,
  "part_title": "Unified diffs",
  "title": "Parsing in code: parse_diff and DiffBundle",
  "order": 507,
  "duration_min": 30,
  "concept_md": "### One pure function, one thin wrapper\n\n`parse_diff` takes text and returns a `DiffBundle`. It touches no file, opens no socket, and reads no environment variable — which is why the parse captures in this part are one-line Python expressions rather than a running service.\n\n```python\ndef parse_diff(raw: str, *, source: str = \"<diff>\") -> DiffBundle:\n```\n\n`source` is a label that travels with the result, so a bundle can say where it came from without the parser knowing what a file is.\n\n### A third entry point\n\n`bundle_from_source(path, source)` wraps a whole file as one all-added hunk, so\nthe diff-based rules can review a file that was never in a pull request. It is\nwhat `POST /review` uses when you send `code` instead of `diff`.\n\n### The wrapper that does the I/O\n\n```python\ndef parse_diff_file(path: Path) -> DiffBundle:\n```\n\nIt reads the path and calls `parse_diff`. That is the whole of its job, and keeping it separate is what makes the pure function testable without fixtures on disk.\n\n### What the bundle holds\n\n`DiffBundle` is the parse result: the file list, plus the lookups the anchorer needs to answer \"which file is this path?\" and \"is this line inside a changed span?\". Downstream code takes a bundle and never re-parses.\n\n### The empty case\n\nAn empty or whitespace-only input raises `DiffParseError(\"diff is empty\")` rather than returning an empty bundle — the first thing the function body does. An empty diff is a caller mistake, not a diff with no files, and the two would be indistinguishable downstream if both produced a bundle.\n\n### Reading it in order\n\nThe signature is at 343, the empty check is the first statement in the body, then the line split, then the loop that walks headers and hunks. The function is 158 lines and has no branches that are not about the format itself.",
  "code_examples": [
    {
      "id": "5.7-ex-0",
      "lang": "python",
      "caption": "The bundle's files and their summaries",
      "code": "from pathlib import Path\n\nfrom app.parser import parse_diff\n\nbundle = parse_diff(Path(\"samples/sample.diff\").read_text())\nprint(len(bundle.files), [summary.path for summary in bundle.summaries()])",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "2 ['app/db.py', 'app/report.py']",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py",
        "app/parser.py",
        "samples/sample.diff"
      ]
    },
    {
      "id": "5.7-ex-1",
      "lang": "console",
      "caption": "The empty input is rejected, not returned",
      "code": "python -c \"from app.parser import parse_diff\ntry:\n    parse_diff('   \\\\n')\nexcept Exception as exc:\n    print(type(exc).__name__ + ':', exc)\"",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "DiffParseError: diff is empty",
      "why_not": "there is no pydantic in the browser runner and no repository checkout to import from, so the parser cannot be built or run there."
    }
  ],
  "quiz": [
    {
      "q": "Which function reads a diff from disk?",
      "options": [
        "`bundle_from_source`, which reads a file from disk",
        "`parse_diff`, which takes a path",
        "`DiffBundle`, which loads lazily",
        "`parse_diff_file`, wrapping `parse_diff`"
      ],
      "answer": 3,
      "why": "`parse_diff` takes text only; the file-reading is isolated in `parse_diff_file` so the parser itself needs no fixtures."
    },
    {
      "q": "Why does an empty input raise rather than return an empty bundle?",
      "options": [
        "Because DiffBundle cannot be empty",
        "Because empty input is a caller mistake",
        "Because the regex would loop forever",
        "Because the API needs one file at least"
      ],
      "answer": 1,
      "why": "If both produced a bundle, downstream code could not tell a caller's bug from a genuinely file-less diff."
    },
    {
      "q": "What does the `source` argument do?",
      "options": [
        "It selects which parser to use",
        "It validates the paths inside the diff",
        "It labels the bundle with its origin",
        "It sets the file's change kind"
      ],
      "answer": 2,
      "why": "It is provenance for the result — `<diff>` by default, a path or a request label when a caller has one — and the parser never acts on it."
    }
  ],
  "try_it": {
    "prompt": "Parse the sample and print the bundle's `source` label.",
    "starter": "",
    "solution": "```console\n$ python -c \"from pathlib import Path; from app.parser import parse_diff; print(parse_diff(Path('samples/sample.diff').read_text()).source)\"\n<diff>\n```",
    "explanation": "The default, because this call did not say where the text came from — `parse_diff_file` passes the path instead."
  },
  "exercise": {
    "prompt": "Name the three public entry points of the parser and say what each takes and returns.",
    "hint": "Two take text or a path and parse it; the third invents a diff from a file's content.",
    "solution": "```text\nparse_diff(raw, *, source)          -> DiffBundle   text in, model out, no I/O\nparse_diff_file(path)               -> DiffBundle   reads the file, then calls parse_diff\nbundle_from_source(path, source)    -> DiffBundle   wraps a whole file as one all-added hunk\n```",
    "explanation": "Only the middle one performs I/O; the other two are pure, which is what makes the whole surface testable offline."
  },
  "common_mistakes": [
    "Calling `parse_diff` with a path instead of the file's text.",
    "Treating an empty bundle and an empty input as the same case.",
    "Re-parsing a bundle downstream instead of passing it along."
  ],
  "project_links": [
    {
      "label": "parse_diff: signature, docstring and body",
      "path": "app/parser.py",
      "lines": "343-500"
    },
    {
      "label": "DiffBundle",
      "path": "app/parser.py",
      "lines": "206-245"
    },
    {
      "label": "parse_diff_file, the I/O wrapper",
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
      "label": "docs/learning/track-2-parser.md — the parser track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-2-parser.md"
    }
  ],
  "glossary_terms": [
    "pure function — text in, model out, no I/O",
    "bundle — the parse result: files plus lookups",
    "source — the label recording where the text came from"
  ]
});
