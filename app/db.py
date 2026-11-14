"""SQLite persistence for reviews, findings, postings, benchmarks and users.

Why this module exists
----------------------
Every other layer in this project is stateless: a diff goes in, a review comes
out, and nothing remembers that it happened. That is fine for a demo and useless
for a report — "how many reviews did the system run, how many were blocked, what
did posting do?" cannot be answered from a process that forgets. This module is
that memory, and it is also where the access-control facts live (who may review,
who may post, who may administer).

Design decisions, stated so they can be argued with
---------------------------------------------------
* **SQLAlchemy Core, not the ORM.** The queries are short and explicit, the
  schema is frozen by the project brief, and an ORM's identity map and lazy
  loading buy nothing here. ``text()`` with bound parameters is used throughout —
  no string interpolation ever reaches the driver.
* **The DDL lives in :data:`SCHEMA_SQL`, a single auditable string.** An examiner
  can print it, diff it against the brief, and run it by hand in ``sqlite3``.
  ``init_schema`` executes exactly that string, so the schema cannot drift from
  the documented one.
* **API keys are never stored, only their SHA-256.** :func:`hash_api_key` is the
  only place a key is converted, and no public method returns the hash, so a
  leaked ``list_users()`` response is not a leaked credential.
* **A database problem must never change an HTTP response.** Nothing here is
  allowed to be clever about that: every caller wraps these calls in
  ``try/except`` and logs one WARNING on ``reviewer.db``. This module raises the
  normal SQLAlchemy exceptions (``IntegrityError`` for a duplicate, ``ValueError``
  for a caller mistake) and lets the caller decide.
* **Timestamps are ISO-8601 UTC strings**, matching the ``TEXT`` columns the
  frozen schema specifies, and they sort lexicographically — which is what
  ``ORDER BY created_at DESC`` relies on.

Threading: the engine is created with ``check_same_thread=False`` and every write
happens inside a single ``engine.begin()`` transaction, so FastAPI's threadpool
and the CLI can share one process-wide instance. SQLite serialises the writes
itself.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.models import verdict_for

__all__ = [
    "DEFAULT_DB_PATH",
    "SCHEMA_SQL",
    "ROLE_NAMES",
    "ROLE_PERMISSIONS",
    "SEED_ADMIN_USERNAME",
    "SEED_ADMIN_EMAIL",
    "Database",
    "get_database",
    "hash_api_key",
]

logger = logging.getLogger("reviewer.db")

#: Where the database lives when ``DATABASE_PATH`` says nothing. Relative to the
#: process working directory, which is the project root under ``uvicorn``/pytest.
DEFAULT_DB_PATH = "data/reviewer.db"

#: The three roles the frozen schema allows, in ascending order of power.
ROLE_NAMES: tuple[str, ...] = ("viewer", "reviewer", "admin")

#: Role name -> ``(can_review, can_post, can_admin)``. The single source of truth
#: for what each role may do; :meth:`Database.seed_defaults` writes these rows and
#: ``tests/test_db.py`` asserts them.
ROLE_PERMISSIONS: dict[str, tuple[int, int, int]] = {
    "viewer": (0, 0, 0),
    "reviewer": (1, 1, 0),
    "admin": (1, 1, 1),
}

#: Identity created by :meth:`Database.seed_defaults` when ``DB_SEED_ADMIN_KEY`` is set.
SEED_ADMIN_USERNAME = "admin"
SEED_ADMIN_EMAIL = "admin@localhost"


# --------------------------------------------------------------------------- #
# The frozen schema, as one auditable string
# --------------------------------------------------------------------------- #

#: The complete DDL. ``init_schema()`` executes this string and nothing else, so
#: what is printed here is exactly what a database gets. Every statement is
#: ``IF NOT EXISTS`` so a second call is a no-op rather than an error.
SCHEMA_SQL = """\
-- roles: the three permission bundles the system recognises.
CREATE TABLE IF NOT EXISTS roles (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE CHECK (name IN ('admin', 'reviewer', 'viewer')),
    can_review  INTEGER NOT NULL DEFAULT 0,
    can_post    INTEGER NOT NULL DEFAULT 0,
    can_admin   INTEGER NOT NULL DEFAULT 0
);

