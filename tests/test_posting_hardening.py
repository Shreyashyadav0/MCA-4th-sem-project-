"""Hardening tests added after the mutation audit.

The audit found six defences with no test behind them: pagination of the marker
listing, the SSRF guard on a `Link` header, `Retry-After` hardening, the posting
target validator, the configured inline cap reaching `build_payload`, and the
literal wire format of the summary marker. Each one is a real failure mode, so each
gets a test here rather than a comment claiming it works.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.github_client as gc
from app.main import app
from app.parser import anchor_findings, parse_diff_file
from app.rules import review_diff

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "sample.diff"

@pytest.fixture(autouse=True)
def _allow_unsigned_webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    """Opt this module into unsigned webhook posting (the app defaults to refusing)."""
    monkeypatch.setenv("WEBHOOK_ALLOW_UNSIGNED", "1")

client = TestClient(app)


class _Resp:
    """Minimal httpx.Response stand-in."""

    def __init__(self, status_code: int, body: object | None = None, headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.headers = headers or {}
        self.text = ""

    def json(self) -> object:
        return self._body


class _Client:
    """Fake GitHub client that scripts GET pages and records calls."""

    def __init__(self, pages: list[_Resp] | None = None, post_status: int = 201) -> None:
        self.pages = pages or []
        self.post_status = post_status
        self.calls: list[tuple[str, str]] = []

    def get(self, url: str, **kwargs: object) -> _Resp:
        self.calls.append(("GET", url))
        if not self.pages:
            return _Resp(200, [])
        return self.pages.pop(0)

    def post(self, url: str, **kwargs: object) -> _Resp:
        self.calls.append(("POST", url))
        return _Resp(self.post_status, {"id": 1})

    def close(self) -> None:
        return None


def _payload() -> gc.ReviewPayload:
    """Build a real payload from the sample diff."""
    bundle = parse_diff_file(SAMPLE)
    findings = anchor_findings(bundle, review_diff(bundle))
    return gc.build_payload(findings, bundle.files)


# --------------------------------------------------------------------------- #
# Pagination: a marker on page 2 must still be found
# --------------------------------------------------------------------------- #


def test_marker_on_a_later_page_is_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skipping pagination would double-post on any PR with more than 100 comments."""
    payload = _payload()
    marker = gc._summary_fingerprint(payload)
    next_url = "https://api.github.com/repos/o/r/issues/1/comments?per_page=100&page=2"
    fake = _Client(
        pages=[
            _Resp(200, [{"body": "unrelated comment"}], {"Link": f'<{next_url}>; rel="next"'}),
            _Resp(200, [{"body": f"<!-- ai-code-reviewer:{marker} -->"}]),
        ]
    )
    monkeypatch.setattr(gc, "_build_github_client", lambda token: fake)

    result = gc.post_review("o", "r", 1, payload, token="ghp_x")

    assert result.ok is True
    assert result.skipped_dup is True
    assert [method for method, _ in fake.calls] == ["GET", "GET"]
    assert not [call for call in fake.calls if call[0] == "POST"]


# --------------------------------------------------------------------------- #
# The PAT must never follow a Link header off api.github.com
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "url",
    [
        "https://attacker.example/collect",
        "http://api.github.com/repos/o/r/issues/1/comments?page=2",
        "https://api.github.com.evil.example/x",
        "ftp://api.github.com/x",
    ],
)
def test_safe_next_url_refuses_offsite_links(url: str) -> None:
    """A hostile Link header must not redirect the bearer token."""
    assert gc._safe_next_url(url) is None


@pytest.mark.parametrize(
    "url",
    ["https://api.github.com/repos/o/r/issues/1/comments?page=2", "/repos/o/r/issues/1/comments?page=2"],
)
def test_safe_next_url_allows_the_api_host(url: str) -> None:
    """Legitimate pagination keeps working."""
    assert gc._safe_next_url(url) == url


def test_hostile_link_stops_pagination_without_posting(monkeypatch: pytest.MonkeyPatch) -> None:
    """An offsite next-link ends the listing; the review still posts once."""
    payload = _payload()
    fake = _Client(
        pages=[_Resp(200, [], {"Link": '<https://attacker.example/collect>; rel="next"'})]
    )
    monkeypatch.setattr(gc, "_build_github_client", lambda token: fake)

    result = gc.post_review("o", "r", 1, payload, token="ghp_x")

    assert result.ok is True
    assert all("attacker.example" not in url for _, url in fake.calls)


