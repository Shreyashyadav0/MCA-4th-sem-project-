"""The one place that decides which provider reviews a diff.

Three providers exist, and exactly one of them runs per review:

``sarvam``
    Sarvam's OpenAI-compatible endpoint (``https://api.sarvam.ai/v1``). Chosen
    when ``SARVAM_API_KEY`` is set.
``local``
    Any self-hosted OpenAI-compatible endpoint — LM Studio by default
    (``http://localhost:1234/v1``). Chosen when ``LMSTUDIO_BASE_URL`` is set.
``mock``
    The deterministic local rule engine. The last resort, and the only provider
    that needs no configuration at all.

Precedence, locked by the Phase 5.5 contract: ``sarvam`` > ``local`` > ``mock``.
**Sarvam wins when both keys are set**, because it is the only provider that can
be reached from a machine that has no GPU and no LM Studio running; a developer
who sets both wants the hosted model unless they say otherwise. Say otherwise
with ``--provider local`` (CLI) or ``provider=local`` (API).

This module owns no transport. Both live providers go through the single
:mod:`app.openai_compat_provider` adapter. Its degraded path calls
:func:`app.mock_provider.offline_diff_findings` directly rather than delegating to
:func:`app.sarvam_provider.review_with_fallback`, so the codebase still holds exactly
one mock implementation while logging exactly one WARNING per degraded run (see
``docs/decisions/0004``).

Selection never raises for a *configuration* reason: a missing variable
degrades to ``mock`` with a one-line reason that names the variable, so a demo
cannot die on stage. Only an unknown provider *name* is a programming error and
raises :class:`ValueError`.

Note on ``REVIEW_MODE``: the Phase 4 setting is still honoured by
:func:`select_provider` for the ``auto`` case (``REVIEW_MODE=mock`` forces the
rule engine), but an explicit provider request — ``--provider`` or the API's
``provider`` field — wins over it. The Phase 5.5 precedence above applies
whenever ``REVIEW_MODE`` is left at its default.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.config import Settings
from app.models import Severity
from app.openai_compat_provider import (
    PROVIDER_LOCAL,
    PROVIDER_SARVAM,
    OpenAICompatConfig,
    ProviderOutcome,
    review_with_fallback,
)
from app.parser import DiffBundle
from app.rules import RuleCategory

__all__ = [
    "PROVIDERS",
    "ProviderSelection",
    "config_for_sarvam",
    "config_for_local",
    "select_provider",
    "review",
]

PROVIDERS: tuple[str, ...] = ("sarvam", "local", "mock")
"""Every provider name, in precedence order. ``auto`` is a request, not a provider."""

PROVIDER_MOCK: str = "mock"
"""Label for the deterministic local rule engine, i.e. a degraded run."""

REQUEST_AUTO: str = "auto"
"""The default request: let the environment decide, using the locked precedence."""

_SARVAM_BASE_URL = "https://api.sarvam.ai/v1"
"""Sarvam's OpenAI-compatible root; the adapter is protocol-only, so it is data."""

_MOCK_MODEL = "local-rules"
"""The model id reported for a mock outcome, matching the adapter's label."""


@dataclass(frozen=True)
class ProviderSelection:
    """One routing decision, with the config it needs and the reason it was made.

    Attributes:
        provider: Exactly one of ``"sarvam"``, ``"local"``, ``"mock"``.
        config: The endpoint config to run, or ``None`` for ``mock``.
        reason: One line, user-facing, explaining the decision — and, when a
            requested provider was unavailable, naming the variable that is
            missing.
    """

    provider: str
    config: OpenAICompatConfig | None
    reason: str


def _non_blank(value: str | None) -> bool:
    """Report whether a setting holds something other than whitespace.

    Args:
        value: A raw setting value, which may be ``None``.

    Returns:
        ``True`` only for a non-empty, non-blank string. An empty environment
        variable therefore counts as unset, exactly as
        :attr:`app.config.Settings.has_sarvam_key` treats it.
    """
    return bool(value and value.strip())


def config_for_sarvam(settings: Settings) -> OpenAICompatConfig | None:
    """Build the Sarvam endpoint config, or ``None`` when it cannot be used.

    Args:
        settings: Application settings.

    Returns:
        An :class:`OpenAICompatConfig` labelled ``"sarvam"`` when
        ``SARVAM_API_KEY`` is non-blank, otherwise ``None``. The timeout is the
        shared ``REQUEST_TIMEOUT_S``, because Sarvam is a hosted endpoint.
    """
    if not _non_blank(settings.sarvam_api_key):
        return None
    return OpenAICompatConfig(
        base_url=_SARVAM_BASE_URL,
        api_key=(settings.sarvam_api_key or "").strip(),
        model=settings.sarvam_model,
        provider_name=PROVIDER_SARVAM,
        timeout=settings.request_timeout_s,
    )


