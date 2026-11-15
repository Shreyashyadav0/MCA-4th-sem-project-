/* 3.8 — Proving the suite is offline
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "3.8",
  "part": 3,
  "part_title": "Testing with pytest",
  "title": "Proving the suite is offline",
  "order": 308,
  "duration_min": 30,
  "concept_md": "### A claim needs a proof\n\n\"The suite needs no network\" is a claim about every test, including the ones not written yet. The way to keep it true is to make a connection attempt fail loudly inside the process that runs the tests.\n\n`scripts/verify_offline.py` patches three things before pytest starts:\n\n- `socket.create_connection` — raises for every destination.\n- `socket.getaddrinfo` — raises for every non-loopback hostname.\n- `socket.socket` — constructing a new AF_INET socket raises.\n\nThen it runs the suite in-process with `pytest.main`. If any test tries to reach the network, the test fails and the proof fails.\n\n### Why loopback and AF_UNIX stay allowed\n\nasyncio builds its event loop's self-pipe with `socket.socketpair()`, which constructs a `socket.socket` from an existing file descriptor. Blocking that breaks the event loop for reasons that have nothing to do with the network. The patch allows AF_UNIX and loopback so the harness itself can run, while every real destination is refused.\n\n### Doing it by hand\n\n```python\nimport socket\nsocket.create_connection = lambda *a, **k: (_ for _ in ()).throw(OSError(\"network disabled\"))\n```\n\nOne line, and any code that dials out now raises. That is the whole technique: replace the seam, not the caller.\n\n### What it does not prove\n\nThat no test *would* use the network on another machine — only that none does here, under these patches. It is evidence, and the reason the README can say \"no network\" without an asterisk.",
  "code_examples": [
    {
      "id": "3.8-ex-0",
      "lang": "python",
      "caption": "Patch the seam, dial out, watch it refuse — the technique verify_offline.py uses",
      "code": "import socket\n\nreal_create = socket.create_connection\n\n\ndef refuse(*args, **kwargs):\n    raise OSError(\"network disabled\")\n\n\nsocket.create_connection = refuse\ntry:\n    socket.create_connection((\"example.com\", 443), timeout=1)\nexcept OSError as error:\n    print(\"blocked:\", error)\n\nsocket.create_connection = real_create\nprint(\"restored:\", socket.create_connection is real_create)\n",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "blocked: network disabled\nrestored: True"
    }
  ],
  "quiz": [
    {
      "q": "What does `verify_offline.py` patch before running the suite?",
      "options": [
        "Only `requests.get`",
        "The DNS resolver only",
        "`socket.create_connection`, `socket.getaddrinfo` and `socket.socket`",
        "Nothing; it runs with the network off"
      ],
      "answer": 2,
      "why": "Three seams, because a library can dial out by any of them — patching one leaves the others open."
    },
    {
      "q": "Why are loopback and AF_UNIX allowed through?",
      "options": [
        "Because tests need localhost",
        "They are not allowed",
        "Because they are faster",
        "Because asyncio's event loop builds a self-pipe with a socket"
      ],
      "answer": 3,
      "why": "Blocking the event loop's own self-pipe breaks every async test for a reason unrelated to the network."
    },
    {
      "q": "What does the proof not establish?",
      "options": [
        "That pytest imported the patches before collection",
        "That no test would use the network on a machine without the patches",
        "That the patches were applied before pytest started",
        "That the suite passed while the patches were in place"
      ],
      "answer": 1,
      "why": "It is evidence about this run under these patches — which is exactly what the README claims, no more."
    }
  ],
  "try_it": {
    "prompt": "Patch `socket.getaddrinfo` instead and try to resolve a hostname. Then try `localhost`.",
    "starter": "import socket\n\nreal = socket.getaddrinfo\n\n\ndef refuse(host, *args, **kwargs):\n    raise OSError(\"dns disabled\")\n\n\nsocket.getaddrinfo = refuse\n",
    "solution": "import socket\n\nreal = socket.getaddrinfo\n\n\ndef refuse(host, *args, **kwargs):\n    if host in (\"localhost\", \"127.0.0.1\"):\n        return real(host, *args, **kwargs)\n    raise OSError(\"dns disabled\")\n\n\nsocket.getaddrinfo = refuse\nfor host in (\"example.com\", \"localhost\"):\n    try:\n        socket.getaddrinfo(host, 80)\n        print(host, \"resolved\")\n    except OSError as error:\n        print(host, \"blocked:\", error)\n",
    "explanation": "`example.com` is refused and `localhost` resolves — the same loopback exception the real script makes, and for the same reason."
  },
  "exercise": {
    "prompt": "Read `scripts/verify_offline.py` and explain, in three lines, why it patches three seams rather than one.",
    "hint": "Each seam is a different way out.",
    "solution": "```text\n1. create_connection covers the common path: a library that dials a host and port.\n2. getaddrinfo covers resolution, which happens before a connection and uses no socket.\n3. socket.socket covers a library that builds its own socket and connects it directly.\nPatching one leaves the other two open, so the proof would be a claim about one code path.\n```",
    "explanation": "A proof is only as good as its coverage of the ways out; the script closes three and says which two stay open on purpose."
  },
  "common_mistakes": [
    "Patching `requests.get` only, so a library using `httpx` or a raw socket sails past.",
    "Forgetting to restore the patched function, leaving later code in the process unable to dial out.",
    "Claiming \"the suite needs no network\" without running the proof on every push."
  ],
  "project_links": [
    {
      "label": "The three patches, and why loopback is exempt",
      "path": "scripts/verify_offline.py",
      "lines": "1-47"
    },
    {
      "label": "The offline decision this proof protects",
      "path": "docs/decisions/0002-offline-first-fallback.md",
      "lines": "1-31"
    }
  ],
  "learn_more": [
    {
      "label": "ADR 0002 — offline-first fallback",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0002-offline-first-fallback.md"
    },
    {
      "label": "docs/learning/track-4-offline-and-config.md — the offline track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-4-offline-and-config.md"
    }
  ],
  "glossary_terms": [
    "seam — a substitutable point where a test can intervene",
    "monkeypatch of a module attribute — replacing a function for the process",
    "loopback — 127.0.0.1, allowed so the harness can run"
  ]
});
