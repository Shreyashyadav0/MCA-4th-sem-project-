/* 12.5 — ADR 0005: a 422 demotes one finding, never the post
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "12.5",
  "part": 12,
  "part_title": "Surfaces: CLI, API, webhook, GitHub",
  "title": "ADR 0005: a 422 demotes one finding, never the post",
  "order": 1205,
  "duration_min": 25,
  "concept_md": "### The failure\n\nGitHub rejects an inline comment anchored to a line that is not part of the diff with HTTP 422. Our anchor is computed from a parsed diff and a canonicalised path, so the 422 should be rare — but a force-push, a rename or a differently spelled path can make GitHub's diff disagree with ours.\n\n### The decision\n\nA 422 demotes **that one finding** into the summary comment. The rest of the post continues, and the run does not fail. `inline_demoted` counts how many were moved.\n\n### Why not fail the post\n\nBecause one bad anchor out of ten would discard nine good comments and mark the check red. The reviewer would learn that the tool is flaky rather than that one line moved.\n\n### Why not retry\n\nA 422 is not transient. Retrying the same anchor produces the same 422, and the only thing a retry buys is a slower failure. The demotion is the retry: the finding still reaches the reader, in the summary instead of on the line.\n\n### What the reader sees\n\nA summary comment that lists the demoted findings with their file and line, so nothing is silently dropped — a demotion is visible, which is the whole difference between this and a silent skip.",
  "code_examples": [
    {
      "id": "12.5-ex-0",
      "lang": "console",
      "caption": "The demotion counter",
      "code": "python - <<'PY'\nimport pathlib\n\nsrc = pathlib.Path(\"app/github_client.py\").read_text()\nfor n, line in enumerate(src.splitlines(), 1):\n    if \"inline_demoted\" in line:\n        print(n, line.strip()[:64])\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "216 inline_demoted: Number of inline comments moved into the summary\n225 inline_demoted: int\n1031 demoted (``inline_demoted``) and the summary is still posted, so",
      "why_not": "the browser runner has no shell and does not embed the surface modules; this command runs from a checkout."
    }
  ],
  "quiz": [
    {
      "q": "What does a 422 demote?",
      "options": [
        "The whole post, into a comment",
        "That one finding, to the summary",
        "The whole review, into a mock run",
        "The anchor, down to the file level"
      ],
      "answer": 1,
      "why": "One bad anchor out of ten should not discard nine good comments."
    },
    {
      "q": "Why not retry a 422?",
      "options": [
        "It costs a rate-limit slot",
        "The token has expired",
        "It is not transient",
        "The diff has been closed"
      ],
      "answer": 2,
      "why": "The same anchor produces the same rejection; a retry only makes the failure slower."
    },
    {
      "q": "Where does a demoted finding end up?",
      "options": [
        "In the check-run output",
        "In the review body only",
        "Nowhere at all; it is dropped",
        "In the summary comment itself"
      ],
      "answer": 3,
      "why": "A demotion is visible: the finding still reaches the reader, with its file and line."
    }
  ],
  "try_it": {
    "prompt": "Find where the demotion count is recorded.",
    "starter": "",
    "solution": "```console\n$ grep -n 'inline_demoted' app/github_client.py app/main.py\n```",
    "explanation": "A counter on the posting result, so the API response can report how many were moved."
  },
  "exercise": {
    "prompt": "Which HTTP status does GitHub return for a bad anchor, and what does the code do with it?",
    "hint": "One status, one demotion.",
    "solution": "```console\n$ grep -n '422' app/github_client.py | head -3\n```\n\n422 — the finding is rebuilt into the summary rather than retried or raised.",
    "explanation": "The status is treated as a fact about one anchor, not about the post."
  },
  "common_mistakes": [
    "Failing the whole post on one 422.",
    "Retrying the same anchor, which cannot succeed.",
    "Dropping the demoted finding instead of summarising it."
  ],
  "project_links": [
    {
      "label": "The demotion counter",
      "path": "app/main.py",
      "lines": "209-224"
    },
    {
      "label": "The posting result it lands on",
      "path": "app/github_client.py",
      "lines": "160-200"
    }
  ],
  "learn_more": [
    {
      "label": "ADR 0005 — the demotion",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0005-422-demotes-single-finding-not-whole-post.md"
    },
    {
      "label": "app/github_client.py",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/github_client.py"
    }
  ],
  "glossary_terms": [
    "anchor — the line a comment is attached to",
    "demote — move a comment into the summary",
    "422 — GitHub's rejection of an unanchorable comment"
  ]
});