-- users: one row per API key holder. Only the SHA-256 of the key is stored.
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT    NOT NULL UNIQUE,
    email         TEXT    NOT NULL UNIQUE,
    api_key_hash  CHAR(64) NOT NULL UNIQUE,
    role_id       INTEGER NOT NULL REFERENCES roles(id),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL
);

-- reviews: one row per completed review, whatever surface produced it.
CREATE TABLE IF NOT EXISTS reviews (
    id              INTEGER PRIMARY KEY,
    created_at      TEXT    NOT NULL,
    mode            TEXT    NOT NULL CHECK (mode IN ('live', 'mock')),
    provider        TEXT    NOT NULL,
    model           TEXT    NOT NULL,
    target          TEXT    NOT NULL,
    findings_count  INTEGER NOT NULL DEFAULT 0,
    verdict         TEXT    NOT NULL CHECK (verdict IN ('block', 'approve with comments', 'approve'))
);

-- findings: the five contract fields, attached to their review.
CREATE TABLE IF NOT EXISTS findings (
    id             INTEGER PRIMARY KEY,
    review_id      INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    file           TEXT    NOT NULL,
    line           TEXT    NOT NULL,
    severity       TEXT    NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    issue          TEXT    NOT NULL,
    suggested_fix  TEXT    NOT NULL
);

-- pr_posts: one row per attempt to publish a review to a pull request.
CREATE TABLE IF NOT EXISTS pr_posts (
    id               INTEGER PRIMARY KEY,
    review_id        INTEGER REFERENCES reviews(id) ON DELETE SET NULL,
    owner            TEXT    NOT NULL,
    repo             TEXT    NOT NULL,
    pr_number        INTEGER NOT NULL,
    ok               INTEGER NOT NULL,
    inline_posted    INTEGER NOT NULL DEFAULT 0,
    inline_demoted   INTEGER NOT NULL DEFAULT 0,
    summary_posted   INTEGER NOT NULL DEFAULT 0,
    skipped_dup      INTEGER NOT NULL DEFAULT 0,
    error            TEXT,
    created_at       TEXT    NOT NULL
);

-- benchmark_runs: one row per benchmark run, with its metrics.
CREATE TABLE IF NOT EXISTS benchmark_runs (
    id            INTEGER PRIMARY KEY,
    created_at    TEXT NOT NULL,
    mode          TEXT NOT NULL,
    dataset       TEXT NOT NULL,
    precision     REAL,
    recall        REAL,
    f1            REAL,
    fpr           REAL,
    tp            INTEGER,
    fp            INTEGER,
    fn            INTEGER,
    tn            INTEGER,
    latency_p50   REAL,
    latency_p95   REAL
);

CREATE INDEX IF NOT EXISTS idx_findings_review_id ON findings (review_id);
CREATE INDEX IF NOT EXISTS idx_pr_posts_pr_number ON pr_posts (pr_number);
CREATE INDEX IF NOT EXISTS idx_reviews_created_at ON reviews (created_at);
"""


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def hash_api_key(api_key: str) -> str:
    """Return the SHA-256 hex digest of an API key — the only form ever stored.

    Args:
        api_key: The caller's plaintext key. Surrounding whitespace is ignored so a
            key pasted with a trailing newline still authenticates.

    Returns:
        64 lowercase hex characters, exactly the width of the ``CHAR(64)`` column.

    Raises:
        ValueError: When the key is empty or whitespace only.
    """
    cleaned = (api_key or "").strip()
    if not cleaned:
        raise ValueError("api_key must not be blank")
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    """Current UTC time as an ISO-8601 string that sorts lexicographically."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _statements(schema: str) -> list[str]:
    """Split a DDL script into single statements.

    ``sqlite3`` executes one statement per ``execute()``; the script is split on
    ``;`` here so :data:`SCHEMA_SQL` can stay one readable string. Comment-only
    fragments are dropped, and SQLite accepts a leading ``--`` comment on a
    statement, so nothing is lost.
    """
    chunks: list[str] = []
    for raw in schema.split(";"):
        body = "\n".join(
            line for line in raw.splitlines() if not line.strip().startswith("--")
        ).strip()
        if body:
            chunks.append(body)
    return chunks


def _severity(value: Any) -> str:
    """Normalise a ``Severity`` enum (or plain string) to its stored text."""
    return getattr(value, "value", str(value))