# --------------------------------------------------------------------------- #
# Retry-After hardening
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("header", ["nan", "inf", "-inf", "abc", ""])
def test_retry_after_rejects_unusable_values(header: str) -> None:
    """`nan`/`inf` would reach time.sleep and raise; they must be refused."""
    assert gc._retry_after(_Resp(429, {}, {"Retry-After": header})) is None


@pytest.mark.parametrize(("header", "expected"), [("-5", 0.0), ("0", 0.0), ("2", 2.0), ("7", 7.0)])
def test_retry_after_parses_and_floors_at_zero(header: str, expected: float) -> None:
    assert gc._retry_after(_Resp(429, {}, {"Retry-After": header})) == expected


def test_retry_after_is_capped() -> None:
    """A hostile 9999-second header cannot wedge a worker."""
    value = gc._retry_after(_Resp(429, {}, {"Retry-After": "9999"}))
    assert value is not None and value <= gc._MAX_RETRY_AFTER


# --------------------------------------------------------------------------- #
# Posting-target validation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("owner,repo", [("..", ".."), ("a b", "r"), ("a", "a?x=1"), ("", "r"), ("a" * 500, "r")])
def test_validate_target_rejects_hostile_values(owner: str, repo: str) -> None:
    assert gc._validate_target(owner, repo, 1) is not None


@pytest.mark.parametrize("owner,repo", [("shreyash", "ai-code-reviewer"), ("a.b", "c_d-e")])
def test_validate_target_accepts_github_names(owner: str, repo: str) -> None:
    assert gc._validate_target(owner, repo, 7) is None


@pytest.mark.parametrize("number", [0, -1])
def test_validate_target_rejects_bad_pr_numbers(number: int) -> None:
    assert gc._validate_target("o", "r", number) is not None


def test_post_review_refuses_a_hostile_target_before_any_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing may reach the network for a target that cannot be trusted."""
    fake = _Client()
    monkeypatch.setattr(gc, "_build_github_client", lambda token: fake)

    result = gc.post_review("../..", "..", 1, _payload(), token="ghp_x")

    assert result.ok is False
    assert fake.calls == []


def test_webhook_refuses_a_hostile_repository_target(monkeypatch: pytest.MonkeyPatch) -> None:
    """The webhook stays 200 and reports the failure instead of posting."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_value")
    fake = _Client()
    monkeypatch.setattr(gc, "_build_github_client", lambda token: fake)
    payload = {
        "action": "opened",
        "number": 3,
        "repository": {"full_name": "../../etc#3"},
        "diff": "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1,2 @@\n import os\n+API_KEY = 'ghp_abcdefghijklmnopqrstuvwxyz1234'\n",
    }
    response = client.post("/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["posting"]["ok"] is False
    assert not [call for call in fake.calls if call[0] == "POST"]


# --------------------------------------------------------------------------- #
# Config wiring and marker wire format
# --------------------------------------------------------------------------- #


def test_configured_inline_cap_reaches_the_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """GITHUB_MAX_INLINE must actually bound the webhook's inline comments."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_value")
    monkeypatch.setenv("GITHUB_MAX_INLINE", "1")
    fake = _Client()
    monkeypatch.setattr(gc, "_build_github_client", lambda token: fake)
    payload = {
        "action": "opened",
        "number": 4,
        "repository": {"full_name": "o/r"},
        "diff": "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1,4 @@\n import os\n+API_KEY = 'ghp_abcdefghijklmnopqrstuvwxyz1234'\n+os.system(f'rm -rf {path}')\n+data = pickle.loads(blob)\n",
    }
    body = client.post("/webhook", json=payload).json()
    assert body["posting"]["ok"] is True
    assert body["posting"]["inline_posted"] == 1


def test_summary_marker_is_a_literal_sixteen_hex_token() -> None:
    """Pinned as a literal shape, not a round trip through the same helper."""
    payload = _payload()
    marker = gc._summary_fingerprint(payload)
    assert re.fullmatch(r"[0-9a-f]{16}", marker)
    assert f"{gc.COMMENT_MARKER_PREFIX}{marker} -->" in payload.summary_body


def test_inline_marker_uses_the_finding_fingerprint() -> None:
    """The inline marker must be the finding's own fingerprint, not a summary hash."""
    payload = _payload()
    for comment in payload.inline_comments:
        assert comment.body.rstrip().endswith(f"{gc.COMMENT_MARKER_PREFIX}{comment.fingerprint} -->")
