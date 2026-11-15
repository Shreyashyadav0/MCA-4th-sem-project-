/* 4.4 — Response models and the generated OpenAPI schema
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "4.4",
  "part": 4,
  "part_title": "HTTP and FastAPI",
  "title": "Response models and the generated OpenAPI schema",
  "order": 404,
  "duration_min": 20,
  "concept_md": "### What leaves is also a contract\n\nA request model guards what comes in; `response_model=` guards what goes out. FastAPI validates the handler's return value against it and serialises only its fields — so a field the handler adds but the model does not declare is dropped, and one the model declares but the handler omits is a bug you see at once.\n\n```python\n@app.get(\"/health\", tags=[\"ops\"], summary=\"…\", response_model=HealthResponse)\n```\n\nThat is the same decorator as lesson 4.2, with one more argument.\n\n### The schema is generated, so it cannot drift\n\n`GET /openapi.json` is not a document someone maintains; it is computed from the decorators and the models at import time. `GET /docs` is a UI over the same document. That is why the endpoint list in the schema is trustworthy: to add a path to it you must add a route, and to add a field you must change a model.\n\nThe schema currently declares twelve paths:\n\n```text\n/, /health, /review, /reviews, /reviews/{review_id}, /rules, /rules/{rule_id},\n/stats, /test-review, /users, /users/{user_id}, /webhook\n```\n\nSeveral of those — `/reviews`, `/users`, `/stats` — are not mentioned in any lesson yet. They exist because the app grew; the schema reports what is there, not what is documented.\n\n### Why it matters for a reviewer\n\nA client can be generated from this schema, and it will be right. That is a stronger promise than a README: a stale README is a lie, a stale schema is impossible without the code being stale too.",
  "code_examples": [
    {
      "id": "4.4-ex-0",
      "lang": "console",
      "caption": "The generated schema, path by path",
      "code": "curl -s http://127.0.0.1:8000/openapi.json | python -c \"import json,sys; print(sorted(json.load(sys.stdin)['paths']))\"",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "['/', '/health', '/review', '/reviews', '/reviews/{review_id}', '/rules', '/rules/{rule_id}', '/stats', '/test-review', '/users', '/users/{user_id}', '/webhook']",
      "why_not": "a request needs a running app on a socket; the browser runner has Python but no server and no repository checkout."
    }
  ],
  "quiz": [
    {
      "q": "What does `response_model=` do to the handler's return value?",
      "options": [
        "Nothing — it is documentation only",
        "It validates and serialises it, dropping fields the model does not declare",
        "It converts it to a string",
        "It sets the status code"
      ],
      "answer": 1,
      "why": "The model filters and validates on the way out, which is why an extra key cannot leak even if the handler returns one."
    },
    {
      "q": "Why can the schema not drift from the code?",
      "options": [
        "A test regenerates it nightly",
        "It is written by hand and reviewed",
        "It is computed from the decorators and models at import time",
        "It is copied from the README"
      ],
      "answer": 2,
      "why": "There is no separate document to update: the same objects that route the request produce the schema."
    },
    {
      "q": "The schema lists `/stats`, which no lesson has mentioned. What follows?",
      "options": [
        "The endpoint exists and the schema reports the code as it is",
        "The schema is wrong",
        "The path is documented elsewhere",
        "It is a generated placeholder"
      ],
      "answer": 0,
      "why": "The schema describes the running app, not the curriculum — which is exactly why it is the safer source of truth about the surface."
    }
  ],
  "try_it": {
    "prompt": "Fetch the schema and find the response model declared for `/review`.",
    "starter": "",
    "solution": "```console\n$ curl -s http://127.0.0.1:8000/openapi.json | python -c \"import json,sys; d=json.load(sys.stdin); print(d['paths']['/review']['post']['responses']['200']['content']['application/json']['schema'])\"\n{'$ref': '#/components/schemas/ReviewResponse'}\n```",
    "explanation": "The `$ref` names the model, and `components.schemas.ReviewResponse` holds its fields — the same class the handler is annotated with."
  },
  "exercise": {
    "prompt": "Compare the twelve schema paths with the thirteen route decorators from lesson 4.2, and explain the difference.",
    "hint": "One path appears twice in the file.",
    "solution": "```text\nThe schema lists 12 paths; the file has 13 decorators. `/webhook` is decorated twice\n(1086 and 1135), and the later registration wins, so the schema has one entry for it.\nThat is the only discrepancy — every other decorator maps to exactly one path.\n```",
    "explanation": "A duplicate registration is invisible in the schema but visible in the file, which is why both are worth reading."
  },
  "common_mistakes": [
    "Treating `/openapi.json` as a hand-written document and editing it — it is regenerated on every import.",
    "Assuming `response_model` only documents; it also filters what the client receives.",
    "Reading the README for the endpoint list when the schema is one request away and always current."
  ],
  "project_links": [
    {
      "label": "The response model for a review",
      "path": "app/main.py",
      "lines": "260-311"
    },
    {
      "label": "A route that declares one",
      "path": "app/main.py",
      "lines": "892-908"
    }
  ],
  "learn_more": [
    {
      "label": "app/main.py — the models and their routes",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/main.py"
    },
    {
      "label": "docs/learning/track-7-surfaces.md — the surfaces track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-7-surfaces.md"
    }
  ],
  "glossary_terms": [
    "response model — the declared shape of what leaves the app",
    "OpenAPI — the machine-readable description of the API",
    "$ref — a pointer into the schema's components",
    "Swagger UI — the page at /docs that renders the schema"
  ]
});
