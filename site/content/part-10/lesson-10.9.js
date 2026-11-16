/* 10.9 — Timeouts, degradation and the one WARNING
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "10.9",
  "part": 10,
  "part_title": "Providers and LLM APIs",
  "title": "Timeouts, degradation and the one WARNING",
  "order": 1009,
  "duration_min": 25,
  "concept_md": "### A bound on every call\n\n`request_timeout_s` defaults to 20 seconds and refuses zero or negative; the local endpoint has its own, larger timeout because a laptop model is slower. A call without a bound is a hang waiting to happen.\n\n### Degrading, once\n\nWhen a live call fails, the run degrades to the rule engine and logs exactly one WARNING. One, not one per finding, and not silence: a reader of the log sees the degradation and its reason in a single line.\n\n### Why exactly one\n\nBecause a per-finding warning buries the signal in noise, and no warning at all makes a degraded run indistinguishable from a clean one. One line is the amount a person will actually read.\n\n### The outcome keeps the record\n\nThe `ProviderOutcome` carries `mode=\"mock\"` and the reason, so the degradation is visible in the result as well as the log. A caller that reads neither gets a real review with an honest provenance it chose not to look at.\n\n### Where the warning is written\n\nThe engine logs it once, at the point it decides to degrade, and the outcome carries the same sentence. That is why the CLI, the API and the JSON output all explain a fallback identically — none of them formats the reason, they only print what the engine recorded.",
  "code_examples": [
    {
      "id": "10.9-ex-0",
      "lang": "console",
      "caption": "Both timeouts, and the constraint on the hosted one",
      "code": "python - <<'PY'\nfrom app.config import Settings\n\nfor name in (\"request_timeout_s\", \"lmstudio_timeout\"):\n    f = Settings.model_fields[name]\n    print(\"%-18s %r %s\" % (name, f.default, [str(m) for m in f.metadata]))\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "request_timeout_s  20.0 ['Gt(gt=0)']\nlmstudio_timeout   120.0 ['Gt(gt=0)']",
      "why_not": "the browser runner does not embed app/config.py or the provider modules; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "How many warnings does a degraded run log?",
      "options": [
        "None; the outcome carries it",
        "One for every finding",
        "Exactly one, with its reason",
        "One per provider tried"
      ],
      "answer": 2,
      "why": "A warning per finding buries the signal; none at all hides the degradation."
    },
    {
      "q": "Why does the local endpoint have its own timeout?",
      "options": [
        "The protocol requires one of its own",
        "The protocol requires one",
        "The SDK defaults to it",
        "A laptop model answers slower"
      ],
      "answer": 3,
      "why": "One bound cannot suit a hosted endpoint and a model running on someone's machine."
    },
    {
      "q": "What carries the record besides the log?",
      "options": [
        "The outcome's mode and reason",
        "The finding's severity",
        "The finding's severity and its count",
        "The diff's file count"
      ],
      "answer": 0,
      "why": "Both surfaces say the same thing, so a caller reading the result is not misled."
    }
  ],
  "try_it": {
    "prompt": "Print both timeouts and confirm neither accepts zero.",
    "starter": "",
    "solution": "```python\nfrom app.config import Settings\n\nfor n in (\"request_timeout_s\", \"lmstudio_timeout\"):\n    print(n, Settings.model_fields[n].default)\n```",
    "explanation": "The hosted bound carries `gt=0`; the local one is larger, as a slower model needs."
  },
  "exercise": {
    "prompt": "Which timeout is larger, and what does the difference assume?",
    "hint": "Compare the two defaults.",
    "solution": "```python\nfrom app.config import Settings\n\nprint(Settings.model_fields[\"lmstudio_timeout\"].default,\n      Settings.model_fields[\"request_timeout_s\"].default)\n```\n\nThe local one is larger, which assumes a model on a laptop is slower than a hosted endpoint.",
    "explanation": "The assumption is stated in the default rather than discovered as a timeout in production."
  },
  "common_mistakes": [
    "Logging a warning per finding, so the degradation is lost in noise.",
    "Giving both endpoints the same timeout.",
    "Setting a timeout to zero to disable it, which the field refuses."
  ],
  "project_links": [
    {
      "label": "The hosted timeout and its bound",
      "path": "app/config.py",
      "lines": "61"
    },
    {
      "label": "The local timeout",
      "path": "app/config.py",
      "lines": "78-82"
    }
  ],
  "learn_more": [
    {
      "label": "app/engine.py — where the fallback happens",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/engine.py"
    },
    {
      "label": "app/config.py — the timeouts",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/config.py"
    }
  ],
  "glossary_terms": [
    "timeout — the bound on one call",
    "degradation — a working path taken when a provider fails",
    "warning — one line in the log, not one per finding"
  ]
});
