/* 12.8 — The GitHub client: what it posts and what it refuses
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "12.8",
  "part": 12,
  "part_title": "Surfaces: CLI, API, webhook, GitHub",
  "title": "The GitHub client: what it posts and what it refuses",
  "order": 1208,
  "duration_min": 25,
  "concept_md": "### One client, a fixed vocabulary\n\n`app/github_client.py` is 1285 lines and it does four things: build a review payload, post it, read existing comments to skip duplicates, and translate every failure into the tool's own errors.\n\n### What it refuses\n\nIt refuses to post without a token, and it refuses to post a single source file as a pull-request comment — a review needs a diff, because an inline comment needs a line that exists in the diff. `--post-to-pr` on a plain file is a usage error, not a silent downgrade.\n\n### The two anchors it can use\n\nA finding is posted inline when its line is in the diff, and demoted to the summary when GitHub rejects the anchor. Those are the only two outcomes, which is why the reader never sees a finding vanish.\n\n### Why the file is long\n\nBecause GitHub's failure modes are numerous and each needs a decision: 401 and 403 mean the token is wrong or lacks a scope; 404 means the repository or the pull request is not visible to it; 429 means back off; 422 means demote one comment; a 5xx means retry later; a transport error means the network is gone. Six decisions, each with its own honest message.",
  "code_examples": [
    {
      "id": "12.8-ex-0",
      "lang": "console",
      "caption": "The client's public surface",
      "code": "python - <<'PY'\nimport pathlib\n\nsrc = pathlib.Path(\"app/github_client.py\").read_text().splitlines()\nfor n, line in enumerate(src, 1):\n    if line.startswith((\"def \", \"class \")) or (line.startswith(\"COMMENT_MARKER\") or line.startswith(\"FILE_ONLY\")):\n        print(n, line[:56])\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "85 FILE_ONLY: str = \"file_only\"\n87 COMMENT_MARKER_PREFIX: str = \"<!-- ai-code-reviewer:\"\n124 class GitHubError(Exception):\n132 class GitHubAuthError(GitHubError):\n136 class GitHubNotFoundError(GitHubError):\n140 class GitHubRateLimitError(GitHubError):\n154 class GitHubUnavailableError(GitHubError):\n164 class InlineComment:\n186 class ReviewPayload:\n210 class PostResult:\n236 def _md_code(value: str) -> str:\n263 def fingerprint(finding: Finding) -> str:\n287 def _marker_line(marker_fingerprint: str) -> str:\n299 def _new_line_end(finding: Finding) -> int:\n315 def render_inline_body(finding: Finding) -> str:\n337 def _status_value(status: object) -> str:\n350 def _canonical_paths(diff_files: Sequence[FileDiff]) -> \n371 def build_payload(\n456 def _summary_fingerprint(payload: ReviewPayload) -> str:\n481 def _counts(bodies: Sequence[str]) -> dict[str, int]:\n498 def _verdict(counts: dict[str, int]) -> str:\n514 def _summary_entry(comment: InlineComment) -> list[str]:\n536 def render_summary_body(payload: ReviewPayload) -> str:\n622 def _has_token(token: str | None) -> bool:\n634 def github_available(token: str | None = None) -> bool:\n647 def _build_github_client(token: str) -> httpx.Client:\n672 def _close_quietly(client: httpx.Client) -> None:\n689 def _retry_after(response: httpx.Response) -> float | No\n718 def _raise_for_status(response: httpx.Response) -> None:\n751 def _next_link(response: httpx.Response) -> str | None:\n773 def _safe_next_url(url: str) -> str | None:\n799 def _markers_in(response: httpx.Response) -> set[str]:\n824 def _get_existing_markers(\n863 def _comment_dict(comment: InlineComment) -> dict[str, o\n880 def _post_review_request(\n915 def _post_summary_request(\n948 def _warn(message: str) -> None:\n957 def _sleep_for(retry_after: float | None) -> None:\n967 def _single_review_payload(comment: InlineComment, event\n989 def _transport_error_message(exc: BaseException) -> str:\n1001 def post_review(\n1064 def _validate_target(owner: str, repo: str, pr_number: i\n1093 def _publish(",
      "why_not": "the browser runner has no shell and does not embed the surface modules; this command runs from a checkout."
    }
  ],
  "quiz": [
    {
      "q": "What does the client refuse to do?",
      "options": [
        "Post a single source file",
        "Post a demoted comment at all",
        "Read the existing comments",
        "Retry after a 5xx error"
      ],
      "answer": 0,
      "why": "An inline comment needs a line that exists in a diff, so a plain file cannot be posted."
    },
    {
      "q": "What does a 403 mean here?",
      "options": [
        "The pull request is closed",
        "The token lacks a scope",
        "The anchor is unanchorable",
        "The rate limit was hit"
      ],
      "answer": 1,
      "why": "401 is a bad token; 403 is a token without the permission the call needs."
    },
    {
      "q": "How many outcomes can a finding have?",
      "options": [
        "Three: inline, summary, dropped",
        "One: inline, or an error",
        "Two: inline or summary",
        "Four: one per severity"
      ],
      "answer": 2,
      "why": "A demotion is the only fallback, which is why a finding never vanishes."
    }
  ],
  "try_it": {
    "prompt": "List the client's top-level definitions.",
    "starter": "",
    "solution": "```console\n$ grep -n '^def \\|^class ' app/github_client.py\n```",
    "explanation": "A handful of functions and classes; the length is in the error translation between them."
  },
  "exercise": {
    "prompt": "Which status does the client retry, and which does it demote?",
    "hint": "One is transient, one is about an anchor.",
    "solution": "```console\n$ grep -n '429\\|422' app/github_client.py | head -4\n```\n\n429 backs off and 5xx retries later; 422 demotes one comment. Neither fails the post.",
    "explanation": "Each status gets the response its meaning deserves rather than one blanket retry."
  },
  "common_mistakes": [
    "Posting a plain source file as a pull-request review.",
    "Treating 401 and 403 as the same failure.",
    "Retrying a 422 instead of demoting the comment."
  ],
  "project_links": [
    {
      "label": "The marker constant",
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
      "label": "app/github_client.py",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/github_client.py"
    },
    {
      "label": "ADR 0005 — the 422 demotion",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0005-422-demotes-single-finding-not-whole-post.md"
    }
  ],
  "glossary_terms": [
    "scope — the permission a token carries",
    "back off — wait longer before the next attempt",
    "payload — the JSON body a review post sends"
  ]
});
