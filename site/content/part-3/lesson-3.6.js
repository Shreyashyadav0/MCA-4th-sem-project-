/* 3.6 — skip, skipif, xfail — and the one skipped test
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "3.6",
  "part": 3,
  "part_title": "Testing with pytest",
  "title": "skip, skipif, xfail — and the one skipped test",
  "order": 306,
  "duration_min": 20,
  "concept_md": "### Three different admissions\n\n`@pytest.mark.skip` — never run this. `@pytest.mark.skipif(condition)` — do not run it here, for a stated reason. `@pytest.mark.xfail` — run it, and expect it to fail; a pass is reported as `xpass` and is usually a signal that the marker should go.\n\n### Why this repository skips exactly one\n\n```python\n@pytest.mark.skipif(not LIVE_BASE_URL, reason=\"needs a live LM Studio server\")\n```\n\nThat is `tests/test_openai_compat_provider.py:1062`. The test is real and valuable: it drives the transport against an actual local model. It is skipped because most environments have no LM Studio at `LIVE_BASE_URL`, not because it is broken.\n\n`-rs` prints the reason with the summary:\n\n```console\nSKIPPED [1] tests/test_openai_compat_provider.py:1062: needs a live LM Studio server\n```\n\n### Why `xfail` would be wrong there\n\n`xfail` says \"this should work and does not\". Nothing here is broken: the test is correct, and the environment lacks a server. Marking it `xfail` would turn a missing prerequisite into a recorded defect, and would start reporting `xpass` on any machine that does have one.\n\n### The honest count\n\n`640 passed, 1 skipped` is a complete account: 641 tests exist, 640 ran, one was skipped for a stated reason. A suite that hid that test would report 640 and be less true.",
  "code_examples": [
    {
      "lang": "console",
      "caption": "The skip, with its reason, from the summary line",
      "code": "python -m pytest -q tests -rs",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "it runs the suite; the browser has no checkout and no pytest.",
      "expected_output": "=========================== short test summary info ============================\nSKIPPED [1] tests/test_openai_compat_provider.py:1062: needs a live LM Studio server\n640 passed, 1 skipped in 19.24s",
      "id": "3.6-ex-0"
    }
  ],
  "quiz": [
    {
      "q": "A test is skipped because a server is not configured. Which marker is right?",
      "options": [
        "`skip`",
        "`skipif`, with the reason stated",
        "`xfail`",
        "None — delete the test"
      ],
      "answer": 1,
      "why": "`skipif` records the condition and the reason, so the report explains itself on every machine."
    },
    {
      "q": "What does an `xpass` mean?",
      "options": [
        "A test marked `xfail` that passed",
        "A test that failed twice",
        "A skipped test",
        "A test that errored"
      ],
      "answer": 0,
      "why": "`xpass` is the signal that a known failure has been fixed and the marker should be removed."
    },
    {
      "q": "Why is `xfail` the wrong marker for the LM Studio test?",
      "options": [
        "Because xfail is deprecated",
        "Because it runs too slowly",
        "Because nothing is broken",
        "Because it is not parametrised"
      ],
      "answer": 2,
      "why": "`xfail` records a defect; this is a missing prerequisite, which `skipif` states exactly."
    }
  ],
  "try_it": {
    "prompt": "Run the suite with `-rs` and then without it. What does the extra flag add?",
    "starter": "",
    "solution": "```console\n$ python -m pytest -q tests -rs\nSKIPPED [1] tests/test_openai_compat_provider.py:1062: needs a live LM Studio server\n640 passed, 1 skipped in 19.24s\n\n$ python -m pytest -q tests\n640 passed, 1 skipped in 19.57s\n```",
    "explanation": "`-rs` adds the reason for each skip. Without it you know a test was skipped but not why, which is the difference between an honest report and a number."
  },
  "exercise": {
    "prompt": "Explain why `xfail` would be the wrong choice for this repository's single skipped test, in three lines.",
    "hint": "The test is correct; the environment is not configured.",
    "solution": "```text\n1. xfail asserts that a test is expected to FAIL; this one is expected to pass wherever LM Studio runs.\n2. It would record a missing prerequisite as a known defect, which is a false claim about the code.\n3. On a machine with a live server it would report xpass, telling the reader the suite is broken.\n```",
    "explanation": "Skip says \"not here, for this reason\"; xfail says \"broken, and we know\". Using the wrong one turns an environment fact into a code claim."
  },
  "common_mistakes": [
    "Using `xfail` for anything that depends on the environment, so a working machine reports `xpass`.",
    "`skip` without a reason, leaving the report unable to say why.",
    "Deleting an environment-dependent test instead of marking it `skipif`."
  ],
  "project_links": [
    {
      "label": "The one skipped test and its marker",
      "path": "tests/test_openai_compat_provider.py",
      "lines": "1062-1085"
    },
    {
      "label": "How a skip differs from a failure",
      "path": "TESTING.md",
      "lines": "189-214"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/PACE.md — pacing the tracks",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/PACE.md"
    }
  ],
  "glossary_terms": [
    "skip — never run this test",
    "skipif — do not run it here, for a stated reason",
    "xfail — expected to fail",
    "xpass — an xfail that passed"
  ]
});
