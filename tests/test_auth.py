"""Tests for the role-based access-control layer and its wiring into the API.

Two things are being proved here:

* the dependency behaves as documented — 401 for a missing or unknown key, 403 for
  a role that is too weak, 200 for the right one — and does nothing at all while
  ``API_AUTH_ENABLED`` is false, which is what keeps the existing suite and the
  open demo untouched;
* a broken database changes nothing the caller can see. A review that cannot be
  stored is still a review: it is answered, and exactly one WARNING is logged on
  ``reviewer.db``.

Everything runs in-process through ``TestClient`` against a temporary database.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.auth import ANONYMOUS, UserContext, auth_enabled, require
from app.config import Settings
from app.db import get_database
from app.main import app

client = TestClient(app)

BAD_DIFF = """diff --git a/app/demo.py b/app/demo.py
--- a/app/demo.py
+++ b/app/demo.py
@@ -1,1 +1,3 @@
 import os
+API_TOKEN = "ghp_demoTokenValue1234567890"
+os.system(f"curl {API_TOKEN}")
"""

#: Every route that must be guarded once API_AUTH_ENABLED is on.
GUARDED: tuple[tuple[str, str, str], ...] = (
    ("GET", "/reviews", "reviewer"),
    ("GET", "/reviews/1", "reviewer"),
    ("GET", "/stats", "reviewer"),
    ("POST", "/users", "admin"),
    ("GET", "/users", "admin"),
    ("PATCH", "/users/1", "admin"),
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DB_SEED_ADMIN_KEY", raising=False)
    monkeypatch.delenv("API_AUTH_ENABLED", raising=False)


@pytest.fixture()
def auth_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the history at a temporary file and switch authentication on."""
    path = tmp_path / "auth.db"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    monkeypatch.setenv("API_AUTH_ENABLED", "1")
    return path


@pytest.fixture()
def auth_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the history at a temporary file and leave authentication off."""
    path = tmp_path / "open.db"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    monkeypatch.setenv("API_AUTH_ENABLED", "0")
    return path


def _call(method: str, url: str, key: str | None = None, **kwargs: object):
    headers = {"X-API-Key": key} if key is not None else {}
    return client.request(method, url, headers=headers, **kwargs)  # type: ignore[arg-type]


def _boom(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("disk on fire")


# --------------------------------------------------------------------------- #
# The flag and the context
# --------------------------------------------------------------------------- #


def test_auth_enabled_follows_the_opt_in_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    assert auth_enabled() is False  # off by default: the demo needs no configuration
    monkeypatch.setenv("API_AUTH_ENABLED", "1")
    assert auth_enabled() is True
    monkeypatch.setenv("API_AUTH_ENABLED", "0")
    assert auth_enabled(Settings()) is False


def test_user_context_is_frozen_and_require_validates_the_level() -> None:
    context = UserContext(1, "priya", "reviewer", True, True, False)
    with pytest.raises(Exception):  # FrozenInstanceError
        context.role = "admin"  # type: ignore[misc]
    assert context.can_admin is False
    assert ANONYMOUS.user_id == 0 and ANONYMOUS.can_admin is False
    for level in ("viewer", "reviewer", "poster", "admin", "ADMIN"):
        assert callable(require(level))
    with pytest.raises(ValueError):
        require("superuser")


# --------------------------------------------------------------------------- #
# Guarding the management endpoints
# --------------------------------------------------------------------------- #


def test_guarded_endpoints_need_a_key_only_when_auth_is_on(
    auth_off: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same six routes: open while the flag is off, 401 with no key once it is on."""
    bodies = {"/users": {"username": "u", "email": "u@x", "role": "viewer", "api_key": "12345678"}}
    for method, url, _level in GUARDED:
        opened = _call(method, url, json=bodies.get(url))
        assert opened.status_code != 401, f"{method} {url} was guarded while auth was off"

    monkeypatch.setenv("API_AUTH_ENABLED", "1")
    for method, url, _level in GUARDED:
        guarded = _call(method, url, json=bodies.get(url))
        assert guarded.status_code == 401, f"{method} {url} was not guarded"
        assert "X-API-Key" in guarded.json()["detail"]


