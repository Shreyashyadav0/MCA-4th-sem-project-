/* 4.5 — Status codes, and raising HTTPException
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "4.5",
  "part": 4,
  "part_title": "HTTP and FastAPI",
  "title": "Status codes, and raising HTTPException",
  "order": 405,
  "duration_min": 20,
  "concept_md": "### Three families, three meanings\n\nThe first digit is the whole story. **2xx** means the request was understood and answered. **4xx** means the client asked for something impossible. **5xx** means the server failed while doing something reasonable.\n\nThe mistake this lesson exists to prevent is answering a client error with `200`. A body that says `{\"ok\": false}` under a 200 status is invisible to every proxy, monitor and retry policy in the path; they read the code and see success.\n\n### Raising, not returning\n\n```python\nraise HTTPException(status_code=404, detail=f\"no rule with id {rule_id!r}\")\n```\n\nFastAPI turns that into the response: the status becomes 404 and the body becomes `{\"detail\": …}`. Raising is better than returning a tuple because the function's happy path stays straight — the error leaves from where it happened.\n\n### The codes this lesson points at\n\n| Code | Where | What the client did |\n|---|---|---|\n| 403 | `app/main.py:427` | asked for a path outside the project |\n| 404 | `:429`, `:935` | named a file that is not readable, or a rule id that does not exist |\n| 422 | `:664`, `:668`, `:1022`, `:1061` | sent a body that cannot be parsed or is missing both fields |\n| 503 | `:627` | asked for review history while storage is unavailable |\n| 401 | `:1178` | sent a webhook whose signature did not match |\n| 400 | `:1183` | sent a webhook body that is not JSON |\n| 409 | `:1543` | tried to register a user that already exists |\n\nEach is a client-side problem with a different fix, which is why they are not all 400.\n\n### The detail is for a human\n\n`detail` is prose, not a code. A client should branch on the status; the sentence is for whoever reads the log. That is why `{\"detail\": \"no rule with id 'nope'\"}` names the id it looked for.",
  "code_examples": [
    {
      "id": "4.5-ex-0",
      "lang": "console",
      "caption": "A 404 with a sentence that names what was missing",
      "code": "curl -s -w '\\n%{http_code}\\n' http://127.0.0.1:8000/rules/nope",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "{\"detail\":\"no rule with id 'nope'\"}\n404",
      "why_not": "there is no fastapi in the browser runner and no repository checkout to import from, so the app cannot be built at all."
    }
  ],
  "quiz": [
    {
      "q": "A handler returns 200 with `{\"ok\": false}`. What is wrong with that?",
      "options": [
        "Nothing — the body already says it failed",
        "The body is not valid JSON at all",
        "Proxies and monitors read the status only",
        "A client cannot parse a false boolean"
      ],
      "answer": 2,
      "why": "Everything in the request path branches on the status code; a failure hidden in a 200 body reaches none of it."
    },
    {
      "q": "Why `raise HTTPException` rather than returning an error object?",
      "options": [
        "The happy path stays straight and the error leaves where it happened",
        "Raising is measurably faster than returning",
        "FastAPI cannot serialise a returned error object on its own, so it needs a handler",
        "Raising sets the status and returning cannot"
      ],
      "answer": 0,
      "why": "The handler keeps one shape; FastAPI converts the exception into the status and the `detail` body."
    },
    {
      "q": "`503` at `app/main.py:627` — what is the client's correct response?",
      "options": [
        "Fix the request and resend it",
        "Re-authenticate",
        "Give up: the request will never work, so no retry is worth making",
        "Retry later: the server could not do it now"
      ],
      "answer": 3,
      "why": "503 is a server-side, temporary condition — the mirror of 422, where the request itself is what must change."
    }
  ],
  "try_it": {
    "prompt": "Request a rule id that does not exist and read the sentence. Then request one that does, and compare the status.",
    "starter": "",
    "solution": "```console\n$ curl -s -o /dev/null -w '%{http_code}\\n' http://127.0.0.1:8000/rules/nope\n404\n$ curl -s -o /dev/null -w '%{http_code}\\n' http://127.0.0.1:8000/rules/auth/verify-false-jwt\n200\n```",
    "explanation": "The status is the branch; the `detail` sentence is the explanation. One id is unknown, the other is the first rule in the registry."
  },
  "exercise": {
    "prompt": "A client sends `POST /review` with a body of `{}`. Predict the status and the shape of `detail`, then say which layer produces each and how a client should tell them apart.",
    "hint": "Two layers can both answer 422; only one of them writes a list.",
    "solution": "```text\nStatus: 422.\nShape:  {\"detail\": \"provide either 'diff' or 'code'\"} — a sentence, not a list.\n\nThe model accepted the body (both fields are optional), so the handler raised it.\nA framework 422 carries a list whose entries have loc/type/msg; a handler 422 carries\none sentence. A client branches on isinstance(detail, list), not on the status.\n```",
    "explanation": "The status alone does not tell you which layer spoke; the type of `detail` does, and that is the thing to branch on."
  },
  "common_mistakes": [
    "Returning 200 for a client error so the dashboard stays green.",
    "Using 500 for something the client could fix; the client will not try.",
    "Putting a machine-readable code in `detail` and parsing it — branch on the status instead."
  ],
  "project_links": [
    {
      "label": "The 403 and 404 raises",
      "path": "app/main.py",
      "lines": "415-430"
    },
    {
      "label": "The unknown-rule 404",
      "path": "app/main.py",
      "lines": "931-942"
    },
    {
      "label": "The signature 401",
      "path": "app/main.py",
      "lines": "1135-1261"
    }
  ],
  "learn_more": [
    {
      "label": "app/main.py — every raise site",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/main.py"
    },
    {
      "label": "docs/learning/track-7-surfaces.md — the surfaces track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-7-surfaces.md"
    }
  ],
  "glossary_terms": [
    "HTTPException — FastAPI's way to end a request with a status and a detail",
    "2xx / 4xx / 5xx — answered / client error / server error",
    "detail — the human sentence in an error body"
  ]
});
