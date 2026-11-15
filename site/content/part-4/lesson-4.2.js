/* 4.2 — The app object and the route decorators
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "4.2",
  "part": 4,
  "part_title": "HTTP and FastAPI",
  "title": "The app object and the route decorators",
  "order": 402,
  "duration_min": 20,
  "concept_md": "### One object, many routes\n\n`app/main.py` builds a single `FastAPI()` instance and attaches every endpoint to it with a decorator. There are fourteen decorators in the file, and each one is a path operation:\n\n```python\n@app.get(\"/health\", tags=[\"ops\"], summary=\"Liveness and credential state\")\ndef health() -> HealthResponse: ...\n```\n\nThe decorator registers the function; the function's name is not part of the URL. Two things inside it are documentation rather than behaviour: `tags` groups the endpoint in the generated UI, and `summary` is the one-line description that appears beside it.\n\n### A decorator can be several lines\n\n`@app.get(\"/rules\", …)` is a single line, but `@app.post(\"/review\", …)` runs to fifteen because it carries a `responses={422: …}` block that documents an error body with an example. That is the same decorator, given more to say — and the example it carries appears in `/docs` untouched by any test.\n\n### What the decorator decides\n\nThe method and the path. `@app.get(\"/rules\")` and `@app.post(\"/rules\")` would be two different operations. Two paths here do carry two methods — `/test-review` (GET and POST) and `/users` (POST and GET) — which is how one path serves two jobs without a second URL. The decorator also fixes the response model when one is given, which is lesson 4.4's subject.\n\n### Reading the file in order\n\nThe routes appear in the order they were added: `/` and `/health` at the top of the block, then `/rules`, `/review`, `/test-review`, `/webhook`, and the later `/reviews`, `/users`, `/stats` group from 1424. Reading them in file order is reading the surface in the order it grew.",
  "code_examples": [
    {
      "id": "4.2-ex-0",
      "lang": "console",
      "caption": "The /health decorator and the answer it produces",
      "code": "curl -s -i http://127.0.0.1:8000/health",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "HTTP/1.1 200 OK\ncontent-type: application/json\n\n{\"status\":\"ok\",\"mode\":\"mock\",\"rules\":63,\"categories\":[\"auth\",\"complexity\",\"config\",\"crypto\",\"deserialisation\",\"injection\",\"quality\",\"reliability\",\"secrets\",\"style\"],\"sarvam_key\":\"missing\",\"github_token\":\"missing\",\"webhook_secret\":\"missing\",…[abridged]",
      "why_not": "a request needs a running app on a socket; the browser runner has Python but no server and no repository checkout."
    }
  ],
  "quiz": [
    {
      "q": "What does `tags=[\"ops\"]` on a decorator change?",
      "options": [
        "How the endpoint is grouped in the docs",
        "The URL path the endpoint answers on",
        "The status code the endpoint returns",
        "Whether the endpoint requires a login"
      ],
      "answer": 0,
      "why": "Tags are documentation: `/docs` groups operations by them, and nothing about the request or the response depends on the value."
    },
    {
      "q": "Why is the `/review` decorator fifteen lines long?",
      "options": [
        "FastAPI requires one parameter per line",
        "The handler carries a long docstring",
        "The decorator was reformatted by hand",
        "It carries a responses block with an example"
      ],
      "answer": 3,
      "why": "The extra lines are the documented 422 example; the decorator is still one decorator, given more metadata."
    },
    {
      "q": "`POST /rules` answers 405. Why?",
      "options": [
        "No route is registered for that path",
        "The path exists, but only GET is allowed",
        "The body did not match the model",
        "The rule registry came back empty"
      ],
      "answer": 1,
      "why": "405 means the method is not allowed on an existing path — the mirror image of 404, which means the path itself is unknown."
    }
  ],
  "try_it": {
    "prompt": "Find the decorator that registers `/rules` and read its `summary` and `tags`.",
    "starter": "",
    "solution": "```console\n$ grep -n '@app.get(\"/rules\"' app/main.py\n909:@app.get(\"/rules\", tags=[\"rules\"], summary=\"List every registered rule\", response_model=list[RuleInfo])\n```",
    "explanation": "`tags=[\"rules\"]` groups it with `/rules/{rule_id}` in the UI, and the summary is the sentence a reader sees instead of the function name. The `response_model` on the same line is what lesson 4.4 is about."
  },
  "exercise": {
    "prompt": "List the fourteen route decorators in file order and give each one's method and path. Two paths appear twice — say which, and why that is not a conflict.",
    "hint": "`grep -n '^@app\\.' app/main.py` gives them in order; the path is on the next line when the decorator is spread out.",
    "solution": "```text\n879  GET    /\n892  GET    /health\n909  GET    /rules\n924  GET    /rules/{rule_id}\n945  POST   /review\n1025 GET    /test-review\n1086 POST   /test-review\n1135 POST   /webhook\n1424 GET    /reviews\n1456 GET    /reviews/{review_id}\n1487 GET    /stats\n1510 POST   /users\n1554 GET    /users\n1576 PATCH  /users/{user_id}\n\n/test-review carries GET and POST; /users carries POST and GET.\nTwo methods on one path is two operations, not a duplicate registration.\n```",
    "explanation": "Twelve unique paths, fourteen decorators. The four extra decorators are the two pairs of methods — which is why the generated schema (lesson 4.4) still lists twelve."
  },
  "common_mistakes": [
    "Assuming the function name is the route — `def health()` is reachable at `/health` only because the decorator says so.",
    "Editing `summary` and expecting a behaviour change; it is documentation.",
    "Adding a second decorator for the same method and path, which silently replaces the first."
  ],
  "project_links": [
    {
      "label": "The health decorator and its handler",
      "path": "app/main.py",
      "lines": "892-908"
    },
    {
      "label": "A decorator spread over several lines",
      "path": "app/main.py",
      "lines": "924-944"
    }
  ],
  "learn_more": [
    {
      "label": "app/main.py — every route in file order",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/main.py"
    },
    {
      "label": "docs/learning/track-7-surfaces.md — the surfaces track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-7-surfaces.md"
    }
  ],
  "glossary_terms": [
    "decorator — the line above a function that registers it",
    "path operation — one method on one path",
    "tag — a documentation grouping",
    "405 — the method is not allowed on this path"
  ]
});
