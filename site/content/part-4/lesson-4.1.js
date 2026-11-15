/* 4.1 — What HTTP is: one request, one response
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "4.1",
  "part": 4,
  "part_title": "HTTP and FastAPI",
  "title": "What HTTP is: one request, one response",
  "order": 401,
  "duration_min": 15,
  "concept_md": "### One question, one answer\n\nEvery call to this project's API is the same shape: the client sends **one request** and gets **one response**. A request is four things.\n\n- **Method** — the verb. `GET` asks for something; `POST` sends something.\n- **Path** — which resource. `/`, `/health`, `/rules`, `/review`.\n- **Headers** — metadata about the message, outside the body.\n- **Body** — the payload, usually absent on a `GET`.\n\nA response is a **status code** plus headers plus a body. The code is the part a program reads before it looks at anything else: `200` means the request was understood and answered, `404` means the path or the thing named in it does not exist, `422` means the body did not match what the endpoint expects.\n\n### Running it, or not\n\nThe app is served by `uvicorn app.main:app`, and that is what a `curl` in this part would talk to. Every capture in Part 4 was instead replayed in-process with `TestClient`, which needs no port at all — lesson 4.7 is about that. The bodies are identical either way. `curl -i` also prints `date`, `server` and `content-length`; those are elided in every capture here, so read the status line and the body.\n\n### Stateless, which is the whole design\n\nThe server keeps nothing between requests. Nothing about your last call changes this one; every request carries everything needed to answer it. That is why the API can be restarted at any moment, and why two identical requests get two identical answers here — there is no session to drift.\n\n### JSON is the body format\n\nBoth directions use JSON: an object with string keys. The `/` endpoint returns six fields, and reading them is the fastest way to learn what the service thinks it is:\n\n```text\n{\"name\": \"…\", \"version\": \"0.1.0\", \"mode\": \"mock\", \"rules\": 63,\n \"endpoints\": [\"/health\", …], \"docs\": \"/docs\"}\n```\n\n`mode` is `mock` because no provider is configured; `rules` is 63 because the rule engine is loaded; `endpoints` is the service describing its own surface. None of that is a status — the status is `200`, and it lives outside the body.",
  "code_examples": [
    {
      "id": "4.1-ex-0",
      "lang": "console",
      "caption": "The banner endpoint, read field by field",
      "code": "curl -s -i http://127.0.0.1:8000/",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "HTTP/1.1 200 OK\ncontent-type: application/json\n\n{\"name\":\"Autonomous AI Code Reviewer & PR Assistant\",\"version\":\"0.1.0\",\"mode\":\"mock\",\"rules\":63,\"endpoints\":[\"/health\",\"/rules\",\"/review\",\"/test-review\",\"/webhook\",\"/docs\"],\"docs\":\"/docs\"}",
      "why_not": "there is no fastapi in the browser runner and no repository checkout to import from, so the app cannot be built at all."
    }
  ],
  "quiz": [
    {
      "q": "Where does the status code live?",
      "options": [
        "Inside the JSON body, as a field",
        "In the request headers",
        "Outside the body, on the response itself",
        "Nowhere — the body says everything"
      ],
      "answer": 2,
      "why": "The body of `/` has no status field at all: 200 is a property of the response, which is why a client checks it before parsing anything."
    },
    {
      "q": "What does `mode: \"mock\"` in that body tell you?",
      "options": [
        "That no provider is configured, so the rules answered",
        "That the request failed and was retried once",
        "That the answer was served from a cache",
        "That this endpoint is read-only by design"
      ],
      "answer": 0,
      "why": "It is the service reporting which reviewer produced the result — the same fact the CLI prints as `mode : mock`."
    },
    {
      "q": "The server keeps nothing between requests. What follows?",
      "options": [
        "Two identical requests can give different answers",
        "The server cannot return JSON",
        "The client must send a session cookie",
        "Every request must carry everything needed to answer it"
      ],
      "answer": 3,
      "why": "Stateless means the request is the whole context; there is no session state to carry information from the previous call."
    }
  ],
  "try_it": {
    "prompt": "Run the banner endpoint and pick out the three fields that describe the service rather than the answer.",
    "starter": "",
    "solution": "```console\n$ curl -s http://127.0.0.1:8000/\n{\"name\":\"…\",\"version\":\"0.1.0\",\"mode\":\"mock\",\"rules\":63,\"endpoints\":[…],\"docs\":\"/docs\"}\n```",
    "explanation": "`mode`, `rules` and `endpoints` describe the running service; `name` and `version` identify it; `docs` points at the generated UI. The status is still the only thing that says whether the call worked."
  },
  "exercise": {
    "prompt": "Given the `/health` response, sort its fields into status and payload, and say which one a load balancer would read.",
    "hint": "One field answers 'is it up'; the rest describe the configuration.",
    "solution": "```text\nstatus      \"ok\"            — the answer to \"is it up\"\nmode        \"mock\"          — which reviewer is configured\nrules       63              — the rule engine is loaded\ncategories  [10 names]      — the rule categories in use\nsarvam_key  \"missing\"       — credential state, not a secret\ngithub_token, webhook_secret, database …\n\nA load balancer reads the status code (200), not the body: the body is for a human\ndeciding why it is up.\n```",
    "explanation": "The split matters: a health check is judged on the status code, while the body exists to explain the configuration when something looks wrong."
  },
  "common_mistakes": [
    "Reading the body before the status code, so a 404's `{\"detail\": …}` is parsed as if it were data.",
    "Treating `mode` or `rules` as part of the protocol — they are this service's own fields, not HTTP.",
    "Assuming a `GET` can carry a body; this API sends data on `POST` only."
  ],
  "project_links": [
    {
      "label": "The banner endpoint",
      "path": "app/main.py",
      "lines": "879-890"
    },
    {
      "label": "What the service says it is",
      "path": "README.md",
      "lines": "1-40"
    }
  ],
  "learn_more": [
    {
      "label": "README.md — the endpoints table",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/README.md"
    },
    {
      "label": "docs/learning/track-7-surfaces.md — the surfaces track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-7-surfaces.md"
    }
  ],
  "glossary_terms": [
    "method — the verb of a request, such as GET or POST",
    "status code — the three-digit answer, outside the body",
    "stateless — the server keeps nothing between requests",
    "JSON — the object format both directions use"
  ]
});
