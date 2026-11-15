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
  "concept_md": "### One file, read in order\n\n`app/main.py` is 1610 lines and holds the whole HTTP surface. Read it in this order and it stops being a wall.\n\n**1. The module docstring** (top of the file) — what the surface promises, and the one rule that governs every handler: a client error is never a 200.\n\n**2. The models** — `ReviewRequest` at **152**, `ReviewResponse` at **260**, `RuleInfo` at **312**, `HealthResponse` at **322**. Everything the API accepts and returns is declared here, before a single route.\n\n**3. The helpers that raise** — the path guard at **427–429**, the storage guard at **627**, the diff-parse failures at **664** and **668**. These are the vocabulary of failures the routes reuse.\n\n**4. `_verify_signature` at 467** — the only cryptographic function in the file.\n\n**5. The route block, in file order, 879–1554** — `/` and `/health`, then `/rules`, `/review`, `/test-review`, `/webhook` (twice), then the later `/reviews`, `/users` and `/stats` group from **1424** on.\n\n### Why file order is the right order\n\nThe routes appear in the order they were added, so reading them top to bottom is reading the project's history: the first four are the minimum viable surface, the webhook is the integration, and the last three are the persistence layer arriving. A reader who starts at 1424 sees the newest code first and has no idea what it is for.\n\n### The two facts worth memorising\n\n`_verify_signature` is at **467** and the `/review` decorator spans **945–959**. Those two are the answers the exercise asks for, and they are the two places you will be asked to point at in a viva.",
  "code_examples": [
    {
      "id": "4.8-ex-0",
      "lang": "console",
      "caption": "The file's own table of contents, from grep",
      "code": "grep -n '^class \\|^def \\|^@app\\.' app/main.py | head -12",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "152:class ReviewRequest(BaseModel):\n260:class ReviewResponse(BaseModel):\n312:class RuleInfo(BaseModel):\n322:class HealthResponse(BaseModel):\n427:        raise HTTPException(status_code=403, detail=\"path must stay inside …\")\n467:def _verify_signature(body: bytes, signature: str | None, secret: str) -> bool:\n879:@app.get(\"/\", tags=[\"ops\"], summary=\"Service banner\")\n892:@app.get(\"/health\", tags=[\"ops\"], summary=\"Liveness and credential state\",\n909:@app.get(\"/rules\", tags=[\"rules\"], summary=\"List every registered rule\",\n924:@app.get(\n945:@app.post(\n1025:@app.get(",
      "why_not": "it greps the repository's own source, which the browser runner does not have."
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
      "q": "Why read the routes in file order rather than starting with `/stats`?",
      "options": [
        "Because file order is the order the surface grew, so each route makes sense of the ones before it",
        "Because `/stats` is broken",
        "Because `/stats` has no decorator",
        "Because the file is alphabetically sorted"
      ],
      "answer": 0,
      "why": "The later routes assume the models and helpers defined above them; starting at 1424 reads the conclusion before the argument."
    }
  ],
  "try_it": {
    "prompt": "Print every route with its line number, then find the two decorators for `/webhook`.",
    "starter": "",
    "solution": "```console\n$ grep -n '^@app\\.' app/main.py\n879:@app.get(\n892:@app.get(\n909:@app.get(\n924:@app.get(\n945:@app.post(\n1025:@app.get(\n1086:@app.post(\n1135:@app.post(\n1424:@app.get(\n1456:@app.get(\n1487:@app.get(\n1510:@app.post(\n1554:@app.get(\n```",
    "explanation": "Thirteen decorators for twelve paths: `/webhook` is registered twice, at 1086 and 1135, and the later registration is the live one."
  },
  "exercise": {
    "prompt": "Name the function that verifies the webhook signature, give its line, and give the line range of the `/review` decorator.",
    "hint": "Both are greppable; the decorator is spread over several lines.",
    "solution": "```text\n_verify_signature            app/main.py:467\nthe /review decorator        app/main.py:945-959\n```",
    "explanation": "The decorator runs to fifteen lines because it carries a documented 422 example — a range, not a line, is the honest citation."
  },
  "common_mistakes": [
    "Citing a decorator by its first line when the metadata runs several lines further.",
    "Reading the route block before the models, so the shapes are unknown when they are first used.",
    "Assuming one decorator per path; `/webhook` has two registrations."
  ],
  "project_links": [
    {
      "label": "The models block",
      "path": "app/main.py",
      "lines": "152-330"
    },
    {
      "label": "The signature check and the helpers that raise",
      "path": "app/main.py",
      "lines": "427-500"
    },
    {
      "label": "The route block, in file order",
      "path": "app/main.py",
      "lines": "879-1554"
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
    "helper raise — a shared function that ends a request with a status",
    "surface — everything the API exposes"
  ]
});
