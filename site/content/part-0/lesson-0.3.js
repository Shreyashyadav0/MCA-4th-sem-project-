/* 0.3 — Setup: Python, venv, git, terminal basics
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "0.3",
  "part": 0,
  "part_title": "Orientation",
  "title": "Setup: Python, venv, git, terminal basics",
  "order": 3,
  "duration_min": 25,
  "concept_md": "### What you need\n\nPython **3.12** — the repository pins `3.12.13` in `.python-version`, and the lock file's wheels are built for it. A different minor version will usually work and occasionally will not; when the test count disagrees with this site, the interpreter is the first thing to check.\n\nGit, so `git status` can tell you what you changed. A terminal you are comfortable in.\n\n### Four commands\n\n```console\ncd ai-code-reviewer        # get to the project root\nls                         # what is here: app/ tests/ samples/ site/\npython -m pytest -q tests  # the whole suite\ngit status                 # only site/ should ever be modified by these waves\n```\n\n### Create the environment\n\n```console\npython -m venv .venv\nsource .venv/bin/activate     # Windows: .venv\\Scripts\\activate\npip install -r requirements.lock\n```\n\nInstall from the **lock**, not from `requirements.txt`. The lock pins all 37 distributions including the test tooling; the plain requirements file lists the runtime dependencies only, so `pytest` will not be there and the suite will not run.\n\n### The one number to remember\n\n`640 passed, 1 skipped`. The skip is a live-model smoke test guarded by an environment variable, so it runs on a machine with LM Studio and skips everywhere else. Collected is **641** — one more than the passes, because the skip is still a test.\n\n### When it goes wrong\n\nIf `python -m pytest` says \"no module named pytest\", the environment is wrong, not the code. If the counts differ from 640/1, re-read the interpreter version and reinstall from the lock before reading another lesson: you are otherwise studying a different program.",
  "code_examples": [
    {
      "id": "0.3-ex-0",
      "lang": "console",
      "caption": "The two commands that tell you the environment is sound",
      "code": "python --version\npython -m pytest -q tests --collect-only | tail -1",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "these are shell commands: they start processes and read the repository from disk, which a browser page cannot do.",
      "expected_output": "Python 3.12.13\n641 tests collected in 7.41s\n\n# the collected count is the number of tests, not of passes: the skipped\n# live-model test is collected too. The timing differs on every run."
    }
  ],
  "quiz": [
    {
      "q": "Which file should you install from?",
      "options": [
        "requirements.txt",
        "requirements.lock",
        "requirements-dev.txt",
        "pyproject.toml"
      ],
      "answer": 1,
      "why": "The lock pins all 37 distributions including the test tooling; requirements.txt lists runtime dependencies only, so pytest would be missing."
    },
    {
      "q": "The suite reports 640 passed, 1 skipped. How many tests were collected?",
      "options": [
        "639",
        "640",
        "641",
        "642"
      ],
      "answer": 2,
      "why": "A skipped test is still collected: 640 passes plus the one skip is 641 collected, which is what --collect-only prints."
    },
    {
      "q": "`python -m pytest` says there is no module named pytest. What is the likely cause?",
      "options": [
        "The repository is corrupt",
        "The virtual environment is not active or was installed from the wrong file",
        "The tests were deleted",
        "Python is too old"
      ],
      "answer": 1,
      "why": "The suite has no runtime dependency on pytest, so a missing pytest means the environment was built from requirements.txt rather than the lock."
    }
  ],
  "try_it": {
    "prompt": "Run `python --version`, then `python -m pytest -q tests --collect-only | tail -1`, and compare the collected count with what a real run reports.",
    "starter": "",
    "solution": "`3.12.13` and `641 tests collected`, against `640 passed, 1 skipped` from a real run. The difference is the skipped test, which is collected but not executed.",
    "explanation": "Two numbers, one test: knowing which is which is the difference between trusting the suite and misreading it."
  },
  "exercise": {
    "prompt": "Run all three commands — `python --version`, `git status`, and the collect-only command — and report what each one tells you. Then say what the collected count should be and why.",
    "hint": "`git status` on a clean checkout prints nothing after the branch line; any entry is a change you made.",
    "solution": "`python --version` prints 3.12.13, matching `.python-version`. `git status` should show a clean tree, or only files under `site/` if you have been editing lessons. The collect-only command prints **641 tests collected**; the run reports 640 passed and 1 skipped, because the skipped live-model test is still a collected test.\n\n> If pytest is not installed at all, the environment came from `requirements.txt` rather than `requirements.lock` — reinstall from the lock.",
    "explanation": "The three commands answer three different questions: which interpreter, what have I changed, and is the suite intact. Run them before trusting any other number."
  },
  "common_mistakes": [
    "Installing from `requirements.txt` and then wondering why pytest is missing: the test tooling lives in the lock and in `requirements-dev.txt`.",
    "Working outside the virtual environment, so `python` is the system interpreter with none of the pinned packages.",
    "Reading the collected count as the pass count. 641 collected, 640 passed, 1 skipped — all three describe the same run."
  ],
  "project_links": [
    {
      "label": "The pinned dependency set — install from this",
      "path": "requirements.lock",
      "lines": "1-37"
    },
    {
      "label": "Test and lint tooling",
      "path": "requirements-dev.txt",
      "lines": "1-2"
    },
    {
      "label": "The interpreter the repository pins",
      "path": ".python-version",
      "lines": "1-1"
    },
    {
      "label": "The targets you will actually type: verify, test, lint, run",
      "path": "Makefile",
      "lines": "1-30"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/PACE.md — how long the curriculum takes",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/PACE.md"
    }
  ],
  "glossary_terms": [
    "venv — a directory holding an isolated interpreter and its packages",
    "lock file — the fully pinned dependency set, including transitive dependencies",
    "collected — the number of tests pytest found, before any of them ran"
  ]
});
