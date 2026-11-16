/* 10.6 — Errors translated, not leaked
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "10.6",
  "part": 10,
  "part_title": "Providers and LLM APIs",
  "title": "Errors translated, not leaked",
  "order": 1006,
  "duration_min": 25,
  "concept_md": "### Three vocabularies, one error\n\nA refused connection, a 401 and a timeout arrive as different exception types from different libraries. `_translate_call_error` maps them onto the tool's own errors, so a caller handles one vocabulary.\n\n### Why translation matters\n\nWithout it, an API surface would have to catch `openai.AuthenticationError` and know what to do with it — a vendor name in a route handler. With it, the route catches the tool's error and the vendor stays in the adapter.\n\n### Scrubbing on the way out\n\n`_one_line` flattens a message to a single line, `_scrub` removes the configured key from it, and `_present` composes the two. Scrub with no config and nothing is removed — the key has to be passed in for the redaction to happen. An error is the most likely place for a secret to escape, because it quotes the request that failed.\n\n### What is deliberately kept\n\nThe model name and the endpoint label, so a reader can tell which provider failed. Redaction removes credentials, not identity — an error that cannot say which provider failed is not much use.\n\n### The three helpers, and the order they run in\n\n`_one_line` first, because a message with newlines breaks a log line and an HTTP header. `_scrub` second, because the key has to be present in the text to be removed. `_present` composes both, so a caller cannot apply one and forget the other.",
  "code_examples": [
    {
      "id": "10.6-ex-0",
      "lang": "console",
      "caption": "Scrubbing removes the key; flattening is a separate step",
      "code": "python - <<'PY'\nfrom app.openai_compat_provider import OpenAICompatConfig, _one_line, _scrub\n\ncfg = OpenAICompatConfig(base_url=\"http://x/v1\", api_key=\"sk-live-abc123\",\n                         model=\"m\", provider_name=\"local\", timeout=20.0)\nraw = \"AuthenticationError: bad key sk-live-abc123\\n  on line two\"\nprint(\"one line:\", _one_line(raw))\nprint(\"scrubbed:\", _scrub(raw, cfg))\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "one line: AuthenticationError: bad key sk-live-abc123 on line two\nscrubbed: AuthenticationError: bad key ***\n  on line two",
      "why_not": "the browser runner does not embed app/config.py or the provider modules; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "Why translate a library's error type?",
      "options": [
        "The HTTP status code can be dropped from it",
        "The error message becomes much shorter",
        "The retry count can be reset between calls",
        "The vendor name stays in the adapter"
      ],
      "answer": 3,
      "why": "Otherwise a route handler has to know the vendor, which is exactly the coupling the adapter exists to remove."
    },
    {
      "q": "What does scrubbing remove from a message?",
      "options": [
        "Key material and credentials",
        "The provider name and the model name",
        "The status code and the model name",
        "The line breaks and the model name"
      ],
      "answer": 0,
      "why": "An error quotes the failed request, which is the most likely place for a secret to escape."
    },
    {
      "q": "What is deliberately kept in an error?",
      "options": [
        "The key that was used for the call",
        "Which provider failed",
        "The full request body as it was sent",
        "The endpoint credentials and the key"
      ],
      "answer": 1,
      "why": "Redaction removes credentials, not identity: a reader still needs to know who failed."
    }
  ],
  "try_it": {
    "prompt": "Flatten a two-line error and show it is one line.",
    "starter": "",
    "solution": "```python\nfrom app.openai_compat_provider import _one_line\n\nmsg = \"first line\\nsecond line\\nthird\"\nprint(repr(_one_line(msg)))\n```",
    "explanation": "The newlines are gone, because a log line and an API message both need one line."
  },
  "exercise": {
    "prompt": "Which function flattens a message and which removes secrets?",
    "hint": "Two small helpers, both private.",
    "solution": "```python\nfrom app.openai_compat_provider import _one_line, _scrub\n\nprint(_one_line.__name__, _scrub.__name__)\n```\n\n`_one_line` flattens; `_scrub` removes credential material.",
    "explanation": "Two jobs, two functions, both applied before a message reaches a human."
  },
  "common_mistakes": [
    "Catching a vendor exception in a route handler.",
    "Logging an error message without scrubbing it.",
    "Redacting so much that the provider can no longer be identified."
  ],
  "project_links": [
    {
      "label": "Flattening a message",
      "path": "app/openai_compat_provider.py",
      "lines": "161-170"
    },
    {
      "label": "Scrubbing credential material",
      "path": "app/openai_compat_provider.py",
      "lines": "173-188"
    },
    {
      "label": "Translating a call error",
      "path": "app/openai_compat_provider.py",
      "lines": "337-359"
    }
  ],
  "learn_more": [
    {
      "label": "app/openai_compat_provider.py",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/openai_compat_provider.py"
    },
    {
      "label": "app/sarvam_provider.py",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/sarvam_provider.py"
    }
  ],
  "glossary_terms": [
    "translation — mapping a vendor error onto your own",
    "scrub — remove credential material from text",
    "one line — flatten a message for a log or a response"
  ]
});
