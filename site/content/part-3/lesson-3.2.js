/* 3.2 — assert, discovery and naming
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "3.2",
  "part": 3,
  "part_title": "Testing with pytest",
  "title": "assert, discovery and naming",
  "order": 302,
  "duration_min": 15,
  "concept_md": "### Discovery is a naming convention\n\npytest finds a test when three things are true: the file matches `test_*.py` (or `*_test.py`), the function name starts with `test_`, and the function is at module level or in a `Test*` class with no `__init__`. Break any one and the test is invisible — not failing, invisible, which is worse.\n\n### `assert` is the whole API\n\n```python\nassert code == 2\nassert \"OWNER/REPO#NUM\" in captured.err\n```\n\npytest rewrites `assert` at import time, so a failure prints the expression, the values and what differed. No `assertEqual`, no message argument needed for the common case.\n\n### The three silent stoppers\n\nA test file named `tests_cli.py` (no underscore before `cli`), a function called `check_target` instead of `test_target`, and a `Test*` class with an `__init__`. Each one is a test that exists and never runs.\n\n### What discovery does not do\n\nIt does not import every file and look for assertions. It matches names, imports the\nmodules that match, and collects the functions it finds. A file that fails to import is\nreported as an error, not as a test — which is why a syntax error in a test module shows\nup as one collection error rather than six hundred failures.\n\n### Asserting on the right thing\n\nAssert on the contract, not on the implementation. `assert code == 2` survives a refactor; `assert \"usage:\" in captured.err` survives a wording change only if the wording is part of the promise. This repository asserts exit codes and the presence of a message, and rarely a whole string.",
  "code_examples": [
    {
      "lang": "console",
      "caption": "What discovery found, without running any of it",
      "code": "python -m pytest -q --collect-only tests | tail -1",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "collection needs the repository on disk and the test tooling installed; neither exists in a browser.",
      "expected_output": "641 tests collected in 6.40s",
      "id": "3.2-ex-0"
    }
  ],
  "quiz": [
    {
      "q": "Which file name will pytest NOT collect?",
      "options": [
        "test_cli.py",
        "cli_test.py",
        "tests_cli.py",
        "test_api.py"
      ],
      "answer": 2,
      "why": "Discovery matches `test_*.py` and `*_test.py`; `tests_cli.py` matches neither and is invisible, not failing."
    },
    {
      "q": "Why does a failing `assert` print the values involved?",
      "options": [
        "Because pytest rewrites assert statements at import time",
        "Because Python does that by default",
        "Because the test passes a message",
        "Because of the `-q` flag"
      ],
      "answer": 0,
      "why": "The rewrite is what turns `assert code == 2` into a report naming both sides of the comparison."
    },
    {
      "q": "A `Test*` class with an `__init__` — what happens to its tests?",
      "options": [
        "They run normally",
        "They are collected but not run",
        "They are not collected at all",
        "pytest raises an error"
      ],
      "answer": 2,
      "why": "pytest instantiates the class without arguments, so a custom `__init__` makes the tests uncollectable."
    }
  ],
  "try_it": {
    "prompt": "Rename a test function in a scratch copy so it no longer starts with `test_`, then run collection and watch the count fall.",
    "starter": "",
    "solution": "```console\n$ python -m pytest -q --collect-only tests | tail -1\n641 tests collected in 6.40s\n$ sed -i 's/def test_malformed_post_target_exits_2/def check_malformed_post_target_exits_2/' tests/test_cli.py\n$ python -m pytest -q --collect-only tests | tail -1\n634 tests collected in 6.31s\n```",
    "explanation": "Seven fewer, because that one test is parametrised seven ways — a good reminder that one `def` can be several collected tests."
  },
  "exercise": {
    "prompt": "Name the three things that silently stop discovery, and say which one is easiest to miss.",
    "hint": "File name, function name, class shape.",
    "solution": "```text\n1. The file name does not match test_*.py or *_test.py.\n2. The function name does not start with test_.\n3. The class starts with Test but defines __init__.\nThe file name is easiest to miss, because the editor still runs the file and it looks like a\nnormal module — pytest simply never mentions it.\n```",
    "explanation": "All three share a symptom: no failure and no output. Silence is the signal."
  },
  "common_mistakes": [
    "Naming a file `tests_helpers.py` and wondering why its tests never run.",
    "Adding `__init__` to a `Test*` class for setup, which makes every test in it uncollectable.",
    "Asserting on a whole log line instead of the part that is a promise."
  ],
  "project_links": [
    {
      "label": "A parametrised test that asserts on an exit code",
      "path": "tests/test_cli.py",
      "lines": "62-80"
    },
    {
      "label": "How the suite is laid out, layer by layer",
      "path": "TESTING.md",
      "lines": "27-70"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/PACE.md — pacing the tracks",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/PACE.md"
    }
  ],
  "glossary_terms": [
    "discovery — the rules pytest uses to find tests",
    "assertion rewriting — the import-time transform that makes failures readable",
    "collected — found by discovery"
  ]
});