def _flag(value: Any) -> int:
    """Normalise a truthy value to SQLite's 0/1."""
    return 1 if value else 0


def _row_to_user(row: dict[str, Any]) -> dict[str, Any]:
    """Shape a joined ``users``+``roles`` row for the API — the hash is dropped."""
    return {
        "id": int(row["id"]),
        "username": str(row["username"]),
        "email": str(row["email"]),
        "role": str(row["role"]),
        "is_active": bool(row["is_active"]),
        "created_at": str(row["created_at"]),
    }


# --------------------------------------------------------------------------- #
# SQL used by the methods below (bound parameters only)
# --------------------------------------------------------------------------- #

_INSERT_REVIEW = text(
    """
    INSERT INTO reviews (created_at, mode, provider, model, target, findings_count, verdict)
    VALUES (:created_at, :mode, :provider, :model, :target, :findings_count, :verdict)
    """
)
_INSERT_FINDING = text(
    """
    INSERT INTO findings (review_id, file, line, severity, issue, suggested_fix)
    VALUES (:review_id, :file, :line, :severity, :issue, :suggested_fix)
    """
)
_SELECT_REVIEW = text("SELECT * FROM reviews WHERE id = :review_id")
_SELECT_FINDINGS = text(
    "SELECT id, file, line, severity, issue, suggested_fix FROM findings "
    "WHERE review_id = :review_id ORDER BY id"
)
_SELECT_REVIEWS = text(
    """
    SELECT id, created_at, mode, provider, model, target, findings_count, verdict
    FROM reviews ORDER BY created_at DESC, id DESC LIMIT :limit
    """
)
_INSERT_PR_POST = text(
    """
    INSERT INTO pr_posts (review_id, owner, repo, pr_number, ok, inline_posted,
                          inline_demoted, summary_posted, skipped_dup, error, created_at)
    VALUES (:review_id, :owner, :repo, :pr_number, :ok, :inline_posted,
            :inline_demoted, :summary_posted, :skipped_dup, :error, :created_at)
    """
)
_INSERT_BENCHMARK = text(
    """
    INSERT INTO benchmark_runs (created_at, mode, dataset, precision, recall, f1, fpr,
                                tp, fp, fn, tn, latency_p50, latency_p95)
    VALUES (:created_at, :mode, :dataset, :precision, :recall, :f1, :fpr,
            :tp, :fp, :fn, :tn, :latency_p50, :latency_p95)
    """
)
_SELECT_ROLE_ID = text("SELECT id FROM roles WHERE name = :name")
_INSERT_ROLE = text(
    """
    INSERT OR IGNORE INTO roles (name, can_review, can_post, can_admin)
    VALUES (:name, :can_review, :can_post, :can_admin)
    """
)
_INSERT_USER = text(
    """
    INSERT INTO users (username, email, api_key_hash, role_id, is_active, created_at)
    VALUES (:username, :email, :api_key_hash, :role_id, :is_active, :created_at)
    """
)
_SELECT_USERS = text(
    """
    SELECT u.id, u.username, u.email, u.is_active, u.created_at, r.name AS role
    FROM users u JOIN roles r ON r.id = u.role_id
    ORDER BY u.id
    """
)
_SELECT_USER_BY_HASH = text(
    """
    SELECT u.id, u.username, u.is_active, r.name AS role,
           r.can_review, r.can_post, r.can_admin
    FROM users u JOIN roles r ON r.id = u.role_id
    WHERE u.api_key_hash = :api_key_hash
    """
)
_UPDATE_USER_ACTIVE = text("UPDATE users SET is_active = :is_active WHERE id = :user_id")
_COUNT_USERS = text("SELECT COUNT(*) FROM users")
_SELECT_USER_ID_BY_NAME = text("SELECT id FROM users WHERE username = :username")


# --------------------------------------------------------------------------- #
# The database
# --------------------------------------------------------------------------- #


