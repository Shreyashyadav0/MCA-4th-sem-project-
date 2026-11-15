/* 4.8 — Guided read of app/main.py
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "4.8",
  "part": 4,
  "part_title": "HTTP and FastAPI",
  "title": "Guided read of app/main.py",
  "order": 408,
  "duration_min": 30,
  "concept_md": "### One file, read in order\n\n`app/main.py` is 1610 lines and holds the whole HTTP surface. Read it in this order and it stops being a wall.\n\n**1. The module docstring** (top of the file) — what the surface promises, and the one rule that governs every handler: a client error is never a 200.\n\n**2. The models** — `ReviewRequest` at **152**, `ReviewResponse` at **260**, `RuleInfo` at **312**, `HealthResponse` at **322**. Everything the API accepts and returns is declared here, before a single route.\n\n**3. The helpers that raise** — the path guard at **427–429**, the storage guard at **627**, the diff-parse failures at **664** and **668**. These are the vocabulary of failures the routes reuse.\n\n**4. `_verify_signature` at 467** — the only cryptographic function in the file.\n\n**5. The route block, in file order, 879–1610** — `/` and `/health`, then `/rules`, `/review`, `/test-review`, `/webhook`, then the later `/reviews`, `/users` and `/stats` group from **1424** on. Fourteen decorators over twelve paths, because `/test-review` and `/users` each carry two methods.\n\n### Where the two halves divide\n\nEverything up to `/review` (945) is the original surface: the banner, a health check, the rule engine's two endpoints and the review endpoint itself. From `/test-review` at 1025 on, each block is a later concern arriving — the review history, the webhook, then persistence at 1424 with its own models and its own 503. A reader who starts at 1424 meets a storage layer before knowing what it stores.\n\n### One habit that pays\n\nCite a decorator by its range, never its first line: `/review` starts at 945 and the closing bracket is at **960**, because the `responses=` block runs to fifteen lines. The same habit applies to `_verify_signature` at **467–479**, which ends where its last `return False` does.",
  "code_examples": [
    {
      "id": "4.8-ex-0",
      "lang": "console",
      "caption": "The file's own table of contents, from grep",
      "code": "grep -n '^class \\|^def \\|^@app\\.' app/main.py | head -12",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "119:def run(cmd):\n152:class ReviewRequest(BaseModel):\n209:class ReviewStats(BaseModel):\n227:class PostingInfo(BaseModel):\n260:class ReviewResponse(BaseModel):\n304:class WebhookAck(BaseModel):\n312:class RuleInfo(BaseModel):\n322:class HealthResponse(BaseModel):\n349:def render_comment(review: DiffReviewResult) -> str:\n394:def _active_mode() -> str:\n406:def _load_fixture() -> tuple[str, str]:\n415:def _confine_to_project(raw: str) -> Path:",
      "why_not": "there is no fastapi in the browser runner and no repository checkout to import from, so the app cannot be built at all."
    }
  ],
  "quiz": [
    {
      "q": "Where does the file declare what the API accepts?",
      "options": [
        "In the route block, beside each handler",
        "In the models at the top, before any route",
        "In `/openapi.json` at runtime",
        "In the module docstring"
      ],
      "answer": 1,
      "why": "`ReviewRequest` at 152 and `ReviewResponse` at 260 come before the first decorator at 879; the routes consume them."
    },
    {
      "q": "What is `_verify_signature` the only example of in this file?",
      "options": [
        "A route handler",
        "A Pydantic validator",
        "A cryptographic check",
        "A test helper"
      ],
      "answer": 2,
      "why": "It is the single HMAC comparison in the file, at line 467, and it is only called when a webhook secret is configured."
    },
    {
      "q": "Why does `/review` need a line range rather than a line number?",
      "options": [
        "Because the decorator carries a responses block",
        "Because the file is not in alphabetical order",
        "Because decorators are never given line numbers",
        "Because the handler is defined in another file"
      ],
      "answer": 0,
      "why": "945 opens the decorator and 960 closes it; the fourteen lines between are the documented 422 example, and citing 945 alone would point at a fragment."
    }
  ],
  "try_it": {
    "prompt": "Print every route with its line number, then find the two decorators for `/webhook`.",
    "starter": "",
    "solution": "```console\n$ grep -n '^@app\\.' app/main.py\n879:@app.get(\n892:@app.get(\n909:@app.get(\n924:@app.get(\n945:@app.post(\n1025:@app.get(\n1086:@app.post(\n1135:@app.post(\n1424:@app.get(\n1456:@app.get(\n1487:@app.get(\n1510:@app.post(\n1554:@app.get(\n1576:@app.patch(\n```",
    "explanation": "Fourteen decorators over twelve paths: `/test-review` carries GET and POST, `/users` carries POST and GET, and `/webhook` appears once."
  },
  "exercise": {
    "prompt": "Where is the webhook's 401 raised, and why is it raised there rather than inside `_verify_signature`?",
    "hint": "The function returns a boolean; something has to turn that into a status.",
    "solution": "```text\nAt app/main.py:1178, inside the webhook handler, guarded by `if settings.has_webhook_secret:`\nat 1174.\n\n`_verify_signature` (467-479) returns a bool and never raises: it is a pure check, so it\ncan be unit-tested without an app. Turning a failed check into a 401 is a routing decision,\nand routing decisions live in the handler.\n```",
    "explanation": "The split is deliberate: the check is a function, the status is a policy. That is also why the same request is a 200 when no secret is configured — the guard, not the function, decides whether a signature is required at all."
  },
  "common_mistakes": [
    "Citing a decorator by its first line when the metadata runs several lines further.",
    "Reading the route block before the models, so the shapes are unknown when they are first used.",
    "Assuming one decorator per path; `/test-review` and `/users` each carry two methods."
  ],
  "project_links": [
    {
      "label": "The models block",
      "path": "app/main.py",
      "lines": "152-346"
    },
    {
      "label": "The signature check and the helpers that raise",
      "path": "app/main.py",
      "lines": "415-430"
    },
    {
      "label": "The signature check",
      "path": "app/main.py",
      "lines": "467-479"
    },
    {
      "label": "The route block, in file order",
      "path": "app/main.py",
      "lines": "879-1610"
    }
  ],
  "learn_more": [
    {
      "label": "app/main.py — the whole surface",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/main.py"
    },
    {
      "label": "ARCHITECTURE.md — how the pieces fit",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/ARCHITECTURE.md"
    }
  ],
  "glossary_terms": [
    "route block — the decorators and handlers, in file order",
    "helper raise — a shared function that ends a request with a status and a detail",
    "surface — everything the API exposes to a client"
  ]
});
