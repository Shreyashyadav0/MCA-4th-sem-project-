/* 3.7 — -q, -k, -x and coverage
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "3.7",
  "part": 3,
  "part_title": "Testing with pytest",
  "title": "-q, -k, -x and coverage",
  "order": 307,
  "duration_min": 15,
  "concept_md": "### Four flags that do most of the work\n\n- `-q` — quiet: dots instead of a line per test.\n- `-k \"github\"` — run only the tests whose name or markers match.\n- `-x` — stop at the first failure. `--maxfail=3` stops after three.\n- `-rs` — show the reason for each skip.\n\n```console\n$ python -m pytest -q tests -k \"github\"\n63 passed, 578 deselected in 6.27s\n```\n\nSelection is a substring match on the test id, so `-k \"github and not webhook\"` is valid too. The deselected count tells you how much you did not run, which is the part people forget to read.\n\n### Why `-x` changes what you learn\n\nA syntax error in one module is a single collection error, not six hundred failures — pytest stops before running anything. `-x` earns its place when a real failure cascades: one broken assumption that fails forty tests with the same traceback. Run `-x` while fixing, and the full suite before pushing.\n\n### Why this repository does not gate on coverage\n\nCoverage measures which lines ran, not whether the assertions were right. A test that calls a function and asserts nothing gives full coverage and proves nothing. The suite is gated on passing, on the zero-network proof, and now on the site's own validator — all three are claims about behaviour, not about lines.",
  "code_examples": [
    {
      "lang": "console",
      "caption": "A selection, and how much of the suite it left out",
      "code": "python -m pytest -q tests -k \"github\"",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "it runs a subset of the suite, which needs the checkout and pytest.",
      "expected_output": "63 passed, 578 deselected in 6.27s",
      "id": "3.7-ex-0"
    }
  ],
  "quiz": [
    {
      "q": "What does the `578 deselected` in that output tell you?",
      "options": [
        "578 tests were not run",
        "578 tests failed",
        "578 tests were skipped",
        "Nothing useful"
      ],
      "answer": 0,
      "why": "Selection narrows the run; the deselected count is the reminder of how much of the suite you did not exercise."
    },
    {
      "q": "When is `-x` the right flag?",
      "options": [
        "In CI, so a single flake cannot hide the later failures",
        "In CI, always, so a run never wastes time on later tests",
        "While fixing a failure",
        "Only when the suite is slow enough to time out"
      ],
      "answer": 2,
      "why": "`-x` filters after discovery, so it stops the run at the first failure rather than hiding the rest; a broken import never gets that far, because collection fails first."
    },
    {
      "q": "Why does this repository not gate on coverage?",
      "options": [
        "Coverage is expensive",
        "Because the suite is too small",
        "Because pytest cannot measure a test that was never collected at all",
        "Because lines executed do not prove assertions were right"
      ],
      "answer": 3,
      "why": "A test that calls a function and asserts nothing covers it completely — the number would be high and the proof absent."
    }
  ],
  "try_it": {
    "prompt": "Run `-k \"github\"`, then `-k \"github and not webhook\"`. Compare the selection counts.",
    "starter": "",
    "solution": "```console\n$ python -m pytest -q tests -k \"github\"\n63 passed, 578 deselected in 6.27s\n\n$ python -m pytest -q tests -k \"github and not webhook\"\n63 passed, 578 deselected in 5.90s\n```",
    "explanation": "The same 63, because no collected id contains both words: the expression is a real boolean filter over test ids, not a single substring."
  },
  "exercise": {
    "prompt": "Apply `-k` to a test you wrote in 3.4: predict the selection count before running it, then check the arithmetic — passed plus deselected should equal the collected total.",
    "hint": "The name you gave the test is the string `-k` matches.",
    "solution": "```console\n$ python -m pytest -q tests -k \"bad_line_is_rejected\"\n641 deselected in 4.10s\n\n0 + 641 = 641, which is the whole suite, the collected total. If your arithmetic does not close, either the name did not\nmatch what you expected or discovery changed.\n```",
    "explanation": "The prediction is the exercise: `-k` is a substring match on the collected id, so knowing the name tells you the count before you run it."
  },
  "common_mistakes": [
    "Reading only the passed count and ignoring how many were deselected.",
    "Gating CI on coverage percentage, which a test full of `assert True` would satisfy.",
    "Using `-x` in CI, so a single flake hides every later failure."
  ],
  "project_links": [
    {
      "label": "The test targets you actually type",
      "path": "Makefile",
      "lines": "20-38"
    },
    {
      "label": "Running a subset, documented",
      "path": "TESTING.md",
      "lines": "79-163"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/PACE.md — pacing the tracks",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/PACE.md"
    }
  ],
  "glossary_terms": [
    "deselected — collected but excluded by the selection expression",
    "-x — stop after the first failure",
    "coverage — the share of lines executed, not of behaviour proven"
  ]
});