class Database:
    """The one object that talks to SQLite.

    Every method opens a short transaction and returns plain Python data
    (``dict``/``int``/``bool``). Nothing leaks a SQLAlchemy ``Row`` or a
    connection, so a caller never has to know the storage layer exists.

    Args:
        path: Filesystem path to the SQLite file, or ``":memory:"`` for an
            in-memory database (used by the tests).

    Example:
        >>> db = Database(":memory:")
        >>> db.init_schema()
        >>> db.seed_defaults()["roles_created"]
        3
    """

    def __init__(self, path: str | Path = DEFAULT_DB_PATH) -> None:
        self.path = str(path)
        self._engine = self._create_engine(self.path)

    # -- lifecycle ---------------------------------------------------------- #

    @staticmethod
    def _create_engine(path: str) -> Engine:
        """Build the engine, honouring ``:memory:`` and enabling foreign keys.

        SQLite ignores ``REFERENCES`` unless ``PRAGMA foreign_keys = ON`` is set on
        *every* connection, so it is set from a ``connect`` event rather than once
        at startup. An in-memory database uses a ``StaticPool`` so all callers
        share the single connection that holds the data.
        """
        if path == ":memory:":
            engine = create_engine(
                "sqlite://",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                future=True,
            )
        else:
            parent = Path(path).expanduser().parent
            if str(parent) not in ("", "."):
                parent.mkdir(parents=True, exist_ok=True)
            engine = create_engine(
                f"sqlite:///{path}",
                connect_args={"check_same_thread": False},
                future=True,
            )

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.close()

        return engine

    def init_schema(self) -> None:
        """Create every table and index from :data:`SCHEMA_SQL`. Idempotent.

        Safe to call on every start: each statement is ``IF NOT EXISTS``, so a
        database that already has the schema is left exactly as it is (no data is
        touched).
        """
        with self._engine.begin() as connection:
            for statement in _statements(SCHEMA_SQL):
                connection.exec_driver_sql(statement)

    def close(self) -> None:
        """Dispose the connection pool and forget this instance in the registry."""
        self._engine.dispose()
        with _REGISTRY_LOCK:
            for key, value in list(_DATABASES.items()):
                if value is self:
                    del _DATABASES[key]

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Database(path={self.path!r})"

    # -- reviews ------------------------------------------------------------ #

    def store_review(
        self,
        review: Any,
        *,
        mode: str,
        provider: str,
        model: str,
        target: str,
    ) -> int:
        """Persist one review and its findings in a single transaction.

        Args:
            review: A :class:`app.models.ReviewResult` or
                :class:`app.parser.DiffReviewResult` — anything with ``findings``
                (each carrying ``file``/``line``/``severity``/``issue``/
                ``suggested_fix``).
            mode: ``"live"`` or ``"mock"``. Passed explicitly because the caller
                knows which provider really ran; the CHECK constraint rejects
                anything else.
            provider: Provider that produced the findings, e.g. ``"mock"``.
            model: Model id behind the findings, e.g. ``"local-rules"``.
            target: What was reviewed — a file path, ``"<request body>"`` or
                ``"owner/repo#42"``.

        Returns:
            The new ``reviews.id``.

        Raises:
            ValueError: When ``mode`` is not ``"live"`` or ``"mock"`` (caught here
                rather than at the CHECK constraint, so the message names the
                argument).
            sqlalchemy.exc.SQLAlchemyError: On any database failure; the caller
                logs it and continues.
        """
        if mode not in ("live", "mock"):
            raise ValueError(f'mode must be "live" or "mock", got {mode!r}')
        findings = list(getattr(review, "findings", []) or [])
        verdict = verdict_for(findings)
        created_at = _utc_now()
        with self._engine.begin() as connection:
            result = connection.execute(
                _INSERT_REVIEW,
                {
                    "created_at": created_at,
                    "mode": mode,
                    "provider": provider,
                    "model": model,
                    "target": target,
                    "findings_count": len(findings),
                    "verdict": verdict,
                },
            )
            review_id = int(result.lastrowid or 0)
            if findings:
                connection.execute(
                    _INSERT_FINDING,
                    [
                        {
                            "review_id": review_id,
                            "file": finding.file,
                            "line": finding.line,
                            "severity": _severity(finding.severity),
                            "issue": finding.issue,
                            "suggested_fix": finding.suggested_fix,
                        }
                        for finding in findings
                    ],
                )
        return review_id

    def list_reviews(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent reviews, newest first.

        Args:
            limit: Maximum rows to return. Values below 1 are treated as 1.

        Returns:
            One dict per review with ``id``, ``created_at``, ``mode``,
            ``provider``, ``model``, ``target``, ``findings_count`` and
            ``verdict``. Findings are not included — use :meth:`get_review`.
        """
        safe_limit = max(1, int(limit))
        with self._engine.connect() as connection:
            rows = connection.execute(_SELECT_REVIEWS, {"limit": safe_limit}).mappings().all()
        return [dict(row) for row in rows]

    def get_review(self, review_id: int) -> dict[str, Any] | None:
        """Return one review with its findings, or ``None`` when it does not exist.

        Args:
            review_id: The ``reviews.id`` to fetch.

        Returns:
            The review dict (as in :meth:`list_reviews`) plus ``"findings"``: a
            list of ``id``/``file``/``line``/``severity``/``issue``/
            ``suggested_fix`` dicts in insertion order.
        """
        with self._engine.connect() as connection:
            row = connection.execute(_SELECT_REVIEW, {"review_id": int(review_id)}).mappings().first()
            if row is None:
                return None
            findings = connection.execute(
                _SELECT_FINDINGS, {"review_id": int(review_id)}
            ).mappings().all()
        record = dict(row)
        record["findings"] = [dict(item) for item in findings]
        return record

    # -- postings ----------------------------------------------------------- #

    def store_pr_post(
        self,
        review_id: int | None,
        *,
        owner: str,
        repo: str,
        pr_number: int,
        ok: bool,
        inline_posted: int = 0,
        inline_demoted: int = 0,
        summary_posted: bool = False,
        skipped_dup: bool = False,
        error: str | None = None,
    ) -> int:
        """Record one attempt to publish a review to a pull request.

        Args:
            review_id: The review being posted, or ``None`` when it is unknown
                (the column allows NULL and is set to NULL if the review is later
                deleted, so the posting history survives).
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull-request number.
            ok: Whether the post succeeded.
            inline_posted: Inline comments GitHub accepted.
            inline_demoted: Inline comments moved into the summary.
            summary_posted: Whether the summary comment was created.
            skipped_dup: Whether an identical review was already present.
            error: Short failure reason, or ``None`` on success.

        Returns:
            The new ``pr_posts.id``.
        """
        with self._engine.begin() as connection:
            result = connection.execute(
                _INSERT_PR_POST,
                {
                    "review_id": None if review_id is None else int(review_id),
                    "owner": owner,
                    "repo": repo,
                    "pr_number": int(pr_number),
                    "ok": _flag(ok),
                    "inline_posted": int(inline_posted),
                    "inline_demoted": int(inline_demoted),
                    "summary_posted": _flag(summary_posted),
                    "skipped_dup": _flag(skipped_dup),
                    "error": error or None,
                    "created_at": _utc_now(),
                },
            )
            return int(result.lastrowid or 0)

    # -- benchmarks --------------------------------------------------------- #

    def store_benchmark_run(
        self,
        *,
        mode: str,
        dataset: str,
        precision: float | None = None,
        recall: float | None = None,
        f1: float | None = None,
        fpr: float | None = None,
        tp: int | None = None,
        fp: int | None = None,
        fn: int | None = None,
        tn: int | None = None,
        latency_p50: float | None = None,
        latency_p95: float | None = None,
    ) -> int:
        """Record one benchmark run and its metrics.

        Every metric is optional so a partially-measured run can still be stored;
        the columns are nullable for exactly that reason.

        Returns:
            The new ``benchmark_runs.id``.
        """
        with self._engine.begin() as connection:
            result = connection.execute(
                _INSERT_BENCHMARK,
                {
                    "created_at": _utc_now(),
                    "mode": mode,
                    "dataset": dataset,
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                    "fpr": fpr,
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                    "tn": tn,
                    "latency_p50": latency_p50,
                    "latency_p95": latency_p95,
                },
            )
            return int(result.lastrowid or 0)

    # -- users and roles ---------------------------------------------------- #

    def create_user(self, username: str, email: str, role: str, api_key: str) -> dict[str, Any]:
        """Create a user, storing only the SHA-256 of ``api_key``.

        Args:
            username: Unique login name.
            email: Unique email address.
            role: One of :data:`ROLE_NAMES`; resolved to ``roles.id``.
            api_key: The plaintext key. It is hashed here and never stored, logged
                or returned — the database keeps ``api_key_hash`` only.

        Returns:
            The created user as ``id``/``username``/``email``/``role``/
            ``is_active``/``created_at``. The hash is deliberately absent, so even
            ``repr()`` of this dict cannot leak credential material.

        Raises:
            ValueError: When ``role`` is not a known role, the key is blank, or the
                ``roles`` table has not been seeded.
            sqlalchemy.exc.IntegrityError: When the username, email or key already
                exists (each is ``UNIQUE``).
        """
        cleaned_role = (role or "").strip().lower()
        if cleaned_role not in ROLE_NAMES:
            raise ValueError(f"role must be one of {', '.join(ROLE_NAMES)}, got {role!r}")
        key_hash = hash_api_key(api_key)
        with self._engine.begin() as connection:
            role_id = connection.execute(_SELECT_ROLE_ID, {"name": cleaned_role}).scalar_one_or_none()
            if role_id is None:
                raise ValueError(
                    f"role {cleaned_role!r} is not in the roles table — call seed_defaults() first"
                )
            created_at = _utc_now()
            result = connection.execute(
                _INSERT_USER,
                {
                    "username": (username or "").strip(),
                    "email": (email or "").strip(),
                    "api_key_hash": key_hash,
                    "role_id": int(role_id),
                    "is_active": 1,
                    "created_at": created_at,
                },
            )
            user_id = int(result.lastrowid or 0)
        return {
            "id": user_id,
            "username": (username or "").strip(),
            "email": (email or "").strip(),
            "role": cleaned_role,
            "is_active": True,
            "created_at": created_at,
        }

    def list_users(self) -> list[dict[str, Any]]:
        """Return every user with its role name, oldest first.

        The API-key hash is never part of the result.
        """
        with self._engine.connect() as connection:
            rows = connection.execute(_SELECT_USERS).mappings().all()
        return [_row_to_user(dict(row)) for row in rows]

    def set_user_active(self, user_id: int, active: bool) -> bool:
        """Activate or deactivate a user.

        Returns:
            ``True`` when a row changed, ``False`` when no user has that id.
        """
        with self._engine.begin() as connection:
            result = connection.execute(
                _UPDATE_USER_ACTIVE,
                {"is_active": _flag(active), "user_id": int(user_id)},
            )
            return bool(result.rowcount)

    def authenticate(self, api_key: str | None) -> Any | None:
        """Resolve an API key to a :class:`app.auth.UserContext`.

        Args:
            api_key: The plaintext key from the ``X-API-Key`` header.

        Returns:
            The caller's context (user id, username, role and the three
            capabilities) when the key hashes to an active user's row; ``None``
            for a missing, blank, unknown or deactivated key. A deactivated user
            is indistinguishable from an unknown one on purpose.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: On a database failure — an outage must
                not be reported as a bad credential.
        """
        from app.auth import UserContext  # local import: auth imports this module

        if not api_key or not api_key.strip():
            return None
        try:
            key_hash = hash_api_key(api_key)
        except ValueError:
            return None
        with self._engine.connect() as connection:
            row = connection.execute(
                _SELECT_USER_BY_HASH, {"api_key_hash": key_hash}
            ).mappings().first()
        if row is None or not row["is_active"]:
            return None
        return UserContext(
            user_id=int(row["id"]),
            username=str(row["username"]),
            role=str(row["role"]),
            can_review=bool(row["can_review"]),
            can_post=bool(row["can_post"]),
            can_admin=bool(row["can_admin"]),
        )

    def seed_defaults(self) -> dict[str, Any]:
        """Insert the three roles, and one admin user when a seed key is configured.

        Idempotent: roles are inserted with ``INSERT OR IGNORE``, and the seed
        admin is created only when no ``admin`` user exists yet. The admin's key
        comes from ``DB_SEED_ADMIN_KEY``; when that variable is unset (the
        default) no user is created at all — an unattended deployment must not
        grow a default credential nobody chose.

        Returns:
            ``{"roles_created": int, "admin_created": bool}``.
        """
        roles_created = 0
        with self._engine.begin() as connection:
            for name in ROLE_NAMES:
                can_review, can_post, can_admin = ROLE_PERMISSIONS[name]
                result = connection.execute(
                    _INSERT_ROLE,
                    {
                        "name": name,
                        "can_review": can_review,
                        "can_post": can_post,
                        "can_admin": can_admin,
                    },
                )
                roles_created += int(result.rowcount or 0)

        admin_created = False
        seed_key = (Settings().db_seed_admin_key or "").strip()
        if seed_key:
            with self._engine.begin() as connection:
                existing = connection.execute(
                    _SELECT_USER_ID_BY_NAME, {"username": SEED_ADMIN_USERNAME}
                ).scalar_one_or_none()
            if existing is None:
                self.create_user(
                    SEED_ADMIN_USERNAME, SEED_ADMIN_EMAIL, "admin", seed_key
                )
                admin_created = True
        return {"roles_created": roles_created, "admin_created": admin_created}

    # -- reporting ---------------------------------------------------------- #

    def stats(self) -> dict[str, Any]:
        """Aggregate counts for ``GET /stats``.

        Additive to the frozen surface: the read methods above are per-row, and
        answering "how many blocked reviews" from ``list_reviews`` would mean
        pulling every row into Python.

        Returns:
            ``reviews``, ``findings``, ``reviews_by_mode``, ``reviews_by_verdict``,
            ``findings_by_severity`` (all four severities always present),
            ``pr_posts``, ``pr_posts_ok``, ``benchmark_runs`` and
            ``latest_review_at`` (``None`` when nothing is stored yet).
        """
        with self._engine.connect() as connection:
            reviews = int(connection.execute(text("SELECT COUNT(*) FROM reviews")).scalar_one())
            findings = int(connection.execute(text("SELECT COUNT(*) FROM findings")).scalar_one())
            by_mode = {
                str(row[0]): int(row[1])
                for row in connection.execute(
                    text("SELECT mode, COUNT(*) FROM reviews GROUP BY mode")
                ).all()
            }
            by_verdict = {
                str(row[0]): int(row[1])
                for row in connection.execute(
                    text("SELECT verdict, COUNT(*) FROM reviews GROUP BY verdict")
                ).all()
            }
            by_severity = {
                str(row[0]): int(row[1])
                for row in connection.execute(
                    text("SELECT severity, COUNT(*) FROM findings GROUP BY severity")
                ).all()
            }
            pr_posts = int(connection.execute(text("SELECT COUNT(*) FROM pr_posts")).scalar_one())
            pr_posts_ok = int(
                connection.execute(text("SELECT COUNT(*) FROM pr_posts WHERE ok = 1")).scalar_one()
            )
            benchmarks = int(
                connection.execute(text("SELECT COUNT(*) FROM benchmark_runs")).scalar_one()
            )
            latest = connection.execute(text("SELECT MAX(created_at) FROM reviews")).scalar_one()
        return {
            "reviews": reviews,
            "findings": findings,
            "reviews_by_mode": by_mode,
            "reviews_by_verdict": by_verdict,
            "findings_by_severity": {
                name: by_severity.get(name, 0)
                for name in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
            },
            "pr_posts": pr_posts,
            "pr_posts_ok": pr_posts_ok,
            "benchmark_runs": benchmarks,
            "latest_review_at": str(latest) if latest else None,
        }


# --------------------------------------------------------------------------- #
# Process-wide singleton
# --------------------------------------------------------------------------- #

_DATABASES: dict[str, Database] = {}
_REGISTRY_LOCK = threading.Lock()


def get_database(settings: Settings | None = None) -> Database:
    """Return the process-wide :class:`Database` for the configured path.

    One instance per path, created on first use, with the schema applied and the
    default roles seeded. Keying on the path (rather than a bare module global)
    means a test that points ``DATABASE_PATH`` at a temporary file gets its own
    isolated database instead of the previous one.

    Args:
        settings: Loaded settings; ``None`` reads them from the environment.

    Returns:
        The shared :class:`Database` for ``settings.database_path``.

    Raises:
        RuntimeError: When ``DATABASE_PATH`` is blank. A blank path is how
            persistence is switched off, and inventing a default here would hide
            that decision from the operator.
    """
    resolved = settings or Settings()
    path = (resolved.database_path or "").strip()
    if not path:
        raise RuntimeError("DATABASE_PATH is blank — persistence is disabled")
    with _REGISTRY_LOCK:
        database = _DATABASES.get(path)
        if database is None:
            database = Database(path)
            database.init_schema()
            database.seed_defaults()
            _DATABASES[path] = database
    return database
