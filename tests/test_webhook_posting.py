"""Offline integration tests for the Phase 5 webhook → pull-request posting path.

What is under test
------------------
``POST /webhook`` in :mod:`app.main`, driven end to end through
``fastapi.testclient.TestClient`` — the HMAC gate, the action gate, the diff
source fallback, :func:`app.main._publish_review`, and the ``posting`` field it
adds to ``ReviewResponse``.

Fake-client strategy (no network anywhere)
-----------------------------------------
``app.github_client`` funnels every HTTP touch through one seam,
``_build_github_client(token)``. Every test here monkeypatches that seam to
return a :class:`FakeClient`, so nothing leaves the process:

* :class:`FakeClient` records **every** request as a :class:`RecordedRequest`
  (method, url, json body, params) in call order. Assertions are therefore on
  exact call counts and exact endpoints — ``fake.post_urls == [REVIEWS_URL,
  COMMENTS_URL]`` — never on "something was called".
* The GET (the duplicate-marker listing) replays ``existing_comments``, and the
  POSTs replay a scripted ``post_queue`` of :class:`FakeResponse` objects or
  exception instances (that is how a 401, a 500, a 422 and an
  ``httpx.ConnectError`` are simulated without a socket).
* ``install_client`` also records the token(s) the seam was called with, so
  "``_build_github_client`` was never called" is assertable exactly.

Every test pins the credential state with ``monkeypatch.setenv`` /
``delenv`` — ``GITHUB_TOKEN``, ``GITHUB_WEBHOOK_SECRET``, ``SARVAM_API_KEY`` —
so a developer's shell cannot change the outcome and the review always degrades
to the local rule engine. All tests are in-process and take milliseconds.

Diff fixtures
-------------
``BAD_DIFF`` is a two-finding patch whose findings both anchor inside the
added lines, so a review produces two inline comments and one summary without
needing the bundled fixture or the GitHub diff fetch. ``CLEAN_DIFF`` yields
zero findings, which is the contract's "post nothing at all" case.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import httpx
import pytest
from fastapi.testclient import TestClient

from app import github_client
from app.github_client import COMMENT_MARKER_PREFIX
from app.main import app

TOKEN = "ghp_webhook_test_token_do_not_leak_0002"
SECRET = "webhook-secret-for-tests"
OWNER = "octo"
REPO = "repo"
PR = 5
HEAD_SHA = "cafe1234deadbeef5678"

REVIEWS_URL = f"/repos/{OWNER}/{REPO}/pulls/{PR}/reviews"
COMMENTS_URL = f"/repos/{OWNER}/{REPO}/issues/{PR}/comments"

GITHUB_LOG = "reviewer.github"
API_LOG = "reviewer.api"

_MARKER_RE = re.compile(re.escape(COMMENT_MARKER_PREFIX) + r"[0-9a-f]{16} -->")

BAD_DIFF = """diff --git a/app/db.py b/app/db.py
--- a/app/db.py
+++ b/app/db.py
@@ -1,2 +1,4 @@
 import sqlite3
 
+def get_user(db, uid):
+    return db.execute(f"SELECT * FROM users WHERE id = {uid}")
"""

CLEAN_DIFF = """diff --git a/app/ok.py b/app/ok.py
--- a/app/ok.py
+++ b/app/ok.py
@@ -1,2 +1,3 @@
 import os
 
