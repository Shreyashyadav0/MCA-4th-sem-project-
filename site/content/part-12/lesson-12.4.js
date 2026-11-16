/* 12.4 — Auth on the management routes, and only those
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "12.4",
  "part": 12,
  "part_title": "Surfaces: CLI, API, webhook, GitHub",
  "title": "Auth on the management routes, and only those",
  "order": 1204,
  "duration_min": 20,
  "concept_md": "### Where the key is required\n\nWhen `API_AUTH_ENABLED` is true, an `X-API-Key` header is required on the management endpoints: `GET /reviews`, `GET /reviews/{id}`, `GET /stats` and the `/users` routes. The review surfaces stay open.\n\n### Why the split\n\nBecause the two jobs are different. Reviewing a diff is the demo, and requiring a key to try it would make the first five minutes harder for no security gain — the diff is the user's own. Reading history is a different matter: those routes expose every review the tool has stored.\n\n### Why it is off by default\n\nA demo that needs a key before it answers is a demo that fails on stage. The default is open, and the README says plainly that a deployment should set it.\n\n### What the header actually is\n\nA per-user key, stored as a SHA-256 hash in the `users` table and resolved to a role. `POST /users` issues one; `DB_SEED_ADMIN_KEY` only seeds the first admin, and its job ends there. A role shortfall is a 403 — a viewer cannot post, a reviewer cannot manage users.\n\nWhat it is not is a session: there is no lifetime and no refresh, so a key is revoked by changing the row rather than by expiring.\n\n### What the split costs\n\nTwo behaviours to explain in the README, and one flag that changes the surface's contract when it is set. That is the price of a demo that answers immediately, and it is worth stating plainly rather than discovering when a deployment returns 401 to a request that worked locally.",
  "code_examples": [
    {
      "id": "12.4-ex-0",
      "lang": "console",
      "caption": "Which routes are guarded",
      "code": "python - <<'PY'\nimport pathlib, re\n\nsrc = pathlib.Path(\"app/main.py\").read_text()\nprint(\"X-API-Key mentions:\", src.count(\"X-API-Key\"))\nfor n, line in enumerate(src.splitlines(), 1):\n    if \"api_auth_enabled\" in line:\n        print(n, line.strip()[:60])\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "X-API-Key mentions: 1",
      "why_not": "the browser runner has no shell and does not embed the surface modules; this command runs from a checkout."
    }
  ],
  "quiz": [
    {
      "q": "Which routes require the header?",
      "options": [
        "The management routes only",
        "Every route in the app",
        "The review routes only",
        "The webhook and the reviews"
      ],
      "answer": 0,
      "why": "History is a different exposure from a review of your own diff."
    },
    {
      "q": "Why is auth off by default?",
      "options": [
        "The header is hard to send",
        "A demo must answer first",
        "The database is optional",
        "The key has no default"
      ],
      "answer": 1,
      "why": "A demo that demands a key before it answers fails in front of people."
    },
    {
      "q": "What is the header, honestly?",
      "options": [
        "A per-user hashed key, with no lifetime",
        "A per-user token that expires daily on every run",
        "One shared secret for the instance",
        "A signed request digest per call"
      ],
      "answer": 0,
      "why": "Each user gets a key stored as a hash and resolved to a role; there is no lifetime, so revocation is a row change."
    }
  ],
  "try_it": {
    "prompt": "Show the flag that turns the requirement on.",
    "starter": "",
    "solution": "```console\n$ grep -n 'def require' -A 4 app/auth.py | head -8\n```",
    "explanation": "The dependency that guards the management routes — it resolves the header to a role."
  },
  "exercise": {
    "prompt": "Which setting holds the key the header is compared against?",
    "hint": "It is seeded, not issued.",
    "solution": "```console\n$ grep -n 'db_seed_admin_key' app/config.py | head -2\n```\n\n`DB_SEED_ADMIN_KEY` — one seeded value, not a table of users.",
    "explanation": "One key with no lifetime is the honest scope for a demo deployment."
  },
  "common_mistakes": [
    "Requiring a key on the review route and breaking the demo.",
    "Describing the header as per-user authentication.",
    "Leaving auth off on a public deployment because it is off by default."
  ],
  "project_links": [
    {
      "label": "The auth setting",
      "path": "app/config.py",
      "lines": "91-98"
    },
    {
      "label": "The review route that stays open",
      "path": "app/main.py",
      "lines": "945-1022"
    }
  ],
  "learn_more": [
    {
      "label": "app/main.py — the routes",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/main.py"
    },
    {
      "label": "app/config.py — the flag",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/config.py"
    }
  ],
  "glossary_terms": [
    "management route — one that reads stored history",
    "shared key — one secret for the whole instance",
    "seed — a value created at first start"
  ]
});
