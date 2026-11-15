/* 9.3 — Secrets: three keys that must never be printed
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "9.3",
  "part": 9,
  "part_title": "Configuration and offline-first",
  "title": "Secrets: three keys that must never be printed",
  "order": 903,
  "duration_min": 25,
  "concept_md": "### Three keys, one rule\n\n`SARVAM_API_KEY`, `GITHUB_TOKEN` and `GITHUB_WEBHOOK_SECRET`. The rule is short: none of them appears in a log, a repr, an error message or a response.\n\n### `repr=False` is the mechanism\n\nEach secret field is declared with `repr=False`. That removes it from the object's representation, so `print(settings)` and a traceback showing the object cannot leak it. It is one word per field, and it is the difference between a careful codebase and one that leaks on the first exception.\n\n### Where the secret is used, and what is shown instead\n\nThe GitHub client takes the token, uses it in a header, and never puts it in a finding or a comment. The webhook secret is compared against a signature and the comparison result is a boolean. The Sarvam key goes into an HTTP header and nothing else.\n\n### What is not protected\n\nThe `.env` file itself. It is gitignored, but a key pasted into a shell history or a screenshot is outside anything this code can do. That is why `.env.example` ships with empty values and why the README says to prefer environment variables for a live key.",
  "code_examples": [
    {
      "id": "9.3-ex-0",
      "lang": "console",
      "caption": "A secret is absent from the representation",
      "code": "python - <<'PY'\nfrom app.config import Settings\n\ns = Settings(sarvam_api_key=\"sk-live-do-not-print\")\nprint(\"leaks in repr:\", \"sk-live\" in repr(s))\nprint(\"field is set:\", s.sarvam_api_key is not None)\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "leaks in repr: False\nfield is set: True",
      "why_not": "the browser runner does not embed app/config.py, and it needs pydantic-settings; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "What keeps a secret out of a traceback?",
      "options": [
        "`repr=False` on the field",
        "Encrypting it at rest",
        "Keeping it in a file only",
        "A validator that redacts"
      ],
      "answer": 0,
      "why": "The value is removed from the object's representation, so a printed object or a settings dump cannot show it."
    },
    {
      "q": "What does the webhook secret produce after comparison?",
      "options": [
        "A boolean result",
        "The signature, echoed",
        "A hash of both values",
        "The secret, asterisked"
      ],
      "answer": 0,
      "why": "The comparison result is what the caller needs; returning anything derived from the secret would widen the surface."
    },
    {
      "q": "Which secret is outside this code's protection?",
      "options": [
        "One pasted in a shell",
        "One in an env variable, never in a file",
        "One loaded from a .env",
        "One held in Settings"
      ],
      "answer": 0,
      "why": "Shell history, screenshots and chat logs are outside the program, which is why the example file ships empty."
    }
  ],
  "try_it": {
    "prompt": "Show that a set secret does not appear in the settings repr.",
    "starter": "",
    "solution": "```python\nfrom app.config import Settings\n\ns = Settings(github_token=\"ghp_secret_value\")\nprint(\"contains token:\", \"ghp_secret_value\" in repr(s))\n```",
    "explanation": "It prints `False`, which is the guarantee the field declaration buys."
  },
  "exercise": {
    "prompt": "Which three fields are declared with `repr=False`? Check rather than assume.",
    "hint": "Read the field metadata for each secret.",
    "solution": "```python\nfrom app.config import Settings\n\nfor name, f in Settings.model_fields.items():\n    if f.repr is False:\n        print(name)\n```",
    "explanation": "The list is the answer, derived from the class rather than from the documentation."
  },
  "common_mistakes": [
    "Logging a settings object that contains a secret without `repr=False`.",
    "Returning the webhook secret in an error message to help debugging.",
    "Committing a real key into `.env` because it is gitignored locally."
  ],
  "project_links": [
    {
      "label": "The Sarvam key field",
      "path": "app/config.py",
      "lines": "30-32"
    },
    {
      "label": "The GitHub token field",
      "path": "app/config.py",
      "lines": "34-36"
    },
    {
      "label": "The webhook secret field",
      "path": "app/config.py",
      "lines": "52-56"
    }
  ],
  "learn_more": [
    {
      "label": "app/config.py — the settings",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/config.py"
    },
    {
      "label": ".env.example — empty by design",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/.env.example"
    }
  ],
  "glossary_terms": [
    "secret — a value that must not appear in output",
    "repr — the text a printed object shows",
    "redaction — removing a value from what is shown"
  ]
});
