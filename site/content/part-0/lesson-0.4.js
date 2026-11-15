/* 0.4 — The 60-second architecture tour
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "0.4",
  "part": 0,
  "part_title": "Orientation",
  "title": "The 60-second architecture tour",
  "order": 4,
  "duration_min": 15,
  "concept_md": "### Five boxes\n\n```text\ndiff ──► parser ──► rule engine (63 rules) ──► findings ──► anchor ──► report\n                        │                                              │\n                        └── optional: OpenAI-compatible adapter ───────┴──► pull request\n                                    (Sarvam | LM Studio)                     (inline + summary)\n```\n\n- **Parser** — turns a unified diff into files, hunks and numbered lines. Only added lines matter, because only they can be commented on.\n- **Rule engine** — 63 deterministic rules over those added lines. No network, no key, no model.\n- **Provider adapter** — one OpenAI-compatible transport used by both Sarvam and LM Studio. It is an upgrade, never a dependency.\n- **Engine selector** — decides which provider runs, in exactly one function, and labels the result honestly.\n- **Surfaces** — the CLI and the HTTP API. They call the engine and do nothing clever themselves.\n\n### Precedence, in one line\n\n`sarvam > local > mock`. With no key and no endpoint configured, the rule engine runs and the response says so in its `note` lines. A local review is never labelled `sarvam`.\n\n### The fallback chain\n\nA missing key, a dead endpoint, a 401, a 429, a reply that does not parse — each ends in the same place: a working rule-based review with **exactly one** warning explaining what happened. That is the property worth remembering. A reviewer should never have to guess whether a result came from a model.\n\n### What is not here\n\nThe model layer has never produced a review in this repository. The local and Sarvam paths are exercised against a stub and a real 403 respectively; `HANDOFF.md` is the ledger, and it is right where other documents disagree.",
  "code_examples": [
    {
      "id": "0.4-ex-0",
      "lang": "console",
      "caption": "Precedence is a tuple in one file, not a rule spread across surfaces",
      "code": "python -c \"from app.engine import PROVIDERS; print(PROVIDERS)\"",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "importing app.engine pulls in app.config, which needs pydantic-settings — a package the browser's Python does not have.",
      "expected_output": "('sarvam', 'local', 'mock')"
    }
  ],
  "quiz": [
    {
      "q": "Which module decides whether the review uses sarvam, local or mock?",
      "options": [
        "app/parser.py",
        "app/rules.py",
        "app/main.py",
        "app/engine.py"
      ],
      "answer": 3,
      "why": "app/engine.py holds PROVIDERS and select_provider; every surface calls it, so the decision cannot drift between CLI and HTTP."
    },
    {
      "q": "You configure neither a Sarvam key nor a local endpoint. What happens?",
      "options": [
        "The review fails with an error telling you to configure a key",
        "The rule engine runs and the response says mock in its note lines",
        "It waits for a key and then gives up after a timeout",
        "It silently returns an empty result with no note at all"
      ],
      "answer": 1,
      "why": "With nothing configured the selector chooses mock and the response reports it, which is why the offline path is the default rather than a special case."
    },
    {
      "q": "A live review fails mid-flight. How many warnings should you see?",
      "options": [
        "Exactly one",
        "None",
        "One per rule",
        "One per retry"
      ],
      "answer": 0,
      "why": "The degraded path is designed to emit a single WARNING; two would mean the adapter and the fallback both logged, which ADR 0004 exists to prevent."
    }
  ],
  "try_it": {
    "prompt": "Open `ARCHITECTURE.md` and find the box that owns line anchoring. Then find which module draws the inline-comment boundary.",
    "starter": "# The precedence order, and the module that owns it.\nPROVIDERS = (\"sarvam\", \"local\", \"mock\")\nprint(\"first choice:\", PROVIDERS[0])\n",
    "solution": "```text\nAnchoring is `app/parser.py` (`anchor_findings`); the inline-versus-summary decision is `app/github_client.py` (`build_payload`). Both are named in the architecture diagram's result shapes.\n```",
    "explanation": "Anchoring is review metadata — can GitHub attach this comment? — so it wraps a finding rather than extending it."
  },
  "exercise": {
    "prompt": "Map each of these five files to its box in the diagram, in one line each: `app/parser.py`, `app/rules.py`, `app/engine.py`, `app/openai_compat_provider.py`, `app/main.py`.",
    "hint": "One of the five is a surface, not a stage in the pipeline.",
    "solution": "```text\n- `app/parser.py` — parser, plus the anchoring step after the findings exist.\n- `app/rules.py` — the rule engine: 63 deterministic rules over added lines.\n- `app/engine.py` — the selector: provider precedence and the single entry point.\n- `app/openai_compat_provider.py` — the one transport both hosted and local models use.\n- `app/main.py` — a surface (FastAPI), which calls the engine and stores the result.\n```",
    "explanation": "Four stages and one surface. Persistence is a side branch: nothing in parser, rules, engine or the providers imports the database, which is why the pipeline runs with no database at all."
  },
  "common_mistakes": [
    "Assuming the model layer runs when nothing is configured. With no key and no endpoint the rule engine runs, and the response says `mock`.",
    "Reading `mode: live` as proof a model answered well. It says which path ran, not how good the answer was — and no benchmark number exists yet.",
    "Looking for a second rule engine on the degraded path. There is one; ADR 0004 explains why the adapter calls it directly."
  ],
  "project_links": [
    {
      "label": "The module graph, the fallback chain and the frozen interfaces",
      "path": "ARCHITECTURE.md",
      "lines": "1-60"
    },
    {
      "label": "PROVIDERS and the selection result",
      "path": "app/engine.py",
      "lines": "57-67"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-6-engine.md — the engine, rebuilt from memory",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-6-engine.md"
    },
    {
      "label": "ADR 0004 — why the degraded path calls the rule engine directly",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0004-degraded-path-calls-offline-findings-directly.md"
    }
  ],
  "glossary_terms": [
    "provider — the thing that produces findings: the rule engine, a local model, or Sarvam",
    "precedence — the fixed order sarvam, local, mock, decided in one function",
    "degraded path — a live review that failed and fell back to the rule engine",
    "surface — a way in: the CLI or the HTTP API"
  ]
});
