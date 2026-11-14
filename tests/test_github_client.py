"""Offline unit tests for :mod:`app.github_client` (Phase 5 GitHub posting).

Strategy: the module hides every network touch behind one seam,
``_build_github_client``, which returns an ``httpx.Client``. These tests never
touch the network: they monkeypatch ``app.github_client._build_github_client``
to hand back a :class:`FakeClient` whose ``.get`` / ``.post`` replay a scripted
queue of :class:`FakeResponse` objects — or raise a scripted exception — and
record every call, so the ``post_review`` state machine is asserted by exact
call order and exact request bodies. ``time.sleep`` is monkeypatched to a
recorder, so a 429 retry costs no wall-clock time and the honoured
``Retry-After`` value can be asserted directly.

The pure half (``fingerprint``, ``render_inline_body``, ``build_payload``,
``render_summary_body``) needs no fake at all and is tested against plain data.
"""

from __future__ import annotations

import dataclasses
import logging
import re
from typing import Any

import httpx
import pytest

from app import github_client
from app.github_client import (
    ANCHORED,
    COMMENT_MARKER_PREFIX,
    DEFAULT_EVENT,
    FILE_ONLY,
    UNANCHORED,
    GitHubAuthError,
    GitHubError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubUnavailableError,
    InlineComment,
    PostResult,
    ReviewPayload,
    build_payload,
    fingerprint,
    github_available,
    post_review,
    render_inline_body,
    render_summary_body,
)
from app.models import AnchorStatus, AnchoredFinding, Finding, Severity
from app.parser import FileDiff

OWNER = "octo"
REPO = "repo"
PR = 7
COMMENTS_URL = f"/repos/{OWNER}/{REPO}/issues/{PR}/comments"
REVIEWS_URL = f"/repos/{OWNER}/{REPO}/pulls/{PR}/reviews"
TOKEN = "ghp_unit_test_token_do_not_leak_0001"
LOG_NAME = "reviewer.github"

_MARKER_RE = re.compile(re.escape(COMMENT_MARKER_PREFIX) + r"([0-9a-f]{16}) -->")


# --------------------------------------------------------------------------- #
# Fakes: a scripted httpx.Client stand-in and its responses
# --------------------------------------------------------------------------- #


