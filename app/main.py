"""FastAPI surface for the reviewer.

Endpoints
---------
``POST /webhook``
    Receives a GitHub ``pull_request`` event. The diff comes from, in order: an
    inline ``diff`` field in the payload (demo hook), the GitHub API when
    ``GITHUB_TOKEN`` is set, or the bundled fixture. When
    ``GITHUB_WEBHOOK_SECRET`` is configured, the ``X-Hub-Signature-256`` header is
    verified first and a bad signature is rejected with 401.
``POST /review``
    Reviews a raw diff or a raw source file submitted in the request body. This is
    the endpoint for the CLI, for a CI job, or for a browser tab.
``GET|POST /test-review``
    The demo: runs the engine over ``samples/sample.diff`` (or a diff in the
    body, or a file under the project root) and answers instantly with no
    credentials, no network and no LLM.
``GET /rules``, ``GET /rules/{rule_id}``
    Publish the rule set, so "what does it check?" is answerable at runtime.
``GET /health``, ``GET /``
    Liveness, active mode, and which credentials are present.

Every review surface runs through :func:`app.engine.review`, the single provider
selector: ``sarvam`` when ``SARVAM_API_KEY`` is set, else ``local`` when
``LMSTUDIO_BASE_URL`` is set, else ``mock`` — sarvam wins when both are set, and
``provider`` in the request body or query string overrides the environment. The
response always names the provider and model that really ran, so a local run is
never labelled sarvam.

Phase 5 publishes the review back to GitHub: for a ``pull_request`` event whose
action is ``opened``, ``reopened`` or ``synchronize`` — and only when a
``GITHUB_TOKEN`` is configured — the review is posted as inline comments plus a
summary, and the outcome is reported in the additive ``posting`` field. A
posting failure is logged at WARNING and never changes the HTTP status: GitHub
must always see 200, or it retries the delivery forever.

Nothing here can 500 for want of a key or a network route: every external step is
wrapped, logged once at WARNING, and degraded to the fixture. A demo must not die
on stage.

Status codes are deliberately not all 200. A *posting* failure never changes the
status (the locked Phase 5 decision: log it, report it in ``posting``, answer 200),
because GitHub retries a 5xx and a comment we could not place is not a bad request.
A malformed request is still reported as one: an unparseable ``diff`` returns 422,
and a bad ``X-Hub-Signature-256`` returns 401.

Run: ``uvicorn app.main:app --reload --port 8000``
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi import Path as ApiPath
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import __version__, engine
from app.auth import require
from app.config import Settings
from app.db import Database, get_database
from app.github_client import build_payload, github_available, post_review
from app.mock_provider import ENGINE_NOTE
from app.models import Severity, severity_counts
from app.parser import (
    DiffParseError,
    DiffReviewResult,
    anchor_findings,
    bundle_from_source,
    parse_diff,
)
from app.rules import RULE_COUNT, RULES, RuleCategory, rule_by_id

__all__ = ["app", "render_comment", "ReviewRequest", "ReviewResponse"]

logger = logging.getLogger("reviewer.api")

_ROOT = Path(__file__).resolve().parent.parent
_FIXTURE = _ROOT / "samples" / "sample.diff"
_GITHUB_API = "https://api.github.com"
_PR_ACTIONS = {"opened", "reopened", "synchronize", "ready_for_review", "edited"}
# The actions worth publishing a review for (contract: all three ON).
_POST_ACTIONS = {"opened", "reopened", "synchronize"}

# Last-resort diff, so the demo still answers if the fixture file is deleted.
_EMBEDDED_DIFF = """diff --git a/app/demo.py b/app/demo.py
--- a/app/demo.py
+++ b/app/demo.py
@@ -1,2 +1,6 @@
 import os
 
+API_TOKEN = "ghp_demoTokenValue1234567890"
+def get_user(uid):
+    query = f"SELECT * FROM users WHERE id = {uid}"
+    return os.system(query)
"""

_EXAMPLE_DIFF = """diff --git a/app/users.py b/app/users.py
--- a/app/users.py
+++ b/app/users.py
@@ -1,3 +1,5 @@
 import sqlite3
 
+def get_user(db, uid):
+    return db.execute(f"SELECT * FROM users WHERE id = {uid}")
"""

_EXAMPLE_CODE = """import os

API_KEY = "AKIAIOSFODNN7EXAMPLE0"

def run(cmd):
    os.system("sh -c " + cmd)
"""

app = FastAPI(
    title="Autonomous AI Code Reviewer & PR Assistant",
    version=__version__,
    summary="Deterministic, offline-first code review over git diffs.",
    description=(
        "A local rule engine (63 OWASP-mapped checks) plus a GitHub webhook surface. "
        "Every endpoint answers with zero credentials and zero network access: the "
        "review is deterministic, and the webhook degrades to a bundled fixture when "
        "the GitHub API is unavailable."
    ),
    contact={"name": "Shreyash Yadav"},
    license_info={"name": "MIT"},
    openapi_tags=[
        {"name": "review", "description": "Run the rule engine over a diff or a source file."},
        {"name": "webhook", "description": "GitHub pull_request integration."},
        {"name": "rules", "description": "Introspect the rule set."},
        {"name": "ops", "description": "Liveness and service metadata."},
        {
            "name": "history",
            "description": "Stored reviews and aggregate statistics from the SQLite history.",
        },
        {
            "name": "users",
            "description": "API-key holders and their roles. Admin only when API_AUTH_ENABLED is on.",
        },
    ],
)


class ReviewRequest(BaseModel):
    """A review submission: either a unified diff or a whole source file."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"diff": _EXAMPLE_DIFF, "min_severity": "MEDIUM"},
                {"code": _EXAMPLE_CODE, "filename": "app/runner.py"},
            ]
        },
    )

    diff: str | None = Field(
        default=None,
        description="Unified diff text (git or plain). Reviewed as a patch.",
        examples=[_EXAMPLE_DIFF],
    )
    code: str | None = Field(
        default=None,
        description="Whole source file. Every line is treated as an added line.",
        examples=[_EXAMPLE_CODE],
    )
    filename: str = Field(
        default="submission.py",
        description="Path reported on findings when reviewing raw code.",
        examples=["app/users.py"],
    )
    min_severity: Severity | None = Field(
        default=None,
        description="Drop findings below this severity. Omit to return everything.",
        examples=["LOW"],
    )
    categories: list[RuleCategory] | None = Field(
        default=None,
        description="Restrict to these rule categories. Omit to run every rule.",
        examples=[["secrets", "injection"]],
    )
    provider: Literal["auto", "local", "sarvam", "mock"] = Field(
        default="auto",
        description=(
            "Which reviewer runs. 'auto' follows the precedence sarvam > local > mock "
            "(SARVAM_API_KEY, then LMSTUDIO_BASE_URL). A forced provider that is not "
            "configured degrades to 'mock' and the response says so."
        ),
        examples=["auto", "mock", "local", "sarvam"],
    )

    @field_validator("code")
    @classmethod
    def _no_null_bytes(cls, value: str | None) -> str | None:
        """Reject NUL bytes: they are never valid source and confuse every tool downstream."""
        if value is not None and "\x00" in value:
            raise ValueError("code contains NUL bytes")
        return value


