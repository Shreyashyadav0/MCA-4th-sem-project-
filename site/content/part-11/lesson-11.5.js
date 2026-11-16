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
  "concept_md": "### The count is the design\n\nA degraded run logs exactly one WARNING. Not one per finding, not one per provider tried, and not silence.\n\n### Why exactly one\n\nA warning per finding buries the signal: a 40-finding review would produce 40 lines saying the same thing. Silence is worse, because a degraded run would then be indistinguishable from a clean one in the log. One line is what a person reads.\n\n### Where it is written\n\nOnce, at the point the decision to degrade is made. That is why the CLI, the API and the JSON output all explain a fallback identically — none of them formats the reason; they print what the engine recorded.\n\n### What the outcome carries\n\nThe same sentence, on `ProviderOutcome.reason`, with `mode=\"mock\"`. A caller that reads neither the log nor the outcome gets a real review with an honest provenance it chose not to look at — which is the failure mode this design cannot prevent, only make visible.\n\n### Why it is a WARNING and not an INFO\n\nBecause a degraded run is not the normal case for a configured deployment. The level says \"this worked, but not the way it was meant to\", which is exactly the distinction a reader of the log needs at three in the morning.",
  "code_examples": [
    {
      "id": "11.5-ex-0",
      "lang": "console",
      "caption": "Where the single warning is described",
      "code": "python - <<'PY'\nimport pathlib\n\nsrc = pathlib.Path(\"app/engine.py\").read_text()\nfor n, line in enumerate(src.splitlines(), 1):\n    if \"WARNING\" in line:\n        print(n, line.strip()[:64])\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "25 one mock implementation while logging exactly one WARNING per de\n295 WARNING. Only the ``reason`` is replaced: the adapter can only d\n332 decision, the honest labels and the single degraded-run WARNING ",
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
        "ProviderOutcome.reason, the same text"
      ],
      "answer": 0,
      "why": "Both surfaces say the same thing, so a caller reading the result is not misled."
    }
  ],
  "try_it": {
    "prompt": "Find every mention of WARNING in the engine.",
    "starter": "",
    "solution": "```console\n$ grep -n WARNING app/engine.py\n```",
    "explanation": "The mentions are in the docstrings that state the rule, which is where the invariant is written down."
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