class FakeResponse:
    """The slice of ``httpx.Response`` the module actually reads."""

    def __init__(
        self,
        status_code: int = 200,
        payload: Any = None,
        headers: dict[str, str] | None = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = [] if payload is None else payload
        self.headers = dict(headers or {})
        self.text = text

    def json(self) -> Any:
        """Return the scripted JSON body."""
        return self._payload

    def raise_for_status(self) -> None:
        """Mirror httpx: raise for a 4xx/5xx status."""
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("bad status", request=None, response=None)  # type: ignore[arg-type]


class FakeClient:
    """Records every request and replays a scripted queue per method.

    Each queue item is either a :class:`FakeResponse` to return or an exception
    instance to raise, which is how transport failures are simulated.
    """

    def __init__(
        self,
        get_responses: tuple[Any, ...] = (),
        post_responses: tuple[Any, ...] = (),
    ) -> None:
        self._gets: list[Any] = list(get_responses)
        self._posts: list[Any] = list(post_responses)
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.closed = False

    def get(self, url: str, params: Any = None) -> FakeResponse:
        """Record a GET and return (or raise) the next scripted item."""
        self.calls.append(("GET", url, {"params": params}))
        return self._take(self._gets, "GET")

    def post(self, url: str, json: Any = None) -> FakeResponse:
        """Record a POST and return (or raise) the next scripted item."""
        self.calls.append(("POST", url, {"json": json}))
        return self._take(self._posts, "POST")

    def close(self) -> None:
        """Record that the module closed the client."""
        self.closed = True

    @staticmethod
    def _take(queue: list[Any], label: str) -> FakeResponse:
        if not queue:
            raise AssertionError(f"unscripted {label} request")
        item = queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    # -- inspection helpers ------------------------------------------------ #

    @property
    def methods(self) -> list[str]:
        """The method of every recorded call, in order."""
        return [call[0] for call in self.calls]

    @property
    def posts(self) -> list[tuple[str, dict[str, Any]]]:
        """Every recorded POST as ``(url, json_body)``."""
        return [(call[1], call[2]["json"]) for call in self.calls if call[0] == "POST"]


def install_client(monkeypatch: pytest.MonkeyPatch, client: FakeClient) -> list[str]:
    """Patch the client seam and return the list of tokens it was called with."""
    built: list[str] = []

    def _fake_build(token: str) -> FakeClient:
        built.append(token)
        return client

    monkeypatch.setattr(github_client, "_build_github_client", _fake_build)
    return built


def install_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Patch ``time.sleep`` inside the module and return the recorded waits."""
    slept: list[float] = []

    def _fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(github_client.time, "sleep", _fake_sleep)
    return slept


# --------------------------------------------------------------------------- #
# Data builders
# --------------------------------------------------------------------------- #


def make_finding(
    *,
    file: str = "app/db.py",
    line: str = "12",
    severity: Severity = Severity.HIGH,
    issue: str = "Unparameterised SQL lets a caller inject statements",
    suggested_fix: str = "Use a bound parameter instead of string interpolation",
) -> Finding:
    """Build a valid :class:`Finding`."""
    return Finding(
        file=file,
        line=line,
        severity=severity,
        issue=issue,
        suggested_fix=suggested_fix,
    )


def make_anchored(
    finding: Finding,
    status: AnchorStatus = AnchorStatus.ANCHORED,
) -> AnchoredFinding:
    """Wrap a finding in the anchor status the payload builder reads."""
    return AnchoredFinding(finding=finding, status=status)


def db_file_diff(path: str = "app/db.py") -> FileDiff:
    """A minimal diff entry for one file (only ``path`` matters here)."""
    return FileDiff(path=path)


def two_finding_payload() -> ReviewPayload:
    """Two anchored findings on one file: two inline comments, empty summary overflow."""
    findings = [
        make_anchored(make_finding(line="12")),
        make_anchored(
            make_finding(
                line="20-22",
                severity=Severity.MEDIUM,
                issue="Bare except swallows the real error",
                suggested_fix="Catch the specific exception and re-raise the rest",
            )
        ),
    ]
    return build_payload(findings, [db_file_diff()])


def empty_payload() -> ReviewPayload:
    """A payload with no findings at all."""
    return ReviewPayload(
        summary_body="",
        inline_comments=(),
        event=DEFAULT_EVENT,
        dropped=(),
        marker_seen=False,
    )


def summary_marker(body: str) -> str:
    """Extract the single summary fingerprint from a rendered summary body."""
    found = _MARKER_RE.findall(body)
    assert len(found) == 1, f"expected exactly one marker, found {found}"
    return found[0]


# --------------------------------------------------------------------------- #
# A. Contract conformance
# --------------------------------------------------------------------------- #

_CONTRACT_SURFACE = {
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
}


def test_exported_surface_matches_contract() -> None:
    """``__all__`` is exactly the contract's public surface, and every name resolves."""
    assert set(github_client.__all__) == _CONTRACT_SURFACE
    assert len(github_client.__all__) == len(_CONTRACT_SURFACE)
    missing = [name for name in github_client.__all__ if not hasattr(github_client, name)]
    assert missing == []


@pytest.mark.parametrize(
    ("cls", "instance"),
    [
        (InlineComment, InlineComment("app/db.py", 12, "RIGHT", "body", "0" * 16)),
        (
            ReviewPayload,
            ReviewPayload("summary", (), "COMMENT", (), False),
        ),
        (PostResult, PostResult(True, 1, 0, True, False, "")),
    ],
)
def test_dataclasses_are_frozen(cls: type, instance: object) -> None:
    """Assignment to any field raises ``FrozenInstanceError``."""
    field_name = dataclasses.fields(cls)[0].name  # type: ignore[arg-type]
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, field_name, "mutated")


@pytest.mark.parametrize(
    ("cls", "expected"),
    [
        (InlineComment, ["path", "line", "side", "body", "fingerprint"]),
        (
            ReviewPayload,
            ["summary_body", "inline_comments", "event", "dropped", "marker_seen"],
        ),
        (
            PostResult,
            [
                "ok",
                "inline_posted",
                "inline_demoted",
                "summary_posted",
                "skipped_dup",
                "error",
            ],
        ),
    ],
)
def test_dataclass_field_names_and_order(cls: type, expected: list[str]) -> None:
    """Field names and their declaration order match the frozen contract."""
    assert [field.name for field in dataclasses.fields(cls)] == expected  # type: ignore[arg-type]