+CONST = 1
"""

@pytest.fixture(autouse=True)
def _allow_unsigned_webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    """Opt this module into unsigned webhook posting.

    The application refuses to post from an unauthenticated delivery by default. These
    tests exercise the posting state machine, so they turn that guard off explicitly
    rather than weakening it for everyone.
    """
    monkeypatch.setenv("WEBHOOK_ALLOW_UNSIGNED", "1")


client = TestClient(app)


# --------------------------------------------------------------------------- #
# Fakes: a recording httpx.Client stand-in and its responses
# --------------------------------------------------------------------------- #


class FakeResponse:
    """The slice of ``httpx.Response`` the posting code actually reads."""

    def __init__(
        self,
        status_code: int = 200,
        payload: Any = None,
        headers: Mapping[str, str] | None = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = [] if payload is None else payload
        self.headers = dict(headers or {})
        self.text = text

    def json(self) -> Any:
        """Return the scripted JSON body."""
        return self._payload


@dataclass(frozen=True)
class RecordedRequest:
    """One request the fake client saw, exactly as the code sent it."""

    method: str
    url: str
    json_body: Any = None
    params: Any = None


class FakeClient:
    """Records every request and replays a scripted queue of responses.

    A ``post_queue`` item is either a :class:`FakeResponse` to return or an
    exception instance to raise, which is how a transport failure is simulated
    without a socket. Once the queue is empty a 201 is returned, so a test that
    only cares about the first POST does not have to script the rest.
    """

    def __init__(
        self,
        *,
        existing_comments: Sequence[Mapping[str, Any]] | None = None,
        get_status: int = 200,
        post_queue: Sequence[Any] = (),
    ) -> None:
        self._existing = list(existing_comments or [])
        self._get_status = get_status
        self._posts: list[Any] = list(post_queue)
        self.calls: list[RecordedRequest] = []
        self.closed = False

    def get(self, url: str, params: Any = None) -> FakeResponse:
        """Record a GET and replay the scripted comment listing."""
        self.calls.append(RecordedRequest("GET", url, None, params))
        return FakeResponse(self._get_status, list(self._existing))

    def post(self, url: str, json: Any = None) -> FakeResponse:  # noqa: A002 - mirror httpx
        """Record a POST and return (or raise) the next scripted item."""
        self.calls.append(RecordedRequest("POST", url, json, None))
        if not self._posts:
            return FakeResponse(201, {})
        item = self._posts.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    def close(self) -> None:
        """Record that the module closed the client."""
        self.closed = True

    @property
    def get_count(self) -> int:
        """How many GETs were issued."""
        return sum(1 for call in self.calls if call.method == "GET")

    @property
    def posts(self) -> list[RecordedRequest]:
        """Every recorded POST, in order."""
        return [call for call in self.calls if call.method == "POST"]

    @property
    def post_urls(self) -> list[str]:
        """The url of every recorded POST, in order."""
        return [call.url for call in self.posts]


# --------------------------------------------------------------------------- #
# Helpers: install the fake seam, pin credentials, build payloads
# --------------------------------------------------------------------------- #


def install_client(monkeypatch: pytest.MonkeyPatch, fake: FakeClient) -> list[str]:
    """Patch the client seam and return the list of tokens it was called with."""
    built: list[str] = []

    def _fake_build(token: str) -> FakeClient:
        built.append(token)
        return fake

    monkeypatch.setattr(github_client, "_build_github_client", _fake_build)
    return built


def clear_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every credential and mode override the app reads."""
    for name in ("SARVAM_API_KEY", "REVIEW_MODE", "GITHUB_TOKEN", "GITHUB_WEBHOOK_SECRET"):
        monkeypatch.delenv(name, raising=False)


def configure_token(monkeypatch: pytest.MonkeyPatch, token: str = TOKEN) -> str:
    """Put the app in "token configured, no webhook secret" mode."""
    clear_credentials(monkeypatch)
    monkeypatch.setenv("GITHUB_TOKEN", token)
    return token


def pr_payload(
    *,
    action: str = "opened",
    diff: str = BAD_DIFF,
    number: int | None = PR,
    sha: str | None = HEAD_SHA,
    full_name: str | None = f"{OWNER}/{REPO}",
) -> dict[str, Any]:
    """Build a ``pull_request`` webhook body, omitting the parts passed as ``None``."""
    pull_request: dict[str, Any] = {}
    if number is not None:
        pull_request["number"] = number
    if sha is not None:
        pull_request["head"] = {"sha": sha}
    payload: dict[str, Any] = {"action": action, "diff": diff, "pull_request": pull_request}
    if number is not None:
        payload["number"] = number
    if full_name is not None:
        payload["repository"] = {"full_name": full_name}
    return payload