def config_for_local(settings: Settings) -> OpenAICompatConfig | None:
    """Build the LM Studio (self-hosted) endpoint config, or ``None``.

    Args:
        settings: Application settings.

    Returns:
        An :class:`OpenAICompatConfig` labelled ``"local"`` when both
        ``LMSTUDIO_BASE_URL`` and ``LMSTUDIO_API_KEY`` are non-blank, otherwise
        ``None``. The API key defaults to ``"lm-studio"`` because LM Studio
        ignores it but the OpenAI SDK insists on one; the timeout is the longer
        ``LMSTUDIO_TIMEOUT`` because a local model on a laptop is slow.
    """
    if not _non_blank(settings.lmstudio_base_url) or not _non_blank(settings.lmstudio_api_key):
        return None
    return OpenAICompatConfig(
        base_url=(settings.lmstudio_base_url or "").strip(),
        api_key=settings.lmstudio_api_key,
        model=settings.lmstudio_model,
        provider_name=PROVIDER_LOCAL,
        timeout=settings.lmstudio_timeout,
    )


def _local_missing(settings: Settings) -> str:
    """Name the variable that stops the local provider from being usable.

    Args:
        settings: Application settings.

    Returns:
        ``"LMSTUDIO_BASE_URL"`` or ``"LMSTUDIO_API_KEY"`` — whichever is blank,
        the base URL first because it is the one a user has to supply.
    """
    if not _non_blank(settings.lmstudio_base_url):
        return "LMSTUDIO_BASE_URL"
    return "LMSTUDIO_API_KEY"


def _mock_selection(reason: str) -> ProviderSelection:
    """Build the degraded selection.

    Args:
        reason: One line explaining why the rule engine is running.

    Returns:
        A :class:`ProviderSelection` for ``mock`` with no config.
    """
    return ProviderSelection(provider=PROVIDER_MOCK, config=None, reason=reason)


def _live_selection(provider: str, config: OpenAICompatConfig, reason: str) -> ProviderSelection:
    """Build a selection for one configured live provider.

    Args:
        provider: ``"sarvam"`` or ``"local"``.
        config: The endpoint config that will run.
        reason: One line explaining the decision.

    Returns:
        A :class:`ProviderSelection` carrying ``config``.
    """
    return ProviderSelection(provider=provider, config=config, reason=reason)


def select_provider(settings: Settings, *, requested: str = "auto") -> ProviderSelection:
    """Decide which provider reviews this run.

    Precedence for ``requested="auto"`` (locked): ``sarvam`` when
    ``SARVAM_API_KEY`` is set, else ``local`` when ``LMSTUDIO_BASE_URL`` is set,
    else ``mock``. When **both** are set, sarvam wins — the hosted model is the
    one that works on a machine with no local server running, and asking for
    ``local`` is one flag away.

    ``REVIEW_MODE=mock`` short-circuits ``auto`` to the rule engine, preserving
    the Phase 4 setting. An explicit ``requested`` value is not overridden by it:
    a flag on the command line or in a request body beats an env default.

    Args:
        settings: Application settings.
        requested: ``"auto"``, ``"local"``, ``"sarvam"`` or ``"mock"``. Case and
            surrounding whitespace are ignored.

    Returns:
        A :class:`ProviderSelection`. A requested provider whose config is
        unavailable degrades to ``mock`` with a reason naming the missing
        variable — this function never raises for a missing credential.

    Raises:
        ValueError: ``requested`` is not one of the four known values. That is a
            programming error, not a configuration state, so it is not hidden.
    """
    wanted = (requested or REQUEST_AUTO).strip().lower()

    if wanted == REQUEST_AUTO:
        if settings.review_mode == "mock":
            return _mock_selection("REVIEW_MODE=mock; local rule engine used")
        sarvam = config_for_sarvam(settings)
        if sarvam is not None:
            return _live_selection(
                PROVIDER_SARVAM,
                sarvam,
                "SARVAM_API_KEY is set; sarvam selected",
            )
        local = config_for_local(settings)
        if local is not None:
            return _live_selection(
                PROVIDER_LOCAL,
                local,
                "LMSTUDIO_BASE_URL is set; local endpoint selected",
            )
        return _mock_selection(
            "no SARVAM_API_KEY or LMSTUDIO_BASE_URL configured; local rule engine used"
        )

    if wanted == PROVIDER_MOCK:
        return _mock_selection("provider forced to mock")

    if wanted == PROVIDER_SARVAM:
        sarvam = config_for_sarvam(settings)
        if sarvam is not None:
            return _live_selection(
                PROVIDER_SARVAM,
                sarvam,
                "provider forced to sarvam",
            )
        return _mock_selection(
            "provider sarvam requested but SARVAM_API_KEY is not set; local rule engine used"
        )

    if wanted == PROVIDER_LOCAL:
        local = config_for_local(settings)
        if local is not None:
            return _live_selection(
                PROVIDER_LOCAL,
                local,
                "provider forced to local",
            )
        return _mock_selection(
            f"provider local requested but {_local_missing(settings)} is not set; "
            "local rule engine used"
        )

    raise ValueError(
        f"unknown provider {requested!r}; expected one of "
        f"{REQUEST_AUTO}, {', '.join(PROVIDERS)}"
    )


