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
  "concept_md": "### What this project is\n\nAn offline-first AI code reviewer. Point it at a unified diff or a source file and it returns findings with exactly five fields — file, line, severity, issue, suggested fix — and it can post them to a pull request as inline comments. The posting path is exercised against a fake HTTP client, not against GitHub itself — `HANDOFF.md` is the ledger on that.\n\nThe deterministic part is the product: **63 OWASP-mapped rules** that read added lines only, with no API key, no network and no model. The model is an upgrade on top of that, never a dependency. If the key is missing, the endpoint is down, or the answer does not parse, the review still completes — with one `WARNING` that says what happened, never an exception and never a silent downgrade.\n\n### What you will be able to do by the end\n\n- Read every module in `app/` without a guide beside you.\n- Rebuild `models.py`, `parser.py`, `rules.py` and `engine.py` from memory, each one proved by the test suite rather than by feeling.\n- Explain the fallback architecture: what degrades, where the single `WARNING` comes from, and why the degraded path calls the rule engine directly (ADR 0004).\n- State the provider precedence — `sarvam > local > mock` — and name the one function that decides it.\n- Defend the honesty limits in `HANDOFF.md` at a viva, including the things that are simulated rather than real.\n\n### The shape of the thing\n\n| Stage | Module | What it decides |\n|---|---|---|\n| Parse | `app/parser.py` | which lines the diff actually added |\n| Review | `app/rules.py` | which of the 63 deterministic rules fire |\n| Choose | `app/engine.py` | sarvam, local or mock — in one place |\n| Anchor | `app/parser.py` | whether a comment can attach to a line |\n| Post | `app/github_client.py` | inline comments, or a summary when anchoring fails |\n\n### Start here\n\n```console\npython -m pytest -q tests\npython reviewer.py samples/sample.diff\n```\n\nThe first command tells you whether the environment is sound. The second shows the whole pipeline on a real diff: mode `mock`, four findings, verdict `block`, exit code 0.\n\n> 640 passed, 1 skipped is the number to expect at this commit. If yours differs, stop and fix the pins in `requirements.lock` before learning anything — otherwise you are studying a different program from the one this site describes.\n\n### How to read this site\n\nEvery lesson has a concept, a worked example, something to try, an exercise, and the mistakes people actually make. The links at the bottom point at the exact file and line range the lesson is about: read that code, close it, and write it again from memory.\n\nThe site is a learning aid. `HANDOFF.md` is the ledger; `docs/learning/` is the curriculum.",
  "code_examples": [
    {
      "id": "0.1-ex-0",
      "lang": "python",
      "caption": "The real rule engine, running on the real sample diff — press Run",
      "code": "from app.models import verdict_for\nfrom app.parser import parse_diff\nfrom app.rules import review_diff\n\nwith open(\"samples/sample.diff\", encoding=\"utf-8\") as handle:\n    bundle = parse_diff(handle.read(), source=\"samples/sample.diff\")\n\nfindings = review_diff(bundle)\nprint(\"files changed:\", bundle.files_changed)\nprint(\"findings     :\", len(findings))\nfor finding in findings:\n    print(f\"  {finding.severity.value:8} {finding.file}:{finding.line}\")\nprint(\"verdict      :\", verdict_for(findings))\n",
      "runnable": true,
      "run_tier": "browser",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py",
        "app/parser.py",
        "app/rules.py",
        "samples/sample.diff"
      ],
      "expected_output": "files changed: 2\nfindings     : 4\n  CRITICAL app/db.py:3\n  CRITICAL app/db.py:3\n  CRITICAL app/db.py:7\n  MEDIUM   app/report.py:1\nverdict      : block"
    },
    {
      "id": "0.1-ex-1",
      "lang": "console",
      "caption": "The same thing from a shell — this half needs a terminal",
      "code": "python -m pytest -q tests\npython reviewer.py samples/sample.diff",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "these are shell commands: they start a process, run a test suite and read the repository from disk. A browser page has no shell, no repository checkout and no subprocess.",
      "expected_output": "640 passed, 1 skipped\n\ntarget   : samples/sample.diff\nmode     : mock\nprovider : mock\nmodel    : local-rules\nfiles    : 2 changed\nfindings : 4 (CRITICAL 3, HIGH 0, MEDIUM 1, LOW 0)\nnote     : mock mode: no SARVAM_API_KEY or LMSTUDIO_BASE_URL configured; local rule engine used\nnote     : local rule engine: 63 deterministic rules, no network, no API key\n\nchanged lines:\n  modified  app/db.py  (+4: 3-4, 7-8)\n  added     app/report.py  (+5: 1-5)\n\nverdict  : block\n\n# abridged: the four findings, their suggested fixes and their anchors are\n# omitted. Everything above is stdout, verbatim; pytest also prints a timing.\n# stderr carries one WARNING: local review degraded to the local rule engine."
    }
  ],
  "try_it": {
    "prompt": "Press Run on the first example and read the seven lines it prints. Then change one thing and press Run again: set `min_severity=Severity.HIGH` on the `review_diff` call and watch which findings survive.\n\n`review_diff` takes `min_severity` as a keyword-only argument, and `Severity` is importable from `app.models`.",
    "starter": "from app.models import Severity, verdict_for\nfrom app.parser import parse_diff\nfrom app.rules import review_diff\n\nwith open(\"samples/sample.diff\", encoding=\"utf-8\") as handle:\n    bundle = parse_diff(handle.read())\n\nfindings = review_diff(bundle)          # add min_severity=Severity.HIGH here\nprint(len(findings), \"findings\")\nprint(\"verdict:\", verdict_for(findings))\n",
    "solution": "from app.models import Severity, verdict_for\nfrom app.parser import parse_diff\nfrom app.rules import review_diff\n\nwith open(\"samples/sample.diff\", encoding=\"utf-8\") as handle:\n    bundle = parse_diff(handle.read())\n\nall_findings = review_diff(bundle)\nhigh_only = review_diff(bundle, min_severity=Severity.HIGH)\nprint(\"all      :\", len(all_findings), verdict_for(all_findings))\nprint(\"HIGH+    :\", len(high_only), verdict_for(high_only))\n",
    "explanation": "`min_severity` drops findings below the threshold before they reach the result, so the count falls from 4 to 3 and the verdict stays `block` — three CRITICAL findings are still enough to block. Filtering never invents a finding; it can only remove one, which is why the verdict can only move towards `approve`."
  },
  "exercise": {
    "prompt": "Run the second example's commands in a terminal, then make the live example agree with them. The CLI reports four findings and `block`; your browser run must say the same. If it does not, the difference is the lesson.",
    "hint": "Compare the two outputs line by line. The CLI prints `findings : 4 (CRITICAL 3, HIGH 0, MEDIUM 1, LOW 0)`; the browser prints one line per finding. Count them.",
    "solution": "Both agree: **4 findings, verdict block** — three CRITICAL in `app/db.py` (lines 3, 3 and 7) and one MEDIUM in `app/report.py`.\n\n```console\n$ python -m pytest -q tests\n640 passed, 1 skipped\n```\n\nThe browser run and the CLI run the same `app/rules.py` over the same diff, which is the whole claim: no model is involved in either.\n\n> If your counts differ, suspect the interpreter and the install before anything else: check `python --version` against `.python-version`, and install from `requirements.lock`.",
    "explanation": "This is the first honesty check of the course. Every later lesson quotes a number from the repository, and a number you cannot reproduce is a number you do not have."
  },
  "quiz": [
    {
      "q": "How many findings does the rule engine produce for samples/sample.diff?",
      "options": [
        "3",
        "4",
        "5",
        "63"
      ],
      "answer": 1,
      "why": "Four: three CRITICAL in app/db.py and one MEDIUM in app/report.py. 63 is the number of rules, not findings."
    },
    {
      "q": "Which command runs the test suite?",
      "options": [
        "python -m pytest -q tests",
        "python reviewer.py tests, without -q",
        "pytest site/",
        "python -m unittest"
      ],
      "answer": 0,
      "why": "The suite lives in tests/ and is pytest-style, so pytest is what runs it; bare `python -m unittest` finds nothing because no test there is a unittest class."
    },
    {
      "q": "Where is the choice between sarvam, local and mock decided?",
      "options": [
        "Separately in each surface (CLI, API, webhook)",
        "In app/engine.py, in one place",
        "In every module that needs a provider",
        "In the command-line flags only"
      ],
      "answer": 1,
      "why": "app/engine.py holds PROVIDERS and select_provider; every surface calls it, so the precedence cannot drift between them."
    }
  ],
  "common_mistakes": [
    "Reading all 157 tracked files first. Read README.md, HANDOFF.md, ARCHITECTURE.md and the ADRs, then follow the lessons — they point at the line ranges that matter.",
    "Trusting a test count from an older note. The suite is 640 passed, 1 skipped at the frozen commit; a different number means your environment is not the pinned one.",
    "Assuming the model layer has produced a review in this repository. It has not: the local and Sarvam paths are simulated, and HANDOFF.md is the authority on which is which.",
    "Editing app/ while learning. The code is the reference implementation; your work goes in rebuild/, and the test suite is your evidence."
  ],
  "project_links": [
    {
      "label": "What it does and how to run it",
      "path": "README.md",
      "lines": "12-57"
    },
    {
      "label": "The honesty ledger: what is real, simulated and deferred",
      "path": "HANDOFF.md",
      "lines": "1-53"
    },
    {
      "label": "The recovery checklist for picking the project back up",
      "path": "RESUME.md",
      "lines": "1-25"
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
