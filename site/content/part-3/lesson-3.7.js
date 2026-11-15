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
  "concept_md": "### Four flags that do most of the work\n\n- `-q` — quiet: dots instead of a line per test.\n- `-k \"github\"` — run only the tests whose name or markers match.\n- `-x` — stop at the first failure. `--maxfail=3` stops after three.\n- `-rs` — show the reason for each skip.\n\n```console\n$ python -m pytest -q tests -k \"github\"\n63 passed, 578 deselected in 6.27s\n```\n\nSelection is a substring match on the test id, so `-k \"github and not webhook\"` is valid too. The deselected count tells you how much you did not run, which is the part people forget to read.\n\n### Why `-x` changes what you learn\n\nWithout it, a broken import produces six hundred failures. With it, you get the first one and a stack trace you can act on. Run `-x` while fixing, and the full suite before pushing.\n\n### Why this repository does not gate on coverage\n\nCoverage measures which lines ran, not whether the assertions were right. A test that calls a function and asserts nothing gives full coverage and proves nothing. The suite is gated on passing, on the zero-network proof, and now on the site's own validator — all three are claims about behaviour, not about lines.",
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
        "578 tests failed",
        "578 tests were not run because they did not match `-k`",
        "578 tests were skipped",
        "Nothing useful"
      ],
      "answer": 1,
      "why": "Selection narrows the run; the deselected count is the reminder of how much of the suite you did not exercise."
    },
    {
      "q": "When is `-x` the right flag?",
      "options": [
        "In CI, always",
        "While fixing a failure, so the first error is the one you read",
        "When tests are slow",
        "Never"
      ],
      "answer": 1,
      "why": "One failure and a traceback beats six hundred, but a full run before pushing still catches what the early stop hid."
    },
    {
      "q": "Why does this repository not gate on coverage?",
      "options": [
        "Coverage is expensive",
        "Because lines executed do not prove assertions were right",
        "Because pytest cannot measure it",
        "Because the suite is too small"
      ],
      "answer": 1,
      "why": "A test that calls a function and asserts nothing covers it completely — the number would be high and the proof absent."
    }
  ],
  "try_it": {
    "prompt": "Run `-k \"github\"`, then `-k \"github and not webhook\"`. Compare the selection counts.",
    "starter": "",
    "solution": "```console\n$ python -m pytest -q tests -k \"github\"\n63 passed, 578 deselected in 6.27s\n\n$ python -m pytest -q tests -k \"github and not webhook\"\n51 passed, 590 deselected in 5.90s\n```",
    "explanation": "Twelve fewer: the expression is a real boolean filter over test ids, not a single substring."
  },
  "exercise": {
    "prompt": "Run `-k \"github\"` and report the selection count, then say what the deselected number proves about the suite's size.",
    "hint": "Passed plus deselected is the total collected, minus the skip.",
    "solution": "```text\n63 passed, 578 deselected — so 641 tests matched the collection, of which 63 ran.\nThat agrees with `--collect-only`: 641 collected, 640 passed and 1 skipped in a full run.\nThe arithmetic is the check: if passed + deselected ever disagrees with the collected count,\nsomething in the selection or the discovery changed.\n```",
    "explanation": "Two commands, one number: the suite's size should be the same whether you measure it by collection or by selection plus deselection."
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
      "lines": "19-30"
    },
    {
      "label": "Running a subset, documented",
      "path": "TESTING.md",
      "lines": "71-110"
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
