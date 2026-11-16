/* 11.1 — The engine owns no transport
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "11.1",
  "part": 11,
  "part_title": "The engine and the fallback",
  "title": "The engine owns no transport",
  "order": 1101,
  "duration_min": 25,
  "concept_md": "### One function, one decision\n\n`app/engine.py` is 387 lines and it contains no HTTP call, no socket and no SDK import. Its own docstring says so: this module owns no transport. Both live providers run through the single `app.openai_compat_provider.py` adapter. The adapter's degraded path calls `app.mock_provider.offline_diff_findings` directly — unless a category filter is set, in which case it calls `app.rules.review_diff`, because categories only exist on local findings.\n\n### What the engine actually does\n\nIt reads `Settings`, decides which provider runs, builds the config that provider needs, calls one function, and relabels the result honestly. Routing and labelling — that is the whole job.\n\n### Why the separation is worth it\n\nBecause a surface that also routed would be a second place the rule lives. The CLI, the API and the webhook all call `review()` and nothing else, so a run that says `mode=\"mock\"` says it for the same reason everywhere.\n\n### What this rules out\n\nAdding a provider means adding an endpoint config, not a transport. If the engine held the HTTP call, every new provider would be a branch inside it — and the branches would drift.\n\n### The claim you can check\n\nGrep the file for `requests`, `httpx`, `openai` or `socket`. The only provider names that appear are the constants it imports, and the only call it makes is `review_with_fallback` from the adapter.",
  "code_examples": [
    {
      "id": "11.1-ex-0",
      "lang": "console",
      "caption": "The engine imports no transport",
      "code": "python - <<'PY'\nimport pathlib, re\n\nsrc = pathlib.Path(\"app/engine.py\").read_text()\nhits = sorted({m for m in (\"requests\", \"httpx\", \"socket\", \"import openai\") if m in src})\nprint(\"transport references:\", hits or \"none\")\nprint(\"lines:\", len(src.splitlines()))\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "transport references: none\nlines: 387",
      "why_not": "the browser runner does not embed app/engine.py or the provider modules; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "What does app/engine.py own?",
      "options": [
        "The retry loop",
        "Routing, labelling and the fallback",
        "Routing and labelling",
        "The prompt text"
      ],
      "answer": 2,
      "why": "It decides which provider runs and labels the result; the transport lives in the adapter."
    },
    {
      "q": "Which module holds the live HTTP call?",
      "options": [
        "app/rules.py",
        "app/engine.py",
        "app/mock_provider.py on every run",
        "openai_compat_provider"
      ],
      "answer": 3,
      "why": "Both live providers run through that one adapter, which is why the engine needs no transport."
    },
    {
      "q": "What do all three surfaces call?",
      "options": [
        "review(), and nothing else",
        "Their own copy of the routing",
        "The adapter directly",
        "The mock provider first"
      ],
      "answer": 0,
      "why": "One entry point means a run labelled mock says so for the same reason on every surface."
    }
  ],
  "try_it": {
    "prompt": "Show that the engine names no transport library.",
    "starter": "",
    "solution": "```console\n$ grep -nE 'requests|httpx|socket|import openai' app/engine.py\n```",
    "explanation": "No output: the file does not import or name a transport at all."
  },
  "exercise": {
    "prompt": "Which single function does the engine call for a live review, and from where is it imported?",
    "hint": "Read the import block at the top of the file.",
    "solution": "```console\n$ sed -n '45,56p' app/engine.py\n```\n\n`review_with_fallback`, imported from `app.openai_compat_provider` — the adapter, not a provider module.",
    "explanation": "The import is the proof: the engine reaches the network only through the adapter."
  },
  "common_mistakes": [
    "Describing the engine as owning the transport; it owns the decision.",
    "Adding a provider by branching inside the engine.",
    "Calling the adapter from a surface instead of the engine."
  ],
  "project_links": [
    {
      "label": "The docstring that says it owns no transport",
      "path": "app/engine.py",
      "lines": "21-26"
    },
    {
      "label": "The one live call",
      "path": "app/engine.py",
      "lines": "382-387"
    }
  ],
  "learn_more": [
    {
      "label": "app/engine.py",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/engine.py"
    },
    {
      "label": "ADR 0002 — every entry point degrades",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0002-offline-first-fallback.md"
    }
  ],
  "glossary_terms": [
    "transport — the code that actually makes a network call",
    "surface — a caller: CLI, API, webhook",
    "routing — deciding which provider runs"
  ]
});
