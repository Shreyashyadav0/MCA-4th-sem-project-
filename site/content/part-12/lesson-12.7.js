/* 12.7 — The webhook: verify the signature, or say you did not
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "12.7",
  "part": 12,
  "part_title": "Surfaces: CLI, API, webhook, GitHub",
  "title": "The webhook: verify the signature, or say you did not",
  "order": 1207,
  "duration_min": 25,
  "concept_md": "### What a webhook has to do\n\nAnswer GitHub within its timeout, verify that the request really came from GitHub, and hand the payload to the same engine every other surface uses.\n\n### The signature\n\nGitHub signs the body with the webhook secret and sends the digest in a header. The route recomputes it and compares. `GITHUB_WEBHOOK_SECRET` supplies the key; `WEBHOOK_ALLOW_UNSIGNED` is the escape hatch for a local test.\n\n### Why the escape hatch exists, and why it is loud\n\nA local demo cannot produce a valid signature without the secret GitHub generated. The flag lets a developer test the route without one — and it is a flag rather than a default precisely so that a deployment which forgets the secret fails closed rather than accepting anything.\n\n### What the route must not do\n\nTrust the payload's claim about which repository it came from. The signature covers the body, so a valid signature plus the configured token is what makes the request actionable; the body is data to be parsed, not an instruction.\n\n### The timeout\n\nGitHub gives a webhook a short window. The route answers and the review proceeds, which is why a degraded review is better than a slow one here — a 500 because a key was missing costs the whole review and shows as a failed check.",
  "code_examples": [
    {
      "id": "12.7-ex-0",
      "lang": "console",
      "caption": "The two settings the webhook reads",
      "code": "python - <<'PY'\nfrom app.config import Settings\n\nfor name in (\"github_webhook_secret\", \"webhook_allow_unsigned\"):\n    f = Settings.model_fields[name]\n    print(\"%-24s default=%r repr=%s\" % (name, f.default, f.repr))\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "github_webhook_secret    default=None repr=False\nwebhook_allow_unsigned   default=False repr=True",
      "why_not": "the browser runner has no shell and does not embed the surface modules; this command runs from a checkout."
    }
  ],
  "quiz": [
    {
      "q": "What does the route compare?",
      "options": [
        "The payload's repository",
        "The sender's login",
        "The event type",
        "A recomputed digest"
      ],
      "answer": 3,
      "why": "The signature covers the body, so the body is parsed rather than obeyed."
    },
    {
      "q": "Why does the unsigned escape hatch exist?",
      "options": [
        "A local test has no secret",
        "GitHub sometimes omits it",
        "The route is faster unsigned",
        "The engine requires it"
      ],
      "answer": 0,
      "why": "A developer cannot produce a valid signature without the secret GitHub generated."
    },
    {
      "q": "Why answer before reviewing?",
      "options": [
        "The engine is asynchronous",
        "GitHub's timeout is short",
        "The payload is large",
        "The token expires quickly"
      ],
      "answer": 1,
      "why": "A degraded review that arrives beats a slow one that misses the window."
    }
  ],
  "try_it": {
    "prompt": "Print the webhook's two settings and their defaults.",
    "starter": "",
    "solution": "```console\n$ python -c \"from app.config import Settings; print({n: Settings.model_fields[n].default for n in ('github_webhook_secret','webhook_allow_unsigned')})\"\n```",
    "explanation": "No secret and unsigned refused — the fail-closed default."
  },
  "exercise": {
    "prompt": "What happens to an unsigned request when the escape hatch is off?",
    "hint": "Fail closed.",
    "solution": "```console\n$ grep -n 'webhook_allow_unsigned' -A 3 app/main.py | head -8\n```\n\nIt is rejected, because the default refuses unsigned deliveries.",
    "explanation": "A deployment that forgets the secret fails closed rather than accepting anything."
  },
  "common_mistakes": [
    "Trusting the payload's repository field instead of the signature.",
    "Defaulting the unsigned flag to true.",
    "Reviewing inline and missing GitHub's timeout."
  ],
  "project_links": [
    {
      "label": "The webhook's two settings",
      "path": "app/config.py",
      "lines": "43-56"
    },
    {
      "label": "The webhook route",
      "path": "app/main.py",
      "lines": "1135-1199"
    }
  ],
  "learn_more": [
    {
      "label": "app/main.py — the webhook",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/main.py"
    },
    {
      "label": "app/config.py — the secret",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/config.py"
    }
  ],
  "glossary_terms": [
    "signature — a digest proving the body came from GitHub",
    "fail closed — refuse when unsure",
    "escape hatch — a flag that relaxes a check for local use"
  ]
});