def test_exceptions_all_subclass_github_error() -> None:
    """The four specific failures are ``GitHubError`` subclasses, and it is an ``Exception``."""
    for exc in (
        GitHubAuthError,
        GitHubNotFoundError,
        GitHubRateLimitError,
        GitHubUnavailableError,
    ):
        assert issubclass(exc, GitHubError), exc.__name__
    assert issubclass(GitHubError, Exception)


def test_constants_have_contract_values() -> None:
    """Every constant carries its frozen value."""
    assert ANCHORED == "anchored"
    assert FILE_ONLY == "file_only"
    assert UNANCHORED == "unanchored"
    assert COMMENT_MARKER_PREFIX == "<!-- ai-code-reviewer:"
    assert DEFAULT_EVENT == "COMMENT"


def test_dataclasses_construct_positionally_in_contract_order() -> None:
    """Positional construction lands each value in the contracted field."""
    comment = InlineComment("app/db.py", 4, "RIGHT", "body text", "0123456789abcdef")
    assert (comment.path, comment.line, comment.side, comment.body, comment.fingerprint) == (
        "app/db.py",
        4,
        "RIGHT",
        "body text",
        "0123456789abcdef",
    )

    payload = ReviewPayload("summary", (comment,), "COMMENT", (comment,), True)
    assert (payload.summary_body, payload.inline_comments, payload.event) == (
        "summary",
        (comment,),
        "COMMENT",
    )
    assert (payload.dropped, payload.marker_seen) == ((comment,), True)

    result = PostResult(True, 3, 1, True, False, "")
    assert (
        result.ok,
        result.inline_posted,
        result.inline_demoted,
        result.summary_posted,
        result.skipped_dup,
        result.error,
    ) == (True, 3, 1, True, False, "")


def test_rate_limit_error_carries_retry_after() -> None:
    """``GitHubRateLimitError`` exposes ``retry_after`` and defaults it to ``None``."""
    assert GitHubRateLimitError("limited", retry_after=3.5).retry_after == 3.5
    assert GitHubRateLimitError("limited").retry_after is None


# --------------------------------------------------------------------------- #
# B. fingerprint()
# --------------------------------------------------------------------------- #


def test_fingerprint_is_stable_across_calls() -> None:
    """Repeated calls on the same finding return the same digest."""
    finding = make_finding()
    assert fingerprint(finding) == fingerprint(finding)


def test_fingerprint_matches_across_identical_findings() -> None:
    """Two separately built but identical findings fingerprint identically."""
    first = make_finding()
    second = make_finding()
    assert first is not second
    assert fingerprint(first) == fingerprint(second)


def test_fingerprint_is_sixteen_lowercase_hex() -> None:
    """The digest is exactly 16 lowercase hex characters."""
    digest = fingerprint(make_finding())
    assert len(digest) == 16
    assert re.fullmatch(r"[0-9a-f]{16}", digest) is not None


def test_fingerprint_changes_with_each_identity_field() -> None:
    """Each of the four identity fields changes the digest on its own."""
    base_digest = fingerprint(make_finding())
    variants: tuple[dict[str, Any], ...] = (
        {"file": "app/other.py"},
        {"line": "13"},
        {"severity": Severity.CRITICAL},
        {"issue": "A completely different issue sentence"},
    )
    for changed in variants:
        assert fingerprint(make_finding(**changed)) != base_digest, changed


def test_fingerprint_ignores_suggested_fix() -> None:
    """Rewording the advice does not make the same finding look new."""
    base = make_finding()
    reworded = make_finding(suggested_fix="Something else entirely")
    assert fingerprint(base) == fingerprint(reworded)


# --------------------------------------------------------------------------- #
# C. render_inline_body()
# --------------------------------------------------------------------------- #


def test_render_inline_body_contains_every_field() -> None:
    """Severity, file:line, issue and suggested fix all appear."""
    finding = make_finding(line="20-22")
    body = render_inline_body(finding)
    assert "**HIGH**" in body
    assert "`app/db.py:20-22`" in body
    assert finding.issue in body
    assert finding.suggested_fix in body


def test_render_inline_body_marker_is_prefix_plus_fingerprint() -> None:
    """The marker line is exactly ``COMMENT_MARKER_PREFIX`` + fingerprint + `` -->``."""
    finding = make_finding()
    body = render_inline_body(finding)
    expected = f"{COMMENT_MARKER_PREFIX}{fingerprint(finding)} -->"
    assert expected in body
    assert body.rstrip().endswith(expected)


