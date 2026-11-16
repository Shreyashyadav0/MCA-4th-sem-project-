/* 11.2 — review(): the single entry point
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "11.2",
  "part": 11,
  "part_title": "The engine and the fallback",
  "title": "review(): the single entry point",
  "order": 1102,
  "duration_min": 25,
  "concept_md": "### One signature, four knobs\n\n```python\ndef review(bundle, settings, *, provider=\"auto\",\n           force_offline=False, min_severity=None, categories=None) -> ProviderOutcome\n```\n\nA parsed diff, the settings, and four things a caller may narrow: which provider is asked for, whether a live call is forbidden, a severity floor, and a category filter.\n\n### The order the branches run in\n\n`force_offline` is checked first and wins outright — a caller that forbids the network does not get a live call even with a valid key. Then an unknown provider name degrades with a reason rather than raising. Then a mock selection or a missing config degrades. Only then does the live call happen.\n\n### Why that order matters\n\nBecause each branch is a promise. Forbidding the network is the strongest, so nothing overrides it. An unknown name is a programming error that still must produce a review, so it degrades. Everything else is a configuration fact.\n\n### What a caller gets back\n\nOne `ProviderOutcome` with `mode`, `provider`, `model`, the findings, a `reason` and `latency_ms`. There is no exception path for a missing key, which is ADR 0002's point: absence is data.\n\n### What a caller should never do\n\nBuild a second entry point. A surface that calls the adapter itself skips the selection, the offline flag and the relabel — and the run it produces will still look like an outcome, so nothing will complain until a demo reports a live review that never happened.",
  "code_examples": [
    {
      "id": "11.2-ex-0",
      "lang": "console",
      "caption": "The branch order, read from the source",
      "code": "python - <<'PY'\nimport inspect\nfrom app.engine import review\n\nsrc = inspect.getsource(review)\nfor line in src.splitlines():\n    s = line.strip()\n    if s.startswith((\"if \", \"return \")) and \"(\" in s:\n        print(s[:64])\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "return _mock_outcome(\nreturn _mock_outcome(\nreturn review_with_fallback(",
      "why_not": "the browser runner does not embed app/engine.py or the provider modules; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "Which branch wins outright?",
      "options": [
        "categories",
        "provider=\"auto\"",
        "min_severity",
        "force_offline"
      ],
      "answer": 3,
      "why": "A caller that forbids the network gets no live call, even with a valid key."
    },
    {
      "q": "What does an unknown provider name do?",
      "options": [
        "Degrades with a reason",
        "Raises ValueError to the caller",
        "Falls through to Sarvam",
        "Retries with auto"
      ],
      "answer": 0,
      "why": "A request must still get a review, so a programming error degrades rather than failing the run."
    },
    {
      "q": "How does a missing key reach the caller?",
      "options": [
        "As an exception from the SDK",
        "As a reason on the outcome",
        "As a 500 from the route",
        "As an empty findings list"
      ],
      "answer": 1,
      "why": "Absence is data: the outcome says mock and explains which variable was missing."
    }
  ],
  "try_it": {
    "prompt": "Print review()'s signature.",
    "starter": "",
    "solution": "```console\n$ python -c \"import inspect, app.engine; print(inspect.signature(app.engine.review))\"\n```",
    "explanation": "Four keyword-only knobs after the diff and the settings."
  },
  "exercise": {
    "prompt": "With a valid key set but force_offline=True, which provider runs?",
    "hint": "The first branch decides.",
    "solution": "```console\n$ python -c \"from app.config import Settings; from app.engine import select_provider; print(select_provider(Settings(sarvam_api_key='x')).provider)\"\n```\n\nSelection says sarvam, but `review(..., force_offline=True)` returns mock regardless — the flag is checked before the selection is used.",
    "explanation": "Two decisions, two places: the selector answers which provider, and force_offline overrules it."
  },
  "common_mistakes": [
    "Expecting force_offline to be a provider name; it is a flag.",
    "Raising for a missing key instead of degrading.",
    "Reading the selection as the final answer without the offline flag."
  ],
  "project_links": [
    {
      "label": "The single entry point",
      "path": "app/engine.py",
      "lines": "320-387"
    }
  ],
  "learn_more": [
    {
      "label": "app/engine.py — review()",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/engine.py"
    },
    {
      "label": "ADR 0002 — absence is data",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0002-offline-first-fallback.md"
    }
  ],
  "glossary_terms": [
    "entry point — the one function every surface calls",
    "forced offline — a flag that forbids a live call",
    "knob — a keyword argument that narrows a run"
  ]
});
