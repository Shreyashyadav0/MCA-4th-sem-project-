/* 3.4 — @pytest.mark.parametrize
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "3.4",
  "part": 3,
  "part_title": "Testing with pytest",
  "title": "@pytest.mark.parametrize",
  "order": 304,
  "duration_min": 20,
  "concept_md": "### One test, many inputs\n\n```python\n@pytest.mark.parametrize(\"target\", [\"bad-format\", \"owner/repo\", \"owner/repo#\"])\ndef test_malformed_post_target_exits_2(target):\n    ...\n```\n\nThe decorator turns one function into one test per value. Each has its own name in the report (`test_...2[bad-format]`), so a failure tells you which input broke without any extra code.\n\nThat is the real shape used in `tests/test_cli.py`, where seven malformed targets each prove the same rule: a bad `--post-to-pr` is a usage error, exit 2, before any review work happens.\n\n### Several parameters at once\n\n```python\n@pytest.mark.parametrize(\"a, b\", [(1, 2), (3, 4)])\n```\n\nThe string names the arguments and each tuple is one case. The tuple's length must match the number of names — the most common mistake, and it fails at collection with a clear message.\n\n### `ids` and `xfail`\n\n`ids=[...]` names the cases when the values are not readable. `pytest.param(value, marks=pytest.mark.xfail)` marks one case as a known failure while the rest must pass — useful when a real input is broken for a reason you have written down.\n\n### Why this beats a loop\n\nA loop stops at the first failure and reports one result. Parametrisation runs every case and reports each one separately, which is the difference between \"something is wrong\" and \"these three inputs are wrong\".",
  "code_examples": [
    {
      "lang": "console",
      "caption": "Seven cases, one test function",
      "code": "python -m pytest -q \"tests/test_cli.py::test_malformed_post_target_exits_2\"",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "it runs one parametrised test, which still needs the checkout and pytest; the browser has neither.",
      "expected_output": "7 passed in 1.41s\n\n# seven cases, one test function: one per malformed target",
      "id": "3.4-ex-0"
    }
  ],
  "quiz": [
    {
      "q": "One `@pytest.mark.parametrize` with five values produces how many tests?",
      "options": [
        "One",
        "One per assertion",
        "Five",
        "None until it fails"
      ],
      "answer": 2,
      "why": "Each value becomes its own collected test with its own id, which is why a failure names the input."
    },
    {
      "q": "`parametrize(\"a, b\", [(1, 2)])` with a tuple of three values — what happens?",
      "options": [
        "pytest splits the tuple and runs it twice",
        "pytest splits the tuple",
        "It passes",
        "Collection fails: the tuple length does not match the names"
      ],
      "answer": 3,
      "why": "The arity is checked at collection, which is the good failure — before any test runs."
    },
    {
      "q": "Where do the ids in `test_...[LOW]` come from?",
      "options": [
        "pytest numbers them in run order",
        "The parameter values, by default",
        "The test function's docstring",
        "You must always supply `ids=`"
      ],
      "answer": 1,
      "why": "Each case is named after its value unless you pass `ids=`, which is what makes a failure read as an input rather than as an index."
    }
  ],
  "try_it": {
    "prompt": "Parametrise a test over three severities and check the ids in the report.",
    "starter": "import pytest\n\n\n@pytest.mark.parametrize(\"severity\", [\"LOW\", \"MEDIUM\", \"CRITICAL\"])\ndef test_severity_is_upper(severity):\n    assert severity == severity.upper()\n",
    "solution": "import pytest\n\n\n@pytest.mark.parametrize(\"severity\", [\"LOW\", \"MEDIUM\", \"CRITICAL\"])\ndef test_severity_is_upper(severity):\n    assert severity == severity.upper()\n\n\n@pytest.mark.parametrize(\"severity\", [\"low\", \"medium\"])\ndef test_lowercase_is_rejected(severity):\n    assert severity != severity.upper()\n",
    "explanation": "The first test passes on all three values; the second passes on both lowercase ones because they really are not uppercase. Two tests, five cases, and the report names each value."
  },
  "exercise": {
    "prompt": "Write a parametrised test over four malformed line values for `Finding`, and say what each case proves.",
    "hint": "Reuse the validator's rule: a number, or an ascending range.",
    "solution": "import pytest\n\nfrom app.models import Finding\n\n\n@pytest.mark.parametrize(\"line\", [\"abc\", \"\", \"45-42\", \"4-5-6\"])\ndef test_bad_line_is_rejected(line):\n    with pytest.raises(Exception):\n        Finding(file=\"a.py\", line=line, severity=\"LOW\", issue=\"x\", suggested_fix=\"y\")\n",
    "explanation": "Four cases, four reasons: not a number, empty, reversed range, malformed range. One function, and the report names whichever one breaks."
  },
  "common_mistakes": [
    "A tuple arity that does not match the parameter names, which fails at collection.",
    "Passing a mutable object as a parameter and mutating it inside the test, so the next case starts dirty.",
    "Using a loop instead of parametrize, so only the first failure is ever reported."
  ],
  "project_links": [
    {
      "label": "The seven-case parametrised test quoted above",
      "path": "tests/test_cli.py",
      "lines": "62-73"
    },
    {
      "label": "A parametrised test over hostile paths",
      "path": "tests/test_api.py",
      "lines": "211-214"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/PACE.md — pacing the tracks",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/PACE.md"
    }
  ],
  "glossary_terms": [
    "parametrize — turn one test into one per value",
    "arity — the number of values a parameter set supplies",
    "xfail — a known failure, recorded rather than hidden"
  ]
});
