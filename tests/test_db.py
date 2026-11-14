"""Tests for the SQLite persistence layer.

Everything here runs against a temporary file — no network, no shared state, no
credentials. The interesting cases are the ones a demo would never hit and a
reviewer would: a constraint that must reject bad data, a cascade that must
actually delete, a key that must never be recoverable, and a database that is
allowed to fail without taking a request down with it.

The tests read the schema with plain SQL rather than through the module's own
helpers wherever they can: a test that checks a CHECK constraint using the same
code path that wrote the row proves very little.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import (
    DEFAULT_DB_PATH,
    ROLE_PERMISSIONS,
    SCHEMA_SQL,
    Database,
    get_database,
    hash_api_key,
)
from app.models import Finding
from app.parser import DiffReviewResult


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the seed key out of these tests unless one sets it deliberately."""
    monkeypatch.delenv("DB_SEED_ADMIN_KEY", raising=False)
    monkeypatch.delenv("API_AUTH_ENABLED", raising=False)


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    """A migrated, seeded database in a temporary file."""
    database = Database(tmp_path / "test.db")
    database.init_schema()
    database.seed_defaults()
    yield database
    database.close()


def _review(*findings: Finding, target: str = "app/users.py") -> DiffReviewResult:
    """A diff review carrying the given findings."""
    return DiffReviewResult(mode="mock", target=target, findings=list(findings))


def _finding(severity: str = "HIGH", line: str = "12") -> Finding:
    return Finding(
        file="app/users.py",
        line=line,
        severity=severity,  # type: ignore[arg-type]
        issue="SQL injection via string formatting",
        suggested_fix="db.execute(query, (uid,))",
    )


def _raw(database: Database, sql: str, params: dict[str, object] | None = None) -> None:
    """Run one statement straight through the engine, bypassing the module's API.

    Used to prove the *schema* rejects bad data — not just that the Python
    methods happen to be careful.
    """
    with database._engine.begin() as connection:  # noqa: SLF001 - deliberate, see docstring
        connection.execute(text(sql), params or {})


def _tables(database: Database) -> set[str]:
    with database._engine.connect() as connection:  # noqa: SLF001
        rows = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type = 'table'")
        ).all()
    return {row[0] for row in rows}


def _indexes(database: Database) -> set[str]:
    with database._engine.connect() as connection:  # noqa: SLF001
        rows = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type = 'index'")
        ).all()
    return {row[0] for row in rows}


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #


