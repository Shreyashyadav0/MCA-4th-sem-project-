/* 8.9 — Benign-input regression tests
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "8.9",
  "part": 8,
  "part_title": "The rule engine",
  "title": "Benign-input regression tests",
  "order": 809,
  "duration_min": 25,
  "concept_md": "### The test that keeps a rule honest\n\nA rule that fires on everything is worse than no rule. `test_benign_lines_do_not_fire` is parametrised over lines that look suspicious and are not — a comment mentioning a password, an `os.environ` read, a variable called `token` — and asserts silence.\n\n### Why parametrised\n\nBecause each false positive is a separate lesson. One test with twenty cases fails with the offending line in the id, so the failure names the input rather than saying \"the rule is wrong\".\n\n### What it protects\n\nThree things at once: the regex, the exemption list, and the test-file skip. A change to any of them can make a benign line fire, and this is the only check that would notice.\n\n### The discipline\n\nWhen a rule is added, a benign line goes with it. When a false positive is reported, the line is added to this list before the regex is changed — so the fix is proven by a test that failed first, which is the only way to know the test is real.\n\n### Reading a failure\n\nWhen the parametrised test fails, the id carries the input, so the failure reads as the line rather than as a rule name. That is deliberate: the first question is always which input, not which rule.",
  "code_examples": [
    {
      "id": "8.9-ex-0",
      "lang": "python",
      "caption": "Benign lines, and the one that is not",
      "code": "from app.rules import LineContext, RULES, review_lines\n\nbenign = [\n    \"password = os.environ[\\\"PASSWORD\\\"]\",\n    \"# TODO: never hardcode the API key here\",\n    \"token_count = 0\",\n]\nfor text in benign:\n    found = review_lines(\"app/demo.py\", [(1, text)])\n    print(\"%-42s -> %d finding(s)\" % (text[:40], len(found)))",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "password = os.environ[\"PASSWORD\"]          -> 0 finding(s)\n# TODO: never hardcode the API key here    -> 1 finding(s)\ntoken_count = 0                            -> 0 finding(s)",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py",
        "app/rules.py"
      ]
    }
  ],
  "quiz": [
    {
      "q": "What does the benign-line test protect?",
      "options": [
        "Only the regex itself",
        "The regex, the exemptions and the skip",
        "Only the severity chosen for the rule",
        "Only the OWASP citation"
      ],
      "answer": 1,
      "why": "Any of the three can turn a benign line into a finding, and this parametrised test is the only check that would notice."
    },
    {
      "q": "Why is the test parametrised per line?",
      "options": [
        "So it runs faster",
        "So it can be skipped in CI",
        "So a failure names the input",
        "So each line gets a severity"
      ],
      "answer": 2,
      "why": "The failing case id carries the line, so the report points at the input rather than saying the rule is wrong."
    },
    {
      "q": "What is the right order when a false positive is reported?",
      "options": [
        "Change the regex, then add the line",
        "Lower the rule's severity",
        "Delete the rule",
        "Add the line, then change the regex"
      ],
      "answer": 3,
      "why": "The line has to fail first, or the test you add afterwards proves nothing about the fix."
    }
  ],
  "try_it": {
    "prompt": "Find one benign line that does fire, if any exists.",
    "starter": "",
    "solution": "```python\nfrom app.rules import review_lines\n\nfor text in (\"key = os.environ['KEY']\", \"api_key = 'not-a-real-key'\", \"# password: see vault\"):\n    print(bool(review_lines(\"app/a.py\", [(1, text)])), text)\n```",
    "explanation": "All three are silent in app code, which is the false-positive budget being spent deliberately."
  },
  "exercise": {
    "prompt": "Which benign line fires only because of the path it is given? Show both paths.",
    "hint": "The test-file skip is a function of the path, not the text.",
    "solution": "```python\nfrom app.rules import review_lines\n\nline = \"KEY = 'AKIAIOSFODNN7EXAMPLE'\"\nprint(\"app/   :\", len(review_lines(\"app/demo.py\", [(1, line)])))\nprint(\"tests/ :\", len(review_lines(\"tests/test_demo.py\", [(1, line)])))\n```",
    "explanation": "The same text is a finding in app code and silent in a test, which is the whole reason `is_test_file` exists."
  },
  "common_mistakes": [
    "Adding a rule without a benign line beside it.",
    "Fixing a false positive by lowering the severity instead of narrowing the pattern.",
    "Assuming a fixture key and a leaked key are judged the same."
  ],
  "project_links": [
    {
      "label": "The benign-line test",
      "path": "tests/test_rules.py",
      "lines": "222-272"
    },
    {
      "label": "The path check it relies on",
      "path": "app/rules.py",
      "lines": "105-109"
    }
  ],
  "learn_more": [
    {
      "label": "tests/test_rules.py — the rule tests",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/tests/test_rules.py"
    },
    {
      "label": "app/rules.py — the rule engine",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/rules.py"
    }
  ],
  "glossary_terms": [
    "false positive — a finding on a line that is not a defect",
    "parametrised test — one test body run over many inputs",
    "regression — a case that once failed and must keep passing"
  ]
});
