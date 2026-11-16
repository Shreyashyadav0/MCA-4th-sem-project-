/* 10.3 — One OpenAI-compatible adapter, many endpoints
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "10.3",
  "part": 10,
  "part_title": "Providers and LLM APIs",
  "title": "One OpenAI-compatible adapter, many endpoints",
  "order": 1003,
  "duration_min": 25,
  "concept_md": "### One protocol, several servers\n\n`app/openai_compat_provider.py` speaks the OpenAI chat-completions protocol. LM Studio implements it locally; so do many hosted services. The adapter does not know which one it is talking to — it knows an address, a model id and a key.\n\n### The config object\n\n`OpenAICompatConfig` carries what one call needs: the base URL, the model, the key and the timeout. The engine builds it from `Settings` for the local endpoint or for Sarvam, and the adapter takes it as an argument.\n\n### Why this is the interesting design\n\nA second hosted provider would be a new config, not a new adapter. The protocol is the seam, so the work of adding a provider is the work of describing its endpoint — and the code that parses the model's answer is written once.\n\n### What the adapter does not abstract\n\nDifferent servers fail differently. A local server that is not running refuses the connection; a hosted one returns 401 for a bad key. The adapter translates both into one error vocabulary rather than pretending they are the same, which is lesson 10.6.\n\n### What a second endpoint costs\n\nAdding one is a config object and a name. The parsing of the model's answer, the scrubbing of its errors and the normalisation of its severity are written once, so a new endpoint inherits behaviour that has already been tested rather than starting from a blank parser.",
  "code_examples": [
    {
      "id": "10.3-ex-0",
      "lang": "console",
      "caption": "The config a single call needs",
      "code": "python - <<'PY'\nfrom app.openai_compat_provider import OpenAICompatConfig\n\nimport dataclasses\n\nprint(\"fields:\", [f.name for f in dataclasses.fields(OpenAICompatConfig)])\nprint(\"provider names:\", __import__(\"app.openai_compat_provider\", fromlist=[\"x\"]).PROVIDER_LOCAL, __import__(\"app.openai_compat_provider\", fromlist=[\"x\"]).PROVIDER_SARVAM)\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "fields: ['base_url', 'api_key', 'model', 'provider_name', 'timeout']\nprovider names: local sarvam",
      "why_not": "the browser runner does not embed app/config.py or the provider modules; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "What would a second hosted provider need?",
      "options": [
        "A new endpoint config",
        "A new answer parser",
        "A new outcome model",
        "A new engine entry point"
      ],
      "answer": 0,
      "why": "The protocol is the seam, so describing an endpoint is the work, not writing another adapter."
    },
    {
      "q": "What does the adapter know about its server?",
      "options": [
        "Its vendor and its error codes",
        "Only address, model and key",
        "Its version and its retry policy",
        "Its model list and its limits"
      ],
      "answer": 1,
      "why": "The same code talks to a laptop server and a hosted one because it knows nothing vendor-specific."
    },
    {
      "q": "What does the adapter refuse to hide?",
      "options": [
        "That keys expire eventually soon",
        "That models answer differently",
        "That servers fail differently",
        "That timeouts vary by server type"
      ],
      "answer": 2,
      "why": "A refused connection and a 401 are translated into one vocabulary rather than flattened into one error."
    }
  ],
  "try_it": {
    "prompt": "Print the two provider names the adapter serves.",
    "starter": "",
    "solution": "```python\nfrom app.openai_compat_provider import PROVIDER_LOCAL, PROVIDER_SARVAM\n\nprint(PROVIDER_LOCAL, PROVIDER_SARVAM)\n```",
    "explanation": "Two names, one adapter: local for LM Studio and sarvam for the hosted endpoint."
  },
  "exercise": {
    "prompt": "Which four things does one call need, and which of them is optional for a local server?",
    "hint": "One of the four is a placeholder locally.",
    "solution": "```python\nimport dataclasses\nfrom app.openai_compat_provider import OpenAICompatConfig\n\nprint([f.name for f in dataclasses.fields(OpenAICompatConfig)])\n```\n\nThe key is the optional one locally: a laptop server does not authenticate.",
    "explanation": "The key stays in the config so the adapter has one shape, even where it is not checked."
  },
  "common_mistakes": [
    "Writing a second adapter for a server that speaks the same protocol.",
    "Baking a vendor name into the parsing code.",
    "Assuming a local server needs a real key."
  ],
  "project_links": [
    {
      "label": "The provider names",
      "path": "app/openai_compat_provider.py",
      "lines": "76-121"
    },
    {
      "label": "The config one call needs",
      "path": "app/openai_compat_provider.py",
      "lines": "124-142"
    }
  ],
  "learn_more": [
    {
      "label": "app/openai_compat_provider.py",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/openai_compat_provider.py"
    },
    {
      "label": "docs/decisions/0003-provider-agnostic-openai-compat.md",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0003-provider-agnostic-openai-compat.md"
    }
  ],
  "glossary_terms": [
    "adapter — code that speaks one protocol to many servers",
    "openai-compatible — the chat-completions protocol",
    "endpoint config — the address, model, key and timeout"
  ]
});
