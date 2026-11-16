/* 12.1 — reviewer.py and the CLI contract
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "12.1",
  "part": 12,
  "part_title": "Surfaces: CLI, API, webhook, GitHub",
  "title": "reviewer.py and the CLI contract",
  "order": 1201,
  "duration_min": 20,
  "concept_md": "### Thirteen lines\n\n`reviewer.py` is thirteen lines: a shebang, a docstring, one import, and `raise SystemExit(main())`. All the logic is in `app/cli.py`. It exists so the command in the README is the command people type, and so the package stays importable without a CLI attached.\n\n### The flags\n\n`--diff` to read a unified diff instead of a source file, `--provider` to ask for one, `--offline` to forbid a live call, `--json` for machine output, `--verbose`, `--min-severity`, `--post-to-pr` and `--list-rules`.\n\n### Three exit codes\n\n`0` for a review that produced something, `1` for bad input or a failed post, `2` for a usage error — the argparse convention. The codes matter because a CI step reads them: a review that found a CRITICAL is still exit `0`, since the tool succeeded at reviewing.\n\n### Why the codes are not findings\n\nIf a CRITICAL finding made the exit non-zero, every CI job would fail on the first real bug and the tool would be turned off. The exit code says whether the review ran; the findings say what it found.\n\n### Why the flag list is short\n\nEight flags is not a thin CLI — it is the set that changes what a review does rather than how it is printed. Anything that only reformats the output belongs in the formatter, and anything that changes the routing belongs in the engine, which is why `--provider` and `--offline` pass straight through.",
  "code_examples": [
    {
      "id": "12.1-ex-0",
      "lang": "console",
      "caption": "The entry script, in full",
      "code": "wc -l reviewer.py && sed -n '1,13p' reviewer.py",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "13 reviewer.py\n#!/usr/bin/env python3\n\"\"\"Phase 1 entry point: ``python reviewer.py <file> [--offline] [--json]``.\n\nAll logic lives in the ``app`` package; this file only anchors the CLI at the\nproject root so the command in the README is the one people type.\n\"\"\"\n\nfrom __future__ import annotations\n\nfrom app.cli import main\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())",
      "why_not": "the browser runner has no shell and does not embed the surface modules; this command runs from a checkout."
    }
  ],
  "quiz": [
    {
      "q": "How many lines is reviewer.py?",
      "options": [
        "About fifty, with the argument parsing",
        "Thirteen, all of them boilerplate",
        "Several hundred, with the review loop",
        "None; it is generated at install"
      ],
      "answer": 1,
      "why": "The logic lives in app/cli.py; the script exists so the README's command works from the repo root."
    },
    {
      "q": "What does exit code 1 mean?",
      "options": [
        "The review found a CRITICAL",
        "The provider was offline",
        "The input was bad",
        "The usage string was printed"
      ],
      "answer": 2,
      "why": "Findings never change the exit code, because a CI job that failed on the first real bug would be switched off."
    },
    {
      "q": "Which flag forbids a live call?",
      "options": [
        "--provider none",
        "--no-network",
        "--mock-only",
        "--offline"
      ],
      "answer": 3,
      "why": "It maps onto force_offline in the engine, so no key can cause a call."
    }
  ],
  "try_it": {
    "prompt": "Print the CLI's exit-code constants.",
    "starter": "",
    "solution": "```console\n$ grep -n '_EXIT_' app/cli.py | head -3\n```",
    "explanation": "Zero, one and two — the argparse convention, named rather than scattered as literals."
  },
  "exercise": {
    "prompt": "Which flag asks for machine-readable output, and what shape does it produce?",
    "hint": "One flag, one JSON object.",
    "solution": "```console\n$ grep -n '\"--json\"' -A 4 app/cli.py\n```\n\n`--json` prints one JSON object rather than the human summary.",
    "explanation": "One object, not a stream, so a caller can parse the whole run at once."
  },
  "common_mistakes": [
    "Making a CRITICAL finding set the exit code non-zero.",
    "Putting the review logic in reviewer.py instead of the package.",
    "Treating a usage error and bad input as the same code."
  ],
  "project_links": [
    {
      "label": "The whole entry script",
      "path": "reviewer.py",
      "lines": "1-13"
    },
    {
      "label": "The exit codes",
      "path": "app/cli.py",
      "lines": "50-55"
    }
  ],
  "learn_more": [
    {
      "label": "reviewer.py",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/reviewer.py"
    },
    {
      "label": "app/cli.py",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/cli.py"
    }
  ],
  "glossary_terms": [
    "surface — a way in: CLI, API, webhook, GitHub",
    "exit code — what a caller reads to know if it ran",
    "entry point — the file a user invokes"
  ]
});