class ReviewStats(BaseModel):
    """Counts and timing for one review, so a caller can gate on them."""

    files: int = Field(description="Files in the diff (1 for raw code).", examples=[2])
    findings: int = Field(description="Findings returned after filtering.", examples=[3])
    critical: int = Field(description="CRITICAL findings.", examples=[2])
    high: int = Field(description="HIGH findings.", examples=[1])
    medium: int = Field(description="MEDIUM findings.", examples=[0])
    low: int = Field(description="LOW findings.", examples=[0])
    verdict: Literal["block", "approve with comments", "approve"] = Field(
        description="Gate decision derived from the severity mix.", examples=["block"]
    )
    rules_evaluated: int = Field(description="Rules in the registry at request time.", examples=[63])
    duration_ms: float = Field(
        description="Engine plus provider wall time in milliseconds.", examples=[1.8]
    )


class PostingInfo(BaseModel):
    """Outcome of publishing a review to the pull request.

    Additive and optional: it is present only when a post was actually attempted,
    and a failure here is reported in this object rather than as an HTTP error.
    """

    ok: bool = Field(
        description="True when the post completed without a failure worth degrading on.",
        examples=[True],
    )
    inline_posted: int = Field(
        description="Inline comments GitHub accepted.",
        examples=[3],
    )
    inline_demoted: int = Field(
        description="Inline comments that were moved into the summary instead.",
        examples=[0],
    )
    summary_posted: bool = Field(
        description="True when the summary comment was created.",
        examples=[True],
    )
    skipped_dup: bool = Field(
        description="True when an identical review was already on the pull request.",
        examples=[False],
    )
    error: str = Field(
        description="Empty on success, otherwise a short reason for the caller.",
        examples=["", "GITHUB_TOKEN not configured"],
    )


class ReviewResponse(BaseModel):
    """A review, the markdown a PR comment would carry, and the counters."""
    source: Literal["sample_fixture", "inline_diff", "raw_code", "github_api"] = Field(
        description="Where the reviewed text came from.", examples=["sample_fixture"]
    )
    notice: str = Field(
        default="",
        description="Why this source was used, in plain words.",
        examples=["no GITHUB_TOKEN configured — using the bundled sample diff"],
    )
    review: DiffReviewResult = Field(description="Structured review: files, findings and anchors.")
    comment: str = Field(description="Markdown ready to post as a pull-request comment.")
    stats: ReviewStats = Field(description="Counts and engine timing.")
    provider: str = Field(
        description=(
            "Which reviewer actually produced the findings: 'sarvam' or 'local' for a "
            "live run, 'mock' when the local rule engine ran."
        ),
        examples=["mock", "local", "sarvam"],
    )
    model: str = Field(
        description="Model id behind the findings: 'local-rules' when degraded.",
        examples=["local-rules", "sarvam-m"],
    )
    posting: PostingInfo | None = Field(
        default=None,
        description=(
            "Outcome of posting this review to the pull request. Absent (null) when no "
            "post was attempted: no GITHUB_TOKEN, an action outside "
            "opened/reopened/synchronize, or an endpoint that never posts."
        ),
        examples=[
            {
                "ok": True,
                "inline_posted": 3,
                "inline_demoted": 0,
                "summary_posted": True,
                "skipped_dup": False,
                "error": "",
            }
        ],
    )


class WebhookAck(BaseModel):
    """Acknowledgement for an event the reviewer deliberately does not act on."""

    status: Literal["ignored"] = Field(description="Always 'ignored'.", examples=["ignored"])
    event: str = Field(description="The X-GitHub-Event header value.", examples=["ping"])
    detail: str = Field(description="Why it was ignored.", examples=["only pull_request events are reviewed"])


class RuleInfo(BaseModel):
    """One registered rule, as published by ``GET /rules``."""

    id: str = Field(description="Stable rule id, e.g. 'unsafe/sql-injection'.", examples=["unsafe/sql-injection"])
    title: str = Field(description="Short human title.", examples=["SQL injection"])
    category: RuleCategory = Field(description="Rule category.", examples=["injection"])
    owasp: str = Field(description="OWASP Top 10 (2021) mapping.", examples=["A03:2021-Injection"])
    severity: Severity = Field(description="Fixed severity for this rule.", examples=["CRITICAL"])


class HealthResponse(BaseModel):
    """Liveness plus the facts a demo operator needs at a glance."""

    status: Literal["ok"] = Field(description="Service liveness.", examples=["ok"])
    mode: Literal["live", "mock"] = Field(description="Active review mode.", examples=["mock"])
    rules: int = Field(description="Rules in the registry.", examples=[63])
    categories: list[str] = Field(description="Rule categories available.")
    sarvam_key: Literal["configured", "missing"] = Field(description="Sarvam credential state.")
    github_token: Literal["configured", "missing"] = Field(description="GitHub token state.")
    webhook_secret: Literal["configured", "missing"] = Field(description="Webhook HMAC state.")
    provider: Literal["sarvam", "local", "mock"] = Field(
        description=(
            "Provider the next review would use, from the same selector the review "
            "endpoints call: sarvam > local > mock."
        ),
        examples=["mock", "local", "sarvam"],
    )
    database: Literal["ok", "disabled", "error"] = Field(
        description=(
            "State of the SQLite history: 'ok' when the schema answers, 'disabled' when "
            "DATABASE_PATH is blank, 'error' when it is configured but unusable. A broken "
            "history never stops a review; it only stops it being remembered."
        ),
        examples=["ok", "disabled", "error"],
    )