def sign(body: bytes, secret: str = SECRET) -> str:
    """Compute the ``X-Hub-Signature-256`` header value GitHub would send."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def post_webhook(
    payload: Mapping[str, Any],
    *,
    headers: Mapping[str, str] | None = None,
) -> httpx.Response:
    """Deliver one webhook body to ``POST /webhook``."""
    return client.post("/webhook", json=dict(payload), headers=dict(headers or {}))


# --------------------------------------------------------------------------- #
# 1. The three posting triggers
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("action", ["opened", "reopened", "synchronize"])
def test_trigger_action_posts_inline_review_and_summary(
    monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    """opened / reopened / synchronize post, and report a successful posting."""
    configure_token(monkeypatch)
    fake = FakeClient()
    built = install_client(monkeypatch, fake)

    response = post_webhook(pr_payload(action=action))

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "inline_diff"
    assert len(body["review"]["findings"]) == 2
    assert body["posting"] == {
        "ok": True,
        "inline_posted": 2,
        "inline_demoted": 0,
        "summary_posted": True,
        "skipped_dup": False,
        "error": "",
    }
    assert built == [TOKEN]
    assert fake.get_count == 1
    assert fake.post_urls == [REVIEWS_URL, COMMENTS_URL]
    assert fake.closed is True


def test_posting_targets_the_contract_endpoints_with_the_contract_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The GET lists issue comments once; the POSTs carry the documented bodies."""
    configure_token(monkeypatch)
    fake = FakeClient()
    install_client(monkeypatch, fake)

    assert post_webhook(pr_payload()).status_code == 200

    listing = fake.calls[0]
    assert listing.method == "GET"
    assert listing.url == COMMENTS_URL
    assert listing.params == {"per_page": 100}

    review_post, summary_post = fake.posts
    assert set(review_post.json_body) == {"body", "event", "comments", "commit_id"}
    assert review_post.json_body["event"] == "COMMENT"
    assert [comment["path"] for comment in review_post.json_body["comments"]] == [
        "app/db.py",
        "app/db.py",
    ]
    assert all(comment["side"] == "RIGHT" for comment in review_post.json_body["comments"])
    assert set(summary_post.json_body) == {"body"}
    assert _MARKER_RE.search(summary_post.json_body["body"]) is not None


