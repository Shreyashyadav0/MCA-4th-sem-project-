/* 9.5 — The zero-network proof
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "9.5",
  "part": 9,
  "part_title": "Configuration and offline-first",
  "title": "The zero-network proof",
  "order": 905,
  "duration_min": 30,
  "concept_md": "### A claim needs a test\n\n\"Works offline\" is easy to say and easy to break. `scripts/verify_offline.py` proves it: it patches the socket layer so any outbound connection raises, then runs the suite. If a test secretly calls the network, it fails.\n\n### How the block works\n\n`block_network()` replaces the connect functions on `socket.socket` and `socket.create_connection` with a refusal that records what was attempted. Loopback is exempt — `localhost`, `127.0.0.1` and `::1` are allowed, because a local model server and an in-process test client both need it.\n\n### Why loopback is exempt\n\nBecause \"offline\" means \"no internet\", not \"no sockets\". A test that binds an ephemeral port to check a webhook signature is still offline. Refusing loopback would make the proof impossible to run rather than stronger.\n\n### What it does not prove\n\nThat the code makes no HTTP call at all — only that it makes none when the suite runs. A code path no test reaches could still call out, which is why the coverage of the suite is part of the argument.",
  "code_examples": [
    {
      "id": "9.5-ex-0",
      "lang": "console",
      "caption": "The loopback set, and what counts as local",
      "code": "python - <<'PY'\nfrom scripts.verify_offline import LOOPBACK_HOSTS\n\nprint(sorted(LOOPBACK_HOSTS))\nfor host in (\"\", \"localhost\", \"127.0.0.1\", \"example.com\"):\n    print(\"%-12s loopback=%s\" % (host or \"(empty)\", host in LOOPBACK_HOSTS))\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "['', '127.0.0.1', '::1', 'localhost', 'localhost.localdomain']\n(empty)      loopback=True\nlocalhost    loopback=True\n127.0.0.1    loopback=True\nexample.com  loopback=False",
      "why_not": "the browser runner does not embed app/config.py, and it needs pydantic-settings; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "What does the proof patch?",
      "options": [
        "The HTTP client library",
        "The socket connect functions",
        "The DNS resolver alone",
        "The pytest collection stage here"
      ],
      "answer": 1,
      "why": "Patching connect at the socket layer catches every client, rather than one library's calls."
    },
    {
      "q": "Why is loopback exempt?",
      "options": [
        "Because pytest binds a local port",
        "Because tests need a real server",
        "Offline means no internet, not no sockets",
        "Because the patch cannot ever see it at all"
      ],
      "answer": 2,
      "why": "A local model and an in-process test client both use loopback, and neither is a network call."
    },
    {
      "q": "What does the proof not establish?",
      "options": [
        "That a call would be recorded",
        "That the suite passes offline",
        "That loopback still works fine for tests",
        "That unreached code never calls out"
      ],
      "answer": 3,
      "why": "It only proves the paths the suite exercises; an untested branch could still reach the network."
    }
  ],
  "try_it": {
    "prompt": "Show which hosts the blocker refuses and which it allows.",
    "starter": "",
    "solution": "```python\nfrom scripts.verify_offline import LOOPBACK_HOSTS\n\nfor host in (\"example.com\", \"localhost\"):\n    print(host, \"allowed\" if host in LOOPBACK_HOSTS else \"blocked\")\n```",
    "explanation": "A public name is blocked and a loopback name is allowed, which is the whole policy in two lines."
  },
  "exercise": {
    "prompt": "Which five host spellings are treated as loopback? Read the set rather than guessing.",
    "hint": "The empty string counts as local.",
    "solution": "```python\nfrom scripts.verify_offline import LOOPBACK_HOSTS\n\nprint(len(LOOPBACK_HOSTS), sorted(LOOPBACK_HOSTS))\n```",
    "explanation": "Five, including the empty string — an empty host means a local bind rather than a remote address."
  },
  "common_mistakes": [
    "Assuming the proof covers code the suite never runs.",
    "Blocking loopback, which makes the local provider untestable.",
    "Reading 'offline' as 'no sockets at all'."
  ],
  "project_links": [
    {
      "label": "The loopback set",
      "path": "scripts/verify_offline.py",
      "lines": "45"
    },
    {
      "label": "The refusal that records the attempt",
      "path": "scripts/verify_offline.py",
      "lines": "54-65"
    }
  ],
  "learn_more": [
    {
      "label": "scripts/verify_offline.py",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/scripts/verify_offline.py"
    },
    {
      "label": "Makefile — the verify target",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/Makefile"
    }
  ],
  "glossary_terms": [
    "loopback — an address that never leaves the machine",
    "monkeypatch — replacing a function for the duration of a run",
    "zero-network — no connection outside the machine"
  ]
});