def test_render_inline_body_marker_appears_exactly_once() -> None:
    """Only one marker line is emitted, so dedupe cannot double-count."""
    body = render_inline_body(make_finding())
    assert body.count(COMMENT_MARKER_PREFIX) == 1
    assert len(_MARKER_RE.findall(body)) == 1


# --------------------------------------------------------------------------- #
# D. build_payload()
# --------------------------------------------------------------------------- #


def test_build_payload_line_is_end_of_range() -> None:
    """An inline comment attaches to the END of the finding's line range."""
    for line, expected in (("3-4", 4), ("7", 7)):
        payload = build_payload([make_anchored(make_finding(line=line))], [db_file_diff()])
        assert len(payload.inline_comments) == 1
        assert payload.inline_comments[0].line == expected, line


def test_build_payload_inline_comment_shape() -> None:
    """Inline comments carry ``side="RIGHT"``, the rendered body and the fingerprint."""
    finding = make_finding()
    payload = build_payload([make_anchored(finding)], [db_file_diff()])
    comment = payload.inline_comments[0]
    assert comment.side == "RIGHT"
    assert comment.path == "app/db.py"
    assert comment.body == render_inline_body(finding)
    assert comment.fingerprint == fingerprint(finding)
    assert payload.event == DEFAULT_EVENT
    assert payload.marker_seen is False


def test_build_payload_respects_inline_cap() -> None:
    """``max_inline=1`` with four anchored findings yields one inline and three dropped."""
    findings = [make_anchored(make_finding(line=str(10 + n))) for n in range(4)]
    payload = build_payload(findings, [db_file_diff()], max_inline=1)
    assert len(payload.inline_comments) == 1
    assert len(payload.dropped) == 3
    assert payload.inline_comments[0].line == 10
    assert [comment.side for comment in payload.dropped] == ["RIGHT", "RIGHT", "RIGHT"]
    assert "**Inline comments:** 1 · **In this summary:** 3" in payload.summary_body
    assert "### Additional findings" in payload.summary_body
    assert "inline cap reached or GitHub rejected the position" in payload.summary_body


def test_build_payload_file_only_findings_are_grouped_by_file() -> None:
    """A ``file_only`` finding is dropped and rendered under a per-file heading."""
    file_only = make_anchored(
        make_finding(line="99", issue="Untouched line has a hardcoded secret"),
        AnchorStatus.FILE_ONLY,
    )
    inline = make_anchored(make_finding(line="12"))
    payload = build_payload([inline, file_only], [db_file_diff()])

    assert len(payload.inline_comments) == 1
    assert len(payload.dropped) == 1
    assert payload.dropped[0].side == FILE_ONLY
    assert "### `app/db.py`" in payload.summary_body
    assert "Untouched line has a hardcoded secret" in payload.summary_body
    assert "### General findings" not in payload.summary_body


def test_build_payload_unanchored_findings_go_under_general_findings() -> None:
    """An ``unanchored`` finding is dropped and rendered under "General findings"."""
    unanchored = make_anchored(
        make_finding(file="docs/notes.md", issue="Docs mention a removed flag"),
        AnchorStatus.UNANCHORED,
    )
    payload = build_payload([unanchored], [db_file_diff()])

    assert payload.inline_comments == ()
    assert len(payload.dropped) == 1
    assert payload.dropped[0].side == UNANCHORED
    assert "### General findings" in payload.summary_body
    assert "Docs mention a removed flag" in payload.summary_body


def test_build_payload_with_zero_findings_is_empty() -> None:
    """No findings means an empty summary, no comments and nothing dropped."""
    payload = build_payload([], [])
    assert payload.summary_body == ""
    assert payload.inline_comments == ()
    assert payload.dropped == ()
    assert payload.event == DEFAULT_EVENT
    assert payload.marker_seen is False


def test_build_payload_bodies_all_carry_the_marker() -> None:
    """Every inline body and the summary body contain the marker prefix."""
    findings = [
        make_anchored(make_finding(line="12")),
        make_anchored(make_finding(line="30"), AnchorStatus.FILE_ONLY),
    ]
    payload = build_payload(findings, [db_file_diff()])
    assert payload.inline_comments
    for comment in payload.inline_comments:
        assert COMMENT_MARKER_PREFIX in comment.body
    assert COMMENT_MARKER_PREFIX in payload.summary_body


