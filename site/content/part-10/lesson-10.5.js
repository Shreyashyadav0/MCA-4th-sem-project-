/* 10.5 — `select_provider`: auto, live and mock
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "10.5",
  "part": 10,
  "part_title": "Providers and LLM APIs",
  "title": "`select_provider`: auto, live and mock",
  "order": 1005,
  "duration_min": 25,
  "concept_md": "### One function decides\n\n`select_provider(settings, requested=\"auto\")` returns a `ProviderSelection`: the provider name, the config it needs, and a one-line reason. Every surface goes through it, so the routing rule exists once.\n\n### The four requests\n\nThe selector accepts `auto`, `sarvam`, `local` and `mock`. `auto` prefers a configured provider and falls back to mock. Naming a provider asks for that one and degrades with a reason if it is unavailable. `mock` forces the rule engine. Anything else raises `ValueError`, listing the four.\n\nForced offline is not a request — it is the `force_offline` flag on `review()`, which stops a live call being made at all.\n\n### Why the reason is part of the return value\n\nBecause a decision without its reason is unauditable. When a run is degraded, the outcome carries the sentence that explains it, and the reader never has to guess whether a key was missing or a mode was forced.\n\n### The ordering\n\nSarvam first when both are configured, because a hosted model is the stronger claim; then local; then mock. The order is written in one place and every surface inherits it.\n\n### Why the selector is one function\n\nThe CLI, the API and the tests all need the same answer to \"which provider runs now\". If each computed it, a demo and a test could disagree about whether a run was live — and the disagreement would show up as a mislabelled outcome rather than an error.",
  "code_examples": [
    {
      "id": "10.5-ex-0",
      "lang": "console",
      "caption": "Three requests, three decisions",
      "code": "python - <<'PY'\nfrom app.config import Settings\nfrom app.engine import select_provider\n\ns = Settings()\nfor asked in (\"auto\", \"sarvam\", \"local\", \"mock\"):\n    sel = select_provider(s, requested=asked)\n    print(\"%-6s -> %-5s | %s\" % (asked, sel.provider, sel.reason[:46]))\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "auto   -> mock  | no SARVAM_API_KEY or LMSTUDIO_BASE_URL configu\nsarvam -> mock  | provider sarvam requested but SARVAM_API_KEY i\nlocal  -> mock  | provider local requested but LMSTUDIO_BASE_URL\nmock   -> mock  | provider forced to mock",
      "why_not": "the browser runner does not embed app/config.py or the provider modules; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "What does a selection carry besides the provider?",
      "options": [
        "Its reason and its model name",
        "Its config and its secret key",
        "Its config and its reason",
        "Its model and its request timeout"
      ],
      "answer": 2,
      "why": "The reason makes the decision auditable, so a degraded run explains itself."
    },
    {
      "q": "Which four requests does the selector accept?",
      "options": [
        "sarvam, local, mock, and live",
        "auto, live, offline, mock",
        "live, local, mock, and auto",
        "auto, sarvam, local, mock"
      ],
      "answer": 3,
      "why": "Forced offline is not a request; it is a separate flag on `review()`, so it is not in the vocabulary."
    },
    {
      "q": "When both are configured, which runs?",
      "options": [
        "Sarvam, then local, then mock",
        "Local, then Sarvam, then mock",
        "Whichever answers fastest",
        "Whichever the request names"
      ],
      "answer": 0,
      "why": "The order is written once in the selector, so every surface inherits the same preference."
    }
  ],
  "try_it": {
    "prompt": "Print all three decisions with nothing configured.",
    "starter": "",
    "solution": "```python\nfrom app.config import Settings\nfrom app.engine import select_provider\n\nfor asked in (\"auto\", \"sarvam\", \"local\", \"mock\"):\n    print(asked, select_provider(Settings(), requested=asked).provider)\n```",
    "explanation": "All three land on mock with an empty environment; only the reason differs."
  },
  "exercise": {
    "prompt": "What does `requested=\"sarvam\"` select when no key is set, and why?",
    "hint": "Naming a provider asks for it; the gate decides whether it is there.",
    "solution": "```python\nfrom app.config import Settings\nfrom app.engine import select_provider\n\nsel = select_provider(Settings(), requested=\"sarvam\")\nprint(sel.provider, \"|\", sel.reason)\n```\n\nMock, with a reason naming the missing key: asking for a provider does not conjure one.",
    "explanation": "A named provider that is unavailable degrades and records why, rather than failing the run."
  },
  "common_mistakes": [
    "Deciding the provider in a surface instead of in the selector.",
    "Dropping the reason when the decision is degraded.",
    "Treating forced offline as a request; it is a flag on `review()`."
  ],
  "project_links": [
    {
      "label": "The selection record",
      "path": "app/engine.py",
      "lines": "83-96"
    },
    {
      "label": "The one routing function",
      "path": "app/engine.py",
      "lines": "200-281"
    }
  ],
  "learn_more": [
    {
      "label": "app/engine.py — the selection",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/engine.py"
    },
    {
      "label": "DEMO.md — the three variants",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/DEMO.md"
    }
  ],
  "glossary_terms": [
    "selection — a routing decision with its config and reason",
    "auto — prefer a provider, fall back to mock",
    "forced offline — a run that may not call out"
  ]
});