def render_comment(review: DiffReviewResult) -> str:
    """Render a review as the markdown a pull-request comment would carry.

    Args:
        review: The diff review to render.

    Returns:
        Markdown with one section per finding, CRITICAL first, then the verdict.
    """
    counts = severity_counts(review.findings)
    lines: list[str] = [
        "## Autonomous AI Code Review",
        "",
        f"**Mode:** `{review.mode}` · **Files:** {len(review.files)} · "
        f"**Findings:** {len(review.findings)} "
        f"(CRITICAL {counts['CRITICAL']}, HIGH {counts['HIGH']}, "
        f"MEDIUM {counts['MEDIUM']}, LOW {counts['LOW']})",
        "",
        "| File | Change | Added lines |",
        "|---|---|---|",
    ]
    for summary in review.files:
        spans = ", ".join(summary.added_spans) if summary.added_spans else "none"
        lines.append(f"| `{summary.path}` | {summary.change} | {spans} |")
    lines.append("")

    if not review.findings:
        lines.append("No findings from the local rule engine.")
    else:
        for index, anchored in enumerate(review.sorted_anchors, start=1):
            finding = anchored.finding
            lines.append(f"### {index}. {finding.severity.value} — `{finding.file}:{finding.line}`")
            lines.append("")
            lines.append(f"- **Issue:** {finding.issue}")
            lines.append(f"- **Suggested fix:** {finding.suggested_fix}")
            anchor = anchored.status.value
            if anchored.hunk_header:
                anchor += f" (`{anchored.hunk_header}`)"
            lines.append(f"- **Anchor:** {anchor}")
            lines.append("")

    lines.append(f"**Verdict:** {review.verdict}")
    return "\n".join(lines) + "\n"


def _active_mode() -> str:
    """Report the mode the service is really in.

    Returns:
        ``"live"`` when :func:`app.engine.select_provider` picks a configured
        provider (``sarvam`` or ``local``), ``"mock"`` when it picks the rule
        engine. A request may still degrade to mock when the live call fails,
        which the per-response ``mode`` reports.
    """
    return "live" if engine.select_provider(Settings()).provider != "mock" else "mock"


def _load_fixture() -> tuple[str, str]:
    """Return ``(diff_text, notice)`` from the bundled sample, or the embedded copy."""
    try:
        return _FIXTURE.read_text(encoding="utf-8"), f"sample fixture: {_FIXTURE.name}"
    except OSError as exc:
        logger.warning("fixture unreadable (%s) — using the embedded demo diff", exc)
        return _EMBEDDED_DIFF, "embedded demo diff (fixture missing)"


def _confine_to_project(raw: str) -> Path:
    """Resolve ``raw`` and refuse anything outside the project root.

    The demo endpoint reads files by path, which is a directory-traversal hole the
    moment it is exposed. Confining the result to the project root closes it.

    Raises:
        HTTPException: 403 when the path escapes the project, 404 when missing.
    """
    candidate = Path(raw)
    resolved = (candidate if candidate.is_absolute() else _ROOT / candidate).resolve()
    if resolved != _ROOT and _ROOT not in resolved.parents:
        raise HTTPException(status_code=403, detail="path must stay inside the project root")
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail=f"not a readable file: {raw}")
    return resolved


def _fetch_pr_diff(repo: str, number: int, settings: Settings) -> tuple[str | None, str]:
    """Try to fetch a pull-request diff from GitHub.

    Args:
        repo: ``owner/name``.
        number: Pull-request number.
        settings: Loaded configuration.

    Returns:
        ``(diff_text, notice)``; ``diff_text`` is ``None`` when the fetch could not
        happen or failed, and the caller degrades to the fixture.
    """
    if not settings.github_token:
        return None, "no GITHUB_TOKEN configured — using the bundled sample diff"
    url = f"{_GITHUB_API}/repos/{repo}/pulls/{number}"
    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github.v3.diff",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        with httpx.Client(timeout=settings.request_timeout_s) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.text, "fetched from the GitHub API"
    except (httpx.HTTPError, httpx.InvalidURL, OSError, RuntimeError, ValueError) as exc:
        # Constructing the client is part of the fetch: a failure there must degrade
        # to the fixture, not 500 the delivery.
        logger.warning("GitHub diff fetch failed (%s) — using the bundled sample diff", exc)
        return None, (
            f"github fetch failed ({exc.__class__.__name__}) — using the bundled sample diff"
        )