# --------------------------------------------------------------------------- #
# 2. Actions that must not post
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("action", ["closed", "labeled"])
def test_unreviewed_action_is_acknowledged_and_never_posts(
    monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    """An action outside the reviewed set is acked, not reviewed, and not posted."""
    configure_token(monkeypatch)
    fake = FakeClient()
    built = install_client(monkeypatch, fake)

    response = post_webhook(pr_payload(action=action))

    assert response.status_code == 200
    assert response.json() == {
        "status": "ignored",
        "event": "pull_request",
        "detail": f"action '{action}' is not reviewed",
    }
    assert "posting" not in response.json()
    assert built == []
    assert fake.calls == []


@pytest.mark.parametrize("action", ["ready_for_review", "edited"])
def test_reviewed_action_outside_the_post_set_has_no_posting(
    monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    """Reviewed actions outside opened/reopened/synchronize answer with posting=None."""
    configure_token(monkeypatch)
    fake = FakeClient()
    built = install_client(monkeypatch, fake)

    response = post_webhook(pr_payload(action=action))

    assert response.status_code == 200
    body = response.json()
    assert body["posting"] is None
    assert len(body["review"]["findings"]) == 2
    assert body["comment"].startswith("## Autonomous AI Code Review")
    assert built == []
    assert fake.calls == []


def test_non_pull_request_event_never_posts(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ping delivery is ignored before any review or post happens."""
    configure_token(monkeypatch)
    fake = FakeClient()
    built = install_client(monkeypatch, fake)

    response = client.post(
        "/webhook", json=dict(pr_payload()), headers={"X-GitHub-Event": "ping"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert response.json()["event"] == "ping"
    assert built == []
    assert fake.calls == []


# --------------------------------------------------------------------------- #
# 3. No token configured
# --------------------------------------------------------------------------- #


def test_missing_token_never_builds_a_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without GITHUB_TOKEN the review is returned but nothing is posted."""
    clear_credentials(monkeypatch)
    fake = FakeClient()
    built = install_client(monkeypatch, fake)

    response = post_webhook(pr_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["posting"] is None
    assert len(body["review"]["findings"]) == 2
    assert built == []
    assert fake.calls == []


# --------------------------------------------------------------------------- #
# 4. Posting failures never change the HTTP status
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("status", "fragment"), [(401, "401"), (500, "500")])
def test_posting_failure_still_returns_200_with_the_review(
    monkeypatch: pytest.MonkeyPatch, status: int, fragment: str
) -> None:
    """A 401 or 5xx on the inline review is reported in `posting`, never as a 5xx."""
    configure_token(monkeypatch)
    fake = FakeClient(post_queue=[FakeResponse(status, {"message": "nope"})])
    install_client(monkeypatch, fake)

    response = post_webhook(pr_payload())

    assert response.status_code == 200
    body = response.json()
    posting = body["posting"]
    assert posting is not None
    assert posting["ok"] is False
    assert posting["summary_posted"] is False
    assert posting["error"] != ""
    assert fragment in posting["error"]
    # The review itself survives untouched.
    assert body["comment"].startswith("## Autonomous AI Code Review")
    assert len(body["review"]["findings"]) == 2
    assert body["stats"]["findings"] == 2
    # No summary POST is attempted after a failed inline review.
    assert fake.post_urls == [REVIEWS_URL]


def test_transport_error_still_returns_200_with_the_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An httpx transport error is degraded to posting.ok=False and HTTP 200."""
    configure_token(monkeypatch)
    fake = FakeClient(post_queue=[httpx.ConnectError("connection refused")])
    install_client(monkeypatch, fake)

    response = post_webhook(pr_payload())

    assert response.status_code == 200
    body = response.json()
    posting = body["posting"]
    assert posting is not None
    assert posting["ok"] is False
    assert posting["inline_posted"] == 0
    assert posting["summary_posted"] is False
    assert "ConnectError" in posting["error"]
    assert len(body["review"]["findings"]) == 2
    assert fake.post_urls == [REVIEWS_URL]


def test_posting_failure_logs_once_and_never_leaks_the_token(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """One WARNING for the degraded post, on the module logger, with no credential."""
    configure_token(monkeypatch)
    fake = FakeClient(post_queue=[FakeResponse(401, {"message": "bad credentials"})])
    install_client(monkeypatch, fake)
    caplog.set_level(logging.DEBUG)

    assert post_webhook(pr_payload()).status_code == 200

    warnings = [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING and record.name in {GITHUB_LOG, API_LOG}
    ]
    assert len(warnings) == 1
    assert warnings[0].name == GITHUB_LOG
    assert TOKEN not in caplog.text


# --------------------------------------------------------------------------- #
# 5. Duplicate delivery
# --------------------------------------------------------------------------- #


def test_duplicate_delivery_is_skipped_without_any_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A PR already carrying the summary marker is acknowledged, not posted twice."""
    configure_token(monkeypatch)
    payload = pr_payload()

    first = FakeClient()
    install_client(monkeypatch, first)
    assert post_webhook(payload).status_code == 200
    assert len(first.posts) == 2
    first_summary = first.posts[1].json_body["body"]
    marker = _MARKER_RE.search(first_summary)
    assert marker is not None

    second = FakeClient(existing_comments=[{"body": f"prior review\n\n{marker.group(0)}\n"}])
    install_client(monkeypatch, second)

    response = post_webhook(payload)

    assert response.status_code == 200
    posting = response.json()["posting"]
    assert posting is not None
    assert posting["ok"] is True
    assert posting["skipped_dup"] is True
    assert posting["inline_posted"] == 0
    assert posting["inline_demoted"] == 0
    assert posting["summary_posted"] is False
    assert posting["error"] == ""
    assert second.get_count == 1
    assert second.posts == []


# --------------------------------------------------------------------------- #
# 6. 422 on the bulk inline review demotes instead of failing
# --------------------------------------------------------------------------- #


def test_422_demotes_a_comment_and_still_posts_the_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 422 costs one inline comment, which moves into the summary."""
    configure_token(monkeypatch)
    fake = FakeClient(
        post_queue=[
            FakeResponse(422, {"message": "line is not part of the diff"}),
            FakeResponse(200, {}),
            FakeResponse(422, {"message": "line is not part of the diff"}),
            FakeResponse(201, {}),
        ]
    )
    install_client(monkeypatch, fake)

    response = post_webhook(pr_payload())

    assert response.status_code == 200
    posting = response.json()["posting"]
    assert posting is not None
    assert posting["ok"] is True
    assert posting["inline_demoted"] > 0
    assert posting["inline_posted"] == 1
    assert posting["summary_posted"] is True
    assert posting["skipped_dup"] is False
    # bulk review, one retry per comment, then the summary.
    assert fake.post_urls == [REVIEWS_URL, REVIEWS_URL, REVIEWS_URL, COMMENTS_URL]
    assert "### Additional findings" in fake.posts[-1].json_body["body"]


# --------------------------------------------------------------------------- #
# 7. commit_id is honoured
# --------------------------------------------------------------------------- #


def test_commit_id_is_sent_when_the_payload_carries_a_head_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pull_request.head.sha pins the review to that commit."""
    configure_token(monkeypatch)
    fake = FakeClient()
    install_client(monkeypatch, fake)

    assert post_webhook(pr_payload(sha=HEAD_SHA)).status_code == 200

    review_post = fake.posts[0]
    assert review_post.url == REVIEWS_URL
    assert review_post.json_body["commit_id"] == HEAD_SHA


def test_commit_id_is_omitted_when_the_payload_has_no_head_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a head sha the reviews body carries no commit_id key at all."""
    configure_token(monkeypatch)
    fake = FakeClient()
    install_client(monkeypatch, fake)

    assert post_webhook(pr_payload(sha=None)).status_code == 200

    review_post = fake.posts[0]
    assert "commit_id" not in review_post.json_body
    assert set(review_post.json_body) == {"body", "event", "comments"}


# --------------------------------------------------------------------------- #
# 8. An unusable posting target
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "payload_kwargs",
    [
        pytest.param({"full_name": None}, id="missing-repository-full-name"),
        pytest.param({"number": None}, id="missing-pr-number"),
    ],
)
def test_missing_target_is_skipped_with_one_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    payload_kwargs: dict[str, Any],
) -> None:
    """No repository.full_name or no PR number: no post, one WARNING, still 200."""
    configure_token(monkeypatch)
    fake = FakeClient()
    built = install_client(monkeypatch, fake)
    caplog.set_level(logging.DEBUG)

    response = post_webhook(pr_payload(**payload_kwargs))

    assert response.status_code == 200
    assert response.json()["posting"] is None
    assert built == []
    assert fake.calls == []
    warnings = [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING
        and record.name == API_LOG
        and "cannot post the review" in record.getMessage()
    ]
    assert len(warnings) == 1


# --------------------------------------------------------------------------- #
# 9. `posting` is additive and documented in the OpenAPI schema
# --------------------------------------------------------------------------- #


def test_openapi_documents_posting_info_and_the_optional_field() -> None:
    """PostingInfo publishes six described fields; ReviewResponse.posting is optional."""
    schema = client.get("/openapi.json").json()
    schemas = schema["components"]["schemas"]

    posting_info = schemas["PostingInfo"]
    properties = posting_info["properties"]
    assert list(properties) == [
        "ok",
        "inline_posted",
        "inline_demoted",
        "summary_posted",
        "skipped_dup",
        "error",
    ]
    for name, field_schema in properties.items():
        assert field_schema["description"].strip() != "", f"{name} has no description"
    assert posting_info["required"] == [
        "ok",
        "inline_posted",
        "inline_demoted",
        "summary_posted",
        "skipped_dup",
        "error",
    ]

    review_response = schemas["ReviewResponse"]
    posting_field = review_response["properties"]["posting"]
    assert posting_field["description"].strip() != ""
    assert {"$ref": "#/components/schemas/PostingInfo"} in posting_field["anyOf"]
    assert {"type": "null"} in posting_field["anyOf"]
    assert "posting" not in review_response.get("required", [])


# --------------------------------------------------------------------------- #
# 10. Every existing endpoint is unchanged and never posts
# --------------------------------------------------------------------------- #


def test_review_endpoint_never_posts(monkeypatch: pytest.MonkeyPatch) -> None:
    """/review keeps its old shape and never touches the GitHub client."""
    configure_token(monkeypatch)
    fake = FakeClient()
    built = install_client(monkeypatch, fake)

    response = client.post("/review", json={"diff": BAD_DIFF})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "source",
        "notice",
        "review",
        "comment",
        "stats",
        "provider",
        "model",
        "posting",
    }
    assert body["source"] == "inline_diff"
    assert body["posting"] is None
    assert len(body["review"]["findings"]) == 2
    assert built == []
    assert fake.calls == []


def test_test_review_endpoints_never_post(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both /test-review verbs keep their old shape and never touch GitHub."""
    configure_token(monkeypatch)
    fake = FakeClient()
    built = install_client(monkeypatch, fake)

    demo = client.get("/test-review")
    body_demo = client.post("/test-review", json={"diff": BAD_DIFF})

    assert demo.status_code == 200
    assert demo.json()["source"] == "sample_fixture"
    assert demo.json()["posting"] is None
    assert demo.json()["notice"] == "sample fixture: sample.diff"
    assert body_demo.status_code == 200
    assert body_demo.json()["source"] == "inline_diff"
    assert body_demo.json()["posting"] is None
    assert built == []
    assert fake.calls == []


def test_ops_endpoints_are_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """/, /health and /rules answer exactly as before Phase 5 posting."""
    configure_token(monkeypatch)
    fake = FakeClient()
    built = install_client(monkeypatch, fake)

    root = client.get("/")
    health = client.get("/health")
    rules = client.get("/rules")

    assert root.status_code == 200
    assert set(root.json()) == {"name", "version", "mode", "rules", "endpoints", "docs"}
    assert "/webhook" in root.json()["endpoints"]
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["github_token"] == "configured"
    assert health.json()["webhook_secret"] == "missing"
    assert rules.status_code == 200
    assert set(rules.json()[0]) == {"id", "title", "category", "owasp", "severity"}
    assert built == []
    assert fake.calls == []


# --------------------------------------------------------------------------- #
# 11. HMAC interplay
# --------------------------------------------------------------------------- #


def test_bad_signature_is_401_and_posts_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """With a secret configured, a wrong signature is rejected before any review."""
    configure_token(monkeypatch)
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)
    fake = FakeClient()
    built = install_client(monkeypatch, fake)
    body = json.dumps(pr_payload()).encode("utf-8")

    response = client.post(
        "/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sign(body, "wrong")},
    )

    assert response.status_code == 401
    assert built == []
    assert fake.calls == []


def test_valid_signature_posts_normally(monkeypatch: pytest.MonkeyPatch) -> None:
    """A correct HMAC signature lets the delivery through and the post happens."""
    configure_token(monkeypatch)
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)
    fake = FakeClient()
    install_client(monkeypatch, fake)
    body = json.dumps(pr_payload()).encode("utf-8")

    response = client.post(
        "/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sign(body)},
    )

    assert response.status_code == 200
    posting = response.json()["posting"]
    assert posting is not None
    assert posting["ok"] is True
    assert posting["inline_posted"] == 2
    assert fake.post_urls == [REVIEWS_URL, COMMENTS_URL]


# --------------------------------------------------------------------------- #
# 12. A clean diff posts nothing at all
# --------------------------------------------------------------------------- #


def test_clean_diff_posts_nothing_at_all(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zero findings means no inline comment and no summary — and no HTTP at all."""
    configure_token(monkeypatch)
    fake = FakeClient()
    built = install_client(monkeypatch, fake)

    response = post_webhook(pr_payload(diff=CLEAN_DIFF))

    assert response.status_code == 200
    body = response.json()
    assert body["stats"]["findings"] == 0
    assert body["review"]["findings"] == []
    posting = body["posting"]
    assert posting is not None
    assert posting["ok"] is True
    assert posting["inline_posted"] == 0
    assert posting["inline_demoted"] == 0
    assert posting["summary_posted"] is False
    assert posting["skipped_dup"] is False
    assert posting["error"] == ""
    assert built == []
    assert fake.calls == []