def test_build_payload_is_deterministic() -> None:
    """Two identical calls produce equal payloads."""
    findings = [
        make_anchored(make_finding(line="12")),
        make_anchored(make_finding(line="40"), AnchorStatus.UNANCHORED),
    ]
    first = build_payload(findings, [db_file_diff()], max_inline=1)
    second = build_payload(findings, [db_file_diff()], max_inline=1)
    assert first == second
    assert first.summary_body == second.summary_body


def test_render_summary_body_reproduces_the_built_summary() -> None:
    """``build_payload``'s summary is exactly what ``render_summary_body`` renders."""
    findings = [
        make_anchored(make_finding(line="12")),
        make_anchored(make_finding(line="40"), AnchorStatus.FILE_ONLY),
    ]
    payload = build_payload(findings, [db_file_diff()], max_inline=0)
    rendered = render_summary_body(payload)
    assert rendered == payload.summary_body
    assert rendered.startswith("## Autonomous AI Code Review")
    assert rendered.endswith("-->\n")
    assert render_summary_body(empty_payload()) == ""


def test_build_payload_canonicalises_the_diff_path() -> None:
    """A finding naming ``a/app/db.py`` is posted under the diff's own spelling."""
    finding = make_finding(file="a/app/db.py")
    payload = build_payload([make_anchored(finding)], [db_file_diff("app/db.py")])
    assert payload.inline_comments[0].path == "app/db.py"


def test_build_payload_zero_cap_is_summary_only() -> None:
    """``max_inline=0`` puts every anchored finding in the summary."""
    findings = [make_anchored(make_finding(line="12"))]
    payload = build_payload(findings, [db_file_diff()], max_inline=0)
    assert payload.inline_comments == ()
    assert len(payload.dropped) == 1
    assert "### Additional findings" in payload.summary_body


# --------------------------------------------------------------------------- #
# E. post_review() state machine
# --------------------------------------------------------------------------- #