def _verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """Check a GitHub ``X-Hub-Signature-256`` header against the raw body."""
    if not signature or not signature.startswith("sha256="):
        return False
    try:
        expected = "sha256=" + hmac.new(
            secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except (UnicodeEncodeError, TypeError):
        # A non-ASCII signature header is a bad request, not a 500.
        return False


# --------------------------------------------------------------------------- #
# Persistence: best effort, and never on the response path
# --------------------------------------------------------------------------- #
#
# The locked decision for this layer mirrors the posting decision above: a
# storage problem is logged once at WARNING on `reviewer.db` and the request is
# answered exactly as it would have been. A demo that loses its history is a
# nuisance; a demo that 500s because a disk filled is a failed demo.

logger_db = logging.getLogger("reviewer.db")


def _persistence_enabled(settings: Settings) -> bool:
    """True when a database path is configured; a blank path switches history off."""
    return bool((settings.database_path or "").strip())


def _database_or_none() -> Database | None:
    """Return the process database, or ``None`` when persistence is switched off.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: When the database is configured but
            unusable. Callers on the write path catch it; read endpoints turn it
            into a 503.
    """
    settings = Settings()
    if not _persistence_enabled(settings):
        return None
    return get_database(settings)


def _persist_review(
    response: ReviewResponse,
    *,
    target: str,
    context: dict[str, Any] | None = None,
) -> int | None:
    """Store the review that was just built, swallowing every failure.

    Called from :func:`_build_response`, the single funnel every review surface
    goes through, so ``/review``, ``/test-review`` and ``/webhook`` are all
    covered by one call and a future surface cannot forget to persist.

    Args:
        response: The response being returned to the caller.
        target: What was reviewed; recorded on the ``reviews`` row.
        context: The webhook's scratch dict. The new review id is put in
            ``context["review_id"]`` so a posting attempt can reference it.

    Returns:
        The new ``reviews.id``, or ``None`` when nothing was stored.
    """
    try:
        database = _database_or_none()
        if database is None:
            return None
        review_id = database.store_review(
            response.review,
            mode=response.review.mode,
            provider=response.provider,
            model=response.model,
            target=target,
        )
    except Exception as exc:  # noqa: BLE001 - a storage failure must not change the response
        logger_db.warning("could not store the review: %s", exc)
        return None
    if context is not None:
        context["review_id"] = review_id
    return review_id


def _persist_pr_post(
    review_id: int | None,
    *,
    owner: str,
    repo: str,
    pr_number: int,
    posting: PostingInfo,
) -> None:
    """Store one posting attempt, swallowing every failure.

    A ``pr_posts`` row is written for every attempt — success, GitHub rejection
    and unexpected exception alike — because "we tried and it failed" is the fact
    worth keeping.

    Args:
        review_id: The stored review, or ``None`` when it could not be stored.
        owner: Repository owner.
        repo: Repository name.
        pr_number: Pull-request number.
        posting: The outcome being reported to the caller.
    """
    try:
        database = _database_or_none()
        if database is None:
            return
        database.store_pr_post(
            review_id,
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            ok=posting.ok,
            inline_posted=posting.inline_posted,
            inline_demoted=posting.inline_demoted,
            summary_posted=posting.summary_posted,
            skipped_dup=posting.skipped_dup,
            error=posting.error or None,
        )
    except Exception as exc:  # noqa: BLE001 - a storage failure must not change the response
        logger_db.warning("could not store the posting outcome: %s", exc)


def _database_state(settings: Settings) -> Literal["ok", "disabled", "error"]:
    """Probe the history for ``GET /health``.

    Returns:
        ``"disabled"`` when no path is configured, ``"ok"`` when the schema
        answers, ``"error"`` when it is configured but unusable.
    """
    if not _persistence_enabled(settings):
        return "disabled"
    try:
        get_database(settings)
    except Exception as exc:  # noqa: BLE001 - health must answer even when the store is broken
        logger_db.warning("database unavailable: %s", exc)
        return "error"
    return "ok"


def _db_for_read() -> Database:
    """Return the database for a read endpoint, or raise the right HTTP error.

    Raises:
        HTTPException: 503 when persistence is disabled or the store is unusable.
            A read endpoint cannot invent the rows it was asked for, so unlike the
            write path it must report the problem.
    """
    settings = Settings()
    if not _persistence_enabled(settings):
        raise HTTPException(
            status_code=503, detail="persistence is disabled (DATABASE_PATH is blank)"
        )
    try:
        return get_database(settings)
    except (SQLAlchemyError, RuntimeError, OSError) as exc:
        logger_db.warning("database unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="review history is unavailable") from exc


def _build_response(
    *,
    diff_text: str | None,
    code: str | None,
    filename: str,
    target: str,
    source: Literal["sample_fixture", "inline_diff", "raw_code", "github_api"],
    notice: str,
    min_severity: Severity | None = None,
    categories: list[RuleCategory] | None = None,
    provider: str = "auto",
    context: dict[str, Any] | None = None,
) -> ReviewResponse:
    """Parse the submitted text, run the engine, anchor the findings, build the response.

    This is the single funnel every review surface goes through, so the parse
    happens exactly once. A caller that also needs the parsed pieces — the
    webhook, which must post the review and therefore needs the anchors and the
    diff's files — passes ``context``; it is filled in place with ``review`` (the
    :class:`DiffReviewResult`, which carries ``anchors``) and ``diff_files`` (the
    parsed bundle's files). Callers that do not pass it see no change.
    ``provider`` is forwarded to :func:`app.engine.review`; ``"auto"`` (the
    default) lets the environment decide, and :attr:`ReviewResponse.provider`
    always names the provider that really ran.

    Raises:
        HTTPException: 422 when the text is neither a parseable diff nor usable code.
    """
    started = time.perf_counter()
    settings = Settings()
    if diff_text is not None:
        try:
            bundle = parse_diff(diff_text, source=target)
        except DiffParseError as exc:
            raise HTTPException(status_code=422, detail=f"cannot parse diff: {exc}") from exc
    elif code is not None:
        bundle = bundle_from_source(filename, code)
    else:
        raise HTTPException(status_code=422, detail="provide either 'diff' or 'code'")

    outcome = engine.review(
        bundle,
        settings,
        provider=provider,
        min_severity=min_severity,
        categories=categories,
    )
    findings = outcome.findings
    if outcome.mode == "live":
        provider_notes = [
            f"live review: {outcome.provider}/{outcome.model} in {outcome.latency_ms} ms"
        ]
    else:
        provider_notes = [ENGINE_NOTE, f"mock mode: {outcome.reason}"]
    review = DiffReviewResult(
        mode=outcome.mode,
        target=target,
        files=bundle.summaries(),
        findings=findings,
        anchors=anchor_findings(bundle, findings),
        notes=[notice, *provider_notes],
    )
    duration_ms = (time.perf_counter() - started) * 1000.0
    counts = severity_counts(findings)
    response = ReviewResponse(
        source=source,
        notice=notice,
        review=review,
        comment=render_comment(review),
        stats=ReviewStats(
            files=len(bundle.files),
            findings=len(findings),
            critical=counts["CRITICAL"],
            high=counts["HIGH"],
            medium=counts["MEDIUM"],
            low=counts["LOW"],
            verdict=review.verdict,  # type: ignore[arg-type]
            rules_evaluated=RULE_COUNT,
            duration_ms=round(duration_ms, 3),
        ),
        provider=outcome.provider,
        model=outcome.model,
    )
    if context is not None:
        context["review"] = review
        context["diff_files"] = bundle.files
    # Every review surface funnels through here, so this is the one place that
    # has to remember the review. It cannot change the response: see
    # _persist_review.
    _persist_review(response, target=target, context=context)
    return response


def _posting_target(payload: dict[str, Any]) -> tuple[str, str, int] | None:
    """Read ``(owner, repo, number)`` out of a webhook payload.

    Args:
        payload: The decoded webhook body.

    Returns:
        The posting target, or ``None`` when ``repository.full_name`` or the
        pull-request number cannot be determined — in which case the caller skips
        posting with a WARNING and still answers 200.
    """
    repository = payload.get("repository")
    full_name = repository.get("full_name") if isinstance(repository, dict) else None
    owner, _, repo = str(full_name or "").partition("/")
    raw_number = payload.get("number")
    if raw_number is None:
        pull_request = payload.get("pull_request")
        if isinstance(pull_request, dict):
            raw_number = pull_request.get("number")
    try:
        number = int(raw_number)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not owner.strip() or not repo.strip() or number <= 0:
        return None
    return owner.strip(), repo.strip(), number


def _head_sha(payload: dict[str, Any]) -> str | None:
    """Read the pull request's head SHA from a webhook payload, when present.

    Args:
        payload: The decoded webhook body.

    Returns:
        The head commit SHA, or ``None`` when the payload does not carry one.
    """
    pull_request = payload.get("pull_request")
    if not isinstance(pull_request, dict):
        return None
    head = pull_request.get("head")
    if not isinstance(head, dict):
        return None
    sha = head.get("sha")
    if isinstance(sha, str) and sha.strip():
        return sha.strip()
    return None


def _publish_review(
    response: ReviewResponse,
    context: dict[str, Any],
    *,
    action: str,
    payload: dict[str, Any],
    settings: Settings,
) -> ReviewResponse:
    """Post the review to its pull request, without ever changing the HTTP status.

    Args:
        response: The review just built.
        context: The dict :func:`_build_response` filled with ``review`` and
            ``diff_files`` — no second parse happens here.
        action: The ``action`` field of the pull_request event.
        payload: The decoded webhook body.
        settings: Loaded configuration (token and inline cap).

    Returns:
        ``response``, with ``posting`` set when a post was attempted. A posting
        failure is reported in ``posting`` and logged once: the single WARNING comes
        from ``reviewer.github`` inside :func:`app.github_client.post_review`, and
        this function adds only a DEBUG line so the same event is never logged twice
        at WARNING. GitHub always sees 200.
    """
    if action not in _POST_ACTIONS:
        return response
    if not github_available():
        logger.debug("no GITHUB_TOKEN configured — not posting %s to the pull request", action)
        return response
    if not settings.has_webhook_secret and not settings.webhook_allow_unsigned:
        # Fail closed. With a token configured and no shared secret, any caller that can
        # reach this endpoint could make the bot comment on a repository of their choice,
        # signed by the operator's own identity. The review still runs; only posting stops.
        logger.warning(
            "not posting: GITHUB_WEBHOOK_SECRET is unset, so this delivery cannot be "
            "authenticated (set the secret, or WEBHOOK_ALLOW_UNSIGNED=1 for a local demo)"
        )
        return response

    target = _posting_target(payload)
    if target is None:
        logger.warning(
            "cannot post the review: repository.full_name or the pull-request number "
            "is missing from the webhook payload"
        )
        return response
    owner, repo, number = target

    try:
        review_payload = build_payload(
            context["review"].anchors,
            context["diff_files"],
            max_inline=settings.github_max_inline,
        )
        result = post_review(
            owner,
            repo,
            number,
            review_payload,
            token=(settings.github_token or "").strip() or None,
            commit_id=_head_sha(payload),
        )
    except Exception as exc:  # noqa: BLE001 - deliberate: GitHub must never see a 5xx
        # This is the webhook boundary. The locked decision is that a posting failure
        # is logged and acknowledged with HTTP 200, so an unexpected exception here is
        # caught, reported in `posting`, and never propagates to a 500.
        logger.warning("posting the review to %s/%s#%s failed: %s", owner, repo, number, exc)
        response.posting = PostingInfo(
            ok=False,
            inline_posted=0,
            inline_demoted=0,
            summary_posted=False,
            skipped_dup=False,
            error=f"{type(exc).__name__}: {exc}",
        )
        _persist_pr_post(
            context.get("review_id"),
            owner=owner,
            repo=repo,
            pr_number=number,
            posting=response.posting,
        )
        return response

    if not result.ok:
        # post_review already logged exactly one WARNING on reviewer.github for this
        # failure; logging again here would be the second line for one event.
        logger.debug("posting to %s/%s#%s failed: %s", owner, repo, number, result.error)
    response.posting = PostingInfo(
        ok=result.ok,
        inline_posted=result.inline_posted,
        inline_demoted=result.inline_demoted,
        summary_posted=result.summary_posted,
        skipped_dup=result.skipped_dup,
        error=result.error,
    )
    _persist_pr_post(
        context.get("review_id"),
        owner=owner,
        repo=repo,
        pr_number=number,
        posting=response.posting,
    )
    return response


@app.get("/", tags=["ops"], summary="Service banner")
def root() -> dict[str, Any]:
    """What this service is, which mode it is in, and where the interesting endpoints are."""
    return {
        "name": "Autonomous AI Code Reviewer & PR Assistant",
        "version": __version__,
        "mode": _active_mode(),
        "rules": RULE_COUNT,
        "endpoints": ["/health", "/rules", "/review", "/test-review", "/webhook", "/docs"],
        "docs": "/docs",
    }


@app.get("/health", tags=["ops"], summary="Liveness and credential state", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness, active mode, rule count, and which credentials are present."""
    settings = Settings()
    return HealthResponse(
        status="ok",
        mode=_active_mode(),  # type: ignore[arg-type]
        rules=RULE_COUNT,
        categories=sorted({rule.category.value for rule in RULES}),
        sarvam_key="configured" if settings.has_sarvam_key else "missing",
        github_token="configured" if settings.github_token else "missing",
        webhook_secret="configured" if settings.has_webhook_secret else "missing",
        provider=engine.select_provider(settings).provider,  # type: ignore[arg-type]
        database=_database_state(settings),
    )


@app.get("/rules", tags=["rules"], summary="List every registered rule", response_model=list[RuleInfo])
def list_rules() -> list[RuleInfo]:
    """Every rule the engine can fire, CRITICAL first, so the policy is auditable at runtime."""
    return [
        RuleInfo(
            id=rule.id,
            title=rule.title,
            category=rule.category,
            owasp=rule.owasp,
            severity=rule.severity,
        )
        for rule in sorted(RULES, key=lambda item: (-item.severity.rank, item.id))
    ]


@app.get(
    "/rules/{rule_id:path}",
    tags=["rules"],
    summary="Fetch one rule by id",
    response_model=RuleInfo,
    responses={404: {"description": "No rule with that id"}},
)
def get_rule(rule_id: str) -> RuleInfo:
    """Look up a single rule, e.g. ``/rules/unsafe/sql-injection``."""
    rule = rule_by_id(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"no rule with id {rule_id!r}")
    return RuleInfo(
        id=rule.id,
        title=rule.title,
        category=rule.category,
        owasp=rule.owasp,
        severity=rule.severity,
    )


@app.post(
    "/review",
    tags=["review"],
    summary="Review a diff or a source file",
    response_model=ReviewResponse,
    responses={
        422: {
            "description": "Neither a parseable diff nor usable code was supplied",
            "content": {
                "application/json": {
                    "example": {"detail": "cannot parse diff: no file headers found"}
                }
            },
        }
    },
)
def review_endpoint(
    payload: Annotated[
        ReviewRequest,
        Body(
            description="The diff or source file to review, plus optional filters.",
            openapi_examples={
                "diff": {
                    "summary": "Review a unified diff",
                    "value": {"diff": _EXAMPLE_DIFF, "min_severity": "MEDIUM"},
                },
                "code": {
                    "summary": "Review a whole source file",
                    "value": {"code": _EXAMPLE_CODE, "filename": "app/runner.py"},
                },
            },
        ),
    ],
) -> ReviewResponse:
    """Review a unified diff or a whole source file with the local rule engine.

    Supply ``diff`` for a patch or ``code`` for a file; when both are present the
    diff wins and the notice says so. ``min_severity`` and ``categories`` filter
    the result. Nothing here calls the network.
    """
    if payload.diff is not None and payload.code is not None:
        notice = "both 'diff' and 'code' supplied — reviewed the diff and ignored 'code'"
        return _build_response(
            diff_text=payload.diff,
            code=None,
            filename=payload.filename,
            target="<request body>",
            source="inline_diff",
            notice=notice,
            min_severity=payload.min_severity,
            categories=payload.categories,
            provider=payload.provider,
        )
    if payload.diff is not None:
        return _build_response(
            diff_text=payload.diff,
            code=None,
            filename=payload.filename,
            target="<request body>",
            source="inline_diff",
            notice="diff supplied in the request body",
            min_severity=payload.min_severity,
            categories=payload.categories,
            provider=payload.provider,
        )
    if payload.code is not None:
        return _build_response(
            diff_text=None,
            code=payload.code,
            filename=payload.filename,
            target=payload.filename,
            source="raw_code",
            notice=f"raw source reviewed as an all-added file: {payload.filename}",
            min_severity=payload.min_severity,
            categories=payload.categories,
            provider=payload.provider,
        )
    raise HTTPException(status_code=422, detail="provide either 'diff' or 'code'")


@app.get(
    "/test-review",
    tags=["review"],
    summary="Offline demo review of the bundled sample diff",
    response_model=ReviewResponse,
    responses={403: {"description": "Path escapes the project root"}, 404: {"description": "Path not found"}},
)
def test_review(
    path: str | None = Query(
        default=None,
        description="Optional .diff file inside the project root to review instead of the fixture.",
        examples=["samples/sample.diff"],
    ),
    min_severity: Severity | None = Query(
        default=None, description="Drop findings below this severity."
    ),
    provider: Literal["auto", "local", "sarvam", "mock"] = Query(
        default="auto",
        description=(
            "Which reviewer runs: 'auto' follows sarvam > local > mock; 'mock' keeps the "
            "demo offline even when a key is configured."
        ),
        examples=["auto", "mock"],
    ),
) -> ReviewResponse:
    """Review the bundled sample diff instantly — no credentials needed.

    This is the endpoint to hit in front of an examiner with the Wi-Fi off: pass
    ``provider=mock`` and no network call is attempted even when a key is set.
    Pass ``path`` to review any diff that lives inside the project root.
    """
    if path:
        candidate = _confine_to_project(path)
        try:
            raw = candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=422, detail=f"cannot read {path}: {exc}") from exc
        return _build_response(
            diff_text=raw,
            code=None,
            filename=str(candidate),
            target=str(candidate.relative_to(_ROOT)),
            source="inline_diff",
            notice=f"file on disk: {candidate.relative_to(_ROOT)}",
            min_severity=min_severity,
            provider=provider,
        )

    raw, notice = _load_fixture()
    return _build_response(
        diff_text=raw,
        code=None,
        filename="samples/sample.diff",
        target="samples/sample.diff",
        source="sample_fixture",
        notice=notice,
        min_severity=min_severity,
        provider=provider,
    )


@app.post(
    "/test-review",
    tags=["review"],
    summary="Offline demo review, optionally with a diff in the body",
    response_model=ReviewResponse,
)
def test_review_body(
    payload: dict[str, Any] | None = None,
    provider: Literal["auto", "local", "sarvam", "mock"] = Query(
        default="auto",
        description="Which reviewer runs; see GET /test-review.",
        examples=["auto", "mock"],
    ),
) -> ReviewResponse:
    """Same as ``GET /test-review`` but accepts ``{"diff": "..."}`` in the body.

    ``provider`` may be given in the query string or as a body field; the body
    wins, so one request can carry both the diff and the choice of reviewer.
    """
    body = payload or {}
    chosen = body.get("provider", provider)
    if chosen not in {"auto", "local", "sarvam", "mock"}:
        raise HTTPException(
            status_code=422,
            detail="provider must be one of auto, local, sarvam, mock",
        )
    raw = body.get("diff")
    if not isinstance(raw, str) or not raw.strip():
        fixture, notice = _load_fixture()
        return _build_response(
            diff_text=fixture,
            code=None,
            filename="samples/sample.diff",
            target="samples/sample.diff",
            source="sample_fixture",
            notice=notice,
            provider=str(chosen),
        )
    return _build_response(
        diff_text=raw,
        code=None,
        filename="<request body>",
        target="<request body>",
        source="inline_diff",
        notice="diff supplied in the request body",
        provider=str(chosen),
    )


@app.post(
    "/webhook",
    tags=["webhook"],
    summary="Handle a GitHub pull_request event",
    responses={
        200: {"description": "A review, or an acknowledgement that the event was ignored"},
        400: {"description": "Body is not valid JSON"},
        401: {"description": "X-Hub-Signature-256 does not match the configured secret"},
        422: {"description": "The diff could not be parsed"},
    },
)
async def webhook(
    request: Request,
    x_github_event: str = Header(
        default="pull_request",
        description="GitHub event type.",
        examples=["pull_request"],
    ),
    x_hub_signature_256: str | None = Header(
        default=None,
        description="GitHub HMAC signature; verified only when GITHUB_WEBHOOK_SECRET is set.",
    ),
) -> Any:
    """Review a pull request, degrading to the fixture when GitHub is unreachable.

    Order of diff sources: inline ``diff`` field in the payload (demo hook), the
    GitHub API when ``GITHUB_TOKEN`` is set, then the bundled fixture. Non-PR
    events and uninteresting PR actions are acknowledged with HTTP 200 and
    ``status: ignored`` rather than treated as errors — GitHub would otherwise
    retry them forever.

    For ``opened``, ``reopened`` and ``synchronize`` with a ``GITHUB_TOKEN``
    configured, the review is also posted to the pull request and the outcome is
    reported in ``posting``. A posting failure never changes the status: GitHub
    must always see 200.
    """
    body = await request.body()
    settings = Settings()

    if settings.has_webhook_secret:
        secret = settings.github_webhook_secret or ""
        if not _verify_signature(body, x_hub_signature_256, secret):
            logger.warning("rejected webhook: signature mismatch")
            raise HTTPException(status_code=401, detail="X-Hub-Signature-256 does not match")

    try:
        payload: dict[str, Any] = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="body is not valid JSON") from exc

    event = x_github_event.lower()
    if event not in {"pull_request", "pull_request_target"}:
        return WebhookAck(
            status="ignored",
            event=event,
            detail="only pull_request events are reviewed",
        )

    action = str(payload.get("action", "opened")).lower()
    if action not in _PR_ACTIONS:
        return WebhookAck(
            status="ignored",
            event=event,
            detail=f"action '{action}' is not reviewed",
        )

    repository = payload.get("repository")
    if not isinstance(repository, dict):
        repository = {}
    repo = str(repository.get("full_name") or "") or "unknown/repo"
    pull_request_body = payload.get("pull_request")
    if not isinstance(pull_request_body, dict):
        pull_request_body = {}
    number = payload.get("number") or pull_request_body.get("number") or 0

    context: dict[str, Any] = {}
    inline = payload.get("diff")
    if isinstance(inline, str) and inline.strip():
        response = _build_response(
            diff_text=inline,
            code=None,
            filename=f"{repo}#{number}",
            target=f"{repo}#{number}",
            source="inline_diff",
            notice="diff supplied in the webhook payload",
            context=context,
        )
        return _publish_review(
            response, context, action=action, payload=payload, settings=settings
        )

    try:
        pr_number = int(number)
    except (TypeError, ValueError):
        pr_number = 0

    if pr_number > 0:
        raw, notice = _fetch_pr_diff(repo, pr_number, settings)
    else:
        raw, notice = None, "the payload carried no usable pull-request number"
    if raw is None:
        # Degrade to the fixture for the REVIEW, but never publish it: posting a
        # fixture review would attach comments about samples/sample.diff to a real
        # pull request. The reason is carried in `notice` instead.
        fixture, fixture_notice = _load_fixture()
        return _build_response(
            diff_text=fixture,
            code=None,
            filename="samples/sample.diff",
            target="samples/sample.diff",
            source="sample_fixture",
            notice=f"{notice}; {fixture_notice} (not posted: the pull-request diff could not be fetched)",
            context=context,
        )

    response = _build_response(
        diff_text=raw,
        code=None,
        filename=f"{repo}#{number}",
        target=f"{repo}#{number}",
        source="github_api",
        notice=notice,
        context=context,
    )
    return _publish_review(
        response, context, action=action, payload=payload, settings=settings
    )


# --------------------------------------------------------------------------- #
# Phase 6: the stored history and the access-control surface
# --------------------------------------------------------------------------- #
#
# These six endpoints read and write the SQLite history in `app/db.py`. They are
# guarded by `Depends(require(...))`, which is a no-op while API_AUTH_ENABLED is
# false (the default) — so the open demo endpoints above keep behaving exactly as
# before, and an operator who sets the flag gets 401/403 on these routes alone.
#
# The review surfaces (`/review`, `/test-review`, `/webhook`) are deliberately
# *not* guarded: they are the product, they carry no data about anyone else, and
# turning the flag on must not break the demo or the CLI. What the flag protects
# is the history and the user table.

_UNAUTHORIZED: dict[int | str, dict[str, Any]] = {
    401: {"description": "X-API-Key missing, unknown, or belonging to a deactivated user"},
    403: {"description": "The key's role lacks the permission this route requires"},
}
_UNAVAILABLE: dict[int | str, dict[str, Any]] = {
    503: {"description": "Persistence is disabled, or the history is unavailable"}
}


class FindingRecord(BaseModel):
    """One stored finding, exactly as the ``findings`` table holds it."""

    id: int = Field(description="Row id.", examples=[1])
    file: str = Field(description="File the finding points at.", examples=["app/users.py"])
    line: str = Field(description='Line number, or a range as "42-45".', examples=["12"])
    severity: Severity = Field(description="LOW | MEDIUM | HIGH | CRITICAL.", examples=["CRITICAL"])
    issue: str = Field(description="What is wrong and why it bites.", examples=["SQL injection"])
    suggested_fix: str = Field(
        description="The change that fixes it.", examples=["db.execute(q, (uid,))"]
    )


class ReviewSummary(BaseModel):
    """A stored review, without its findings — one row of ``GET /reviews``."""

    id: int = Field(description="Review id, usable with GET /reviews/{review_id}.", examples=[7])
    created_at: str = Field(description="UTC timestamp, ISO-8601.", examples=["2026-11-14T06:12:00Z"])
    mode: Literal["live", "mock"] = Field(description="Review mode that really ran.", examples=["mock"])
    provider: str = Field(description="Provider that produced the findings.", examples=["mock"])
    model: str = Field(description="Model id behind the findings.", examples=["local-rules"])
    target: str = Field(description="What was reviewed.", examples=["<request body>"])
    findings_count: int = Field(description="Findings recorded for this review.", examples=[3])
    verdict: Literal["block", "approve with comments", "approve"] = Field(
        description="Gate decision derived from the severity mix.", examples=["block"]
    )


class ReviewDetail(ReviewSummary):
    """A stored review with its findings, in insertion order."""

    findings: list[FindingRecord] = Field(
        description="Every finding stored for this review, oldest first."
    )


class UserInfo(BaseModel):
    """A user as published by the API. The API-key hash is never included."""

    id: int = Field(description="User id.", examples=[2])
    username: str = Field(description="Unique login name.", examples=["priya"])
    email: str = Field(description="Unique email address.", examples=["priya@example.org"])
    role: Literal["admin", "reviewer", "viewer"] = Field(
        description="Role name; decides the permissions.", examples=["reviewer"]
    )
    is_active: bool = Field(description="A deactivated key no longer authenticates.", examples=[True])
    created_at: str = Field(description="UTC timestamp, ISO-8601.", examples=["2026-11-14T06:12:00Z"])


class UserCreateRequest(BaseModel):
    """The body of ``POST /users``."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "username": "priya",
                    "email": "priya@example.org",
                    "role": "reviewer",
                    "api_key": "a-long-random-string-from-a-password-manager",
                }
            ]
        },
    )

    username: str = Field(
        min_length=1, max_length=64, description="Unique login name.", examples=["priya"]
    )
    email: str = Field(
        min_length=3, max_length=254, description="Unique email address.", examples=["priya@example.org"]
    )
    role: Literal["admin", "reviewer", "viewer"] = Field(
        description="Role to grant: viewer reads, reviewer reviews, admin manages users.",
        examples=["reviewer"],
    )
    api_key: str = Field(
        min_length=8,
        max_length=256,
        repr=False,
        description=(
            "The plaintext key for this user. It is hashed with SHA-256 before it is "
            "stored and is never returned, logged or echoed."
        ),
        examples=["a-long-random-string-from-a-password-manager"],
    )


