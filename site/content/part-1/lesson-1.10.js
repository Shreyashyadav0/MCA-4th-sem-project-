/* 1.10 — pathlib, json and re
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "1.10",
  "part": 1,
  "part_title": "Python fundamentals",
  "title": "pathlib, json and re",
  "order": 110,
  "duration_min": 25,
  "concept_md": "### pathlib instead of string paths\n\n```python\nfrom pathlib import Path\npath = Path(\"benchmarks/golden/expected.json\")\npath.read_text(encoding=\"utf-8\")\n```\n\n`Path` gives you `/` for joining, `.exists()`, `.is_file()`, `.stat().st_size` and `.read_text()`. The repository reads files this way everywhere — `app/cli.py`'s `read_source` checks existence, size and UTF-8 before returning text, and each failure becomes a `ReviewInputError`.\n\n### json: two functions, one caveat\n\n`json.loads(text)` parses a string; `json.loads(path.read_text())` is the file version without the file handle. `json.dumps(obj, indent=2)` writes it back. The caveat: JSON has no tuples, no sets and no comments, so a round trip through JSON turns a tuple into a list.\n\n### re: compile once, then use the groups\n\n```python\n# simplified: the real pattern makes the counts optional\nHUNK = re.compile(r\"^@@ -(\\d+),(\\d+) \\+(\\d+),(\\d+) @@ ?(.*)$\")\nmatch = HUNK.match(\"@@ -1,5 +1,8 @@ def check():\")\nmatch.group(1)   # \"1\"\n```\n\n`match` anchors at the start; `search` scans; `findall` returns every hit. Compiled patterns are reused and readable — `app/parser.py` keeps its hunk-header pattern in a module constant for exactly that reason.\n\n### Where this shows up\n\n`benchmarks/loader.py` loads `expected.json` next to each sample's diff and validates it into `ExpectedFinding` objects, so a malformed label file fails with a message naming the sample rather than a bare KeyError.\n\n### One more habit worth copying\n\n`Path` also removes the `os.path.join` dance from the rest of the codebase: `root / sample_id / \"expected.json\"` is a path, and `sorted(root.glob(\"*/expected.json\"))` is a directory listing you can read aloud. When a path is data rather than a string, the bugs that need quoting disappear.",
  "code_examples": [
    {
      "id": "1.10-ex-0",
      "lang": "python",
      "caption": "Write JSON, read it back, and pull groups out of a hunk header",
      "code": "import json\nimport re\nfrom pathlib import Path\n\npath = Path(\"expected.json\")\npath.write_text(json.dumps([{\"file\": \"app/db.py\", \"line_start\": 3, \"severity\": \"CRITICAL\"}]), encoding=\"utf-8\")\n\nloaded = json.loads(path.read_text(encoding=\"utf-8\"))\nprint(\"loaded:\", loaded)\n\nHUNK = re.compile(r\"^@@ -(\\d+),(\\d+) \\+(\\d+),(\\d+) @@ ?(.*)$\")\nmatch = HUNK.match(\"@@ -1,5 +1,8 @@ def check():\")\nprint(\"old start/count:\", match.group(1), match.group(2))\nprint(\"new start/count:\", match.group(3), match.group(4))\nprint(\"section:\", repr(match.group(5)))\n",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "loaded: [{'file': 'app/db.py', 'line_start': 3, 'severity': 'CRITICAL'}]\nold start/count: 1 5\nnew start/count: 1 8\nsection: 'def check():'"
    }
  ],
  "quiz": [
    {
      "q": "`re.match` and `re.search` differ in what way?",
      "options": [
        "match is faster because it stops at the first character that fails",
        "match anchors at the start",
        "search only ever returns the first capture group it finds",
        "They are the same function, kept under two names for history"
      ],
      "answer": 1,
      "why": "A hunk header must be matched at position 0, which is why the parser compiles `^@@ ...` and calls match rather than search."
    },
    {
      "q": "What happens to a tuple when it round-trips through JSON?",
      "options": [
        "It comes back as a list",
        "It stays a tuple",
        "It raises TypeError",
        "It becomes a string, because the field is typed as one"
      ],
      "answer": 0,
      "why": "JSON has arrays, not tuples, so `json.dumps((1, 2))` writes `[1, 2]` and loading gives a list — a silent shape change."
    },
    {
      "q": "Why does `read_source` check the path before reading it?",
      "options": [
        "Because checking first is faster than reading and failing",
        "Because pathlib refuses to read a file it has not stat'ed first, as a safety rule",
        "So a missing path or a directory becomes one typed error, not a raw OSError",
        "To count how many files the CLI was given on the command line"
      ],
      "answer": 2,
      "why": "`exists()` and `is_file()` turn two low-level failures into one typed error the CLI can print — which is what makes the message readable instead of a traceback."
    }
  ],
  "try_it": {
    "prompt": "Extract every added line from a fake diff with `re`, using a pattern that captures the text after the leading `+` and skips the `+++` file header.",
    "starter": "import re\n\nDIFF = \"+++ b/app/db.py\\n@@ -1,2 +1,3 @@\\n context\\n+added\\n\"\nADDED = re.compile(r\"^\\+(?!\\+\\+)(.*)$\", re.MULTILINE)\n",
    "solution": "import re\n\nDIFF = \"+++ b/app/db.py\\n@@ -1,2 +1,3 @@\\n context\\n+added\\n\"\nADDED = re.compile(r\"^\\+(?!\\+\\+)(.*)$\", re.MULTILINE)\nprint(ADDED.findall(DIFF))\n",
    "explanation": "It prints `['added']`. The negative lookahead `(?!\\+\\+)` is what keeps the `+++` header out — without it you would get the file name as an added line, which is the classic off-by-one in diff parsing."
  },
  "exercise": {
    "prompt": "Write `load_expected(path) -> list[dict]` with pathlib and json, for the shape the sample label files actually use: an object with a `findings` key holding the list, each entry with file, line_start, line_end, category and severity.",
    "hint": "Read the text, parse it, take `payload[\"findings\"]`, then check the keys before returning.",
    "solution": "import json\nfrom pathlib import Path\n\n\nFIELDS = {\"file\", \"line_start\", \"line_end\", \"category\", \"severity\"}\n\n\ndef load_expected(path: Path) -> list[dict]:\n    payload = json.loads(Path(path).read_text(encoding=\"utf-8\"))\n    entries = payload.get(\"findings\", [])\n    for index, entry in enumerate(entries):\n        missing = FIELDS - set(entry)\n        if missing:\n            raise ValueError(f\"{path}: finding {index} is missing {sorted(missing)}\")\n    return entries\n",
    "explanation": "The sample files are `{\"note\": ..., \"findings\": [...]}`, so the list is one level down — `benchmarks/loader.py` models that as `_ExpectedFileIn.findings` and validates each entry into an `ExpectedFinding`, which is what turns a typo into a message naming the sample."
  },
  "common_mistakes": [
    "Building paths with string concatenation and a stray slash; `Path / \"name\"` cannot get it wrong.",
    "Assuming a JSON round trip is lossless: tuples become lists, sets cannot be encoded at all.",
    "Using `re.search` where the pattern must anchor at the start, so a hunk header matches in the middle of a line."
  ],
  "project_links": [
    {
      "label": "The expected-label shape this exercise mirrors",
      "path": "benchmarks/loader.py",
      "lines": "91-109"
    },
    {
      "label": "The compiled hunk-header pattern",
      "path": "app/parser.py",
      "lines": "62-66"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-2-parser.md — the parser track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-2-parser.md"
    }
  ],
  "glossary_terms": [
    "pathlib.Path — an object that is a path, with read/write and existence checks",
    "json.loads / json.dumps — parse text to objects, serialise objects to text",
    "capture group — a parenthesised part of a pattern, read back with .group(n)",
    "lookahead — `(?!...)`, a zero-width assertion that the next characters do not match"
  ]
});
