/* 4.7 — Testing an API in-process with TestClient
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "4.7",
  "part": 4,
  "part_title": "HTTP and FastAPI",
  "title": "Testing an API in-process with TestClient",
  "order": 407,
  "duration_min": 25,
  "concept_md": "### No socket, no port, no network\n\n`TestClient` drives the ASGI application directly in the current process. There is no server listening and no connection made, so a request costs a function call rather than a round trip — and the API can be tested on a machine with the network switched off.\n\n```python\nfrom fastapi.testclient import TestClient\nfrom app.main import app\n\nclient = TestClient(app)\nresponse = client.get(\"/rules/nope\")\n```\n\n`tests/test_api.py` does exactly this: the import at line 17 and `client = TestClient(app)` at line 23, once, for the whole file.\n\n### Why that is the right default here\n\nThe project's promise is that it works with no network and no credentials. A test that reached a real port would quietly break that promise the first time CI had no loopback. Driving the app in-process makes the claim testable, and `scripts/verify_offline.py` makes it enforceable by refusing outbound sockets before the suite starts.\n\n### Every capture in this part was produced this way\n\nThe responses quoted throughout Part 4 came from a script that imported `app`, built a `TestClient`, and printed `response.status_code` and `response.text`. No `uvicorn` process was involved. That is also how you would check a change: import, call, assert on the status and the body.\n\n### What it does not prove\n\nIt does not prove the app works behind a real server, a proxy, or a TLS terminator, and it does not render `/docs` in a browser. It proves the application layer, which is where the contracts live.",
  "code_examples": [
    {
      "id": "4.7-ex-0",
      "lang": "console",
      "caption": "A request and its status, in one process",
      "code": "python -c \"from fastapi.testclient import TestClient; from app.main import app; \\\nc = TestClient(app); r = c.get('/rules/nope'); print(r.status_code, r.json())\"",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "404 {'detail': \"no rule with id 'nope'\"}",
      "why_not": "it imports the application and needs an installed fastapi plus the repository on disk; the browser runner has neither."
    }
  ],
  "quiz": [
    {
      "q": "What does `TestClient` actually do with a request?",
      "options": [
        "Starts a uvicorn server on a random port",
        "Sends a real HTTP request over loopback",
        "Calls the handler function directly, skipping routing, which is what a unit test does",
        "Drives the ASGI application in-process, with no socket"
      ],
      "answer": 3,
      "why": "It speaks ASGI to the app object in the same process — routing, validation and serialisation all run, but nothing listens."
    },
    {
      "q": "Why does that matter for this project's offline claim?",
      "options": [
        "It makes the whole suite run faster",
        "A test needing a port would break the offline promise",
        "It removes the need for any assertions",
        "It lets the tests run without Python installed, which is not the reason"
      ],
      "answer": 1,
      "why": "The suite's zero-network promise is only true if the tests never open a socket; in-process requests make that structural."
    },
    {
      "q": "What can a TestClient test not prove?",
      "options": [
        "That request routing resolves correctly",
        "That the response model filters its own output",
        "That the app works behind a proxy or TLS",
        "That a 404 carries a detail string"
      ],
      "answer": 2,
      "why": "The application layer is what it exercises; deployment concerns live outside the process."
    }
  ],
  "try_it": {
    "prompt": "Call `/health` with TestClient and print only the status code.",
    "starter": "",
    "solution": "```console\n$ python -c \"from fastapi.testclient import TestClient; from app.main import app; \\\n  print(TestClient(app).get('/health').status_code)\"\n200\n```",
    "explanation": "One import, one call, one integer — and no server was started at any point."
  },
  "exercise": {
    "prompt": "Write the test that would catch a `/rules` endpoint returning 62 rules instead of the registered count.",
    "hint": "Assert against the registry, not against a literal.",
    "solution": "```python\nfrom app.main import app\nfrom app.rules import RULES\nfrom fastapi.testclient import TestClient\n\nclient = TestClient(app)\n\n\ndef test_rules_endpoint_lists_every_registered_rule() -> None:\n    response = client.get(\"/rules\")\n    assert response.status_code == 200\n    assert len(response.json()) == len(RULES)\n```",
    "explanation": "Asserting against `len(RULES)` catches a dropped rule without hard-coding a number that a later wave would have to edit."
  },
  "common_mistakes": [
    "Hard-coding a count in the assertion, so adding a rule breaks an unrelated test.",
    "Starting a real server in a unit test, which reintroduces the port and the network.",
    "Asserting only the status and never the body, which misses a wrong payload under a 200."
  ],
  "project_links": [
    {
      "label": "The TestClient import and the single client",
      "path": "tests/test_api.py",
      "lines": "17-23"
    },
    {
      "label": "A request asserted on status and body",
      "path": "tests/test_api.py",
      "lines": "135-152"
    }
  ],
  "learn_more": [
    {
      "label": "tests/test_api.py — the API tests",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/tests/test_api.py"
    },
    {
      "label": "TESTING.md — how the suite is run",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/TESTING.md"
    }
  ],
  "glossary_terms": [
    "TestClient — a client that calls the ASGI app object directly instead of opening a socket",
    "ASGI — the interface between a Python web app and the server that drives it",
    "in-process — the app runs in the same interpreter, so no port is bound and no packet is sent"
  ]
});
