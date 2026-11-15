/* 3.3 — Fixtures and conftest.py
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "3.3",
  "part": 3,
  "part_title": "Testing with pytest",
  "title": "Fixtures and conftest.py",
  "order": 303,
  "duration_min": 25,
  "concept_md": "### A fixture is injected setup\n\n```python\n@pytest.fixture()\ndef client():\n    ...\n    return _FakeClient()\n```\n\nA test that names `client` as a parameter receives the fixture's return value. The test does not import it, construct it, or clean it up: pytest calls the fixture, passes the value, and runs the teardown if the fixture yields.\n\n### `return` or `yield`\n\n`return` gives a value and no teardown. `yield` splits the fixture in two: everything before the yield is setup, everything after is teardown, and the teardown runs even when the test fails. A fixture that opens something should yield.\n\n### Scope decides how often it runs\n\nThe default is `function`: a fresh value per test. `module` and `session` share one value, which is right for something expensive and wrong for anything mutable — a shared dict between tests is how a suite starts passing in a random order.\n\n### conftest.py is shared discovery\n\nA `conftest.py` makes its fixtures available to every test in that directory without an import. This repository has none: its fixtures are local to the file that uses them, which keeps each test file readable on its own. That is a choice, not an accident — a shared conftest is how a suite grows hidden coupling.",
  "code_examples": [
    {
      "lang": "console",
      "caption": "Collection of one file: the fixture-using tests are all here",
      "code": "python -m pytest -q tests/test_auth.py --collect-only | tail -1",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "collection needs the checkout and the tooling; the browser has neither.",
      "expected_output": "13 tests collected in 3.16s",
      "id": "3.3-ex-0"
    }
  ],
  "quiz": [
    {
      "q": "A test names `client` as a parameter. Where does the value come from?",
      "options": [
        "A fixture with that name",
        "A global variable",
        "An import in the test file",
        "conftest.py, always"
      ],
      "answer": 0,
      "why": "The parameter name is the lookup key; the fixture supplies the value and owns the teardown."
    },
    {
      "q": "When should a fixture `yield` instead of `return`?",
      "options": [
        "When it is expensive",
        "When it returns a Path rather than raising on failure",
        "When it has cleanup to do after the test",
        "Always"
      ],
      "answer": 2,
      "why": "Everything after the yield is teardown, which is why a fixture that opens a file or a connection yields."
    },
    {
      "q": "What is the risk of a `session`-scoped fixture holding a mutable value?",
      "options": [
        "It is slower",
        "It cannot be parametrised",
        "pytest refuses to run it",
        "State leaks between tests"
      ],
      "answer": 3,
      "why": "One shared object across the session means one test's changes are the next test's starting point."
    }
  ],
  "try_it": {
    "prompt": "Write a fixture that returns a small dict, use it in one test, then rewrite it with `yield` so it prints a teardown line after the test. (`tmp_path`, the other useful built-in, arrives in 3.5.)",
    "starter": "import pytest\n\n\n@pytest.fixture()\ndef diff():\n    return \"@@ -1 +1 @@\\n-old\\n+new\\n\"\n",
    "solution": "import pytest\n\n\n@pytest.fixture()\ndef diff():\n    print(\"setup\")\n    yield \"@@ -1 +1 @@\\n-old\\n+new\\n\"\n    print(\"teardown\")\n\n\ndef test_diff_has_a_hunk(diff):\n    assert diff.startswith(\"@@\")\n",
    "explanation": "The test sees the diff; the report shows `setup` before it and `teardown` after. That ordering is the whole difference between `return` and `yield` in a fixture."
  },
  "exercise": {
    "prompt": "Read a real fixture in `tests/test_auth.py` and say what it sets up, what scope it has, and why that scope is right.",
    "hint": "One of them is `autouse=True` — ask what it prevents.",
    "solution": "```text\n`tests/test_auth.py:52` is `@pytest.fixture(autouse=True)` — it runs for every test in the\nfile without being named, and it exists so no test can accidentally inherit a real credential\nfrom the developer's environment.\nThe other two fixtures are function-scoped: each test gets a fresh object, so one test cannot\nleave state that changes the next one's result.\n```",
    "explanation": "`autouse` is for isolation you never want to opt out of — removing a real token from the environment is the textbook case."
  },
  "common_mistakes": [
    "A session-scoped fixture holding a mutable object, so tests pass alone and fail together.",
    "Doing setup in a `Test*` class `__init__` instead of a fixture, which stops collection entirely.",
    "A fixture that returns instead of yields, leaving a file handle open after the test."
  ],
  "project_links": [
    {
      "label": "Real fixtures, one of them autouse",
      "path": "tests/test_auth.py",
      "lines": "52-73"
    },
    {
      "label": "A function-scoped fixture used by many tests",
      "path": "tests/test_db.py",
      "lines": "36-50"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/PACE.md — pacing the tracks",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/PACE.md"
    }
  ],
  "glossary_terms": [
    "fixture — setup injected into a test by parameter name",
    "scope — how often a fixture value is rebuilt",
    "autouse — a fixture applied without being named",
    "tmp_path — a per-test directory pytest cleans up"
  ]
});
