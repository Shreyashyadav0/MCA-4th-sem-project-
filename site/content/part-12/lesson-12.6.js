/* 12.6 — The idempotency marker and the fingerprint
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "12.6",
  "part": 12,
  "part_title": "Surfaces: CLI, API, webhook, GitHub",
  "title": "The idempotency marker and the fingerprint",
  "order": 1206,
  "duration_min": 25,
  "concept_md": "### The problem\n\nA webhook can be delivered twice. Re-running a review that has already posted must not post again — a duplicate comment on someone's pull request is worse than no comment.\n\n### The marker\n\nEvery posted body ends with one line:\n\n```html\n<!-- ai-code-reviewer:<fingerprint> -->\n```\n\nThe prefix is the constant `COMMENT_MARKER_PREFIX`, `<!-- ai-code-reviewer:`. The form is exact: an HTML comment, so it renders as nothing, and a marker a later run can find without guessing.\n\n### The fingerprint\n\nSixteen lowercase hex characters, a SHA-256 prefix over exactly four fields joined by a unit separator: `file`, `line`, `severity` and the whitespace-collapsed `issue`. The suggested fix is deliberately excluded — rewording the advice must not make the same finding look new.\n\n### Why those four\n\nThey are the finding's identity. Change the file or the line and it is a different finding; change the wording of the fix and it is the same finding with better advice. Hashing the whole object would make every edit a new comment.\n\n### How it is used\n\nA re-run computes the fingerprint, looks for the marker in the existing comments, and skips what it already posted — which is why the CLI can report `skipped_dup` and still exit 0.",
  "code_examples": [
    {
      "id": "12.6-ex-0",
      "lang": "console",
      "caption": "The marker prefix and a real fingerprint",
      "code": "python - <<'PY'\nfrom app.github_client import COMMENT_MARKER_PREFIX, fingerprint\nfrom app.models import Finding\n\nf = Finding(file=\"app/db.py\", line=\"12\", severity=\"CRITICAL\", issue=\"x1\", suggested_fix=\"y\")\nprint(\"prefix:\", repr(COMMENT_MARKER_PREFIX))\nprint(\"marker:\", COMMENT_MARKER_PREFIX + fingerprint(f) + \" -->\")\nprint(\"length:\", len(fingerprint(f)))\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "prefix: '<!-- ai-code-reviewer:'\nmarker: <!-- ai-code-reviewer:ccd8171df4807f92 -->\nlength: 16",
      "why_not": "the browser runner has no shell and does not embed the surface modules; this command runs from a checkout."
    }
  ],
  "quiz": [
    {
      "q": "What form does the marker take?",
      "options": [
        "A Markdown heading",
        "A YAML front matter",
        "An HTML comment",
        "A bare hex string"
      ],
      "answer": 2,
      "why": "It renders as nothing in the pull request, so a reader never sees it and a later run can find it."
    },
    {
      "q": "Which field is excluded from the fingerprint?",
      "options": [
        "The line number",
        "The severity value",
        "The file path",
        "The suggested fix"
      ],
      "answer": 3,
      "why": "Rewording the advice must not make the same finding look like a new one."
    },
    {
      "q": "How long is a fingerprint?",
      "options": [
        "Sixteen hex characters",
        "Thirty-two hex characters",
        "Eight hex characters",
        "Sixty-four hex characters"
      ],
      "answer": 0,
      "why": "A SHA-256 prefix, long enough to separate findings and short enough to read in a comment."
    }
  ],
  "try_it": {
    "prompt": "Print a marker line for a made-up finding.",
    "starter": "",
    "solution": "```console\n$ python -c \"from app.github_client import COMMENT_MARKER_PREFIX, fingerprint; from app.models import Finding; f=Finding(file='a.py', line='1', severity='LOW', issue='x', suggested_fix='y'); print(COMMENT_MARKER_PREFIX + fingerprint(f) + ' -->')\"\n```",
    "explanation": "The exact form a posted body ends with — an HTML comment wrapping a sixteen-hex fingerprint."
  },
  "exercise": {
    "prompt": "Does changing the suggested fix change the fingerprint? Prove it.",
    "hint": "Compute two fingerprints that differ only in the fix.",
    "solution": "```console\n$ python -c \"from app.github_client import fingerprint; from app.models import Finding; a=Finding(file='a.py',line='1',severity='LOW',issue='x',suggested_fix='one'); b=Finding(file='a.py',line='1',severity='LOW',issue='x',suggested_fix='two'); print(fingerprint(a)==fingerprint(b))\"\n```\n\nTrue — the fix is not part of the identity.",
    "explanation": "That equality is the property the marker depends on."
  },
  "common_mistakes": [
    "Hashing the whole finding, so every reworded fix posts again.",
    "Using a visible marker a reader would see.",
    "Comparing the issue text without collapsing whitespace."
  ],
  "project_links": [
    {
      "label": "The marker prefix",
      "path": "app/github_client.py",
      "lines": "87"
    },
    {
      "label": "The fingerprint",
      "path": "app/github_client.py",
      "lines": "263-283"
    }
  ],
  "learn_more": [
    {
      "label": "app/github_client.py — the marker",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/github_client.py"
    },
    {
      "label": "docs/decisions/ — the ADRs",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions"
    }
  ],
  "glossary_terms": [
    "idempotent — running twice leaves the same result",
    "fingerprint — a short hash that identifies a finding",
    "marker — a line a later run can search for"
  ]
});
