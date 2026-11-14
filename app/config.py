"""Configuration boundary.

Credentials are read once, here, at process start. A missing key is data — the
reviewer switches mode — never an exception. Nothing else in the codebase reads
``os.environ``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "ReviewMode"]

ReviewMode = Literal["live", "mock"]


class Settings(BaseSettings):
    """Environment-driven settings. Every field has a safe default."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    sarvam_api_key: str | None = Field(
        default=None, repr=False, description="Sarvam API key; optional."
    )
    sarvam_model: str = Field(default="sarvam-m", description="Sarvam model id.")
    github_token: str | None = Field(
        default=None, repr=False, description="GitHub token; optional."
    )
    github_max_inline: int = Field(
        default=30,
        gt=0,
        le=100,
        description="Maximum inline PR comments before overflow moves to the summary.",
    )
    webhook_allow_unsigned: bool = Field(
        default=False,
        description=(
            "Post reviews from unsigned webhook deliveries. Off by default: when a "
            "GITHUB_TOKEN is configured but no GITHUB_WEBHOOK_SECRET is, the endpoint "
            "reviews but refuses to post, because anyone who can reach it could otherwise "
            "make the bot comment on a repository of their choosing."
        ),
    )
    github_webhook_secret: str | None = Field(
        default=None,
        repr=False,
        description="HMAC secret for X-Hub-Signature-256; when unset, signatures are not checked.",
    )
    review_mode: Literal["auto", "live", "mock"] = Field(
        default="auto",
        description="auto = live when a key exists, mock otherwise; live = force live, degrade on failure.",
    )
    request_timeout_s: float = Field(default=20.0, gt=0, description="HTTP timeout, seconds.")
    lmstudio_base_url: str | None = Field(
        default=None,
        description=(
            "LM Studio (or any OpenAI-compatible) base URL, e.g. "
            "http://localhost:1234/v1; when set, the local provider is selected."
        ),
    )
    lmstudio_model: str = Field(
        default="qwen2.5-coder-7b-instruct",
        description="Model id sent to the local OpenAI-compatible endpoint.",
    )
    lmstudio_api_key: str = Field(
        default="lm-studio",
        repr=False,
        description="Bearer key for the local endpoint; LM Studio ignores it but the SDK needs one.",
    )
    lmstudio_timeout: float = Field(
        default=120.0,
        gt=0,
        description="Per-request timeout for the local endpoint, seconds; a local model is slow.",
    )
    database_path: str = Field(
        default="data/reviewer.db",
        description=(
            "SQLite file for the review, posting and user history; relative paths are "
            "resolved from the working directory. Set it to blank to switch persistence "
            "off entirely (GET /health then reports database=disabled)."
        ),
    )
    api_auth_enabled: bool = Field(
        default=False,
        description=(
            "Require an X-API-Key header on the management endpoints (GET /reviews, "
            "GET /reviews/{id}, GET /stats, and the /users routes). Off by default: the "
            "review surfaces stay open so the demo answers with zero configuration."
        ),
    )
    db_seed_admin_key: str | None = Field(
        default=None,
        repr=False,
        description=(
            "API key for the seed admin user created by Database.seed_defaults(). When "
            "unset, no user is created at all — no deployment grows a default credential."
        ),
    )

    @property
    def has_webhook_secret(self) -> bool:
        """True only for a non-blank webhook secret."""
        return bool(self.github_webhook_secret and self.github_webhook_secret.strip())

    @property
    def has_sarvam_key(self) -> bool:
        """True only for a non-blank key; an empty env var counts as missing."""
        return bool(self.sarvam_api_key and self.sarvam_api_key.strip())

    def resolve_mode(self, *, force_offline: bool = False) -> ReviewMode:
        """Pick the review mode, degrading instead of raising.

        Kept for the Phase 4 surfaces and for ``REVIEW_MODE=mock``;
        :func:`app.engine.select_provider` is what decides which provider runs.
        ``force_offline`` (the ``--offline`` flag) wins over everything.
        ``REVIEW_MODE=live`` without a key degrades to ``mock`` rather than
        failing the run — a demo must not die on stage.
        """
        if force_offline or self.review_mode == "mock":
            return "mock"
        if not self.has_sarvam_key:
            return "mock"
        return "live"
