/* 10.1 — The provider contract: one shape, three implementations
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "10.1",
  "part": 10,
  "part_title": "Providers and LLM APIs",
  "title": "The provider contract: one shape, three implementations",
  "order": 1001,
  "duration_min": 25,
  "concept_md": "### What a provider must return\n\nEvery provider returns a `ProviderOutcome`:\n\n```python\nclass ProviderOutcome(BaseModel):\n    mode: Literal[\"live\", \"mock\"]\n    provider: str\n    model: str\n    findings: list[Finding]\n    reason: str = \"\"\n    latency_ms: float = 0.0\n```\n\n`mode` is the honest label. A caller reading an outcome can never mistake a degraded run for a live one, because the field says which it was.\n\n### Why the shape is fixed\n\nThe CLI, the API and the JSON output all read the same object. If a provider could return its own shape, each surface would need its own translation, and one of them would eventually drop `reason` and report a mock run as a live one.\n\n### What the model is asked for\n\n`LLMFinding` is the wire contract: five fields, `extra=\"forbid\"`, and `line` typed `str | int` because models answer `42` and `\"42\"` interchangeably. A `field_validator` upper-cases the severity before validation, so `\"high\"` is accepted and `\"urgent\"` is still rejected.\n\n### Two paths, one adapter\n\n`app/mock_provider.py` runs the rule engine with no network. Both live providers — `local` and `sarvam` — go through the single `app/openai_compat_provider.py` adapter, because Sarvam speaks the same protocol. The engine's docstring says so: this module owns no transport.\n\n`app/sarvam_provider.py` supplies the contract itself — `LLMFinding`, `ProviderOutcome`, the prompt builder — and holds a `review_with_fallback` the engine deliberately does not call, so there is exactly one mock implementation.",
  "code_examples": [
    {
      "id": "10.1-ex-0",
      "lang": "console",
      "caption": "The outcome's fields, and the two modes",
      "code": "python - <<'PY'\nfrom app.sarvam_provider import LLMFinding, ProviderOutcome\n\nprint(\"outcome:\", list(ProviderOutcome.model_fields))\nprint(\"wire:\", list(LLMFinding.model_fields))\nf = LLMFinding(file=\"a.py\", line=\"42\", severity=\"high\", issue=\"x\", suggested_fix=\"y\")\nprint(\"line kept as text:\", repr(f.line), \"| severity:\", f.severity.value)\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "outcome: ['mode', 'provider', 'model', 'findings', 'reason', 'latency_ms']\nwire: ['file', 'line', 'severity', 'issue', 'suggested_fix']\nline kept as text: '42' | severity: HIGH",
      "why_not": "the browser runner does not embed app/config.py or the provider modules; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "Which field stops a caller mistaking a fallback for a live run?",
      "options": [
        "`findings` on the outcome",
        "`mode` on the outcome",
        "`mode` on the outcome",
        "`latency_ms` on the outcome"
      ],
      "answer": 1,
      "why": "It is a literal of live or mock, so a degraded run is labelled rather than inferred from a missing field."
    },
    {
      "q": "Why is `LLMFinding.line` typed `str | int`?",
      "options": [
        "The line can be a range of lines",
        "JSON has no integer type in the spec",
        "Models answer 42 and \"42\" alike",
        "Pydantic cannot coerce to an int"
      ],
      "answer": 2,
      "why": "Both spellings are normalised to the `Finding` contract later, so the wire type has to accept either."
    },
    {
      "q": "What does a provider return to its caller?",
      "options": [
        "A tuple of mode and findings",
        "A list of findings alone",
        "A dict keyed by provider",
        "One `ProviderOutcome`"
      ],
      "answer": 3,
      "why": "One object with one shape, so no surface needs its own translation and none can drop the mode."
    }
  ],
  "try_it": {
    "prompt": "Print the two modes and the default reason.",
    "starter": "",
    "solution": "```python\nfrom app.sarvam_provider import ProviderOutcome\n\nfor name in (\"mode\", \"reason\", \"latency_ms\"):\n    print(name, ProviderOutcome.model_fields[name].annotation)\n```",
    "explanation": "The literal admits exactly two modes, and the reason defaults to an empty string."
  },
  "exercise": {
    "prompt": "Which field of `LLMFinding` accepts two Python types, and why does that not weaken the contract?",
    "hint": "Look at the annotation and the validator that follows it.",
    "solution": "```python\nfrom app.sarvam_provider import LLMFinding\n\nprint(LLMFinding.model_fields[\"line\"].annotation)\n```\n\n`str | int`: both are accepted on the wire and normalised into the one `Finding` contract afterwards.",
    "explanation": "A lenient wire type with a strict normalisation step is not a weaker contract; it is the same contract with a tolerant reader."
  },
  "common_mistakes": [
    "Returning a bare list of findings from a provider, losing the mode.",
    "Inferring live-vs-mock from an empty reason instead of reading `mode`.",
    "Loosening the severity field instead of normalising its case."
  ],
  "project_links": [
    {
      "label": "The outcome every provider returns",
      "path": "app/sarvam_provider.py",
      "lines": "102-166"
    },
    {
      "label": "The wire contract",
      "path": "app/sarvam_provider.py",
      "lines": "72-99"
    }
  ],
  "learn_more": [
    {
      "label": "app/sarvam_provider.py — the contract",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/sarvam_provider.py"
    },
    {
      "label": "DEMO.md — the three variants",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/DEMO.md"
    }
  ],
  "glossary_terms": [
    "provider — the thing that produces a review outcome",
    "outcome — the labelled result of one review attempt",
    "wire contract — the shape a model is asked to return"
  ]
});
