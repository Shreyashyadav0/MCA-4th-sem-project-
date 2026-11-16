/* 10.7 — Sarvam: a second adapter, and it is unexercised
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "10.7",
  "part": 10,
  "part_title": "Providers and LLM APIs",
  "title": "Sarvam: the contract module, and why it is unexercised",
  "order": 1007,
  "duration_min": 20,
  "concept_md": "### What exists\n\n`app/sarvam_provider.py` is 993 lines. It defines the wire contract (`LLMFinding`), the outcome (`ProviderOutcome`), the prompt builder and its own availability check. It also holds a `review_with_fallback` — and the engine does not call it. Both live providers run through the OpenAI-compatible adapter instead, so this module is the contract, not a second transport.\n\n### What has been run\n\nThe code has been tested against stubs and a scripted fake client with the real exception classes. It has **never** had a real key or a real model behind it in this repository, and `DEMO.md` says so in its table.\n\n### Why the honesty matters\n\nAn adapter that has never made a real call is a claim about an API's behaviour made from its documentation. The shape of the answer, the error types and the retry policy are all written to a spec that has not been exercised. A reader who is told that can judge the risk; a reader who is not will assume a green test suite means a working integration.\n\n### What a reader should conclude\n\nThat variant C of the demo runs the adapter labelled `sarvam`, that it is unexercised, that no capture of a Sarvam review exists, and that adding a key is the step which would turn this from a spec-faithful adapter into a verified one — and the first thing that step would produce is a bug report, not a confirmation.",
  "code_examples": [
    {
      "id": "10.7-ex-0",
      "lang": "console",
      "caption": "The availability check, with no key set",
      "code": "python - <<'PY'\nfrom app.config import Settings\nfrom app.sarvam_provider import provider_available\n\nprint(\"with no key:\", provider_available(Settings()))\nprint(\"sdk installed:\", __import__(\"app.sarvam_provider\", fromlist=[\"x\"])._sdk_available())\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "with no key: False\nsdk installed: True",
      "why_not": "the browser runner does not embed app/config.py or the provider modules; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "What has the Sarvam adapter been run against?",
      "options": [
        "Stubs and a scripted client",
        "A real key and a real model",
        "A hosted sandbox and a key",
        "Nothing at all, not even a stub"
      ],
      "answer": 0,
      "why": "The tests use the real exception classes against fakes, which is not the same as a live call."
    },
    {
      "q": "What does a green suite mean for this adapter?",
      "options": [
        "It works against the live API today",
        "It matches the documented spec",
        "Its key is known to be valid",
        "Its model is known to answer"
      ],
      "answer": 1,
      "why": "The tests establish fidelity to a written spec, not behaviour of a service nobody has called."
    },
    {
      "q": "What would a real key produce first?",
      "options": [
        "A benchmark figure at last",
        "A clean pass on the very first try",
        "A bug report, not a confirmation",
        "A new provider selection"
      ],
      "answer": 2,
      "why": "An unexercised integration usually disagrees with its spec somewhere, and that disagreement is the finding."
    }
  ],
  "try_it": {
    "prompt": "Show that the Sarvam gate is closed with no key.",
    "starter": "",
    "solution": "```python\nfrom app.config import Settings\nfrom app.sarvam_provider import provider_available\n\nprint(provider_available(Settings()))\nprint(provider_available(Settings(sarvam_api_key=\"x\")))\n```",
    "explanation": "The first is False; the second depends on whether the SDK is installed, which is the other half of the gate."
  },
  "exercise": {
    "prompt": "Which two things must hold for the Sarvam gate to open?",
    "hint": "One is a value, one is a package.",
    "solution": "```python\nimport inspect\nfrom app import sarvam_provider\n\nprint(inspect.getsource(sarvam_provider.provider_available))\n```\n\nA key must be set and the SDK must be importable.",
    "explanation": "Both halves are checked, because a key without the SDK cannot make a call either."
  },
  "common_mistakes": [
    "Reading a green suite as proof the integration works.",
    "Assuming a documented API and an exercised API behave alike.",
    "Adding a key and expecting a confirmation rather than a discrepancy."
  ],
  "project_links": [
    {
      "label": "The Sarvam gate",
      "path": "app/sarvam_provider.py",
      "lines": "188-198"
    },
    {
      "label": "The SDK availability check",
      "path": "app/sarvam_provider.py",
      "lines": "169-185"
    }
  ],
  "learn_more": [
    {
      "label": "app/sarvam_provider.py",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/sarvam_provider.py"
    },
    {
      "label": "DEMO.md — variant C is unexercised",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/DEMO.md"
    }
  ],
  "glossary_terms": [
    "unexercised — written to a spec, never run against the service",
    "stub — a fake that answers the way a spec says",
    "sdk — the vendor's client library"
  ]
});
