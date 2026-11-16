/* 11.5 — One WARNING per degraded run
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "11.5",
  "part": 11,
  "part_title": "The engine and the fallback",
  "title": "One WARNING per degraded run",
  "order": 1105,
  "duration_min": 20,
  "concept_md": "### The count is the design\n\nA degraded run logs exactly one WARNING. Not one per finding, not one per provider tried, and not silence.\n\n### Why exactly one\n\nA warning per finding buries the signal: a 40-finding review would produce 40 lines saying the same thing. Silence is worse, because a degraded run would then be indistinguishable from a clean one in the log. One line is what a person reads.\n\n### Where it is written\n\nThe line is emitted inside the adapter, in `openai_compat_provider`, at the point the live attempt is abandoned. `app/engine.py` never logs: its three mentions of WARNING are docstrings stating the invariant. So the log carries the adapter's generic sentence — \"no OpenAI-compatible provider selected\" — while `ProviderOutcome.reason` is relabelled by the caller to the more specific cause. Two sentences, one event: the log is the adapter's view, the outcome is the caller's.\n\n### What the outcome carries\n\nA more specific sentence on `ProviderOutcome.reason`, with `mode=\"mock\"`. A caller that reads neither the log nor the outcome gets a real review with an honest provenance it chose not to look at — which is the failure mode this design cannot prevent, only make visible.\n\n### Why it is a WARNING and not an INFO\n\nBecause a degraded run is not the normal case for a configured deployment. The level says \"this worked, but not the way it was meant to\", which is exactly the distinction a reader of the log needs at three in the morning.",
  "code_examples": [
    {
      "id": "11.5-ex-0",
      "lang": "console",
      "caption": "The invariant is written in the engine; the line is emitted in the adapter",
      "code": "python - <<'PY'\nimport pathlib\n\nfor name in (\"app/engine.py\", \"app/openai_compat_provider.py\"):\n    src = pathlib.Path(name).read_text().splitlines()\n    hits = [n for n, l in enumerate(src, 1) if \"WARNING\" in l or \"logger.warning\" in l]\n    print(name, hits)\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "app/engine.py [25, 295, 332]\napp/openai_compat_provider.py [15, 25, 497, 582, 591, 635, 681]",
      "why_not": "the browser runner does not embed app/engine.py or the provider modules; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "How many warnings does a degraded run log?",
      "options": [
        "One per provider",
        "One per finding",
        "Exactly one",
        "None at all"
      ],
      "answer": 2,
      "why": "A warning per finding buries the signal; none at all hides the degradation."
    },
    {
      "q": "Why is silence the worse failure?",
      "options": [
        "The findings become invalid",
        "The log file grows larger",
        "The caller cannot retry",
        "A degraded run looks clean"
      ],
      "answer": 3,
      "why": "Without the line, a run without a model is indistinguishable from one with it."
    },
    {
      "q": "What else carries the same sentence?",
      "options": [
        "ProviderOutcome.reason",
        "The findings list",
        "The HTTP status code",
        "The module docstring on every run"
      ],
      "answer": 0,
      "why": "Both surfaces say the same thing, so a caller reading the result is not misled."
    }
  ],
  "try_it": {
    "prompt": "Find every mention of WARNING in the engine.",
    "starter": "",
    "solution": "```console\n$ grep -n 'logger.warning' app/openai_compat_provider.py\n```",
    "explanation": "One call site in the adapter. The engine's mentions are prose that states the rule, not code that logs."
  },
  "exercise": {
    "prompt": "Which two fields of the outcome make a degraded run visible?",
    "hint": "One is a mode, one is a sentence.",
    "solution": "```console\n$ python -c \"from app.sarvam_provider import ProviderOutcome; print([f for f in ('mode','reason') if f in ProviderOutcome.model_fields])\"\n```\n\n`mode` says mock, and `reason` says why.",
    "explanation": "A caller needs both: the mode to branch on and the reason to report."
  },
  "common_mistakes": [
    "Logging a warning per finding.",
    "Degrading silently so the log looks clean.",
    "Formatting the reason in each surface instead of printing the engine's."
  ],
  "project_links": [
    {
      "label": "The invariant, in the module docstring",
      "path": "app/engine.py",
      "lines": "21-26"
    },
    {
      "label": "The reason the caller keeps",
      "path": "app/engine.py",
      "lines": "284-317"
    }
  ],
  "learn_more": [
    {
      "label": "app/engine.py",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/engine.py"
    },
    {
      "label": "ADR 0002 — the fallback decision",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0002-offline-first-fallback.md"
    }
  ],
  "glossary_terms": [
    "degraded run — a review produced without a model",
    "invariant — a rule that must hold on every run",
    "provenance — where a result came from"
  ]
});
