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
  "concept_md": "### Metadata outside the body\n\nA header is a name/value pair sent with the message, not inside it. GitHub sends two that this app reads:\n\n- `X-GitHub-Event` — which kind of event fired, such as `pull_request`.\n- `X-Hub-Signature-256` — an HMAC of the body, so the receiver can prove the body is unchanged and came from someone holding the secret.\n\nIn FastAPI a header becomes a parameter by being declared:\n\n```python\nx_github_event: str = Header(\n    default=\"pull_request\",\n    description=\"GitHub event type.\",\n    examples=[\"pull_request\"],\n)\n```\n\nThe parameter name is the header name with underscores: `x_github_event` reads the\n`X-GitHub-Event` header, and FastAPI does that mapping itself. An `alias=` would only be\nneeded if the two spellings did not correspond.\n\n### Verified only when a secret exists\n\n`_verify_signature` compares the HMAC only when `GITHUB_WEBHOOK_SECRET` is configured. With no secret, the same request succeeds — which is why the capture below is a **200** and not a 401. That is a deliberate local-development behaviour, and it is the kind of default worth knowing before you deploy: an unset secret means unverified bodies are accepted.\n\n### What the capture shows\n\nThe webhook accepted a body with no usable pull-request number and fell back to the bundled sample diff, saying so in `notice`. Nothing was posted. That sentence is the honesty rule in action: the run happened, the outcome is described, and no claim is made about a real pull request.",
  "code_examples": [
    {
      "id": "4.6-ex-0",
      "lang": "console",
      "caption": "A signed-capable webhook with no secret configured",
      "code": "curl -s -w '\\n%{http_code}\\n' -X POST http://127.0.0.1:8000/webhook \\\n  -H \"content-type: application/json\" -H \"X-GitHub-Event: pull_request\" \\\n  -d '{\"action\": \"opened\"}'",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "{\"source\":\"sample_fixture\",\"notice\":\"the payload carried no usable pull-request number; sample fixture: sample.diff (not posted: the pull-request diff could not be fetched)\",\"review\":{\"mode\":\"mock\",\"target\":\"samples/sample.diff\",\"files\":[{\"path\":\"app/db.py\",\"change\":\"modified\",\"added_spans\":[\"3-4\",\"7-8\"],\"added_line_count\":4,\"hunk_count\":1,\"binary\":false},{\"path\":\"app/report.py\",\"change\":\"added\",\"added_spans\":[\"1-5\"],\"added_line_count\":5,\"hunk_count\":1,\"binary\":false}],\"findings\":[{\"file\":\"app/db.py\",\"line\":\"3\",\"severity\":\"CRITICAL\",\"issue\":\"A GitHub token literal is committed here, granting every scope the token holds to anyone who reads the repository. (rule: secret/github-token)\",\"suggested_fix\":\"Revoke the token, then read it at runtime: `token = os.environ[\\\"GITHUB_TOKEN\\\"]`.\"},{\"file\":\"app/db.py\",\"line\":\"3\",\"severity\":\"CRITICAL\",\"issue\":\"`API_TOKEN` is assigned a literal credential, so the secret is committed to git history and stays readable to anyone with repo access even after it is rotated. (rule: secret/hardcoded-credential)\",\"suggested_fix\":\"API_TOKEN = os.environ[\\\"API_TOKEN\\\"]  # load from the environment; fail loudly when it is unset\"},{\"file\":\"app/db.py\",\"line\":\"7\",\"severity\":\"CRITICAL\",\"issue\":\"SQL is assembled by string interpolation, so any value reaching this line can change the statement and read, alter or drop the table. (rule: unsafe/sql-injection)\",\"suggested_fix\":\"Pass parameters instead: `db.execute(\\\"SELECT * FROM users WHERE id = ?\\\", (uid,))` — the driver quotes them, interpolation does not.\"},{\"file\":\"app/report.py\",\"line\":\"1\",\"severity\":\"MEDIUM\",\"issue\":\"`render` is a public function without full annotations, so callers and the reviewer cannot tell what goes in or what comes out. (rule: quality/missing-type-hints)\",\"suggested_fix\":\"Annotate it: `def render(value: str) -> str:` — every parameter and the return type.\"}],\"anchors\":[{\"finding\":{\"file\":\"app/db.py\",\"line\":\"3\",\"severity\":\"CRITICAL\",\"issue\":\"A GitHub token literal is committed here, granting every scope the token holds to anyone who reads the repository. (rule: secret/github-token)\",\"suggested_fix\":\"Revoke the token, then read it at runtime: `token = os.environ[\\\"GITHUB_TOKEN\\\"]`.\"},\"status\":\"anchored\",\"hunk_header\":\"@@ -1,5 +1,8 @@\",\"detail\":\"added line: 3\"},{\"finding\":{\"file\":\"app/db.py\",\"line\":\"3\",\"severity\":\"CRITICAL\",\"issue\":\"`API_TOKEN` is assigned a literal credential, so the secret is committed to git history and stays readable to anyone with repo access even after it is rotated. (rule: secret/hardcoded-credential)\",\"suggested_fix\":\"API_TOKEN = os.environ[\\\"API_TOKEN\\\"]  # load from the environment; fail loudly when it is unset\"},\"status\":\"anchored\",\"hunk_header\":\"@@ -1,5 +1,8 @@\",\"detail\":\"added line: 3\"},{\"finding\":{\"file\":\"app/db.py\",\"line\":\"7\",\"severity\":\"CRITICAL\",\"issue\":\"SQL is assembled by string interpolation, so any value reaching this line can change the statement and read, alter or drop the table. (rule: unsafe/sql-injection)\",\"suggested_fix\":\"Pass parameters instead: `db.execute(\\\"SELECT * FROM users WHERE id = ?\\\", (uid,))` — the driver quotes them, interpolation does not.\"},\"status\":\"anchored\",\"hunk_header\":\"@@ -1,5 +1,8 @@\",\"detail\":\"added line: 7\"},{\"finding\":{\"file\":\"app/report.py\",\"line\":\"1\",\"severity\":\"MEDIUM\",\"issue\":\"`render` is a public function without full annotations, so callers and the reviewer cannot tell what goes in or what comes out. (rule: quality/missing-type-hints)\",\"suggested_fix\":\"Annotate it: `def render(value: str) -> str:` — every parameter and the return type.\"},\"status\":\"anchored\",\"hunk_header\":\"@@ -0,0 +1,5 @@\",\"detail\":\"added line: 1\"}],\"notes\":[\"the payload carried no usable pull-request number; sample fixture: sample.diff (not posted: the pull-request diff could not be fetched)\",\"local rule engine: 63 deterministic rules, no network, no API key\",\"mock mode: no SARVAM_API_KEY or LMSTUDIO_BASE_URL configured; local rule engine used\"],\"verdict\":\"block\"},\"comment\":\"## Autonomous AI Code Review\\n\\n**Mode:** `mock` · **Files:** 2 · **Findings:** 4 (CRITICAL 3, HIGH 0, MEDIUM 1, LOW 0)\\n\\n| File | Change | Added lines |\\n|---|---|---|\\n| `app/db.py` | modified | 3-4, 7-8 |\\n| `app/report.py` | added | 1-5 |\\n\\n### 1. CRITICAL — `app/db.py:3`\\n\\n- **Issue:** A GitHub token literal is committed here, granting every scope the token holds to anyone who reads the repository. (rule: secret/github-token)\\n- **Suggested fix:** Revoke the token, then read it at runtime: `token = os.environ[\\\"GITHUB_TOKEN\\\"]`.\\n- **Anchor:** anchored (`@@ -1,5 +1,8 @@`)\\n\\n### 2. CRITICAL — `app/db.py:3`\\n\\n- **Issue:** `API_TOKEN` is assigned a literal credential, so the secret is committed to git history and stays readable to anyone with repo access even after it is rotated. (rule: secret/hardcoded-credential)\\n- **Suggested fix:** API_TOKEN = os.environ[\\\"API_TOKEN\\\"]  # load from the environment; fail loudly when it is unset\\n- **Anchor:** anchored (`@@ -1,5 +1,8 @@`)\\n\\n### 3. CRITICAL — `app/db.py:7`\\n\\n- **Issue:** SQL is assembled by string interpolation, so any value reaching this line can change the statement and read, alter or drop the table. (rule: unsafe/sql-injection)\\n- **Suggested fix:** Pass parameters instead: `db.execute(\\\"SELECT * FROM users WHERE id = ?\\\", (uid,))` — the driver quotes them, interpolation does not.\\n- **Anchor:** anchored (`@@ -1,5 +1,8 @@`)\\n\\n### 4. MEDIUM — `app/report.py:1`\\n\\n- **Issue:** `render` is a public function without full annotations, so callers and the reviewer cannot tell what goes in or what comes out. (rule: quality/missing-type-hints)\\n- **Suggested fix:** Annotate it: `def render(value: str) -> str:` — every parameter and the return type.\\n- **Anchor:** anchored (`@@ -0,0 +1,5 @@`)\\n\\n**Verdict:** block\\n\",\"stats\":{\"files\":2,\"findings\":4,\"critical\":3,\"high\":0,\"medium\":1,\"low\":0,\"verdict\":\"block\",\"rules_evaluated\":63,\"duration_ms\":5.042},\"provider\":\"mock\",\"model\":\"local-rules\",\"posting\":null}\n200",
      "why_not": "there is no fastapi in the browser runner and no repository checkout to import from, so the app cannot be built at all."
    }
  ],
  "quiz": [
    {
      "q": "How does `x_github_event` end up reading the `X-GitHub-Event` header?",
      "options": [
        "FastAPI maps underscores onto hyphens for you",
        "An alias argument spells the header name out",
        "The handler reads it off the raw request",
        "GitHub sends both spellings in the request"
      ],
      "answer": 0,
      "why": "The conversion is automatic: underscores become hyphens and the lookup is case-insensitive, which is why no alias appears in this file."
    },
    {
      "q": "The webhook answers 200 with no secret configured. Why?",
      "options": [
        "The signature matched the body exactly",
        "GitHub webhooks can never be rejected",
        "The request was rejected and then retried",
        "No secret is set, so nothing was checked"
      ],
      "answer": 3,
      "why": "`_verify_signature` runs only when `settings.has_webhook_secret` — an unset secret means unverified bodies are accepted locally."
    },
    {
      "q": "What does `notice` in that body tell the reader?",
      "options": [
        "That the request was rejected outright",
        "Which source was used, and why, in words",
        "Which signature was compared, and with what",
        "How many rules the engine applied"
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
      "lines": "1146-1284"
    },
    {
      "label": "The signature check",
      "path": "app/main.py",
      "lines": "467-490"
    },
    {
      "label": "The guard that decides whether to check",
      "path": "app/main.py",
      "lines": "1146-1284"
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
    "ping — the event GitHub sends to test a webhook"
  ]
});
