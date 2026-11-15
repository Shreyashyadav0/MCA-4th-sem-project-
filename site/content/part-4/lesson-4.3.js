/* 4.3 — The request body is a Pydantic model
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "4.3",
  "part": 4,
  "part_title": "HTTP and FastAPI",
  "title": "The request body is a Pydantic model",
  "order": 403,
  "duration_min": 25,
  "concept_md": "### The model is the contract\n\n`POST /review` accepts a body that FastAPI validates against `ReviewRequest`. If the declared model is the contract, then the model's fields are the API: a field you add to the class becomes an accepted field, and one you remove becomes a 422.\n\n```python\nclass ReviewRequest(BaseModel):\n    model_config = ConfigDict(extra=\"forbid\")\n    diff: str | None = None\n    code: str | None = None\n```\n\n### Two different 422s\n\nThis distinction is the point of the lesson. A **422 raised by FastAPI** happens before your function runs: the body did not match the model. Its `detail` is a **list** of entries, each naming a location:\n\n```text\n{\"detail\": [{\"type\": \"extra_forbidden\", \"loc\": [\"body\", \"nope\"], …}]}\n```\n\nA **422 raised by your own code** is a plain sentence, because it is an `HTTPException` you wrote:\n\n```text\n{\"detail\": \"provide either 'diff' or 'code'\"}\n```\n\nSame status, different shape — and a client that parses one will misread the other. That is why the model carries `extra=\"forbid\"`: an unknown field is a client bug, and it should be reported as one rather than silently dropped.\n\n### Neither field is required\n\nBoth `diff` and `code` are optional, so `{}` is a valid *body* — it fails later, in the handler, with the sentence above. The model says \"you may send either\"; the handler says \"you must send one\". Contracts in two layers, each with its own error.",
  "code_examples": [
    {
      "id": "4.3-ex-0",
      "lang": "console",
      "caption": "An empty body: valid model, rejected by the handler",
      "code": "curl -s -i -X POST http://127.0.0.1:8000/review -H \"content-type: application/json\" -d \"{}\"",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "HTTP/1.1 422 Unprocessable Entity\ncontent-type: application/json\n\n{\"detail\":\"provide either 'diff' or 'code'\"}",
      "why_not": "a request needs a running app on a socket; the browser runner has Python but no server and no repository checkout."
    },
    {
      "id": "4.3-ex-1",
      "lang": "console",
      "caption": "An unknown field: rejected by the model, before any handler runs",
      "code": "curl -s -i -X POST http://127.0.0.1:8000/review -H \"content-type: application/json\" -d '{\"diff\": \"x\", \"nope\": 1}'",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "HTTP/1.1 422 Unprocessable Entity\ncontent-type: application/json\n\n{\"detail\":[{\"type\":\"extra_forbidden\",\"loc\":[\"body\",\"nope\"],\"msg\":\"Extra inputs are not permitted\",\"input\":1}]}",
      "why_not": "a request needs a running app on a socket; the browser runner has Python but no server and no repository checkout."
    }
  ],
  "quiz": [
    {
      "q": "Which 422 comes from the framework rather than your code?",
      "options": [
        "The one whose detail is a plain sentence",
        "Neither — every 422 is raised by you",
        "Both shapes come from your own code",
        "The one whose detail is a list with loc"
      ],
      "answer": 3,
      "why": "A list with locations is FastAPI's validation report; a sentence is an `HTTPException` you raised yourself."
    },
    {
      "q": "Why does `ReviewRequest` set `extra=\"forbid\"`?",
      "options": [
        "To make every declared field required",
        "So an unknown key is an error, not a shrug",
        "To make parsing measurably faster",
        "To allow either diff or code, not both"
      ],
      "answer": 1,
      "why": "Silently ignoring `nope` would let a client believe it sent something meaningful; forbidding turns it into a named error."
    },
    {
      "q": "`{}` is rejected with a sentence, not a list. What does that tell you?",
      "options": [
        "The body did not match the model",
        "The endpoint path does not exist",
        "The body was valid; the handler refused",
        "The request carried no content type"
      ],
      "answer": 2,
      "why": "Both fields are optional, so an empty object is a valid model; the sentence is the handler's own check firing afterwards."
    }
  ],
  "try_it": {
    "prompt": "Send `{\"diff\": \"x\"}` — a field that exists but holds a diff with no file headers. Read the `detail` and say which layer rejected it.",
    "starter": "",
    "solution": "```console\n$ curl -s -X POST http://127.0.0.1:8000/review -H \"content-type: application/json\" -d '{\"diff\": \"x\"}'\n{\"detail\":\"cannot parse diff: no file headers found; expected 'diff --git' or a '--- / +++' pair\"}\n```",
    "explanation": "A sentence, so it came from the handler after the model accepted the body — the diff parsed to nothing usable."
  },
  "exercise": {
    "prompt": "Predict the status and the shape of `detail` for three bodies: `{}`, `{\"nope\": 1}`, and `{\"diff\": \"x\"}`. Then check all three.",
    "hint": "Ask which layer sees each one first: the model, or the handler.",
    "solution": "```text\n{}                 422, detail is a sentence   (model ok, handler says \"provide either …\")\n{\"nope\": 1}        422, detail is a list       (model rejects the unknown key)\n{\"diff\": \"x\"}      422, detail is a sentence   (model ok, the diff does not parse)\n```",
    "explanation": "Two of the three reach the handler; only the unknown key is stopped by the model. The status is identical, so only the shape of `detail` tells you which."
  },
  "common_mistakes": [
    "Parsing `detail` as a string when it can be a list — check its type before reading it.",
    "Assuming an optional field means the endpoint accepts a body without it.",
    "Adding a field to the request in a client and expecting the server to ignore it; `extra=\"forbid\"` refuses it."
  ],
  "project_links": [
    {
      "label": "The request model",
      "path": "app/main.py",
      "lines": "152-207"
    },
    {
      "label": "The review endpoint that consumes it",
      "path": "app/main.py",
      "lines": "945-1024"
    }
  ],
  "learn_more": [
    {
      "label": "app/main.py — the request and response models",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/main.py"
    },
    {
      "label": "docs/learning/track-1-models.md — the models track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-1-models.md"
    }
  ],
  "glossary_terms": [
    "request body — the payload a POST carries",
    "422 — the body was understood and rejected",
    "extra_forbidden — the error for an undeclared field",
    "loc — the path to the offending part of the body"
  ]
});
