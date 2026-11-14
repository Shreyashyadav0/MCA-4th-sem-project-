/* 0.1 — What this project is and what you'll know by the end
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "0.1",
  "part": 0,
  "part_title": "Orientation",
  "title": "What this project is and what you'll know by the end",
  "order": 1,
  "duration_min": 10,
  "concept_md": "### What this project is\n\nAn offline-first AI code reviewer. Point it at a unified diff or a source file and it returns findings with exactly five fields — file, line, severity, issue, suggested fix — and it can post them to a pull request as inline comments.\n\nThe deterministic part is the product: **63 OWASP-mapped rules** that read added lines only, with no API key, no network and no model. The model is an upgrade on top of that, never a dependency. If the key is missing, the endpoint is down, or the answer does not parse, the review still completes — with one `WARNING` that says what happened, never an exception and never a silent downgrade.\n\n### What you will be able to do by the end\n\n- Read every module in `app/` without a guide beside you.\n- Rebuild `models.py`, `parser.py`, `rules.py` and `engine.py` from memory, each one proved by the test suite rather than by feeling.\n- Explain the fallback architecture: what degrades, where the single `WARNING` comes from, and why the degraded path calls the rule engine directly (ADR 0004).\n- State the provider precedence — `sarvam > local > mock` — and name the one function that decides it.\n- Defend the honesty limits in `HANDOFF.md` at a viva, including the things that are simulated rather than real.\n\n### The shape of the thing\n\n| Stage | Module | What it decides |\n|---|---|---|\n| Parse | `app/parser.py` | which lines the diff actually added |\n| Review | `app/rules.py` | the 63 deterministic findings |\n| Choose | `app/engine.py` | sarvam, local or mock — in one place |\n| Anchor | `app/parser.py` | whether a comment can attach to a line |\n| Post | `app/github_client.py` | inline comments, or a summary when anchoring fails |\n\n### Start here\n\n```console\npython -m pytest -q tests\npython reviewer.py samples/sample.diff\n```\n\nThe first command tells you whether the environment is sound. The second shows the whole pipeline on a real diff: mode `mock`, four findings, verdict `block`, exit code 0.\n\n> 640 passed, 1 skipped is the number to expect at this commit. If yours differs, stop and fix the pins in `requirements.lock` before learning anything — otherwise you are studying a different program from the one this site describes.\n\n### How to read this site\n\nEvery lesson has a concept, a worked example, something to try, an exercise, and the mistakes people actually make. The links at the bottom point at the exact file and line range the lesson is about: read that code, close it, and write it again from memory.\n\nThe site is a learning aid. `docs/learning/` is the source of truth.",
  "code_examples": [
    {
      "lang": "console",
      "caption": "Quick start — from the repository root, with no key and no network",
      "code": "python -m pytest -q tests\npython reviewer.py samples/sample.diff",
      "runnable": false,
      "expected_output": "# abridged: the full run also prints the four findings, their suggested fixes\n# and their anchors. Nothing else in it is omitted.\n640 passed, 1 skipped\n\ntarget   : samples/sample.diff\nmode     : mock\nprovider : mock\nmodel    : local-rules\nfiles    : 2 changed\nfindings : 4 (CRITICAL 3, HIGH 0, MEDIUM 1, LOW 0)\n\nverdict  : block"
    }
  ],
  "try_it": {
    "prompt": "Run both commands in the repository root and write down two things: the test counts, and the verdict line.\n\n```console\npython -m pytest -q tests\npython reviewer.py samples/sample.diff\n```",
    "starter": "",
    "solution": "```console\n$ python -m pytest -q tests\n640 passed, 1 skipped\n\n$ python reviewer.py samples/sample.diff\ntarget   : samples/sample.diff\nmode     : mock\nprovider : mock\nmodel    : local-rules\nfiles    : 2 changed\nfindings : 4 (CRITICAL 3, HIGH 0, MEDIUM 1, LOW 0)\n\nverdict  : block\n```\n\nExit code 0. No key was set and no request left the machine.",
    "explanation": "The second command chose `mock` because neither `SARVAM_API_KEY` nor `LMSTUDIO_BASE_URL` was set. That decision is made in one place, `app/engine.py`, and the response says so in its `note` lines rather than leaving you to guess."
  },
  "exercise": {
    "prompt": "Run both commands and report the counts you see. If the test count is not 640 passed and 1 skipped, find out why before you read another lesson.",
    "hint": "Compare `python --version` with the `.python-version` file, and check that you installed from `requirements.lock` rather than from an unpinned list.",
    "solution": "The expected result is **640 passed, 1 skipped**.\n\nThe one skip is the LM Studio smoke test, guarded by an environment variable: it runs on a machine with a local endpoint and skips everywhere else. A second skip, or a failure, is not the same thing.\n\n> If your count differs, you have dependency rot. Fix the pins before learning anything: an unpinned install can change the program you are studying.",
    "explanation": "This is the first honesty check of the course. Every later lesson quotes a number from the repository, and a number you cannot reproduce is a number you do not have."
  },
  "common_mistakes": [
    "Reading all 157 tracked files first. Read README.md, HANDOFF.md, ARCHITECTURE.md and the ADRs, then follow the lessons — they point at the line ranges that matter.",
    "Trusting a test count from an older note. The suite is 640 passed, 1 skipped at this commit; a different number means your environment is not the pinned one.",
    "Assuming the model layer has produced a review in this repository. It has not: the local and Sarvam paths are simulated, and HANDOFF.md is the authority on which is which.",
    "Editing app/ while learning. The code is the reference implementation; your work goes in rebuild/, and the test suite is your evidence."
  ],
  "project_links": [
    {
      "label": "What it does, how to run it, and the honest status table",
      "path": "README.md",
      "lines": ""
    },
    {
      "label": "The recovery checklist for picking the project back up",
      "path": "RESUME.md",
      "lines": ""
    },
    {
      "label": "The honesty ledger: real, simulated, deferred",
      "path": "HANDOFF.md",
      "lines": ""
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning — the seven-track curriculum this site follows",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/README.md"
    }
  ],
  "glossary_terms": [
    "offline-first — the review completes with no network and no credential; the model is optional",
    "five-field contract — a finding is file, line, severity, issue, suggested fix, and nothing else",
    "provider precedence — sarvam, then local, then mock, decided in app/engine.py alone",
    "degraded path — the live review failed and the deterministic rules answered instead",
    "ADR — architecture decision record; seven of them live in docs/decisions/"
  ]
});