def test_a_bad_key_is_401_and_a_weak_role_is_403(auth_on: Path) -> None:
    database = get_database()
    database.create_user("priya", "priya@example.org", "viewer", "viewer-key-123")
    database.create_user("ravi", "ravi@example.org", "reviewer", "reviewer-key-123")
    database.create_user("asha", "asha@example.org", "admin", "admin-key-123")

    assert _call("GET", "/reviews", key="not-a-key").status_code == 401
    assert _call("GET", "/reviews", key="").status_code == 401

    # A viewer may not review, and only an admin may touch /users.
    assert _call("GET", "/reviews", key="viewer-key-123").status_code == 403
    assert _call("GET", "/users", key="viewer-key-123").status_code == 403
    assert _call("GET", "/users", key="reviewer-key-123").status_code == 403

    # The right role gets through.
    assert _call("GET", "/reviews", key="reviewer-key-123").status_code == 200
    assert _call("GET", "/stats", key="reviewer-key-123").status_code == 200
    assert _call("GET", "/users", key="admin-key-123").status_code == 200


def test_the_review_surfaces_stay_open_even_when_auth_is_on(auth_on: Path) -> None:
    """The flag protects the history and the user table, not the product itself."""
    assert client.post("/review", json={"diff": BAD_DIFF}).status_code == 200
    assert client.get("/test-review").status_code == 200
    assert client.get("/health").status_code == 200


