/* 12.3 — The API: fourteen routes over twelve paths
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "12.3",
  "part": 12,
  "part_title": "Surfaces: CLI, API, webhook, GitHub",
  "title": "The API: fourteen routes over twelve paths",
  "order": 1203,
  "duration_min": 25,
  "concept_md": "### One app, several jobs\n\n`app/main.py` registers fourteen route decorators over twelve paths. Two paths carry two methods each — `/test-review` and `/users` — which is why the counts differ and why quoting either number without the other is misleading.\n\n### The groups\n\nOperational routes (`/`, `/health`), the rule listing, the review routes (`/review`, `/reviews`, `/reviews/{review_id}`), the webhook, statistics, and the user routes. Each group has its own tag in the OpenAPI schema.\n\n### Why /health matters more than it looks\n\nIt reports the credential state and whether the database is enabled. A demo that opens with `/health` can say which providers are configured before anyone tries a review, which is the difference between a five-second answer and a five-minute diagnosis.\n\n### What the API does not do\n\nIt does not review anything itself. Every route that produces a review calls the engine, so the routing, the labels and the single warning are the same as the CLI's.\n\n### Why the routes are grouped by tag\n\nBecause the OpenAPI page is documentation, and a reader looking for the webhook should not have to scan the user routes. The tags are ops, rules, review, webhook, history and users — six groups over twelve paths, which is how the schema page stays readable.",
  "code_examples": [
    {
      "id": "12.3-ex-0",
      "lang": "console",
      "caption": "Fourteen decorators over twelve paths",
      "code": "python - <<'PY'\nimport re, pathlib\n\nsrc = pathlib.Path(\"app/main.py\").read_text()\npaths = re.findall(r'@app\\.(?:get|post|patch|delete)\\(\\s*\"([^\"]+)\"', src)\nprint(\"decorators:\", src.count(\"@app.\"), \"| unique paths:\", len(set(paths)))\nprint(\"doubled:\", sorted(p for p in set(paths) if paths.count(p) > 1))\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "decorators: 14 | unique paths: 12\ndoubled: ['/test-review', '/users']",
      "why_not": "the browser runner has no shell and does not embed the surface modules; this command runs from a checkout."
    }
  ],
  "quiz": [
    {
      "q": "How many paths does the app register?",
      "options": [
        "Fourteen, over twelve decorators",
        "Ten, over ten decorators",
        "Sixteen, over fourteen decorators",
        "Twelve, over fourteen decorators"
      ],
      "answer": 3,
      "why": "Two paths carry two methods each, which is why the two numbers differ."
    },
    {
      "q": "What does /health report?",
      "options": [
        "Credential state and the database",
        "The rule registry and its size",
        "The last review and its mode",
        "The provider latency and the model"
      ],
      "answer": 0,
      "why": "It answers which providers are configured before anyone attempts a review."
    },
    {
      "q": "What does every review route call?",
      "options": [
        "The adapter, called directly",
        "The engine, and nothing else",
        "The CLI's own formatter",
        "The rule registry, first"
      ],
      "answer": 1,
      "why": "So the routing, labels and single warning match the CLI's exactly."
    }
  ],
  "try_it": {
    "prompt": "List the route decorators.",
    "starter": "",
    "solution": "```console\n$ grep -n '@app\\.' app/main.py\n```",
    "explanation": "Fourteen lines, and two paths appear twice."
  },
  "exercise": {
    "prompt": "Which two paths carry more than one method?",
    "hint": "One is a test helper, one is a collection.",
    "solution": "```console\n$ python -c \"import re,pathlib; s=pathlib.Path('app/main.py').read_text(); p=re.findall(r'@app\\\\.(?:get|post|delete)\\\\(\\\\s*\\\"([^\\\"]+)\\\"', s); print(sorted({x for x in p if p.count(x)>1}))\"\n```\n\n`/test-review` and `/users`.",
    "explanation": "Each answers a GET and a POST, which is why the decorator count exceeds the path count."
  },
  "common_mistakes": [
    "Quoting the route count without saying whether it is paths or decorators.",
    "Adding a route that calls the adapter instead of the engine.",
    "Treating /health as decoration rather than a diagnostic."
  ],
  "project_links": [
    {
      "label": "The app and its route groups",
      "path": "app/main.py",
      "lines": "879-889"
    },
    {
      "label": "The review route",
      "path": "app/main.py",
      "lines": "945-1022"
    }
  ],
  "learn_more": [
    {
      "label": "app/main.py",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/main.py"
    },
    {
      "label": "app/engine.py — what every route calls",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/engine.py"
    }
  ],
  "glossary_terms": [
    "route — a path plus a method",
    "tag — a group in the OpenAPI schema",
    "health check — a route that reports readiness"
  ]
});
