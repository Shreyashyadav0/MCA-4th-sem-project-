/* 9.4 — Precedence, defaults and timeouts: what happens when nothing is set
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "9.4",
  "part": 9,
  "part_title": "Configuration and offline-first",
  "title": "Precedence, defaults and timeouts: what happens when nothing is set",
  "order": 904,
  "duration_min": 25,
  "concept_md": "### Nothing set is a valid state\n\nRun the tool with an empty environment and it starts in `mock` mode with persistence on and no credentials. That is not a fallback bolted on late; it is what every default in `Settings` is chosen for.\n\n### The precedence\n\nA value comes from the process environment first, then from `.env`, then from the field default. Environment beats file because a shell variable is the more deliberate act — you typed it for this run.\n\n### Timeouts\n\n`request_timeout_s` defaults to 20 seconds and refuses zero or negative. `lmstudio_timeout` is larger, because a local model on a laptop is slower than a hosted endpoint. Both are floats, so a caller can tune without a code change.\n\n### Why the defaults are conservative\n\nPersistence on, authentication off, review mode `auto`. Each is the choice that keeps a demo answerable: a database that exists means history works, open management endpoints mean no key is needed to look at the result, and `auto` means the selector decides rather than the reader.\n\n### What the defaults are not\n\nThey are not a security posture. Authentication off is right for a demo and wrong for a deployment, and `api_auth_enabled` exists for exactly that reason.",
  "code_examples": [
    {
      "id": "9.4-ex-0",
      "lang": "console",
      "caption": "What nothing set actually gives you",
      "code": "python - <<'PY'\nfrom app.config import Settings\n\ns = Settings()\nfor name in (\"review_mode\", \"api_auth_enabled\", \"request_timeout_s\", \"lmstudio_timeout\"):\n    print(\"%-20s %r\" % (name, getattr(s, name)))\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "review_mode          'auto'\napi_auth_enabled     False\nrequest_timeout_s    20.0\nlmstudio_timeout     120.0",
      "why_not": "the browser runner does not embed app/config.py, and it needs pydantic-settings; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "Which source wins when both are set?",
      "options": [
        "The process environment",
        "The .env file",
        "The field default",
        "Whichever one loaded first"
      ],
      "answer": 0,
      "why": "A shell variable is the more deliberate act for one run, so it beats the file."
    },
    {
      "q": "What does `request_timeout_s` refuse?",
      "options": [
        "Zero and negative values",
        "Values above sixty seconds, which are refused",
        "Non-integer values only",
        "Nothing; it is unbounded"
      ],
      "answer": 0,
      "why": "The field carries `gt=0`, so an unusable timeout fails at construction rather than at request time."
    },
    {
      "q": "Is authentication on by default?",
      "options": [
        "No, it is off for the demo",
        "Yes, with a seeded key",
        "Only when a database exists",
        "Only in live review mode"
      ],
      "answer": 0,
      "why": "Open management endpoints keep the demo answerable without a key; `api_auth_enabled` exists for deployments."
    }
  ],
  "try_it": {
    "prompt": "Print the four defaults that make an empty environment usable.",
    "starter": "",
    "solution": "```python\nfrom app.config import Settings\n\ns = Settings()\nprint(s.review_mode, s.api_auth_enabled, s.request_timeout_s, s.database_path)\n```",
    "explanation": "`auto`, `False`, `20.0` and a relative SQLite path — the four that keep a demo answerable."
  },
  "exercise": {
    "prompt": "Which default would you change first for a deployment, and which field changes it?",
    "hint": "Think about what is open that should not be.",
    "solution": "```python\nfrom app.config import Settings\n\nprint(Settings.model_fields[\"api_auth_enabled\"].default)\n```\n\n`False` — set `API_AUTH_ENABLED=true` and seed an admin key before exposing the management endpoints.",
    "explanation": "The default is right for a demo and wrong for a deployment, which is why the switch exists rather than a hardcoded choice."
  },
  "common_mistakes": [
    "Assuming `.env` overrides a shell variable; the environment wins.",
    "Setting a zero timeout to disable it, which the field refuses.",
    "Exposing the management endpoints with authentication still off."
  ],
  "project_links": [
    {
      "label": "The auth switch and its default",
      "path": "app/config.py",
      "lines": "91-98"
    },
    {
      "label": "The database path default",
      "path": "app/config.py",
      "lines": "83-90"
    }
  ],
  "learn_more": [
    {
      "label": "app/config.py — the settings",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/config.py"
    },
    {
      "label": ".env.example — every variable",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/.env.example"
    }
  ],
  "glossary_terms": [
    "precedence — which source wins when two are set",
    "default — the value used when nothing is set",
    "timeout — the bound on one HTTP request"
  ]
});
