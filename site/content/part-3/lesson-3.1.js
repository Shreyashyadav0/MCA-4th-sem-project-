/* 3.1 — Why tests, and red-green-refactor
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "3.1",
  "part": 3,
  "part_title": "Testing with pytest",
  "title": "Why tests, and red-green-refactor",
  "order": 301,
  "duration_min": 15,
  "concept_md": "### What a failing test buys\n\nA test that fails is information: it says the code does not do what you believe. Writing the test first forces you to say what \"done\" means before you have written anything that could be mistaken for done.\n\nThe loop has three states. **Red**: the test fails, and it fails for the reason you expect. **Green**: the smallest change that makes it pass. **Refactor**: improve the code with the test still green, so a mistake is caught in seconds rather than in review.\n\n### Unit and integration are different questions\n\nA unit test asks whether one function obeys its contract. An integration test asks whether the pieces work together — this repository's `TestClient` tests drive the whole FastAPI app in-process. Both are honest; neither substitutes for the other.\n\n### What 640 and 1 mean\n\n`640 passed, 1 skipped` is the whole suite. The skip is a test that needs a live LM Studio server: the test exists, is collected, and is skipped because the environment cannot satisfy it. That is why `--collect-only` says 641.\n\nA number you can reproduce is worth more than a number that sounds impressive. If your count differs, the environment differs — check the interpreter and the lock before reading another lesson.",
  "code_examples": [
    {
      "lang": "console",
      "caption": "The whole suite, quiet",
      "code": "python -m pytest -q tests",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "it runs the repository's test suite: a browser page has no checkout and no pytest.",
      "expected_output": "640 passed, 1 skipped in 19.57s\n\n# the timing differs on every run; the counts do not",
      "id": "3.1-ex-0"
    }
  ],
  "quiz": [
    {
      "q": "What does the red step of red-green-refactor require?",
      "options": [
        "A test that passes",
        "A test with no assertions",
        "A test that is skipped",
        "A test that fails, for the reason you expect"
      ],
      "answer": 3,
      "why": "A test that fails for the wrong reason proves nothing; the failure has to be the one you predicted."
    },
    {
      "q": "Why is the collected count 641 when the run reports 640 passed and 1 skipped?",
      "options": [
        "A test was added after the run",
        "A skipped test is still collected",
        "pytest counts parametrised cases twice",
        "The count is a bug"
      ],
      "answer": 1,
      "why": "Discovery finds the test and the marker then skips it, so it appears in collection and not in the pass count."
    },
    {
      "q": "What is the difference between a unit test and an integration test here?",
      "options": [
        "One tests a function's contract, the other tests the pieces together",
        "One is faster",
        "One uses pytest and the other does not",
        "There is none"
      ],
      "answer": 0,
      "why": "The `TestClient` tests drive the whole app in-process; a unit test drives one function and nothing else."
    }
  ],
  "try_it": {
    "prompt": "Run the suite, then run it again with `-q` removed. What changes?",
    "starter": "",
    "solution": "```console\n$ python -m pytest -q tests\n640 passed, 1 skipped in 19.57s\n\n$ python -m pytest tests\n... dots, one per test ...\n640 passed, 1 skipped in 21.03s\n```",
    "explanation": "Same result, more noise: `-q` changes the progress display, never the outcome."
  },
  "exercise": {
    "prompt": "Pick one test file, read three of its tests, and write down what each one would catch that the others would not.",
    "hint": "Look for the boundary each test crosses — a parse, a permission, an exit code.",
    "solution": "```text\nAny three tests will do, provided you can say what each one proves. Example from tests/test_cli.py:\n- a malformed --post-to-pr exits 2 and does no review work (a usage boundary)\n- a missing file raises ReviewInputError with a sentence (an input boundary)\n- a valid diff prints the findings and exits 0 (the happy path)\n```",
    "explanation": "Three tests, three different questions. A suite is a set of claims, not a pile of assertions."
  },
  "common_mistakes": [
    "Writing a test that passes before the code exists, which proves nothing about the code.",
    "Asserting on a message string that is not part of the contract, so the test breaks on a wording change.",
    "Treating a skip as a failure — or as a pass. It is a third outcome and it says why."
  ],
  "project_links": [
    {
      "label": "How to run the suite",
      "path": "README.md",
      "lines": "59-80"
    },
    {
      "label": "The testing document: what the suite covers",
      "path": "TESTING.md",
      "lines": "27-75"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/PACE.md — how the tracks are paced",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/PACE.md"
    }
  ],
  "glossary_terms": [
    "red-green-refactor — the failing-test-first loop",
    "collected — the tests discovery found",
    "skip — a test that exists and did not run"
  ]
});
