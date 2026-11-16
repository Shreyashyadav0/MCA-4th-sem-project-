/* 11.3 — Absence as data: what config_for_* actually checks
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "11.3",
  "part": 11,
  "part_title": "The engine and the fallback",
  "title": "Absence as data: what config_for_* actually checks",
  "order": 1103,
  "duration_min": 25,
  "concept_md": "### Two builders, two different tests\n\n`config_for_sarvam` returns a config only when `SARVAM_API_KEY` is non-blank. `config_for_local` returns one only when `LMSTUDIO_BASE_URL` is non-blank **and** `LMSTUDIO_API_KEY` is non-blank.\n\n### Why the local check looks redundant\n\nBecause `LMSTUDIO_API_KEY` defaults to the placeholder `lm-studio`, so in practice the base URL decides. The key check is still there — a caller who blanks it deliberately gets no local config, which is the escape hatch.\n\n### What \"absence is data\" means here\n\nA missing variable is not an error to raise; it is the input that decides the mode. `Settings` defaults every field, so the builders are reading presence, not existence. That is why a fresh checkout produces a review rather than a traceback.\n\n### What the builders do not check\n\nThat the key is valid, that the server is awake, or that the SDK is installed. `sarvam_provider.provider_available` checks the SDK, and the selector does not call it — so a key with no SDK still selects sarvam and fails at call time, as lesson 10.4 records.\n\n### Why the check is written even when it looks redundant\n\nA default that satisfies a check is not the same as a check that is unnecessary. Blanking `LMSTUDIO_API_KEY` is how a caller says \"do not use the local server even though a URL is set\", and the builder honours that because the test is on the value, not on whether it was provided.",
  "code_examples": [
    {
      "id": "11.3-ex-0",
      "lang": "console",
      "caption": "Both builders, with nothing and then with a value",
      "code": "python - <<'PY'\nfrom app.config import Settings\nfrom app.engine import config_for_local, config_for_sarvam\n\nprint(\"empty   :\", config_for_local(Settings()), config_for_sarvam(Settings()))\nprint(\"local   :\", bool(config_for_local(Settings(lmstudio_base_url=\"http://x/v1\"))))\nprint(\"sarvam  :\", bool(config_for_sarvam(Settings(sarvam_api_key=\"k\"))))\nprint(\"key blank:\", config_for_local(Settings(lmstudio_base_url=\"http://x/v1\", lmstudio_api_key=\"\")))\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "empty   : None None\nlocal   : True\nsarvam  : True\nkey blank: None",
      "why_not": "the browser runner does not embed app/engine.py or the provider modules; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "What does config_for_sarvam test?",
      "options": [
        "A non-blank key",
        "A base URL",
        "An installed SDK",
        "A loaded model"
      ],
      "answer": 0,
      "why": "Only the key; the SDK is checked by provider_available, which the selector never calls."
    },
    {
      "q": "Why does the local key check look redundant?",
      "options": [
        "The SDK supplies a key of its own",
        "The key defaults to a placeholder",
        "Settings has no key field at all",
        "The base URL implies a key"
      ],
      "answer": 1,
      "why": "LMSTUDIO_API_KEY defaults to lm-studio, so in practice the base URL decides."
    },
    {
      "q": "What does a missing variable become?",
      "options": [
        "A 500 from the route",
        "An error logged and then retried",
        "The input that picks the mode",
        "A warning and a retry"
      ],
      "answer": 2,
      "why": "Absence is data: the builders read presence, and every field has a default."
    }
  ],
  "try_it": {
    "prompt": "Show that blanking the local key removes the config.",
    "starter": "",
    "solution": "```console\n$ python -c \"from app.config import Settings; from app.engine import config_for_local; print(config_for_local(Settings(lmstudio_base_url='http://x/v1', lmstudio_api_key='')))\"\n```",
    "explanation": "None — the key check is real, even though the default makes it rarely visible."
  },
  "exercise": {
    "prompt": "Which two settings does config_for_local require, and which one has a default?",
    "hint": "Read the function rather than the settings class.",
    "solution": "```console\n$ sed -n '135,158p' app/engine.py\n```\n\nA base URL and a non-blank key; the key defaults to `lm-studio`, so only the URL is usually set by hand.",
    "explanation": "A defaulted field still participates in the check — which is why blanking it is a deliberate act."
  },
  "common_mistakes": [
    "Saying the local builder checks only the URL; it checks the key too.",
    "Assuming a selected provider implies a working SDK.",
    "Treating a missing variable as an error rather than a mode."
  ],
  "project_links": [
    {
      "label": "The Sarvam builder",
      "path": "app/engine.py",
      "lines": "113-132"
    },
    {
      "label": "The local builder",
      "path": "app/engine.py",
      "lines": "135-156"
    }
  ],
  "learn_more": [
    {
      "label": "app/engine.py — the builders",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/engine.py"
    },
    {
      "label": "app/config.py — the defaults",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/config.py"
    }
  ],
  "glossary_terms": [
    "presence — whether a value is non-blank",
    "builder — the function that turns settings into a config",
    "placeholder — a default value that satisfies a check"
  ]
});
