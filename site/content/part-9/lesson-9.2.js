/* 9.2 — The LMSTUDIO_* variables and what each changes
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "9.2",
  "part": 9,
  "part_title": "Configuration and offline-first",
  "title": "The LMSTUDIO_* variables and what each changes",
  "order": 902,
  "duration_min": 20,
  "concept_md": "### Four variables, one local server\n\n`LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL`, `LMSTUDIO_API_KEY` and `LMSTUDIO_TIMEOUT` describe a chat-completions server on your own machine. LM Studio speaks the OpenAI-compatible protocol, so the adapter that talks to a hosted endpoint talks to it.\n\n### What each one does\n\n`LMSTUDIO_BASE_URL` is the address, typically `http://localhost:1234/v1`. It is optional: when empty, the local provider is not selected. `LMSTUDIO_MODEL` names the model the server should load. `LMSTUDIO_API_KEY` is usually a placeholder, because a local server does not authenticate — but the field exists so the adapter has one shape. `LMSTUDIO_TIMEOUT` bounds the request and is larger than the hosted default, because a laptop model is slower.\n\n### Absence is a mode, not an error\n\nAn empty `LMSTUDIO_BASE_URL` does not raise. The selector sees no local endpoint and moves on, which is what lets the tool start on a machine that never installed a model.\n\n### The trap\n\nSetting the URL and forgetting the model gives a request the server rejects. Both are needed for a local run; the URL alone is not a configuration.",
  "code_examples": [
    {
      "id": "9.2-ex-0",
      "lang": "console",
      "caption": "The four fields and their defaults",
      "code": "python - <<'PY'\nfrom app.config import Settings\n\nfor name in (\"lmstudio_base_url\", \"lmstudio_model\", \"lmstudio_api_key\", \"lmstudio_timeout\"):\n    f = Settings.model_fields[name]\n    print(\"%-20s %r\" % (name, f.default))\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "lmstudio_base_url    None\nlmstudio_model       'qwen2.5-coder-7b-instruct'\nlmstudio_api_key     'lm-studio'\nlmstudio_timeout     120.0",
      "why_not": "the browser runner does not embed app/config.py, and it needs pydantic-settings; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "What happens when `LMSTUDIO_BASE_URL` is empty?",
      "options": [
        "Local is simply not selected",
        "The application will not start",
        "The Sarvam key is used instead",
        "The timeout falls back to zero"
      ],
      "answer": 0,
      "why": "Absence is a mode: the selector sees no endpoint and moves on, which keeps a fresh checkout startable."
    },
    {
      "q": "Why does a local server still have an API-key field?",
      "options": [
        "So the adapter has one shape",
        "Because LM Studio requires auth",
        "So the key can be rotated",
        "Because Pydantic demands a secret"
      ],
      "answer": 0,
      "why": "A local server does not authenticate, but keeping the field means the adapter needs no special case."
    },
    {
      "q": "What is missing if the URL is set but the model is not?",
      "options": [
        "The model name to load",
        "The port to listen on",
        "The key the server wants",
        "The timeout for the call"
      ],
      "answer": 0,
      "why": "The server needs to know which model to run; the URL alone is not a configuration."
    }
  ],
  "try_it": {
    "prompt": "Print the local timeout and compare it with the hosted one.",
    "starter": "",
    "solution": "```python\nfrom app.config import Settings\n\nprint(\"local :\", Settings.model_fields[\"lmstudio_timeout\"].default)\nprint(\"hosted:\", Settings.model_fields[\"request_timeout_s\"].default)\n```",
    "explanation": "The local timeout is larger, because a model on a laptop is slower than a hosted endpoint."
  },
  "exercise": {
    "prompt": "Which two LMSTUDIO fields must both be set for a local run to work?",
    "hint": "One is the address, one names the model.",
    "solution": "```text\nLMSTUDIO_BASE_URL and LMSTUDIO_MODEL.\n\nThe URL alone leaves the server without a model to load; the model alone leaves\nthe adapter without an address to call.\n```",
    "explanation": "Both are needed, and neither is required for the tool to start — that is the difference between a mode and an error."
  },
  "common_mistakes": [
    "Setting the base URL and forgetting the model name.",
    "Expecting an empty base URL to raise; it is a mode switch.",
    "Assuming a local server needs a real API key."
  ],
  "project_links": [
    {
      "label": "The four local fields",
      "path": "app/config.py",
      "lines": "62-82"
    }
  ],
  "learn_more": [
    {
      "label": "app/config.py — the settings",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/config.py"
    },
    {
      "label": "docker-compose.yml — the local passthrough",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docker-compose.yml"
    }
  ],
  "glossary_terms": [
    "lm studio — a local server speaking the OpenAI protocol",
    "base url — the address the adapter calls",
    "model id — the name the server loads"
  ]
});
