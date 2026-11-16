/* 11.4 — The degraded path calls the rule engine directly
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "11.4",
  "part": 11,
  "part_title": "The engine and the fallback",
  "title": "The degraded path calls the rule engine directly",
  "order": 1104,
  "duration_min": 25,
  "concept_md": "### ADR 0004's decision\n\nTwo functions can produce the rule engine's findings: `sarvam_provider.review_with_fallback(..., force_offline=True)` and `mock_provider.offline_diff_findings`. The adapter's degraded path calls the second directly, and `review_with_fallback` itself calls it too.\n\n### Why one implementation\n\nTwo call paths to the same findings means two places to keep honest, and one of them will eventually log a second warning or return a differently labelled outcome. Calling `offline_diff_findings` directly keeps exactly one mock implementation and exactly one WARNING per degraded run.\n\n### What `_mock_outcome` adds\n\nIt calls `review_with_fallback(bundle, None, ...)` — config `None` means no live attempt — and then replaces only the `reason`. The adapter can describe its own decision (\"no provider selected\"); the caller knows the more useful fact (\"offline mode requested\").\n\n### Why the reason is worth replacing\n\nBecause a reader of the log needs to know why this run was degraded. \"No provider selected\" is true for every degraded run; \"offline mode requested\" says the caller asked for it, which is a different diagnosis.\n\n### What the tests pin\n\nThat the relabel happens only when the reason differs, and that the findings are untouched. Both are checked by comparing two outcomes field by field — which is why a change to the reason text is a visible edit rather than a silent one.",
  "code_examples": [
    {
      "id": "11.4-ex-0",
      "lang": "console",
      "caption": "The relabel, and what the adapter would have said",
      "code": "python - <<'PY'\nimport inspect\nfrom app.engine import _mock_outcome\n\nsrc = inspect.getsource(_mock_outcome)\nfor line in src.splitlines():\n    s = line.strip()\n    if \"review_with_fallback\" in s or \"model_copy\" in s or s.startswith(\"return\"):\n        print(s[:70])\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "The findings come from :func:`app.openai_compat_provider.review_with_f\noutcome = review_with_fallback(\nreturn outcome.model_copy(update={\"reason\": reason})\nreturn outcome",
      "why_not": "the browser runner does not embed app/engine.py or the provider modules; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "Which function does the degraded path call?",
      "options": [
        "offline_diff_findings directly",
        "offline_diff_findings",
        "select_provider",
        "review()"
      ],
      "answer": 1,
      "why": "Calling it directly keeps one mock implementation and one WARNING per degraded run."
    },
    {
      "q": "What does _mock_outcome replace?",
      "options": [
        "The provider and the model",
        "The findings and the mode",
        "Only the reason",
        "The latency and the mode"
      ],
      "answer": 2,
      "why": "The adapter can describe its own decision; the caller knows the more useful one."
    },
    {
      "q": "Why is one mock implementation worth keeping?",
      "options": [
        "The tests require a single one",
        "It is fewer lines of code",
        "The adapter cannot import it",
        "Two paths drift apart"
      ],
      "answer": 3,
      "why": "Two paths to the same findings means two places to keep honest, and one will fall behind."
    }
  ],
  "try_it": {
    "prompt": "Show the config the relabel passes to the adapter.",
    "starter": "",
    "solution": "```console\n$ grep -n 'review_with_fallback(' -A 4 app/engine.py | head -8\n```",
    "explanation": "The second argument is None, which is how the adapter knows not to attempt a live call."
  },
  "exercise": {
    "prompt": "What reason does the adapter itself produce for a degraded run, and what does the caller replace it with?",
    "hint": "One is generic, one names the cause.",
    "solution": "```console\n$ grep -n 'offline mode requested\\|local rule engine used' app/engine.py\n```\n\nThe adapter says no provider was selected; the caller substitutes the specific cause, such as offline mode being requested.",
    "explanation": "The replacement is a diagnosis, not a decoration — it distinguishes a forced offline run from an unconfigured one."
  },
  "common_mistakes": [
    "Adding a second path to the rule engine's findings.",
    "Logging a warning in both the adapter and the caller.",
    "Keeping the adapter's generic reason when the caller knows the cause."
  ],
  "project_links": [
    {
      "label": "The relabel",
      "path": "app/engine.py",
      "lines": "284-316"
    },
    {
      "label": "The direct call it relies on",
      "path": "app/mock_provider.py",
      "lines": "59-75"
    }
  ],
  "learn_more": [
    {
      "label": "ADR 0004 — the direct call",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0004-degraded-path-calls-offline-findings-directly.md"
    },
    {
      "label": "app/mock_provider.py",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/mock_provider.py"
    }
  ],
  "glossary_terms": [
    "degraded path — the branch that runs without a model",
    "relabel — replace a generic reason with a specific one",
    "single implementation — one function that produces the findings"
  ]
});