def _mock_outcome(
    bundle: DiffBundle,
    reason: str,
    *,
    min_severity: Severity | None,
    categories: Iterable[RuleCategory] | None,
) -> ProviderOutcome:
    """Produce the honest mock outcome, relabelled with this run's reason.

    The findings come from :func:`app.openai_compat_provider.review_with_fallback`
    with ``config=None``, so the repo keeps one mock implementation and logs one
    WARNING. Only the ``reason`` is replaced: the adapter can only describe *its*
    decision ("no provider selected"), while the caller knows the more useful
    fact ("provider forced to mock", "offline mode requested").

    Args:
        bundle: Parsed diff.
        reason: One-line, user-facing explanation for this run.
        min_severity: Drop findings below this severity when set.
        categories: Restrict the rule engine to these categories when set.

    Returns:
        A :class:`ProviderOutcome` with ``mode="mock"``, ``provider="mock"``,
        ``model="local-rules"`` and ``reason`` set to ``reason``.
    """
    outcome = review_with_fallback(
        bundle,
        None,
        min_severity=min_severity,
        categories=categories,
    )
    if reason and reason != outcome.reason:
        return outcome.model_copy(update={"reason": reason})
    return outcome


def review(
    bundle: DiffBundle,
    settings: Settings,
    *,
    provider: str = REQUEST_AUTO,
    force_offline: bool = False,
    min_severity: Severity | None = None,
    categories: Iterable[RuleCategory] | None = None,
) -> ProviderOutcome:
    """Review a diff with the selected provider. The single entry point.

    The CLI and every API surface call this and nothing else, so the provider
    decision, the honest labels and the single degraded-run WARNING all live in
    one place.

    Args:
        bundle: Parsed diff to review.
        settings: Application settings.
        provider: ``"auto"`` (default), ``"local"``, ``"sarvam"`` or ``"mock"``.
        force_offline: The ``--offline`` flag. Wins over ``provider``: no network
            call is attempted and the rule engine runs.
        min_severity: Drop findings below this severity when set.
        categories: Restrict the mock path to these rule categories when set.

    Returns:
        A :class:`ProviderOutcome` whose ``mode``/``provider``/``model`` describe
        what actually ran: ``live`` with ``provider=config.provider_name`` and
        ``model=config.model`` on a successful live review, or ``mock`` with
        ``provider="mock"`` and ``model="local-rules"`` when degraded.

    Raises:
        Nothing for a configuration or provider failure: a missing variable, a
        missing SDK, a connection error, a timeout and a rejected key all
        degrade to ``mock``. An unknown provider *name* is also degraded here
        rather than raised, because a bad query parameter must not 500 a
        request; the CLI rejects it earlier, as a usage error, via ``argparse``.
    """
    try:
        selection = select_provider(settings, requested=provider)
    except ValueError:
        # Defensive: only reachable if a caller bypasses the CLI/API validation.
        # A request must still get a review, so fall back to the rule engine.
        selection = _mock_selection(
            f"unknown provider {provider!r}; local rule engine used"
        )

    if force_offline:
        return _mock_outcome(
            bundle,
            "offline mode requested; local rule engine used",
            min_severity=min_severity,
            categories=categories,
        )

    if selection.provider == PROVIDER_MOCK or selection.config is None:
        return _mock_outcome(
            bundle,
            selection.reason,
            min_severity=min_severity,
            categories=categories,
        )

    return review_with_fallback(
        bundle,
        selection.config,
        min_severity=min_severity,
        categories=categories,
    )
