/* 12.10 — Guided read: four surfaces, one engine
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "12.10",
  "part": 12,
  "part_title": "Surfaces: CLI, API, webhook, GitHub",
  "title": "Guided read: four surfaces, one engine",
  "order": 1210,
  "duration_min": 30,
  "concept_md": "### The shape of the last part\n\nFour ways in, one way through. The CLI parses arguments and prints; the API routes and serialises; the webhook verifies and hands over; the GitHub client posts. Every one of them calls `review()` in `app/engine.py` and renders the `ProviderOutcome` it gets back.\n\n### What to read, and in what order\n\n`reviewer.py` first, because it is thirteen lines and shows where the CLI lives. Then `app/cli.py` for the flags and the exit codes. Then `app/main.py` for the routes and the auth split. Then `app/github_client.py` for the posting rules, the marker and the demotion.\n\n### The invariant to look for\n\nNo surface decides which provider runs. Each one passes a `--provider` value or a request body through, and the engine answers. That is why a mock run is labelled the same way whether it came from a terminal, a webhook or a pull request.\n\n### The rebuild exercise\n\n`rebuild/tests/test_rebuild_surfaces.py` asks you to reimplement the CLI's exit codes and the marker, which are the two contracts a surface owns. The engine is not your problem there; the shape of what it returns is.\n\n### What the site has covered\n\nTwelve parts, from a first script to the four surfaces in front of you. The last lesson is the one that says which of it has been run and which has not — because that distinction is the difference between a project and a demo.",
  "code_examples": [
    {
      "id": "12.10-ex-0",
      "lang": "console",
      "caption": "The four surfaces, by size",
      "code": "wc -l reviewer.py app/cli.py app/main.py app/github_client.py app/engine.py",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "    13 reviewer.py\n   549 app/cli.py\n  1610 app/main.py\n  1285 app/github_client.py\n   387 app/engine.py\n  3844 total",
      "why_not": "the browser runner has no shell and does not embed the surface modules; this command runs from a checkout."
    }
  ],
  "quiz": [
    {
      "q": "What do all four surfaces call?",
      "options": [
        "The adapter, called directly",
        "The rule registry, first",
        "review() in the engine",
        "Their own routing code"
      ],
      "answer": 2,
      "why": "That is why a mock run is labelled identically from every surface."
    },
    {
      "q": "Which file should be read first?",
      "options": [
        "app/main.py, the largest file",
        "app/engine.py, at the centre",
        "app/cli.py, with all of its flags",
        "reviewer.py, at thirteen lines"
      ],
      "answer": 3,
      "why": "It is short enough to show where the CLI lives before you read the CLI."
    },
    {
      "q": "Which two contracts does a surface own?",
      "options": [
        "Exit codes and the marker",
        "Routing and the labels",
        "The prompt and the parser",
        "The schema and the rule ids"
      ],
      "answer": 0,
      "why": "The rebuild suite asks for those two, because the rest belongs to the engine."
    }
  ],
  "try_it": {
    "prompt": "Compare the four surface files by size.",
    "starter": "",
    "solution": "```console\n$ wc -l reviewer.py app/cli.py app/main.py app/github_client.py\n```",
    "explanation": "Thirteen lines to 1610 — the entry script is a signpost, the client carries the error vocabulary."
  },
  "exercise": {
    "prompt": "Which surface file is largest, and what makes it large?",
    "hint": "One file holds six failure decisions.",
    "solution": "```console\n$ wc -l app/main.py app/github_client.py\n```\n\n`app/main.py` at 1610 lines — routes, models and the auth dependency. The client is 1285, mostly error translation.",
    "explanation": "Both are long for the same reason: many small decisions that each need their own honest message."
  },
  "common_mistakes": [
    "Reading the client before the engine and assuming it routes.",
    "Reimplementing the engine in a rebuild of a surface.",
    "Treating the largest file as the most important one."
  ],
  "project_links": [
    {
      "label": "The rebuild suite",
      "path": "rebuild/tests/test_rebuild_surfaces.py",
      "lines": "1-40"
    },
    {
      "label": "The engine every surface calls",
      "path": "app/engine.py",
      "lines": "320-387"
    }
  ],
  "learn_more": [
    {
      "label": "app/cli.py",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/cli.py"
    },
    {
      "label": "rebuild/README.md — the exercises",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/rebuild/README.md"
    }
  ],
  "glossary_terms": [
    "surface — a way into the same engine",
    "contract — what a surface promises its caller",
    "invariant — a rule that holds on every path"
  ]
});
