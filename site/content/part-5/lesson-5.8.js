/* 5.8 — When a diff is not parseable
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "5.8",
  "part": 5,
  "part_title": "Unified diffs",
  "title": "When a diff is not parseable",
  "order": 508,
  "duration_min": 20,
  "concept_md": "### Prose is not a diff\n\nSend the parser a sentence and it cannot pretend otherwise. It raises one exception, with one message:\n\n```text\nDiffParseError: no file headers found; expected 'diff --git' or a '--- / +++' pair\n```\n\nThat message names both acceptable headers, so a caller who has never read the parser can fix their input from the error alone.\n\n### One exception type, at the boundary\n\n`DiffParseError` subclasses `ValueError`. Every unparseable input raises this one type — empty text, and text with no file headers — so a caller writes one `except` and cannot miss a case. A hunk whose counts disagree with its body is tolerated rather than raised: the parser closes the hunk and lets the outer loop re-read the line as a header.\n\n### The API turns it into a 422\n\nIn `app/main.py` the parse sits inside a try, and the failure becomes a client error:\n\n```python\ntry:\n    bundle = parse_diff(diff_text, source=target)\nexcept DiffParseError as exc:\n    raise HTTPException(status_code=422, detail=f\"cannot parse diff: {exc}\") from exc\n```\n\nThree things to notice. The status is 422, not 500, because the caller sent something the server cannot use. The parser's own sentence is carried into `detail`, so the client sees the real reason. And `from exc` keeps the cause, so the traceback still shows where it started.\n\n### Why not 500\n\nA 500 says the server broke. Nothing broke here: the input was prose. A client that retries on 500 would retry forever on a malformed diff, which is why the distinction is worth a lesson rather than a comment.",
  "code_examples": [
    {
      "id": "5.8-ex-0",
      "lang": "console",
      "caption": "Prose, rejected with a message that names the fix",
      "code": "python -c \"from app.parser import parse_diff\ntry:\n    parse_diff('this is prose, not a diff\\\\n')\nexcept Exception as exc:\n    print(type(exc).__name__ + ':', exc)\"",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "DiffParseError: no file headers found; expected 'diff --git' or a '--- / +++' pair",
      "why_not": "it raises an exception, and the runner reports only what a snippet prints; a traceback is not stdout, so the failure has no expected output to match."
    },
    {
      "id": "5.8-ex-1",
      "lang": "console",
      "caption": "The same failure as the API reports it",
      "code": "python -c \"from fastapi.testclient import TestClient; from app.main import app; r = TestClient(app).post('/review', json={'diff': 'this is prose'}); print(r.status_code, r.json())\"",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "422 {'detail': \"cannot parse diff: no file headers found; expected 'diff --git' or a '--- / +++' pair\"}",
      "why_not": "it imports fastapi and drives the app in-process; fastapi is not in the browser runner, so the app cannot be built there."
    }
  ],
  "quiz": [
    {
      "q": "Why is an unparseable diff a 422 rather than a 500?",
      "options": [
        "Because the parser is slow on big diffs",
        "Because the client sent unusable input",
        "Because 500 is reserved for database faults",
        "Because the endpoint has no response model"
      ],
      "answer": 1,
      "why": "Nothing on the server failed; the input was wrong. A 500 would invite a client to retry a request that can never succeed."
    },
    {
      "q": "What does the error message name?",
      "options": [
        "The file the diff came from",
        "The line number where parsing stopped",
        "Both header forms the parser would accept",
        "The exception's class hierarchy"
      ],
      "answer": 2,
      "why": "It says `diff --git` or a `--- / +++` pair — enough for a caller to fix the input without reading the source."
    },
    {
      "q": "Why does the API write `from exc` when raising?",
      "options": [
        "It keeps the parser error as the cause",
        "It logs the same error a second time",
        "It converts the exception to a 422",
        "It silences the traceback entirely"
      ],
      "answer": 0,
      "why": "Chaining preserves the original traceback, so the log shows where the parse failed rather than only where it was caught."
    }
  ],
  "try_it": {
    "prompt": "Send the parser an empty string and read the message it produces.",
    "starter": "",
    "solution": "```console\n$ python -c \"from app.parser import parse_diff; parse_diff('')\"\nTraceback (most recent call last):\n  ...\napp.parser.DiffParseError: diff is empty\n```",
    "explanation": "A different message from the prose case — empty is caught before any header is looked for, so the two failures stay distinguishable."
  },
  "exercise": {
    "prompt": "Send `{\"diff\": \"diff --git a/x.py b/x.py\\n\"}` — a header and no hunks — to `/review`. What comes back, and which of the parser's failures is it?",
    "hint": "An empty string is not the same failure as prose.",
    "solution": "```text\nA 200, not an error. A diff with a header and no hunks is a file that changed\nnothing: parse_diff returns a bundle with one file and zero hunks, and the review\nfinds nothing to say about it.\n```",
    "explanation": "This is the case the two error paths do not cover, which is why it is worth trying: absence of hunks is data, not a failure."
  },
  "common_mistakes": [
    "Catching broad `ValueError` and swallowing unrelated bugs, since DiffParseError subclasses it.",
    "Returning 500 for a malformed diff, which tells the client to retry forever.",
    "Dropping the parser's message from the API detail, so the client sees only 'bad request'."
  ],
  "project_links": [
    {
      "label": "DiffParseError",
      "path": "app/parser.py",
      "lines": "69-71"
    },
    {
      "label": "The empty check",
      "path": "app/parser.py",
      "lines": "356-357"
    },
    {
      "label": "Where the API converts it to a 422",
      "path": "app/main.py",
      "lines": "661-664"
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
    "DiffParseError — the one exception every parse failure raises",
    "422 — the request was understood and rejected",
    "exception chaining — keeping the original cause when re-raising"
  ]
});