def test_init_schema_creates_every_table_and_index(db: Database) -> None:
    """The DDL string names every table and index, and init_schema() applied it."""
    for table in ("roles", "users", "reviews", "findings", "pr_posts", "benchmark_runs"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in SCHEMA_SQL
    for index in ("idx_findings_review_id", "idx_pr_posts_pr_number", "idx_reviews_created_at"):
        assert index in SCHEMA_SQL
    assert DEFAULT_DB_PATH == "data/reviewer.db"
    assert _tables(db) >= {
        "roles",
        "users",
        "reviews",
        "findings",
        "pr_posts",
        "benchmark_runs",
    }
    assert _indexes(db) >= {
        "idx_findings_review_id",
        "idx_pr_posts_pr_number",
        "idx_reviews_created_at",
    }
    # Idempotent: a second and third init neither raise nor drop what is stored.
    db.create_user("keeper", "keeper@example.org", "viewer", "keeper-key-123")
    db.init_schema()
    db.init_schema()
    assert [user["username"] for user in db.list_users()] == ["keeper"]


def test_foreign_keys_are_enforced_on_every_connection(db: Database) -> None:
    """SQLite ignores REFERENCES unless the pragma is on; this proves it is."""
    with pytest.raises(IntegrityError):
        _raw(
            db,
            "INSERT INTO users (username, email, api_key_hash, role_id, created_at) "
            "VALUES ('ghost', 'ghost@example.org', :h, 999, '2026-01-01T00:00:00Z')",
            {"h": "a" * 64},
        )


# --------------------------------------------------------------------------- #
# Constraints
# --------------------------------------------------------------------------- #


def test_roles_check_constraint_rejects_an_unknown_role(db: Database) -> None:
    with pytest.raises(IntegrityError):
        _raw(db, "INSERT INTO roles (name) VALUES ('superuser')")


def test_roles_name_is_unique(db: Database) -> None:
    with pytest.raises(IntegrityError):
        _raw(db, "INSERT INTO roles (name) VALUES ('admin')")


def test_users_username_and_email_are_unique(db: Database) -> None:
    db.create_user("priya", "priya@example.org", "viewer", "priya-key-123")
    with pytest.raises(IntegrityError):
        db.create_user("priya", "other@example.org", "viewer", "other-key-123")
    with pytest.raises(IntegrityError):
        db.create_user("other", "priya@example.org", "viewer", "third-key-123")
    # Two accounts may not share a key either: the hash column is UNIQUE and exact.
    db.create_user("ravi", "ravi@example.org", "viewer", "shared-key-123")
    with pytest.raises(IntegrityError):
        db.create_user("asha", "asha@example.org", "viewer", "shared-key-123")


def test_reviews_check_constraint_rejects_a_bad_mode(db: Database) -> None:
    with pytest.raises(IntegrityError):
        _raw(
            db,
            "INSERT INTO reviews (created_at, mode, provider, model, target, verdict) "
            "VALUES ('2026-01-01T00:00:00Z', 'maybe', 'mock', 'local-rules', 'x', 'approve')",
        )
    with pytest.raises(IntegrityError):
        _raw(
            db,
            "INSERT INTO reviews (created_at, mode, provider, model, target, verdict) "
            "VALUES ('2026-01-01T00:00:00Z', 'mock', 'mock', 'local-rules', 'x', 'reject')",
        )


def test_findings_check_constraint_rejects_a_bad_severity(db: Database) -> None:
    review_id = db.store_review(_review(), mode="mock", provider="mock", model="local-rules", target="x")
    with pytest.raises(IntegrityError):
        _raw(
            db,
            "INSERT INTO findings (review_id, file, line, severity, issue, suggested_fix) "
            "VALUES (:rid, 'a.py', '1', 'SEVERE', 'bad', 'fix')",
            {"rid": review_id},
        )
    with pytest.raises(IntegrityError):
        _raw(
            db,
            "INSERT INTO findings (review_id, file, line, severity, issue, suggested_fix) "
            "VALUES (424242, 'a.py', '1', 'LOW', 'x', 'y')",
        )


def test_deleting_a_review_cascades_to_its_findings(db: Database) -> None:
    review_id = db.store_review(
        _review(_finding("CRITICAL"), _finding("LOW")),
        mode="mock",
        provider="mock",
        model="local-rules",
        target="x",
    )
    db.store_pr_post(review_id, owner="o", repo="r", pr_number=7, ok=True)
    _raw(db, "DELETE FROM reviews WHERE id = :rid", {"rid": review_id})
    assert db.get_review(review_id) is None
    with db._engine.connect() as connection:  # noqa: SLF001
        left = connection.execute(text("SELECT COUNT(*) FROM findings")).scalar_one()
        post = connection.execute(text("SELECT review_id, pr_number FROM pr_posts")).one()
    assert left == 0
    # Posting history outlives the review it referenced: the FK is SET NULL.
    assert post[0] is None
    assert post[1] == 7


# --------------------------------------------------------------------------- #
# Reviews and findings
# --------------------------------------------------------------------------- #


def test_store_review_round_trip(db: Database) -> None:
    review_id = db.store_review(
        _review(_finding("CRITICAL"), _finding("LOW", line="40")),
        mode="mock",
        provider="mock",
        model="local-rules",
        target="app/users.py",
    )
    record = db.get_review(review_id)
    assert record is not None
    assert record["mode"] == "mock"
    assert record["provider"] == "mock"
    assert record["model"] == "local-rules"
    assert record["target"] == "app/users.py"
    assert record["findings_count"] == 2
    assert record["verdict"] == "block"  # a CRITICAL finding blocks
    assert [finding["severity"] for finding in record["findings"]] == ["CRITICAL", "LOW"]
    assert record["findings"][0]["suggested_fix"] == "db.execute(query, (uid,))"
    assert db.get_review(9999) is None


def test_store_review_with_no_findings_approves(db: Database) -> None:
    review_id = db.store_review(_review(), mode="live", provider="sarvam", model="sarvam-m", target="clean.py")
    record = db.get_review(review_id)
    assert record is not None
    assert record["findings"] == []
    assert record["findings_count"] == 0
    assert record["verdict"] == "approve"


def test_store_review_rejects_an_unknown_mode(db: Database) -> None:
    with pytest.raises(ValueError):
        db.store_review(_review(), mode="offline", provider="mock", model="local-rules", target="x")


def test_list_reviews_is_newest_first_and_honours_the_limit(db: Database) -> None:
    for target in ("first", "second", "third"):
        db.store_review(_review(), mode="mock", provider="mock", model="local-rules", target=target)
    listed = db.list_reviews(limit=2)
    assert len(listed) == 2
    assert [row["target"] for row in listed] == ["third", "second"]
    assert db.list_reviews(limit=0)[0]["target"] == "third"  # limit is clamped to 1


# --------------------------------------------------------------------------- #
# Postings and benchmarks
# --------------------------------------------------------------------------- #


def test_store_pr_post_persists_every_flag(db: Database) -> None:
    review_id = db.store_review(_review(), mode="mock", provider="mock", model="local-rules", target="x")
    post_id = db.store_pr_post(
        review_id,
        owner="shreyash",
        repo="demo",
        pr_number=7,
        ok=False,
        inline_posted=3,
        inline_demoted=1,
        summary_posted=True,
        skipped_dup=False,
        error="403 from GitHub",
    )
    with db._engine.connect() as connection:  # noqa: SLF001
        row = connection.execute(
            text("SELECT * FROM pr_posts WHERE id = :pid"), {"pid": post_id}
        ).mappings().one()
    assert (row["owner"], row["repo"], row["pr_number"]) == ("shreyash", "demo", 7)
    assert row["ok"] == 0
    assert row["inline_posted"] == 3
    assert row["inline_demoted"] == 1
    assert row["summary_posted"] == 1
    assert row["skipped_dup"] == 0
    assert row["error"] == "403 from GitHub"
    assert row["created_at"]
    # A posting attempt whose review could not be stored is still worth recording.
    orphan_id = db.store_pr_post(None, owner="o", repo="r", pr_number=1, ok=True)
    with db._engine.connect() as connection:  # noqa: SLF001
        orphan = connection.execute(
            text("SELECT review_id, error FROM pr_posts WHERE id = :pid"), {"pid": orphan_id}
        ).one()
    assert orphan[0] is None and orphan[1] is None


def test_store_benchmark_run_persists_its_metrics(db: Database) -> None:
    run_id = db.store_benchmark_run(
        mode="mock",
        dataset="samples/sample.diff",
        precision=0.8,
        recall=0.6,
        f1=0.6857,
        fpr=0.1,
        tp=6,
        fp=1,
        fn=4,
        tn=9,
        latency_p50=1.5,
        latency_p95=4.25,
    )
    with db._engine.connect() as connection:  # noqa: SLF001
        row = connection.execute(
            text("SELECT * FROM benchmark_runs WHERE id = :rid"), {"rid": run_id}
        ).mappings().one()
    assert row["dataset"] == "samples/sample.diff"
    assert row["precision"] == pytest.approx(0.8)
    assert (row["tp"], row["fp"], row["fn"], row["tn"]) == (6, 1, 4, 9)
    assert row["latency_p95"] == pytest.approx(4.25)
    # Every metric is nullable, so a run that only timed itself can still be stored.
    partial_id = db.store_benchmark_run(mode="mock", dataset="d", latency_p50=2.0)
    with db._engine.connect() as connection:  # noqa: SLF001
        partial = connection.execute(
            text("SELECT precision, tp FROM benchmark_runs WHERE id = :rid"), {"rid": partial_id}
        ).one()
    assert partial[0] is None and partial[1] is None


# --------------------------------------------------------------------------- #
# Users, keys and roles
# --------------------------------------------------------------------------- #


def test_api_key_is_stored_only_as_a_sha256_hash(db: Database) -> None:
    """The plaintext key must not survive anywhere in the row — or in the return value."""
    key = "super-secret-key-abcdef"
    created = db.create_user("priya", "priya@example.org", "reviewer", key)
    with db._engine.connect() as connection:  # noqa: SLF001
        row = connection.execute(
            text("SELECT * FROM users WHERE username = 'priya'")
        ).mappings().one()
    stored = dict(row)
    assert stored["api_key_hash"] == hashlib.sha256(key.encode()).hexdigest()
    assert len(stored["api_key_hash"]) == 64
    assert key not in str(stored)
    assert "api_key_hash" not in created  # never returned to a caller
    assert key not in repr(created)
    # The hash itself is deterministic, whitespace-tolerant and 64 characters wide.
    assert hash_api_key("abc") == hash_api_key("  abc\n")
    assert hash_api_key("abc") != hash_api_key("abd")
    assert len(hash_api_key("abc")) == 64


def test_create_user_rejects_an_unknown_role(db: Database) -> None:
    with pytest.raises(ValueError):
        db.create_user("x", "x@example.org", "superuser", "some-key-1234")
    with pytest.raises(ValueError):
        db.create_user("y", "y@example.org", "viewer", "   ")


def test_list_users_hides_the_hash_and_names_the_role(db: Database) -> None:
    db.create_user("priya", "priya@example.org", "admin", "priya-key-123")
    db.create_user("ravi", "ravi@example.org", "viewer", "ravi-key-123")
    users = db.list_users()
    assert [user["username"] for user in users] == ["priya", "ravi"]
    assert [user["role"] for user in users] == ["admin", "viewer"]
    assert all(user["is_active"] is True for user in users)
    assert all("api_key_hash" not in user for user in users)
    assert "priya-key-123" not in repr(users)


def test_set_user_active_toggles_and_reports_a_missing_user(db: Database) -> None:
    created = db.create_user("priya", "priya@example.org", "reviewer", "priya-key-123")
    assert db.set_user_active(created["id"], False) is True
    assert db.list_users()[0]["is_active"] is False
    assert db.set_user_active(created["id"], True) is True
    assert db.list_users()[0]["is_active"] is True
    assert db.set_user_active(9999, False) is False


def test_authenticate_resolves_a_good_key_to_its_permissions(db: Database) -> None:
    db.create_user("priya", "priya@example.org", "reviewer", "priya-key-123")
    context = db.authenticate("priya-key-123")
    assert context is not None
    assert (context.username, context.role) == ("priya", "reviewer")
    assert context.can_review is True
    assert context.can_post is True
    assert context.can_admin is False


def test_authenticate_rejects_a_bad_key(db: Database) -> None:
    db.create_user("priya", "priya@example.org", "reviewer", "priya-key-123")
    for key in (None, "", "   ", "not-a-real-key"):
        assert db.authenticate(key) is None


def test_authenticate_rejects_a_deactivated_user(db: Database) -> None:
    created = db.create_user("priya", "priya@example.org", "admin", "priya-key-123")
    assert db.authenticate("priya-key-123") is not None
    db.set_user_active(created["id"], False)
    assert db.authenticate("priya-key-123") is None


def test_seed_defaults_creates_three_roles_with_the_documented_permissions(db: Database) -> None:
    with db._engine.connect() as connection:  # noqa: SLF001
        rows = connection.execute(
            text("SELECT name, can_review, can_post, can_admin FROM roles ORDER BY name")
        ).all()
    assert [(row[0], row[1], row[2], row[3]) for row in rows] == [
        ("admin", 1, 1, 1),
        ("reviewer", 1, 1, 0),
        ("viewer", 0, 0, 0),
    ]
    assert ROLE_PERMISSIONS["admin"] == (1, 1, 1)


def test_seed_defaults_creates_no_admin_without_a_seed_key(db: Database) -> None:
    """No default credential: an unattended start must not grow an admin account."""
    assert db.list_users() == []
    assert db.seed_defaults() == {"roles_created": 0, "admin_created": False}


def test_seed_defaults_creates_one_admin_when_the_key_is_set(
    db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DB_SEED_ADMIN_KEY", "seed-admin-key-123")
    assert db.seed_defaults()["admin_created"] is True
    users = db.list_users()
    assert [(user["username"], user["role"]) for user in users] == [("admin", "admin")]
    context = db.authenticate("seed-admin-key-123")
    assert context is not None and context.can_admin is True
    # Idempotent: a second seed neither duplicates the roles nor the admin.
    assert db.seed_defaults() == {"roles_created": 0, "admin_created": False}
    assert len(db.list_users()) == 1


# --------------------------------------------------------------------------- #
# Singleton and reporting
# --------------------------------------------------------------------------- #


def test_get_database_is_a_singleton_per_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first_path = tmp_path / "one.db"
    monkeypatch.setenv("DATABASE_PATH", str(first_path))
    first = get_database()
    assert get_database() is first  # same path, same instance
    first.close()

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "two.db"))
    second = get_database()
    assert second is not first
    assert second.path != first.path
    second.close()

    # A blank path is how persistence is switched off; it must not invent a default.
    monkeypatch.setenv("DATABASE_PATH", "  ")
    with pytest.raises(RuntimeError):
        get_database()


