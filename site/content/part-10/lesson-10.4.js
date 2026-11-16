/* 10.4 — `provider_available`: an honest gate before a call
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "10.4",
  "part": 10,
  "part_title": "Providers and LLM APIs",
  "title": "`provider_available`: an honest gate before a call",
  "order": 1004,
  "duration_min": 20,
  "concept_md": "### Ask before calling\n\nEach provider exposes `provider_available`. For the local adapter it checks that a base URL is set; for Sarvam it checks the key and that the SDK is installed. The engine calls it before building a client.\n\n### Why a predicate rather than a try\n\nA call that fails because a key is missing produces an error from deep inside a library, and translating that into \"set SARVAM_API_KEY\" is guesswork. A predicate answers the question before anything is sent, so the reason a provider was skipped is known rather than inferred.\n\n### The two answers it gives the engine\n\nAvailable, so the engine builds a config and runs live. Not available, so the engine records why and degrades to mock. The reason string is user-facing and names the variable that is missing.\n\n### What it cannot check\n\nThat the model is loaded, that the key is valid, or that the server is awake. It answers \"is this configured\", not \"will this work\" — and the difference is why a live call can still fail after a passing check.",
  "code_examples": [
    {
      "id": "10.4-ex-0",
      "lang": "console",
      "caption": "The local gate, and what it does not check",
      "code": "python - <<'PY'\nfrom app.config import Settings\nfrom app.engine import config_for_local, config_for_sarvam\n\ns = Settings()\nprint(\"local config:\", config_for_local(s))\nprint(\"sarvam config:\", config_for_sarvam(s))\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "local config: None\nsarvam config: None",
      "why_not": "the browser runner does not embed app/config.py or the provider modules; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "What does the gate answer?",
      "options": [
        "Is this configured",
        "Will this call succeed",
        "Is the model loaded",
        "Is the key still valid"
      ],
      "answer": 0,
      "why": "It answers the configuration question, which is why a live call can still fail after it passes."
    },
    {
      "q": "Why a predicate rather than catching an error?",
      "options": [
        "The reason is known, not inferred",
        "It is faster than making the call",
        "It avoids importing the vendor SDK",
        "It removes the need for a key"
      ],
      "answer": 0,
      "why": "Reading a library's error and guessing which variable is missing is guesswork; asking first is not."
    },
    {
      "q": "What does the engine do when the gate says no?",
      "options": [
        "Records why and degrades",
        "Retries with a longer timeout",
        "Asks the other provider first",
        "Raises and stops the run"
      ],
      "answer": 0,
      "why": "The reason becomes the outcome's reason, so the degraded run explains itself."
    }
  ],
  "try_it": {
    "prompt": "Print both configs with nothing set.",
    "starter": "",
    "solution": "```python\nfrom app.config import Settings\nfrom app.engine import config_for_local, config_for_sarvam\n\ns = Settings()\nprint(config_for_local(s), config_for_sarvam(s))\n```",
    "explanation": "Both are None with an empty environment — the gate has nothing to offer, so the run degrades."
  },
  "exercise": {
    "prompt": "Set only the local base URL and print what changes.",
    "hint": "The engine builds a config from the settings it is given.",
    "solution": "```python\nfrom app.config import Settings\nfrom app.engine import config_for_local\n\nprint(config_for_local(Settings()))\nprint(config_for_local(Settings(lmstudio_base_url=\"http://localhost:1234/v1\")))\n```",
    "explanation": "The first is None and the second is a config, which is the gate switching on."
  },
  "common_mistakes": [
    "Treating a passing gate as proof the call will work.",
    "Catching a library error instead of asking whether the key exists.",
    "Degrading without recording the reason."
  ],
  "project_links": [
    {
      "label": "The local config builder",
      "path": "app/engine.py",
      "lines": "135-156"
    },
    {
      "label": "The Sarvam config builder",
      "path": "app/engine.py",
      "lines": "113-132"
    }
  ],
  "learn_more": [
    {
      "label": "app/engine.py — the selection",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/engine.py"
    },
    {
      "label": "app/config.py — the settings",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/config.py"
    }
  ],
  "glossary_terms": [
    "predicate — a function that answers yes or no",
    "gate — a check made before an expensive action",
    "degrade — fall back to a working path"
  ]
});
