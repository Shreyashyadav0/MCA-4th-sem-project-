/* 4.6 — Headers: how the client identifies itself
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "4.6",
  "part": 4,
  "part_title": "HTTP and FastAPI",
  "title": "Headers: how the client identifies itself",
  "order": 406,
  "duration_min": 20,
  "concept_md": "### Metadata outside the body\n\nA header is a name/value pair sent with the message, not inside it. GitHub sends two that this app reads:\n\n- `X-GitHub-Event` — which kind of event fired, such as `pull_request`.\n- `X-Hub-Signature-256` — an HMAC of the body, so the receiver can prove the body is unchanged and came from someone holding the secret.\n\nIn FastAPI a header becomes a parameter by being declared:\n\n```python\nx_github_event: str = Header(alias=\"X-GitHub-Event\")\n```\n\nThe alias is needed because a Python identifier cannot contain a hyphen.\n\n### Verified only when a secret exists\n\n`_verify_signature` compares the HMAC only when `GITHUB_WEBHOOK_SECRET` is configured. With no secret, the same request succeeds — which is why the capture below is a **200** and not a 401. That is a deliberate local-development behaviour, and it is the kind of default worth knowing before you deploy: an unset secret means unverified bodies are accepted.\n\n### What the capture shows\n\nThe webhook accepted a body with no usable pull-request number and fell back to the bundled sample diff, saying so in `notice`. Nothing was posted. That sentence is the honesty rule in action: the run happened, the outcome is described, and no claim is made about a real pull request.",
  "code_examples": [
    {
      "id": "4.6-ex-0",
      "lang": "console",
      "caption": "A signed-capable webhook with no secret configured",
      "code": "curl -s -i -X POST http://127.0.0.1:8000/webhook \\\n  -H \"content-type: application/json\" -H \"X-GitHub-Event: pull_request\" \\\n  -d '{\"action\": \"opened\"}'",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "HTTP/1.1 200 OK\ncontent-type: application/json\n\n{\"source\":\"sample_fixture\",\"notice\":\"the payload carried no usable pull-request number; sample fixture: sample.diff (not posted: the pull-request diff could not be fetched)\",\"review\":{\"mode\":\"mock\",\"target\":\"samples/sample.diff\",…[abridged]",
      "why_not": "a request needs a running app on a socket; the browser runner has Python but no server and no repository checkout."
    }
  ],
  "quiz": [
    {
      "q": "Why does the header parameter need `alias=\"X-GitHub-Event\"`?",
      "options": [
        "Because a Python identifier cannot contain a hyphen",
        "To rename it in the JSON body",
        "To make it optional",
        "To lowercase the header name"
      ],
      "answer": 0,
      "why": "`x_github_event` is a valid Python name; the alias is how it maps back to the real header spelling."
    },
    {
      "q": "The webhook answers 200 with no secret configured. Why?",
      "options": [
        "The signature was correct",
        "GitHub webhooks cannot be rejected",
        "The request was rejected and retried",
        "The signature is only checked when a secret is set, so nothing was checked"
      ],
      "answer": 3,
      "why": "`_verify_signature` runs only when `settings.has_webhook_secret` — an unset secret means unverified bodies are accepted locally."
    },
    {
      "q": "What does `notice` in that body tell the reader?",
      "options": [
        "That the request failed",
        "Which source was used and why, in plain words",
        "The signature that was checked",
        "The number of rules applied"
      ],
      "answer": 1,
      "why": "It is the same honesty field the CLI prints: the run happened, and the fallback is named rather than hidden."
    }
  ],
  "try_it": {
    "prompt": "Send the same webhook twice, once with `X-GitHub-Event: pull_request` and once with `X-GitHub-Event: ping`. Compare the bodies.",
    "starter": "",
    "solution": "```console\n$ curl -s -o /dev/null -w '%{http_code}\\n' -X POST http://127.0.0.1:8000/webhook \\\n  -H \"X-GitHub-Event: ping\" -H \"content-type: application/json\" -d '{\"action\": \"opened\"}'\n200\n```",
    "explanation": "Both are 200: the event filter decides whether to act, not whether to accept. A `ping` is acknowledged and ignored, which is what GitHub expects."
  },
  "exercise": {
    "prompt": "Read `_verify_signature` and say, in three lines, what it compares and what it does when the secret is empty.",
    "hint": "It takes the raw body, the header value and the secret.",
    "solution": "```text\n1. It recomputes an HMAC-SHA256 of the raw body using the secret as the key.\n2. It compares that with the X-Hub-Signature-256 header value, in constant time.\n3. The caller only invokes it when settings.has_webhook_secret is true; with no secret\n   there is nothing to compare against, so the body is accepted unverified.\n```",
    "explanation": "The function itself is unconditional; the guard is at the call site (`app/main.py:1174`), which is why the behaviour changes with configuration rather than with the request."
  },
  "common_mistakes": [
    "Checking a signature against a re-serialised body — the HMAC must be over the raw bytes.",
    "Assuming an unset secret means requests are rejected; here it means they are accepted unverified.",
    "Reading headers from the JSON body; they are outside it."
  ],
  "project_links": [
    {
      "label": "The header parameters",
      "path": "app/main.py",
      "lines": "1148-1155"
    },
    {
      "label": "The signature check",
      "path": "app/main.py",
      "lines": "467-500"
    },
    {
      "label": "The guard that decides whether to check",
      "path": "app/main.py",
      "lines": "1174-1179"
    }
  ],
  "learn_more": [
    {
      "label": "app/main.py — the webhook handler",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/main.py"
    },
    {
      "label": "docs/learning/track-7-surfaces.md — the surfaces track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-7-surfaces.md"
    }
  ],
  "glossary_terms": [
    "header — metadata sent alongside the body",
    "HMAC — a keyed hash used to prove a body is authentic",
    "alias — the real spelling of a header or field",
    "ping — the event GitHub sends to test a webhook"
  ]
});