def test_stats_aggregates_the_history(db: Database) -> None:
    db.store_review(_review(_finding("CRITICAL")), mode="mock", provider="mock", model="local-rules", target="a")
    db.store_review(_review(), mode="live", provider="sarvam", model="sarvam-m", target="b")
    db.store_pr_post(None, owner="o", repo="r", pr_number=1, ok=True)
    db.store_pr_post(None, owner="o", repo="r", pr_number=2, ok=False, error="boom")
    db.store_benchmark_run(mode="mock", dataset="d")
    stats = db.stats()
    assert stats["reviews"] == 2
    assert stats["findings"] == 1
    assert stats["reviews_by_mode"] == {"mock": 1, "live": 1}
    assert stats["reviews_by_verdict"] == {"block": 1, "approve": 1}
    assert stats["findings_by_severity"] == {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 1}
    assert (stats["pr_posts"], stats["pr_posts_ok"]) == (2, 1)
    assert stats["benchmark_runs"] == 1
    assert stats["latest_review_at"]


def test_the_database_is_a_real_sqlite_file(tmp_path: Path) -> None:
    """Proof the store is on disk and readable by ``sqlite3`` itself, not a pickle."""
    path = tmp_path / "on_disk.db"
    database = Database(path)
    database.init_schema()
    database.close()
    connection = sqlite3.connect(path)
    try:
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    finally:
        connection.close()
    assert {"reviews", "findings", "users", "roles"} <= names
