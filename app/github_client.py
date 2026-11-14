"""GitHub PR comment posting: pure rendering plus the six I/O seams.

Phase 5 publishes a review to a pull request. Everything that decides *what*
the comment says is a pure function (no client, no I/O, no logging) so it can be
tested against plain data; everything that talks to GitHub lives in a seam that
can be patched in tests.

Design rules this module holds to:

* **Idempotency by marker.** Every body this module generates ends with a
  marker line ``<!-- ai-code-reviewer:<fingerprint> -->``. Re-running a review
  on the same commit therefore never double-posts: one listing call fetches the
  PR's existing comment bodies (paged further only when GitHub reports more
  pages), and if the summary marker is already there the whole post is skipped.
  The marker hashes the findings, not the commit, so an identical re-review of a
  later push is treated as a duplicate on purpose.
* **Degrade, never crash.** :func:`post_review` converts a missing token,
  401/403, 404, 429, a 422 on a single inline comment, a 5xx and a transport
  error into a :class:`PostResult` carrying ``error``. The caller (webhook or
  CLI) decides what to print; GitHub itself never sees a 5xx because of us.
* **An inline comment is a privilege, not a right.** GitHub silently drops — or
  422s — a comment anchored to a line that is not part of the diff. Findings
  that cannot be attached inline (``file_only``, ``unanchored``) and findings
  beyond the inline cap are therefore carried in the summary body instead, and a
  comment demoted by a 422 at post time is rebuilt into that same summary.
* **``categories`` filtering is local-only by design.** Live findings carry no
  rule id, so nothing here can map a category onto a finding. Do not invent a
  mapping: filter with :func:`app.rules.review_diff` before calling
  :func:`build_payload`.

Auth is a personal access token from ``GITHUB_TOKEN`` (via
:class:`app.config.Settings`). :func:`_build_github_client` is the seam where
GitHub App authentication would later replace the PAT; nothing else here knows
how the client was built.
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
import math
import re
import time
from typing import TYPE_CHECKING

import httpx

from app.config import Settings as _Settings
from app.parser import normalize_path as _normalize_path

if TYPE_CHECKING:  # pragma: no cover - typing only, keeps the runtime surface clean
    from collections.abc import Sequence

    from app.models import AnchoredFinding, Finding
    from app.parser import FileDiff

__all__ = [
    "GitHubError",
    "GitHubAuthError",
    "GitHubNotFoundError",
    "GitHubRateLimitError",
    "GitHubUnavailableError",
    "ANCHORED",
    "FILE_ONLY",
    "UNANCHORED",
    "COMMENT_MARKER_PREFIX",
    "DEFAULT_EVENT",
    "InlineComment",
    "ReviewPayload",
    "PostResult",
    "fingerprint",
    "render_inline_body",
    "build_payload",
    "render_summary_body",
    "github_available",
    "post_review",
]

# --------------------------------------------------------------------------- #
# Constants (frozen contract)
# --------------------------------------------------------------------------- #

ANCHORED: str = "anchored"
FILE_ONLY: str = "file_only"
UNANCHORED: str = "unanchored"
COMMENT_MARKER_PREFIX: str = "<!-- ai-code-reviewer:"
DEFAULT_EVENT: str = "COMMENT"

_GITHUB_API_URL = "https://api.github.com"
_API_VERSION = "2022-11-28"
_ACCEPT = "application/vnd.github+json"

_NO_TOKEN_ERROR = "GITHUB_TOKEN not configured"
_RIGHT = "RIGHT"

#: Hard ceiling on how long a 429 retry will wait, so a hostile
#: ``Retry-After`` header can never wedge a worker.
_MAX_RETRY_SLEEP_S = 60.0

#: Default wait when GitHub returns 429 without a usable ``Retry-After``.
_DEFAULT_RETRY_SLEEP_S = 1.0

#: Comment listing is one page in practice; a bounded loop keeps a busy PR from
#: turning the marker check into an unbounded crawl.
_SAFE_OWNER_RE = re.compile(r"[A-Za-z0-9_.-]{1,100}")
_MAX_RETRY_AFTER = 10.0  # ceiling for a single honoured Retry-After
_MAX_COMMENT_PAGES = 5

_MARKER_RE = re.compile(re.escape(COMMENT_MARKER_PREFIX) + r"([0-9a-f]{16})\s*-->")
_SEVERITY_RE = re.compile(r"^\*\*(CRITICAL|HIGH|MEDIUM|LOW)\*\*", re.MULTILINE)
_ISSUE_RE = re.compile(r"^- \*\*Issue:\*\* (.*)$", re.MULTILINE)
_FIX_RE = re.compile(r"^- \*\*Suggested fix:\*\* (.*)$", re.MULTILINE)
_LINK_NEXT_RE = re.compile(r'<([^>]+)>\s*;\s*rel="next"')

logger = logging.getLogger("reviewer.github")


# --------------------------------------------------------------------------- #
# Typed exceptions
# --------------------------------------------------------------------------- #


class GitHubError(Exception):
    """Base class for every GitHub posting failure.

    Raised by :func:`_raise_for_status` for an unexpected status code; callers
    that want fine-grained handling catch a subclass.
    """


class GitHubAuthError(GitHubError):
    """Authentication or authorisation failed (401 / 403, or no token)."""


class GitHubNotFoundError(GitHubError):
    """The repository, pull request or issue does not exist (404)."""


class GitHubRateLimitError(GitHubError):
    """GitHub rate limited the request (429).

    Args:
        message: Human-readable description.
        retry_after: Seconds to wait before retrying, from the ``Retry-After``
            header, or ``None`` when GitHub did not send a usable value.
    """

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after: float | None = retry_after


class GitHubUnavailableError(GitHubError):
    """GitHub returned a 5xx; the request is worth retrying later."""


# --------------------------------------------------------------------------- #
# Frozen data structures
# --------------------------------------------------------------------------- #


@dataclasses.dataclass(frozen=True)
class InlineComment:
    """One comment destined for a PR review, or one carried in the summary.

    Attributes:
        path: Repository-relative file path the comment targets.
        line: New-side line number; the end of the finding's line range.
        side: ``"RIGHT"`` for a real inline comment. For an entry that is only
            carried in the summary this records the finding's anchor status
            (``"file_only"`` / ``"unanchored"``) so the summary can group it;
            the field is never sent to GitHub for such an entry.
        body: Markdown body, always ending with the idempotency marker line.
        fingerprint: Stable 16-hex fingerprint of the underlying finding.
    """

    path: str
    line: int
    side: str
    body: str
    fingerprint: str


@dataclasses.dataclass(frozen=True)
class ReviewPayload:
    """Everything needed to publish one review.

    Attributes:
        summary_body: Rendered markdown summary (empty when there are no
            findings at all).
        inline_comments: Comments to attach to changed lines, in post order.
        event: Review event, always :data:`DEFAULT_EVENT` for now.
        dropped: Findings that could not (or must not) go inline: file-only,
            unanchored, and anchored ones beyond the inline cap.
        marker_seen: Records that an earlier summary marker was found. It is set on
            the internal copy :func:`post_review` renders from, never on the caller's
            payload (the dataclass is frozen); the observable outcome is
            :attr:`PostResult.skipped_dup`, which is what callers should read.
    """

    summary_body: str
    inline_comments: tuple[InlineComment, ...]
    event: str
    dropped: tuple[InlineComment, ...]
    marker_seen: bool


@dataclasses.dataclass(frozen=True)
class PostResult:
    """Outcome of one :func:`post_review` call. Never an exception.

    Attributes:
        ok: True when the post completed without a failure worth degrading on.
        inline_posted: Number of inline comments GitHub accepted.
        inline_demoted: Number of inline comments moved into the summary.
        summary_posted: True when the summary comment was created.
        skipped_dup: True when an earlier summary marker was found and the whole
            post was skipped.
        error: Empty on success, otherwise a short reason for the caller.
    """

    ok: bool
    inline_posted: int
    inline_demoted: int
    summary_posted: bool
    skipped_dup: bool
    error: str


# --------------------------------------------------------------------------- #
# Pure functions: no client, no I/O, no logging
# --------------------------------------------------------------------------- #


def _md_code(value: str) -> str:
    """Render ``value`` as a CommonMark code span that cannot break out of it.

    A diff path is attacker-chosen (it comes from the pull request). A backtick inside
    it would close a single-backtick span and let the rest render as markdown, which is
    how a path becomes a live link inside the bot's own comment. Backslash escapes do
    not help: CommonMark does not process them inside code spans, so the fence itself
    has to be longer than the longest backtick run in the value.

    Args:
        value: Text to render as inline code.

    Returns:
        A code span fenced with one more backtick than the value contains, padded with a
        space when the value starts or ends with a backtick (required by CommonMark).
    """
    text = value.replace("\n", " ").replace("\r", " ")
    longest = run = 0
    for char in text:
        run = run + 1 if char == "`" else 0
        longest = max(longest, run)
    fence = "`" * (longest + 1)
    if text.startswith("`") or text.endswith("`"):
        text = f" {text} "
    return f"{fence}{text}{fence}"


def fingerprint(finding: Finding) -> str:
    """Stable 16-hex fingerprint of a finding.

    The digest covers exactly the four identity fields (file, line, severity,
    issue) — not the suggested fix, so rewording the advice does not make the
    same finding look new.

    Args:
        finding: The finding to fingerprint.

    Returns:
        Sixteen lowercase hex characters, identical across runs and machines.
    """
    material = "\x1f".join(
        (
            finding.file.strip(),
            finding.line.strip(),
            finding.severity.value,
            " ".join(finding.issue.split()),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _marker_line(marker_fingerprint: str) -> str:
    """Return the idempotency marker line for ``marker_fingerprint``.

    Args:
        marker_fingerprint: 16-hex fingerprint of the finding or payload.

    Returns:
        The marker line ``<!-- ai-code-reviewer:<fingerprint> -->``.
    """
    return f"{COMMENT_MARKER_PREFIX}{marker_fingerprint} -->"


def _new_line_end(finding: Finding) -> int:
    """Return the last line of a finding's line range.

    ``"42"`` gives 42 and ``"42-45"`` gives 45 — the line an inline comment
    attaches to, because GitHub wants the end of a range, not its start.

    Args:
        finding: Finding whose ``line`` field is ``"42"`` or ``"42-45"``.

    Returns:
        The end line number of the range.
    """
    start, _, end = finding.line.partition("-")
    return int(end or start)


def render_inline_body(finding: Finding) -> str:
    """Render one finding as an inline comment body.

    Args:
        finding: The finding to render.

    Returns:
        Markdown carrying the severity, ``file:line``, the issue, the suggested
        fix, and the trailing idempotency marker line.
    """
    return "\n".join(
        (
            f"**{finding.severity.value}** — {_md_code(f'{finding.file}:{finding.line}')}",
            "",
            f"- **Issue:** {finding.issue}",
            f"- **Suggested fix:** {finding.suggested_fix}",
            "",
            _marker_line(fingerprint(finding)),
        )
    )


def _status_value(status: object) -> str:
    """Normalise an anchor status (enum or string) to its lowercase value.

    Args:
        status: ``AnchorStatus`` member or its string value.

    Returns:
        ``"anchored"``, ``"file_only"``, ``"unanchored"`` or ``""``.
    """
    raw = getattr(status, "value", status)
    return str(raw).strip().lower() if isinstance(raw, str) else ""


def _canonical_paths(diff_files: Sequence[FileDiff]) -> dict[str, str]:
    """Map normalised diff paths to the path GitHub knows them by.

    A finding may name ``a/app/db.py`` where the diff says ``app/db.py``; the
    inline comment must use the diff's spelling or GitHub 422s it.

    Args:
        diff_files: Files of the parsed diff.

    Returns:
        Mapping of normalised path to the diff's own path.
    """
    mapping: dict[str, str] = {}
    for diff_file in diff_files:
        path = getattr(diff_file, "path", "")
        if not path:
            continue
        mapping[_normalize_path(path)] = path
    return mapping


def build_payload(
    findings: Sequence[AnchoredFinding],
    diff_files: Sequence[FileDiff],
    *,
    max_inline: int = 30,
) -> ReviewPayload:
    """Turn anchored findings into an inline set plus a summary.

    Anchored findings within ``max_inline`` become inline comments; everything
    else is carried in the summary. ``diff_files`` is used to canonicalise the
    paths GitHub will validate against the diff (it never changes a line
    number: the comment line is always the end of the finding's range).

    Args:
        findings: Anchored findings from :func:`app.parser.anchor_findings`.
        diff_files: Files of the parsed diff.
        max_inline: Maximum number of inline comments; the remainder overflow
            into the summary. Zero or negative means summary-only.

    Returns:
        A :class:`ReviewPayload` with ``event=DEFAULT_EVENT`` and
        ``marker_seen=False``. With no findings at all the payload has an empty
        ``summary_body``, no inline comments and nothing dropped.
    """
    canonical = _canonical_paths(diff_files)
    cap = max(max_inline, 0)

    inline: list[InlineComment] = []
    dropped: list[InlineComment] = []

    for anchored in findings:
        finding = anchored.finding
        path = canonical.get(_normalize_path(finding.file), finding.file)
        line = _new_line_end(finding)
        body = render_inline_body(finding)
        digest = fingerprint(finding)
        status = _status_value(anchored.status)

        if status == ANCHORED:
            if len(inline) < cap:
                inline.append(
                    InlineComment(
                        path=path,
                        line=line,
                        side=_RIGHT,
                        body=body,
                        fingerprint=digest,
                    )
                )
            else:
                # Over the cap: still an anchored comment, but summary-only.
                dropped.append(
                    InlineComment(
                        path=path,
                        line=line,
                        side=_RIGHT,
                        body=body,
                        fingerprint=digest,
                    )
                )
            continue

        summary_side = FILE_ONLY if status == FILE_ONLY else UNANCHORED
        dropped.append(
            InlineComment(
                path=path,
                line=line,
                side=summary_side,
                body=body,
                fingerprint=digest,
            )
        )

    payload = ReviewPayload(
        summary_body="",
        inline_comments=tuple(inline),
        event=DEFAULT_EVENT,
        dropped=tuple(dropped),
        marker_seen=False,
    )
    if not inline and not dropped:
        return payload
    return dataclasses.replace(payload, summary_body=render_summary_body(payload))


def _summary_fingerprint(payload: ReviewPayload) -> str:
    """Return the fingerprint that identifies this payload in the summary.

    Derived from every finding fingerprint in the payload (inline and dropped), so
    a re-run that produces the same findings produces the same summary marker and is
    detected as a duplicate. The commit id is deliberately not part of the hash: a
    push whose review yields identical findings is a duplicate of what is already on
    the PR, while any change in the findings produces a new marker.

    Args:
        payload: Payload to identify.

    Returns:
        Sixteen hex characters, or ``""`` when the payload carries no findings.
    """
    digests = sorted(
        comment.fingerprint
        for comment in (*payload.inline_comments, *payload.dropped)
        if comment.fingerprint
    )
    if not digests:
        return ""
    return hashlib.sha256("|".join(digests).encode("utf-8")).hexdigest()[:16]


def _counts(bodies: Sequence[str]) -> dict[str, int]:
    """Tally severities across rendered bodies.

    Args:
        bodies: Markdown bodies produced by :func:`render_inline_body`.

    Returns:
        A dict with all four severity keys, in ladder order.
    """
    tally = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for body in bodies:
        match = _SEVERITY_RE.search(body)
        if match:
            tally[match.group(1)] += 1
    return tally


def _verdict(counts: dict[str, int]) -> str:
    """Gate decision from a severity tally, matching ``app.models.verdict_for``.

    Args:
        counts: Tally as returned by :func:`_counts`.

    Returns:
        ``"block"``, ``"approve with comments"`` or ``"approve"``.
    """
    if counts["CRITICAL"] or counts["HIGH"]:
        return "block"
    if counts["MEDIUM"] or counts["LOW"]:
        return "approve with comments"
    return "approve"


def _summary_entry(comment: InlineComment) -> list[str]:
    """Render one summary bullet (and its fix) from a carried comment body.

    Args:
        comment: The carried comment.

    Returns:
        Markdown lines for the entry, without a trailing blank line.
    """
    body = comment.body
    severity_match = _SEVERITY_RE.search(body)
    issue_match = _ISSUE_RE.search(body)
    fix_match = _FIX_RE.search(body)
    severity = severity_match.group(1) if severity_match else "LOW"
    issue = issue_match.group(1) if issue_match else ""
    fix = fix_match.group(1) if fix_match else ""
    lines = [f"- **{severity}** `{comment.path}:{comment.line}` — {issue}".rstrip(" —")]
    if fix:
        lines.append(f"  - Suggested fix: {fix}")
    return lines


def render_summary_body(payload: ReviewPayload) -> str:
    """Render the markdown summary for a payload.

    The summary is the home for everything that cannot be an inline comment:
    file-only findings grouped by file, unanchored findings under "General
    findings", and anchored findings that overflowed the inline cap or were
    demoted by a 422 at post time.

    Args:
        payload: The payload to summarise.

    Returns:
        Markdown with a verdict line, severity counts, one section per file for
        file-only findings, a "General findings" section, an overflow section,
        and the summary marker line. Empty string when the payload has no
        findings at all.
    """
    inline = payload.inline_comments
    dropped = payload.dropped
    if not inline and not dropped:
        return ""

    bodies = [*(comment.body for comment in inline), *(comment.body for comment in dropped)]
    counts = _counts(bodies)
    total = sum(counts.values())

    file_groups: dict[str, list[InlineComment]] = {}
    general: list[InlineComment] = []
    overflow: list[InlineComment] = []
    for comment in dropped:
        if comment.side == FILE_ONLY:
            file_groups.setdefault(comment.path, []).append(comment)
        elif comment.side == UNANCHORED:
            general.append(comment)
        else:
            # Anchored, but beyond the inline cap or demoted by a 422.
            overflow.append(comment)

    lines: list[str] = [
        "## Autonomous AI Code Review",
        "",
        f"**Verdict:** {_verdict(counts)} · **Findings:** {total} "
        f"(CRITICAL {counts['CRITICAL']}, HIGH {counts['HIGH']}, "
        f"MEDIUM {counts['MEDIUM']}, LOW {counts['LOW']})",
        f"**Inline comments:** {len(inline)} · **In this summary:** {len(dropped)}",
        "",
    ]

    for path, group in file_groups.items():
        lines.append(f"### `{path}`")
        lines.append("")
        for comment in group:
            lines.extend(_summary_entry(comment))
        lines.append("")

    if general:
        lines.append("### General findings")
        lines.append("")
        for comment in general:
            lines.extend(_summary_entry(comment))
        lines.append("")

    if overflow:
        lines.append("### Additional findings")
        lines.append("")
        lines.append(
            "_Anchored findings that could not be attached inline "
            "(inline cap reached or GitHub rejected the position)._"
        )
        lines.append("")
        for comment in overflow:
            lines.extend(_summary_entry(comment))
        lines.append("")

    marker_fingerprint = _summary_fingerprint(payload)
    if marker_fingerprint:
        lines.append(_marker_line(marker_fingerprint))

    return "\n".join(lines).rstrip("\n") + "\n"


# --------------------------------------------------------------------------- #
# I/O seams
# --------------------------------------------------------------------------- #


def _has_token(token: str | None) -> bool:
    """Report whether a token is present and not blank.

    Args:
        token: Candidate token.

    Returns:
        True only for a non-empty, non-whitespace token.
    """
    return bool(token and token.strip())


def github_available(token: str | None = None) -> bool:
    """Report whether PR posting is configured.

    Args:
        token: Explicit token; when ``None`` the value from
            :class:`app.config.Settings` is used.

    Returns:
        True when a non-blank token exists. Callable with no arguments.
    """
    return _has_token(token if token is not None else _Settings().github_token)


def _build_github_client(token: str) -> httpx.Client:
    """Build the httpx client every seam uses.

    This is the authentication seam: a GitHub App installation token would be
    minted here instead of using the PAT directly.

    Args:
        token: Personal access token sent as a Bearer credential.

    Returns:
        A configured :class:`httpx.Client` rooted at the GitHub REST API.
    """
    settings = _Settings()
    return httpx.Client(
        base_url=_GITHUB_API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": _ACCEPT,
            "X-GitHub-Api-Version": _API_VERSION,
            "User-Agent": "ai-code-reviewer",
        },
        timeout=settings.request_timeout_s,
    )


def _close_quietly(client: httpx.Client) -> None:
    """Close a client if it exposes ``close``; never raise from cleanup.

    Args:
        client: Client to close, real or fake.
    """
    close = getattr(client, "close", None)
    if callable(close):
        try:
            close()
        except Exception:  # noqa: BLE001 - cleanup must never mask the real outcome
            # Deliberately broad: this runs in a ``finally``, and a close() failure
            # (real or from a test double) must not replace the PostResult we are
            # about to return. Nothing is swallowed silently - it is logged.
            logger.debug("closing the GitHub client failed", exc_info=True)


def _retry_after(response: httpx.Response) -> float | None:
    """Read ``Retry-After`` from a response as seconds.

    Args:
        response: The 429 response.

    Returns:
        A non-negative float, or ``None`` when the header is missing or not a
        number.
    """
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    try:
        raw = headers.get("Retry-After")
    except (AttributeError, TypeError):
        return None
    if raw is None:
        return None
    try:
        seconds = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(seconds):
        # "nan" or "inf" would otherwise reach time.sleep and raise or hang.
        return None
    return min(max(seconds, 0.0), _MAX_RETRY_AFTER)


def _raise_for_status(response: httpx.Response) -> None:
    """Translate a failure status into a typed exception.

    A 422 is deliberately *not* raised: it means "this inline position is not
    part of the diff", which the caller handles by demoting one comment.

    Args:
        response: Response to inspect.

    Raises:
        GitHubAuthError: 401 or 403.
        GitHubNotFoundError: 404.
        GitHubRateLimitError: 429, carrying ``retry_after``.
        GitHubUnavailableError: 5xx.
        GitHubError: Any other non-2xx status.
    """
    status = response.status_code
    if 200 <= status < 300:
        return
    if status in (401, 403):
        raise GitHubAuthError(f"GitHub rejected the credentials (HTTP {status})")
    if status == 404:
        raise GitHubNotFoundError("GitHub could not find the repository or pull request (HTTP 404)")
    if status == 429:
        raise GitHubRateLimitError(
            "GitHub rate limited the request (HTTP 429)",
            retry_after=_retry_after(response),
        )
    if status >= 500:
        raise GitHubUnavailableError(f"GitHub is unavailable (HTTP {status})")
    raise GitHubError(f"GitHub returned an unexpected status (HTTP {status})")


def _next_link(response: httpx.Response) -> str | None:
    """Return the ``rel="next"`` URL from a Link header, if any.

    Args:
        response: Response to inspect.

    Returns:
        The next-page URL, or ``None`` on a single-page listing.
    """
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    try:
        link = headers.get("Link") or ""
    except (AttributeError, TypeError):
        return None
    match = _LINK_NEXT_RE.search(str(link))
    if match is None:
        return None
    return _safe_next_url(match.group(1))


def _safe_next_url(url: str) -> str | None:
    """Return ``url`` only when it points at the GitHub API over HTTPS.

    The ``Link`` header is attacker-influenceable in a compromised or spoofed
    response, and the follow-up request carries the token. Anything that is not
    a relative path or an ``https://api.github.com`` URL is refused, so a hostile
    header cannot redirect the PAT to another host.

    Args:
        url: The ``rel="next"`` target from the Link header.

    Returns:
        A safe URL to request, or ``None`` to stop paginating.
    """
    candidate = url.strip()
    if not candidate:
        return None
    if candidate.startswith("/"):
        return candidate
    parsed = httpx.URL(candidate)
    if parsed.scheme != "https" or parsed.host != "api.github.com":
        logger.debug("ignoring a Link next URL outside api.github.com")
        return None
    return candidate


def _markers_in(response: httpx.Response) -> set[str]:
    """Collect fingerprints from every marker line in a comment listing.

    Args:
        response: Response whose JSON body is a list of comment objects.

    Returns:
        The set of 16-hex fingerprints found; empty for an unexpected shape.
    """
    try:
        data = response.json()
    except ValueError:
        return set()
    if not isinstance(data, list):
        return set()
    found: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        body = item.get("body")
        if isinstance(body, str):
            found.update(_MARKER_RE.findall(body))
    return found


def _get_existing_markers(
    client: httpx.Client,
    owner: str,
    repo: str,
    pr_number: int,
) -> set[str]:
    """List the PR's existing comment bodies and extract their markers.

    Args:
        client: GitHub client from :func:`_build_github_client`.
        owner: Repository owner.
        repo: Repository name.
        pr_number: Pull request (issue) number.

    Returns:
        The set of fingerprints whose marker line already appears on the PR.

    Raises:
        GitHubAuthError: 401 or 403.
        GitHubNotFoundError: 404.
        GitHubRateLimitError: 429.
        GitHubUnavailableError: 5xx.
        GitHubError: Any other unexpected status.
        httpx.HTTPError: Transport failure or timeout.
    """
    url = f"/repos/{owner}/{repo}/issues/{pr_number}/comments"
    params: dict[str, int] | None = {"per_page": 100}
    markers: set[str] = set()
    for _ in range(_MAX_COMMENT_PAGES):
        response = client.get(url, params=params)
        _raise_for_status(response)
        markers |= _markers_in(response)
        next_url = _next_link(response)
        if not next_url:
            break
        url, params = next_url, None
    return markers


def _comment_dict(comment: InlineComment) -> dict[str, object]:
    """Serialise one inline comment for the reviews API.

    Args:
        comment: Comment to serialise.

    Returns:
        The ``{"path", "line", "side", "body"}`` object GitHub expects.
    """
    return {
        "path": comment.path,
        "line": comment.line,
        "side": comment.side,
        "body": comment.body,
    }


def _post_review_request(
    client: httpx.Client,
    owner: str,
    repo: str,
    pr_number: int,
    payload: ReviewPayload,
    commit_id: str | None,
) -> httpx.Response:
    """POST a pull-request review carrying the inline comments.

    Args:
        client: GitHub client from :func:`_build_github_client`.
        owner: Repository owner.
        repo: Repository name.
        pr_number: Pull request number.
        payload: Payload whose inline comments are attached; its
            ``summary_body`` becomes the review body.
        commit_id: Head SHA to pin the review to; omitted when ``None``.

    Returns:
        The raw response; the caller inspects ``status_code``.

    Raises:
        httpx.HTTPError: Transport failure or timeout.
    """
    body: dict[str, object] = {
        "body": payload.summary_body,
        "event": payload.event,
        "comments": [_comment_dict(comment) for comment in payload.inline_comments],
    }
    if commit_id:
        body["commit_id"] = commit_id
    return client.post(f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews", json=body)


def _post_summary_request(
    client: httpx.Client,
    owner: str,
    repo: str,
    pr_number: int,
    body: str,
) -> httpx.Response:
    """POST the summary as a plain PR conversation comment.

    Args:
        client: GitHub client from :func:`_build_github_client`.
        owner: Repository owner.
        repo: Repository name.
        pr_number: Pull request (issue) number.
        body: Rendered summary markdown, marker line included.

    Returns:
        The raw response; the caller inspects ``status_code``.

    Raises:
        httpx.HTTPError: Transport failure or timeout.
    """
    return client.post(
        f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
        json={"body": body},
    )


# --------------------------------------------------------------------------- #
# The state machine
# --------------------------------------------------------------------------- #


def _warn(message: str) -> None:
    """Emit the single WARNING a degraded post is allowed.

    Args:
        message: Reason, never containing a token, header or response body.
    """
    logger.warning(message)


def _sleep_for(retry_after: float | None) -> None:
    """Wait out a rate limit, clamped to a sane maximum.

    Args:
        retry_after: Seconds GitHub asked for, or ``None``.
    """
    wait = _DEFAULT_RETRY_SLEEP_S if retry_after is None else retry_after
    time.sleep(min(max(wait, 0.0), _MAX_RETRY_SLEEP_S))


def _single_review_payload(comment: InlineComment, event: str) -> ReviewPayload:
    """Build a one-comment payload for the 422 per-comment retry.

    The review body is left empty: the comment already carries the finding, and
    repeating the whole summary once per comment would spam the PR.

    Args:
        comment: The comment to post alone.
        event: Review event to send.

    Returns:
        A payload with exactly one inline comment and no summary body.
    """
    return ReviewPayload(
        summary_body="",
        inline_comments=(comment,),
        event=event,
        dropped=(),
        marker_seen=False,
    )


def _transport_error_message(exc: BaseException) -> str:
    """Describe a transport failure without leaking request details.

    Args:
        exc: The httpx exception.

    Returns:
        A short message naming the failure type only.
    """
    return f"network error contacting GitHub ({type(exc).__name__})"


def post_review(
    owner: str,
    repo: str,
    pr_number: int,
    payload: ReviewPayload,
    *,
    token: str | None = None,
    commit_id: str | None = None,
) -> PostResult:
    """Publish a review to a pull request, degrading instead of raising.

    The state machine, in order: missing token, empty payload, marker check,
    bulk inline review, per-comment 422 demotion, single 429 retry, then the
    summary comment.

    Args:
        owner: Repository owner (user or organisation).
        repo: Repository name.
        pr_number: Pull request number.
        payload: Payload from :func:`build_payload`.
        token: Explicit token; when ``None`` the value from
            :class:`app.config.Settings` is used.
        commit_id: Head SHA to pin inline comments to, when known.

    Returns:
        A :class:`PostResult`. ``ok`` is False with ``error`` set for a missing
        token, 401/403, 404, a 5xx, a transport error, a failure while building the
        client, or a 429 on the marker check or the summary POST. ``skipped_dup`` is
        True when the summary marker was already on the PR. A 429 that survives its
        single retry is **not** a failure of the whole post: the inline comments are
        demoted (``inline_demoted``) and the summary is still posted, so that case
        returns ``ok=True``. This function never raises for any of those failures.
    """
    resolved = token if token is not None else _Settings().github_token
    if not _has_token(resolved):
        _warn(f"{_NO_TOKEN_ERROR}; skipping the PR comment post")
        return PostResult(False, 0, 0, False, False, _NO_TOKEN_ERROR)

    if not payload.inline_comments and not payload.dropped:
        # Nothing to say: post nothing at all, not even an empty summary.
        return PostResult(True, 0, 0, False, False, "")

    problem = _validate_target(owner, repo, pr_number)
    if problem is not None:
        _warn(f"refusing to post: {problem}")
        return PostResult(False, 0, 0, False, False, problem)

    try:
        client = _build_github_client(str(resolved))
    except (httpx.HTTPError, httpx.InvalidURL, OSError, RuntimeError, ValueError) as exc:
        # _build_github_client is a patchable seam; a failure there is a transport
        # failure, not a programming error the caller should handle.
        _warn(f"could not create the GitHub client ({type(exc).__name__}); skipping the post")
        return PostResult(
            False, 0, 0, False, False, f"could not create the GitHub client ({type(exc).__name__})"
        )

    try:
        return _publish(client, owner, repo, pr_number, payload, commit_id)
    finally:
        _close_quietly(client)


def _validate_target(owner: str, repo: str, pr_number: int) -> str | None:
    """Reject a repository target that could steer the request somewhere else.

    ``owner`` and ``repo`` arrive from a webhook payload, so they are untrusted:
    a value like ``../../user`` would retarget the URL through path traversal, and
    ``a b`` or ``a?x=1`` would produce an invalid or ambiguous request.

    Args:
        owner: Repository owner from the caller.
        repo: Repository name from the caller.
        pr_number: Pull request number.

    Returns:
        A human-readable problem, or ``None`` when the target is safe.
    """
    for label, value in (("owner", owner), ("repo", repo)):
        if not isinstance(value, str) or not value:
            return f"{label} is empty"
        if not _SAFE_OWNER_RE.fullmatch(value):
            return f"{label} contains characters GitHub does not allow"
        if set(value) <= {"."} or ".." in value:
            # "." / ".." / "a..b" pass the character class but resolve as path
            # traversal, which would retarget the request URL.
            return f"{label} is not a valid GitHub name"
    if not isinstance(pr_number, int) or pr_number <= 0:
        return "pull request number must be a positive integer"
    return None


def _publish(
    client: httpx.Client,
    owner: str,
    repo: str,
    pr_number: int,
    payload: ReviewPayload,
    commit_id: str | None,
) -> PostResult:
    """Run the post state machine against an already-built client.

    Args:
        client: GitHub client.
        owner: Repository owner.
        repo: Repository name.
        pr_number: Pull request number.
        payload: Payload to publish.
        commit_id: Head SHA, when known.

    Returns:
        A :class:`PostResult`; never raises for a GitHub or transport failure.
    """
    warned = [False]

    def warn(message: str) -> None:
        """Emit at most ONE WARNING for this post.

        Args:
            message: Reason, never containing a token, header or response body.
        """
        if warned[0]:
            return
        warned[0] = True
        _warn(message)

    # Step 3 — idempotency: one listing of the PR's existing comments (paged if needed).
    try:
        markers = _get_existing_markers(client, owner, repo, pr_number)
    except GitHubRateLimitError as exc:
        warn(f"GitHub rate limited the duplicate check: {exc}")
        return PostResult(False, 0, 0, False, False, str(exc))
    except GitHubError as exc:
        warn(f"duplicate check failed: {exc}")
        return PostResult(False, 0, 0, False, False, str(exc))
    except (httpx.TimeoutException, httpx.HTTPError) as exc:
        message = _transport_error_message(exc)
        warn(f"duplicate check failed: {message}")
        return PostResult(False, 0, 0, False, False, message)

    summary_fingerprint = _summary_fingerprint(payload)
    if summary_fingerprint and summary_fingerprint in markers:
        # The same review is already on the PR: nothing to do, nothing to say.
        return PostResult(True, 0, 0, False, True, "")

    # Step 4 — the inline review.
    inline_posted = 0
    demoted: list[InlineComment] = []
    kept: tuple[InlineComment, ...] = payload.inline_comments
    rate_limited_twice = False

    if payload.inline_comments:
        try:
            response = _post_review_request(client, owner, repo, pr_number, payload, commit_id)
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            message = _transport_error_message(exc)
            warn(f"inline review post failed: {message}")
            return PostResult(False, 0, 0, False, False, message)

        status = response.status_code

        if status == 429:
            # One retry, honouring Retry-After, then summary-only.
            _sleep_for(_retry_after(response))
            try:
                response = _post_review_request(
                    client, owner, repo, pr_number, payload, commit_id
                )
            except (httpx.TimeoutException, httpx.HTTPError) as exc:
                message = _transport_error_message(exc)
                warn(f"inline review retry failed: {message}")
                return PostResult(False, 0, 0, False, False, message)
            status = response.status_code
            if status == 429:
                rate_limited_twice = True
                demoted = list(payload.inline_comments)
                kept = ()
                warn("GitHub rate limited the inline review twice; posting the summary only")

        if status in (401, 403):
            message = f"GitHub rejected the credentials (HTTP {status})"
            warn(f"inline review post failed: {message}")
            return PostResult(False, 0, 0, False, False, message)
        if status == 404:
            message = "GitHub could not find the repository or pull request (HTTP 404)"
            warn(f"inline review post failed: {message}")
            return PostResult(False, 0, 0, False, False, message)
        if status >= 500:
            message = f"GitHub is unavailable (HTTP {status})"
            warn(f"inline review post failed: {message}")
            return PostResult(False, 0, 0, False, False, message)

        if 200 <= status < 300:
            inline_posted = len(payload.inline_comments)
        elif status == 422:
            # Step 4b — one comment at a time; a repeat 422 demotes that comment.
            survivors: list[InlineComment] = []
            for comment in payload.inline_comments:
                single = _single_review_payload(comment, payload.event)
                try:
                    single_response = _post_review_request(
                        client, owner, repo, pr_number, single, commit_id
                    )
                except (httpx.TimeoutException, httpx.HTTPError) as exc:
                    message = _transport_error_message(exc)
                    warn(f"per-comment review post failed: {message}")
                    return PostResult(False, inline_posted, len(demoted), False, False, message)

                single_status = single_response.status_code
                if single_status == 429:
                    _sleep_for(_retry_after(single_response))
                    try:
                        single_response = _post_review_request(
                            client, owner, repo, pr_number, single, commit_id
                        )
                    except (httpx.TimeoutException, httpx.HTTPError) as exc:
                        message = _transport_error_message(exc)
                        warn(f"per-comment review retry failed: {message}")
                        return PostResult(
                            False, inline_posted, len(demoted), False, False, message
                        )
                    single_status = single_response.status_code

                if 200 <= single_status < 300:
                    inline_posted += 1
                    survivors.append(comment)
                elif single_status in (401, 403):
                    message = f"GitHub rejected the credentials (HTTP {single_status})"
                    warn(f"per-comment review post failed: {message}")
                    return PostResult(
                        False, inline_posted, len(demoted), False, False, message
                    )
                elif single_status >= 500 and single_status != 429:
                    message = f"GitHub is unavailable (HTTP {single_status})"
                    warn(f"per-comment review post failed: {message}")
                    return PostResult(
                        False, inline_posted, len(demoted), False, False, message
                    )
                else:
                    # A 422 (or any other refusal) means "this position is not
                    # in the diff": demote that one comment, keep the rest.
                    demoted.append(comment)
            kept = tuple(survivors)
        elif not rate_limited_twice:
            message = f"GitHub returned an unexpected status (HTTP {status})"
            warn(f"inline review post failed: {message}")
            return PostResult(False, 0, 0, False, False, message)

    # Step 5 — the summary, rebuilt so demoted findings appear in it.
    final_payload = dataclasses.replace(
        payload,
        inline_comments=kept,
        dropped=tuple(payload.dropped) + tuple(demoted),
        marker_seen=True,
    )
    summary_body = render_summary_body(final_payload)
    if not summary_body:
        warn("no summary body to post")
        return PostResult(False, inline_posted, len(demoted), False, False, "empty summary body")

    try:
        summary_response = _post_summary_request(client, owner, repo, pr_number, summary_body)
    except (httpx.TimeoutException, httpx.HTTPError) as exc:
        message = _transport_error_message(exc)
        warn(f"summary post failed: {message}")
        return PostResult(False, inline_posted, len(demoted), False, False, message)

    summary_status = summary_response.status_code
    if not 200 <= summary_status < 300:
        message = f"GitHub returned an unexpected status for the summary (HTTP {summary_status})"
        if summary_status in (401, 403):
            message = f"GitHub rejected the credentials (HTTP {summary_status})"
        elif summary_status == 404:
            message = "GitHub could not find the repository or pull request (HTTP 404)"
        elif summary_status >= 500:
            message = f"GitHub is unavailable (HTTP {summary_status})"
        warn(f"summary post failed: {message}")
        return PostResult(False, inline_posted, len(demoted), False, False, message)

    # Step 6 — success, with the single WARNING when something was demoted.
    if demoted:
        warn(
            f"{len(demoted)} inline comment(s) could not be attached and moved to the summary"
        )
    return PostResult(True, inline_posted, len(demoted), True, False, "")