def test_post_review_without_a_token_never_builds_a_client(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A missing or blank token fails fast, mentions ``GITHUB_TOKEN`` and does no I/O."""
    for token in (None, "", "   "):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        client = FakeClient()
        built = install_client(monkeypatch, client)
        caplog.clear()

        with caplog.at_level(logging.WARNING, logger=LOG_NAME):
            result = post_review(OWNER, REPO, PR, two_finding_payload(), token=token)

        assert result.ok is False, token
        assert result.inline_posted == 0, token
        assert result.inline_demoted == 0, token
        assert result.summary_posted is False, token
        assert result.skipped_dup is False, token
        assert result.error == "GITHUB_TOKEN not configured", token
        assert built == [], token
        assert client.calls == [], token


def test_post_review_with_empty_payload_posts_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No findings at all means success with no client and no request."""
    client = FakeClient()
    built = install_client(monkeypatch, client)

    result = post_review(OWNER, REPO, PR, empty_payload(), token=TOKEN)

    assert result == PostResult(True, 0, 0, False, False, "")
    assert built == []
    assert client.calls == []


def test_post_review_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One GET, one bulk review POST, one summary POST — in that order."""
    payload = two_finding_payload()
    client = FakeClient(
        get_responses=(FakeResponse(200, []),),
        post_responses=(FakeResponse(200, {}), FakeResponse(201, {})),
    )
    built = install_client(monkeypatch, client)

    with caplog.at_level(logging.WARNING, logger=LOG_NAME):
        result = post_review(OWNER, REPO, PR, payload, token=TOKEN, commit_id="deadbeef")

    assert built == [TOKEN]
    assert client.methods == ["GET", "POST", "POST"]
    assert client.calls[0][1] == COMMENTS_URL
    assert client.calls[0][2]["params"] == {"per_page": 100}
    assert [url for url, _ in client.posts] == [REVIEWS_URL, COMMENTS_URL]

    review_body = client.posts[0][1]
    assert review_body["event"] == DEFAULT_EVENT
    assert review_body["commit_id"] == "deadbeef"
    assert review_body["body"] == payload.summary_body
    assert len(review_body["comments"]) == 2
    assert review_body["comments"][0]["side"] == "RIGHT"
    assert review_body["comments"][1]["line"] == 22

    summary_body = client.posts[1][1]["body"]
    assert "## Autonomous AI Code Review" in summary_body
    assert COMMENT_MARKER_PREFIX in summary_body

    assert result == PostResult(True, 2, 0, True, False, "")
    assert client.closed is True


def test_post_review_skips_a_duplicate_summary_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the summary marker is already on the PR, no POST happens at all."""
    payload = two_finding_payload()
    existing = f"earlier review\n\n{COMMENT_MARKER_PREFIX}{summary_marker(payload.summary_body)} -->\n"
    client = FakeClient(get_responses=(FakeResponse(200, [{"body": existing}]),))
    install_client(monkeypatch, client)

    result = post_review(OWNER, REPO, PR, payload, token=TOKEN)

    assert result == PostResult(True, 0, 0, False, True, "")
    assert client.methods == ["GET"]


def test_post_review_posts_when_only_an_unrelated_marker_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A marker from a different review does not suppress this one."""
    payload = two_finding_payload()
    unrelated = f"old\n\n{COMMENT_MARKER_PREFIX}{'a' * 16} -->\n"
    client = FakeClient(
        get_responses=(FakeResponse(200, [{"body": unrelated}]),),
        post_responses=(FakeResponse(201, {}), FakeResponse(201, {})),
    )
    install_client(monkeypatch, client)

    result = post_review(OWNER, REPO, PR, payload, token=TOKEN)

    assert result == PostResult(True, 2, 0, True, False, "")
    assert client.methods == ["GET", "POST", "POST"]


def test_post_review_422_demotes_only_the_rejected_comment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bulk 422 triggers a per-comment retry; the repeat 422 is demoted to the summary."""
    payload = two_finding_payload()
    client = FakeClient(
        get_responses=(FakeResponse(200, []),),
        post_responses=(
            FakeResponse(422, {}),
            FakeResponse(201, {}),
            FakeResponse(422, {}),
            FakeResponse(201, {}),
        ),
    )
    install_client(monkeypatch, client)

    result = post_review(OWNER, REPO, PR, payload, token=TOKEN)

    assert client.methods == ["GET", "POST", "POST", "POST", "POST"]
    assert len(client.posts[1][1]["comments"]) == 1
    assert len(client.posts[2][1]["comments"]) == 1
    assert client.posts[1][1]["body"] == ""
    assert client.posts[1][1]["comments"][0]["line"] == 12

    summary_body = client.posts[3][1]["body"]
    assert "Bare except swallows the real error" in summary_body
    assert "Unparameterised SQL lets a caller inject statements" not in summary_body
    assert "**Inline comments:** 1 · **In this summary:** 1" in summary_body

    assert result == PostResult(True, 1, 1, True, False, "")


def test_post_review_422_on_every_comment_demotes_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When every per-comment retry 422s, all findings move to the summary and it still posts."""
    payload = two_finding_payload()
    client = FakeClient(
        get_responses=(FakeResponse(200, []),),
        post_responses=(
            FakeResponse(422, {}),
            FakeResponse(422, {}),
            FakeResponse(422, {}),
            FakeResponse(201, {}),
        ),
    )
    install_client(monkeypatch, client)

    result = post_review(OWNER, REPO, PR, payload, token=TOKEN)

    summary_body = client.posts[3][1]["body"]
    assert "Unparameterised SQL lets a caller inject statements" in summary_body
    assert "Bare except swallows the real error" in summary_body
    assert "**Inline comments:** 0 · **In this summary:** 2" in summary_body
    assert result == PostResult(True, 0, 2, True, False, "")


def test_post_review_auth_failure_posts_no_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """401 and 403 both fail the post, name the status and never post the summary."""
    for status in (401, 403):
        client = FakeClient(
            get_responses=(FakeResponse(200, []),),
            post_responses=(FakeResponse(status, {}),),
        )
        install_client(monkeypatch, client)

        result = post_review(OWNER, REPO, PR, two_finding_payload(), token=TOKEN)

        assert result.ok is False, status
        assert result.summary_posted is False, status
        assert result.inline_posted == 0, status
        assert result.error == f"GitHub rejected the credentials (HTTP {status})"
        assert client.methods == ["GET", "POST"], status


def test_post_review_404_fails_without_a_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 404 on the review POST fails the post and skips the summary."""
    client = FakeClient(
        get_responses=(FakeResponse(200, []),),
        post_responses=(FakeResponse(404, {}),),
    )
    install_client(monkeypatch, client)

    result = post_review(OWNER, REPO, PR, two_finding_payload(), token=TOKEN)

    assert result.ok is False
    assert result.summary_posted is False
    assert "404" in result.error
    assert client.methods == ["GET", "POST"]


def test_post_review_429_is_retried_once_honouring_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One 429 is slept off for the ``Retry-After`` value, then the review succeeds."""
    slept = install_sleep(monkeypatch)
    client = FakeClient(
        get_responses=(FakeResponse(200, []),),
        post_responses=(
            FakeResponse(429, {}, headers={"Retry-After": "7"}),
            FakeResponse(201, {}),
            FakeResponse(201, {}),
        ),
    )
    install_client(monkeypatch, client)

    result = post_review(OWNER, REPO, PR, two_finding_payload(), token=TOKEN)

    assert slept == [7.0]
    assert client.methods == ["GET", "POST", "POST", "POST"]
    assert [url for url, _ in client.posts] == [REVIEWS_URL, REVIEWS_URL, COMMENTS_URL]
    assert result == PostResult(True, 2, 0, True, False, "")


def test_post_review_429_twice_degrades_to_summary_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second 429 demotes every inline comment and still posts the summary."""
    slept = install_sleep(monkeypatch)
    payload = two_finding_payload()
    client = FakeClient(
        get_responses=(FakeResponse(200, []),),
        post_responses=(
            FakeResponse(429, {}, headers={"Retry-After": "2"}),
            FakeResponse(429, {}, headers={"Retry-After": "2"}),
            FakeResponse(201, {}),
        ),
    )
    install_client(monkeypatch, client)

    result = post_review(OWNER, REPO, PR, payload, token=TOKEN)

    assert slept == [2.0]
    assert client.methods == ["GET", "POST", "POST", "POST"]
    summary_body = client.posts[2][1]["body"]
    assert "Unparameterised SQL lets a caller inject statements" in summary_body
    assert "Bare except swallows the real error" in summary_body
    assert result == PostResult(True, 0, len(payload.inline_comments), True, False, "")


def test_post_review_transport_error_does_not_escape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ``httpx.ConnectError`` on the review POST becomes ``ok=False``, never an exception."""
    client = FakeClient(
        get_responses=(FakeResponse(200, []),),
        post_responses=(httpx.ConnectError("connection refused"),),
    )
    install_client(monkeypatch, client)

    result = post_review(OWNER, REPO, PR, two_finding_payload(), token=TOKEN)

    assert result.ok is False
    assert result.summary_posted is False
    assert result.error == "network error contacting GitHub (ConnectError)"
    assert client.methods == ["GET", "POST"]


def test_post_review_transport_error_on_marker_check_does_not_escape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transport error on the duplicate-check GET also degrades instead of raising."""
    client = FakeClient(get_responses=(httpx.ConnectError("dns failure"),))
    install_client(monkeypatch, client)

    result = post_review(OWNER, REPO, PR, two_finding_payload(), token=TOKEN)

    assert result.ok is False
    assert result.summary_posted is False
    assert result.error == "network error contacting GitHub (ConnectError)"
    assert client.methods == ["GET"]


def test_post_review_500_fails_without_a_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 5xx fails the post with a typed message and no summary POST."""
    client = FakeClient(
        get_responses=(FakeResponse(200, []),),
        post_responses=(FakeResponse(503, {}),),
    )
    install_client(monkeypatch, client)

    result = post_review(OWNER, REPO, PR, two_finding_payload(), token=TOKEN)

    assert result.ok is False
    assert result.summary_posted is False
    assert result.error == "GitHub is unavailable (HTTP 503)"
    assert client.methods == ["GET", "POST"]


def test_post_review_summary_failure_reports_not_posted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 403 on the summary POST keeps the inline count but reports failure."""
    client = FakeClient(
        get_responses=(FakeResponse(200, []),),
        post_responses=(FakeResponse(201, {}), FakeResponse(403, {})),
    )
    install_client(monkeypatch, client)

    result = post_review(OWNER, REPO, PR, two_finding_payload(), token=TOKEN)

    assert result.ok is False
    assert result.inline_posted == 2
    assert result.summary_posted is False
    assert result.error == "GitHub rejected the credentials (HTTP 403)"


def test_post_review_never_leaks_the_token(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The token appears in no error, no posted body and no log record."""
    client = FakeClient(
        get_responses=(FakeResponse(200, []),),
        post_responses=(FakeResponse(401, {}),),
    )
    built = install_client(monkeypatch, client)

    with caplog.at_level(logging.WARNING, logger=LOG_NAME):
        result = post_review(OWNER, REPO, PR, two_finding_payload(), token=TOKEN)

    assert built == [TOKEN]
    assert TOKEN not in result.error
    assert TOKEN not in repr(client.calls)
    assert TOKEN not in caplog.text
    assert "Bearer" not in caplog.text


# --------------------------------------------------------------------------- #
# F. Logging discipline
# --------------------------------------------------------------------------- #


def test_happy_path_logs_no_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A clean post emits zero WARNING records on ``reviewer.github``."""
    client = FakeClient(
        get_responses=(FakeResponse(200, []),),
        post_responses=(FakeResponse(201, {}), FakeResponse(201, {})),
    )
    install_client(monkeypatch, client)

    with caplog.at_level(logging.WARNING, logger=LOG_NAME):
        result = post_review(OWNER, REPO, PR, two_finding_payload(), token=TOKEN)

    assert result.ok is True
    warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert warnings == []


def test_each_degraded_path_logs_exactly_one_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Every degraded post emits exactly one WARNING, naming the reason."""
    cases: tuple[tuple[tuple[Any, ...], tuple[Any, ...], str], ...] = (
        ((FakeResponse(200, []),), (FakeResponse(401, {}),), "rejected the credentials"),
        ((FakeResponse(200, []),), (FakeResponse(503, {}),), "unavailable"),
        ((FakeResponse(200, []),), (httpx.ConnectError("boom"),), "network error"),
        ((FakeResponse(404, {}),), (), "could not find"),
    )
    for get_responses, post_responses, expected_fragment in cases:
        client = FakeClient(get_responses=get_responses, post_responses=post_responses)
        install_client(monkeypatch, client)
        caplog.clear()

        with caplog.at_level(logging.WARNING, logger=LOG_NAME):
            result = post_review(OWNER, REPO, PR, two_finding_payload(), token=TOKEN)

        assert result.ok is False, expected_fragment
        warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
        assert len(warnings) == 1, expected_fragment
        assert warnings[0].name == LOG_NAME, expected_fragment
        assert expected_fragment in warnings[0].getMessage()


def test_demotion_logs_exactly_one_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A 422 demotion logs one warning even though the post ultimately succeeds."""
    client = FakeClient(
        get_responses=(FakeResponse(200, []),),
        post_responses=(
            FakeResponse(422, {}),
            FakeResponse(422, {}),
            FakeResponse(422, {}),
            FakeResponse(201, {}),
        ),
    )
    install_client(monkeypatch, client)

    with caplog.at_level(logging.WARNING, logger=LOG_NAME):
        result = post_review(OWNER, REPO, PR, two_finding_payload(), token=TOKEN)

    assert result.ok is True
    assert result.inline_demoted == 2
    warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert len(warnings) == 1
    assert "moved to the summary" in warnings[0].getMessage()


def test_missing_token_logs_one_warning_without_the_token(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The no-token path warns once about ``GITHUB_TOKEN`` and logs nothing sensitive."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    client = FakeClient()
    install_client(monkeypatch, client)

    with caplog.at_level(logging.WARNING, logger=LOG_NAME):
        post_review(OWNER, REPO, PR, two_finding_payload(), token=None)

    warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert len(warnings) == 1
    assert "GITHUB_TOKEN" in warnings[0].getMessage()
    assert "Authorization" not in caplog.text


# --------------------------------------------------------------------------- #
# G. github_available()
# --------------------------------------------------------------------------- #


def test_github_available_false_without_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """No configured token means PR posting is unavailable."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert github_available() is False


def test_github_available_false_for_a_blank_token() -> None:
    """A blank token counts as missing."""
    for blank in ("", "   "):
        assert github_available(blank) is False, repr(blank)


def test_github_available_true_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """A token in the environment makes posting available, with no argument needed."""
    monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
    assert github_available() is True


def test_github_available_true_from_the_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit token wins over an empty environment."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert github_available(TOKEN) is True