class UserPatchRequest(BaseModel):
    """The body of ``PATCH /users/{user_id}``."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"examples": [{"is_active": False}]}
    )

    is_active: bool = Field(
        strict=True,
        description=(
            "True to let the user's key authenticate again, false to revoke it now. "
            "Strict: a string like \"false\" is rejected rather than read as truthy."
        ),
        examples=[False],
    )


class UserStatusUpdate(BaseModel):
    """The result of ``PATCH /users/{user_id}``."""

    user_id: int = Field(description="The user that changed.", examples=[2])
    is_active: bool = Field(description="Its new active state.", examples=[False])


class StatsResponse(BaseModel):
    """Aggregate counts over the whole stored history."""

    reviews: int = Field(description="Reviews stored in total.", examples=[12])
    findings: int = Field(description="Findings stored in total.", examples=[31])
    reviews_by_mode: dict[str, int] = Field(
        description="Review count per mode.", examples=[{"mock": 12}]
    )
    reviews_by_verdict: dict[str, int] = Field(
        description="Review count per verdict.", examples=[{"block": 9, "approve": 3}]
    )
    findings_by_severity: dict[str, int] = Field(
        description="Finding count per severity; all four keys are always present.",
        examples=[{"LOW": 4, "MEDIUM": 9, "HIGH": 12, "CRITICAL": 6}],
    )
    pr_posts: int = Field(description="Posting attempts recorded.", examples=[3])
    pr_posts_ok: int = Field(description="Posting attempts that succeeded.", examples=[2])
    benchmark_runs: int = Field(description="Benchmark runs recorded.", examples=[1])
    latest_review_at: str | None = Field(
        default=None,
        description="Timestamp of the newest review, or null when nothing is stored.",
        examples=["2026-11-14T06:12:00Z"],
    )


@app.get(
    "/reviews",
    tags=["history"],
    summary="List stored reviews, newest first",
    description=(
        "The review history written by /review, /test-review and /webhook. Findings are "
        "omitted here; fetch one review with GET /reviews/{review_id}. Requires the "
        "reviewer capability when API_AUTH_ENABLED is true."
    ),
    response_model=list[ReviewSummary],
    responses={**_UNAUTHORIZED, **_UNAVAILABLE},
    dependencies=[Depends(require("reviewer"))],
)
def list_reviews(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Maximum reviews to return, newest first.",
        examples=[20],
    ),
) -> list[ReviewSummary]:
    """Return the most recent reviews, newest first."""
    database = _db_for_read()
    try:
        rows = database.list_reviews(limit)
    except (SQLAlchemyError, OSError) as exc:
        logger_db.warning("database unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="review history is unavailable") from exc
    return [ReviewSummary(**row) for row in rows]


@app.get(
    "/reviews/{review_id}",
    tags=["history"],
    summary="Fetch one stored review with its findings",
    description=(
        "One review row plus every finding recorded against it. 404 when the id is not "
        "in the history. Requires the reviewer capability when API_AUTH_ENABLED is true."
    ),
    response_model=ReviewDetail,
    responses={
        404: {"description": "No review with that id"},
        **_UNAUTHORIZED,
        **_UNAVAILABLE,
    },
    dependencies=[Depends(require("reviewer"))],
)
def get_review(
    review_id: int = ApiPath(ge=1, description="The reviews.id to fetch.", examples=[7]),
) -> ReviewDetail:
    """Return one stored review with its findings."""
    database = _db_for_read()
    try:
        record = database.get_review(review_id)
    except (SQLAlchemyError, OSError) as exc:
        logger_db.warning("database unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="review history is unavailable") from exc
    if record is None:
        raise HTTPException(status_code=404, detail=f"no review with id {review_id}")
    return ReviewDetail(**record)


@app.get(
    "/stats",
    tags=["history"],
    summary="Aggregate statistics over the stored history",
    description=(
        "Review, finding, posting and benchmark totals — the numbers a report needs. "
        "All four severity keys are always present, so a chart never has a missing bar. "
        "Requires the reviewer capability when API_AUTH_ENABLED is true."
    ),
    response_model=StatsResponse,
    responses={**_UNAUTHORIZED, **_UNAVAILABLE},
    dependencies=[Depends(require("reviewer"))],
)
def get_stats() -> StatsResponse:
    """Count reviews, findings, postings and benchmarks."""
    database = _db_for_read()
    try:
        return StatsResponse(**database.stats())
    except (SQLAlchemyError, OSError) as exc:
        logger_db.warning("database unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="review history is unavailable") from exc


@app.post(
    "/users",
    tags=["users"],
    summary="Create a user and issue an API key",
    description=(
        "Stores the SHA-256 of the supplied key and grants the named role. The key itself "
        "is never stored, logged or returned — write it down before you send this request. "
        "Admin only when API_AUTH_ENABLED is true."
    ),
    response_model=UserInfo,
    status_code=201,
    responses={
        409: {"description": "That username, email or API key is already registered"},
        422: {"description": "Unknown role, or a key shorter than 8 characters"},
        **_UNAUTHORIZED,
        **_UNAVAILABLE,
    },
    dependencies=[Depends(require("admin"))],
)
def create_user(
    payload: Annotated[
        UserCreateRequest,
        Body(description="The user to create, and the key they will authenticate with."),
    ],
) -> UserInfo:
    """Create a user, storing only the hash of the API key."""
    database = _db_for_read()
    try:
        created = database.create_user(
            payload.username, payload.email, payload.role, payload.api_key
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="username, email or API key is already registered",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (SQLAlchemyError, OSError) as exc:
        logger_db.warning("database unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="user store is unavailable") from exc
    return UserInfo(**created)


@app.get(
    "/users",
    tags=["users"],
    summary="List users and their roles",
    description=(
        "Every user with the role that decides their permissions. The API-key hash is "
        "never part of the response. Admin only when API_AUTH_ENABLED is true."
    ),
    response_model=list[UserInfo],
    responses={**_UNAUTHORIZED, **_UNAVAILABLE},
    dependencies=[Depends(require("admin"))],
)
def list_users() -> list[UserInfo]:
    """Return every user, oldest first, without credential material."""
    database = _db_for_read()
    try:
        return [UserInfo(**row) for row in database.list_users()]
    except (SQLAlchemyError, OSError) as exc:
        logger_db.warning("database unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="user store is unavailable") from exc


@app.patch(
    "/users/{user_id}",
    tags=["users"],
    summary="Activate or deactivate a user",
    description=(
        "Deactivating a user revokes access immediately: their key still hashes to the "
        "same row, but Database.authenticate refuses an inactive user, so every guarded "
        "route answers 401. Admin only when API_AUTH_ENABLED is true."
    ),
    response_model=UserStatusUpdate,
    responses={
        404: {"description": "No user with that id"},
        **_UNAUTHORIZED,
        **_UNAVAILABLE,
    },
    dependencies=[Depends(require("admin"))],
)
def update_user(
    payload: Annotated[
        UserPatchRequest,
        Body(description="The change to apply to this user."),
    ],
    user_id: int = ApiPath(ge=1, description="The users.id to change.", examples=[2]),
) -> UserStatusUpdate:
    """Set ``is_active`` on one user."""
    active = payload.is_active
    database = _db_for_read()
    try:
        changed = database.set_user_active(user_id, active)
    except (SQLAlchemyError, OSError) as exc:
        logger_db.warning("database unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="user store is unavailable") from exc
    if not changed:
        raise HTTPException(status_code=404, detail=f"no user with id {user_id}")
    return UserStatusUpdate(user_id=user_id, is_active=active)
