/* 10.2 — The mock provider: the rule engine, no network
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "10.2",
  "part": 10,
  "part_title": "Providers and LLM APIs",
  "title": "The mock provider: the rule engine, no network",
  "order": 1002,
  "duration_min": 20,
  "concept_md": "### The one provider that always works\n\n`app/mock_provider.py` is 75 lines. `offline_review` and `offline_diff_findings` run the rule engine over the diff and return a `ReviewResult` — mode, target, findings, notes. No socket, no key, no model. The `ProviderOutcome` that reaches a caller is assembled one level up, in `engine._mock_outcome`, so the mock never builds the wrapper itself.\n\n### Why it is not a stub\n\nA stub would return canned findings. This runs the real 63 rules over the real diff, so the findings a reader sees in mock mode are true findings about their code — they are just not model-assisted. That is why variant A of the demo is the one that is exercised: it produces a real review with no external dependency.\n\n### What mock mode is for\n\nThree things. It lets the tool start on a machine with nothing configured, which is the offline-first promise. It makes the test suite runnable without a network. And it gives the live providers something to be compared against, which is the benchmark that has not been run.\n\n### The label\n\n`mode=\"mock\"` and a `reason` naming why the fallback happened — no key, no local endpoint, or a forced offline run. A caller that ignores the label gets a true review with an honest provenance it did not read.",
  "code_examples": [
    {
      "id": "10.2-ex-0",
      "lang": "console",
      "caption": "Mock mode is a real review, labelled",
      "code": "python - <<'PY'\nimport inspect\nfrom app import mock_provider\n\nprint(\"public:\", [n for n in dir(mock_provider) if not n.startswith(\"_\") and n not in (\"pydantic\",)][:4])\nprint(\"source lines:\", len(inspect.getsource(mock_provider).splitlines()))\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "public: ['DiffBundle', 'ENGINE_NOTE', 'Finding', 'Path']\nsource lines: 75",
      "why_not": "the browser runner does not embed app/config.py or the provider modules; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "What makes the mock provider more than a stub?",
      "options": [
        "It calls a tiny local model",
        "It returns canned findings",
        "It caches a previous run",
        "It runs the real rules"
      ],
      "answer": 3,
      "why": "The findings are true findings about the diff; what is absent is the model, not the analysis."
    },
    {
      "q": "Which promise does mock mode keep?",
      "options": [
        "The tool starts unconfigured",
        "The model runs faster",
        "The key stays in memory",
        "The model runs measurably faster"
      ],
      "answer": 0,
      "why": "Offline-first means a fresh checkout produces a real review with nothing set up."
    },
    {
      "q": "What does a mock outcome still carry?",
      "options": [
        "A key and a model name",
        "A mode and a reason",
        "A retry count and a key",
        "A cache id and a mode"
      ],
      "answer": 1,
      "why": "The label is what keeps a degraded run honest when the caller reads it."
    }
  ],
  "try_it": {
    "prompt": "Print how the mock provider is selected when nothing is configured.",
    "starter": "",
    "solution": "```python\nfrom app.config import Settings\nfrom app.engine import select_provider\n\ns = Settings()\nprint(select_provider(s).provider, \"|\", select_provider(s).reason)\n```",
    "explanation": "With nothing set, the selection is mock and the reason names what is missing."
  },
  "exercise": {
    "prompt": "How many lines is the mock provider, and how many rules does it run?",
    "hint": "One number is the file, the other is the registry.",
    "solution": "```python\nimport inspect\nfrom app import mock_provider\nfrom app.rules import RULE_COUNT\n\nprint(len(inspect.getsource(mock_provider).splitlines()), RULE_COUNT)\n```",
    "explanation": "A short file that delegates to the rule registry — the size is the point, not the rule count."
  },
  "common_mistakes": [
    "Treating mock findings as fake; they are real findings about the diff.",
    "Ignoring the mode and reporting a mock run as a live one.",
    "Assuming mock mode needs a key or a model."
  ],
  "project_links": [
    {
      "label": "The mock provider",
      "path": "app/mock_provider.py",
      "lines": "1-75"
    }
  ],
  "learn_more": [
    {
      "label": "app/mock_provider.py",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/mock_provider.py"
    },
    {
      "label": "DEMO.md — variant A",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/DEMO.md"
    }
  ],
  "glossary_terms": [
    "mock — a provider that runs the rules with no model",
    "fallback — a degraded path taken when a provider is absent",
    "offline-first — working with nothing configured"
  ]
});