def test_users_lifecycle_from_the_seed_admin(
    auth_on: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The documented bootstrap: DB_SEED_ADMIN_KEY, then POST /users for everyone else."""
    monkeypatch.setenv("DB_SEED_ADMIN_KEY", "seed-admin-key-123")
    get_database()  # seeds the admin on first use

    created = _call(
        "POST",
        "/users",
        key="seed-admin-key-123",
        json={"username": "priya", "email": "priya@example.org", "role": "reviewer", "api_key": "priya-key-123"},
    )
    assert created.status_code == 201
    body = created.json()
    assert (body["username"], body["role"], body["is_active"]) == ("priya", "reviewer", True)
    assert "priya-key-123" not in created.text  # the key is never echoed back

    listed = _call("GET", "/users", key="seed-admin-key-123").json()
    assert [user["username"] for user in listed] == ["admin", "priya"]
    assert all("api_key_hash" not in user for user in listed)

    duplicate = _call(
        "POST",
        "/users",
        key="seed-admin-key-123",
        json={"username": "priya", "email": "other@example.org", "role": "viewer", "api_key": "another-key-123"},
    )
    assert duplicate.status_code == 409

    # The new key works, then stops working the moment the admin deactivates it.
    assert _call("GET", "/stats", key="priya-key-123").status_code == 200
    patched = _call(
        "PATCH", f"/users/{body['id']}", key="seed-admin-key-123", json={"is_active": False}
    )
    assert patched.status_code == 200
    assert patched.json() == {"user_id": body["id"], "is_active": False}
    assert _call("GET", "/stats", key="priya-key-123").status_code == 401


def test_patch_rejects_a_missing_user_and_a_bad_body(auth_on: Path) -> None:
    database = get_database()
    database.create_user("asha", "asha@example.org", "admin", "admin-key-123")
    assert _call("PATCH", "/users/9999", key="admin-key-123", json={"is_active": False}).status_code == 404
    assert _call("PATCH", "/users/1", key="admin-key-123", json={"active": False}).status_code == 422
    assert _call("PATCH", "/users/1", key="admin-key-123", json={"is_active": "no"}).status_code == 422


# --------------------------------------------------------------------------- #
# Persistence through the API
# --------------------------------------------------------------------------- #


def test_a_review_is_stored_and_readable(auth_off: Path) -> None:
    posted = client.post("/review", json={"diff": BAD_DIFF})
    assert posted.status_code == 200

    listed = client.get("/reviews").json()
    assert len(listed) == 1
    stored = listed[0]
    assert stored["target"] == "<request body>"
    assert stored["verdict"] == "block"
    assert stored["mode"] == "mock"
    assert stored["findings_count"] >= 1

    detail = client.get(f"/reviews/{stored['id']}").json()
    assert detail["id"] == stored["id"]
    assert detail["findings"][0]["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    assert detail["findings"][0]["file"]

    stats = client.get("/stats").json()
    assert stats["reviews"] == 1
    assert stats["findings"] == stored["findings_count"]
    assert set(stats["findings_by_severity"]) == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert stats["latest_review_at"] == stored["created_at"]

    assert client.get("/reviews/9999").status_code == 404
    assert client.get("/reviews?limit=1").json()[0]["id"] == stored["id"]


def test_webhook_and_test_review_are_stored_too(auth_off: Path) -> None:
    """Every review surface funnels through one persistence call, so all of them count."""
    assert client.post("/test-review", json={"diff": BAD_DIFF}).status_code == 200
    assert client.post("/webhook", json={"action": "opened", "number": 1, "diff": BAD_DIFF}).status_code == 200
    targets = [row["target"] for row in client.get("/reviews").json()]
    assert len(targets) == 2
    assert any(target.startswith("unknown/repo") for target in targets)


# --------------------------------------------------------------------------- #
# A broken database changes nothing the caller can see
# --------------------------------------------------------------------------- #


def test_a_database_failure_does_not_break_a_review(
    auth_off: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(main, "get_database", _boom)
    with caplog.at_level(logging.WARNING, logger="reviewer.db"):
        response = client.post("/review", json={"diff": BAD_DIFF})
    assert response.status_code == 200  # the review still answers
    assert response.json()["review"]["findings"]
    warnings = [r for r in caplog.records if r.name == "reviewer.db" and r.levelno == logging.WARNING]
    assert len(warnings) == 1  # exactly one WARNING for one failed write
    assert "could not store the review" in warnings[0].getMessage()


def test_health_reports_the_database_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "health.db"))
    assert client.get("/health").json()["database"] == "ok"

    monkeypatch.setenv("DATABASE_PATH", "  ")  # a blank path switches history off
    assert client.get("/health").json()["database"] == "disabled"

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "broken.db"))
    monkeypatch.setattr(main, "get_database", _boom)
    assert client.get("/health").json()["database"] == "error"
    # A read endpoint cannot invent rows, so it reports the outage honestly.
    assert client.get("/reviews").status_code == 503
    assert client.get("/stats").status_code == 503


def test_persistence_off_still_reviews(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_PATH", "")
    assert client.post("/review", json={"diff": BAD_DIFF}).status_code == 200
    assert client.get("/reviews").status_code == 503


def test_a_posting_attempt_is_recorded_in_pr_posts(
    auth_off: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One ``pr_posts`` row per attempt, linked to the review that was posted."""
    from sqlalchemy import text

    from app.github_client import PostResult

    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake_token_for_the_test")
    monkeypatch.setenv("WEBHOOK_ALLOW_UNSIGNED", "1")
    monkeypatch.setattr(main, "github_available", lambda: True)
    monkeypatch.setattr(
        main,
        "post_review",
        lambda *args, **kwargs: PostResult(
            ok=True,
            inline_posted=2,
            inline_demoted=0,
            summary_posted=True,
            skipped_dup=False,
            error="",
        ),
    )
    payload = {
        "action": "opened",
        "number": 7,
        "repository": {"full_name": "shreyash/demo"},
        "diff": BAD_DIFF,
    }
    assert client.post("/webhook", json=payload).status_code == 200

    database = get_database()
    review_id = database.list_reviews()[0]["id"]
    with database._engine.connect() as connection:  # noqa: SLF001 - read the row straight
        rows = connection.execute(
            text("SELECT * FROM pr_posts")
        ).mappings().all()
    assert len(rows) == 1
    row = rows[0]
    assert (row["owner"], row["repo"], row["pr_number"]) == ("shreyash", "demo", 7)
    assert row["review_id"] == review_id
    assert row["ok"] == 1
    assert row["inline_posted"] == 2
    assert row["summary_posted"] == 1
