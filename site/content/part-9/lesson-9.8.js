/* 9.8 — make verify, then a guided read and rebuild
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "9.8",
  "part": 9,
  "part_title": "Configuration and offline-first",
  "title": "make verify, then a guided read and rebuild",
  "order": 908,
  "duration_min": 30,
  "concept_md": "### One command\n\n`make verify` runs `bash scripts/verify.sh`, which installs from the lock, runs the suite with outbound connections blocked, and validates the learning site. It is the acceptance test: if it prints a green summary, the tree is as good as it claims.\n\n### What it protects\n\nThree things at once — that the suite passes, that it passes with no network, and that the site's lessons are still coherent. Running them separately is how one of the three silently rots.\n\n### Reading `app/config.py` in order\n\nFour blocks: the class and its `model_config`, the credential fields, the local-model fields, and the persistence and auth fields. Every field has a default, every secret has `repr=False`, and the descriptions carry the reasoning that would otherwise live in a wiki.\n\n### The rebuild exercise\n\n`rebuild/tests/test_rebuild_offline.py` asks you to reimplement the settings object and the mock/offline path against a small suite. The blocker itself lives in `scripts/verify_offline.py`; the suite tests the degradation that happens when no provider is configured. The tests name the behaviour, not the line.\n\n### What the guided read should leave you with\n\nThat configuration is data, not code — one class, every field defaulted, secrets unprintable, and one command that proves the whole thing runs without a network.",
  "code_examples": [
    {
      "id": "9.8-ex-0",
      "lang": "console",
      "caption": "The verify target and what it runs",
      "code": "grep -n \"^verify\" -A 2 Makefile",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "the browser runner has Python but no shell, so this command cannot run there; it needs a checkout on disk.",
      "expected_output": "20:verify:\n21-\tbash scripts/verify.sh\n22-"
    },
    {
      "id": "9.8-ex-1",
      "lang": "console",
      "caption": "The rebuild suite, which skips until you write the module",
      "code": "python -m pytest -q rebuild/tests/test_rebuild_offline.py 2>&1 | tail -2 | sed -E 's/ in [0-9.]+s$//'",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "the browser runner has Python but no shell, so this command cannot run there; it needs a checkout on disk.",
      "expected_output": "sssss                                                                    [100%]\n5 skipped"
    }
  ],
  "quiz": [
    {
      "q": "What does `make verify` run?",
      "options": [
        "bash scripts/verify.sh",
        "pytest on the tests directory",
        "The Docker build and push",
        "The site validator alone"
      ],
      "answer": 0,
      "why": "It delegates to one script, so the three checks cannot be run separately and drift apart."
    },
    {
      "q": "Which three things does it protect at once?",
      "options": [
        "Lint, types, and test coverage",
        "Suite, offline, site coherence",
        "Build, image, and deployment",
        "Config, secrets, and auth"
      ],
      "answer": 1,
      "why": "Running them separately is how one of the three silently rots while the others stay green."
    },
    {
      "q": "What does the guided read conclude?",
      "options": [
        "Secrets belong in the repo",
        "Config must be read at import",
        "Configuration is data, not code",
        "Timeouts should be hardcoded in code"
      ],
      "answer": 2,
      "why": "One class, every field defaulted, secrets unprintable, and one command that proves it offline."
    }
  ],
  "try_it": {
    "prompt": "Print the four blocks of `app/config.py` by their line ranges.",
    "starter": "",
    "solution": "```console\n$ grep -n '^class \\|^    [a-z_]*: ' app/config.py | head -20\n```",
    "explanation": "The class first, then credentials, local model, and persistence — the order the guided read follows."
  },
  "exercise": {
    "prompt": "Which line does the `verify` target start on, and what command does it run?",
    "hint": "Read the Makefile rather than the README.",
    "solution": "```console\n$ grep -n '^verify' -A 1 Makefile\n20:verify:\n21-\tbash scripts/verify.sh\n```",
    "explanation": "Line 20, and it delegates to the script so the three checks stay together."
  },
  "common_mistakes": [
    "Running the suite and the validator separately, so one rots.",
    "Reimplementing the blocker without the loopback exemption.",
    "Treating the rebuild suite's skips as passes."
  ],
  "project_links": [
    {
      "label": "The verify target",
      "path": "Makefile",
      "lines": "20-21"
    },
    {
      "label": "The rebuild suite",
      "path": "rebuild/tests/test_rebuild_offline.py",
      "lines": "1-109"
    }
  ],
  "learn_more": [
    {
      "label": "Makefile — the targets",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/Makefile"
    },
    {
      "label": "rebuild/README.md — the rebuild exercises",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/rebuild/README.md"
    }
  ],
  "glossary_terms": [
    "acceptance test — the one command that proves the tree",
    "guided read — a walk through a file in dependency order",
    "rebuild exercise — reimplementing a module against its tests"
  ]
});
