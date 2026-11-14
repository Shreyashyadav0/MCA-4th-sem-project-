"""One OpenAI-compatible chat-completions adapter, driven by a config.

Sarvam (``https://api.sarvam.ai/v1``) and LM Studio (``http://localhost:1234/v1``)
both speak the OpenAI chat-completions protocol, so there is exactly one
transport here and no provider-specific live path: the difference between them
is an :class:`OpenAICompatConfig` and nothing else.

The Phase 4 guards are *reused*, not reimplemented. From
:mod:`app.sarvam_provider` this module imports :class:`LLMFinding`,
:class:`ProviderOutcome`, :class:`SarvamUnavailableError`,
:func:`build_prompt` and :func:`parse_findings_payload`. The degraded path calls
:func:`app.mock_provider.offline_diff_findings` (or
:func:`app.rules.review_diff` when a category filter is given) *directly* rather
than delegating to that module's ``review_with_fallback(force_offline=True)``:
the delegated call logs its own WARNING naming *sarvam*, which is untrue on a
local run, and silencing it required mutating a logger level, which is
process-global and races between concurrent webhook requests. It is still the
same one mock implementation. See ``docs/decisions/0004`` — this deviation is
deliberate and must not be "fixed" back.

The retry budget is the contract's: at most **two** model calls per review. The
first asks for ``response_format={"type": "json_object"}``; a repair retry —
only for a rejection the endpoint could plausibly recover from, or for a
parse/validation failure — appends the one-line error to the prompt and drops
``response_format``. Two failures in a row log exactly one WARNING on
``reviewer.openai_compat`` and return an empty live review; they never raise and
never switch to mock. Credential, transport, timeout, rate-limit and 5xx
failures are not repairable and raise :class:`SarvamUnavailableError`
immediately, which is what lets :func:`review_with_fallback` degrade.

The ``openai`` SDK is imported inside :func:`_build_client`, so importing this
module works on a machine without the SDK installed. The API key never appears
in a log record, an exception message, a ``ProviderOutcome.reason`` or a
finding: messages are built from exception class names, and any echoed SDK text
is scrubbed of the key before it is logged or returned.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from app.models import Finding, Severity, sort_findings
from app.parser import DiffBundle
from app.rules import RuleCategory
from app.mock_provider import offline_diff_findings as _offline_findings
from app.rules import review_diff as _rule_review
from app.sarvam_provider import (
    LLMFinding,
    ProviderOutcome,
    SarvamUnavailableError,
    build_prompt,
    parse_findings_payload,
)

__all__ = [
    "PROVIDER_NAME",
    "PROVIDER_LOCAL",
    "PROVIDER_SARVAM",
    "OpenAICompatConfig",
    "SarvamUnavailableError",
    "LLMFinding",
    "ProviderOutcome",
    "provider_available",
    "build_prompt",
    "parse_findings_payload",
    "review_diff_live",
    "review_with_fallback",
]

PROVIDER_NAME: str = "local"
"""The adapter's default label; the honest per-run label is ``config.provider_name``."""

PROVIDER_LOCAL: str = "local"
"""Label for an LM Studio (or any self-hosted) OpenAI-compatible endpoint."""

PROVIDER_SARVAM: str = "sarvam"
"""Label for Sarvam's OpenAI-compatible endpoint."""

logger = logging.getLogger("reviewer.openai_compat")


_MAX_TOKENS = 2000
_MOCK_MODEL = "local-rules"
_JSON_RESPONSE_FORMAT: dict[str, str] = {"type": "json_object"}

_SYSTEM_PROMPT = (
    "You are a senior code reviewer performing a security and correctness review "
    "of a pull request. You only see added lines."
)

#: Class names of SDK failures that a retry cannot fix. Matched on the
#: exception's MRO names so a test double can raise a lookalike without the SDK.
_UNREPAIRABLE_ERROR_NAMES: frozenset[str] = frozenset(
    {
        "AuthenticationError",
        "PermissionDeniedError",
        "APIConnectionError",
        "APITimeoutError",
        "RateLimitError",
        "InternalServerError",
    }
)

#: Class names of SDK failures that a retry plausibly can fix (the endpoint
#: rejected ``response_format``).
_REPAIRABLE_ERROR_NAMES: frozenset[str] = frozenset({"BadRequestError"})

#: Everything :func:`_call_model` is expected to raise besides the SDK tree.
_TRANSPORT_ERRORS: tuple[type[BaseException], ...] = (TimeoutError, OSError)

#: ``True`` on a first attempt, ``False`` for the single repair retry, which
#: must omit ``response_format``. Kept in a ContextVar rather than as an extra
#: parameter so the ``_call_model(client, prompt, config)`` seam keeps the exact
#: three-argument signature the contract fixes.
_JSON_MODE: ContextVar[bool] = ContextVar("openai_compat_json_mode", default=True)


@dataclass(frozen=True)
class OpenAICompatConfig:
    """Everything one OpenAI-compatible endpoint needs, and nothing else.

    Attributes:
        base_url: Endpoint root, e.g. ``http://localhost:1234/v1``.
        api_key: Bearer key for the endpoint; excluded from ``repr`` so it cannot
            reach a log line or a traceback through the config object.
        model: Model id sent with every request.
        provider_name: Honest label for this run, ``"local"`` or ``"sarvam"``;
            it is what lands in :attr:`ProviderOutcome.provider`.
        timeout: Per-request timeout in seconds, handed to the SDK.
    """

    base_url: str
    api_key: str = field(repr=False)
    model: str
    provider_name: str
    timeout: float


class _RepairableCallError(SarvamUnavailableError):
    """A model-call failure that one repair retry could plausibly fix.

    Private: it is a :class:`SarvamUnavailableError`, so every caller and test
    that catches that type still sees it. It only carries the extra fact that
    the failure came from the request itself (the endpoint rejected
    ``response_format``, or answered with nothing usable) rather than from
    credentials or transport.
    """


# --------------------------------------------------------------------------- #
# Small text helpers
# --------------------------------------------------------------------------- #


def _one_line(text: str) -> str:
    """Collapse whitespace so a reason fits on one log line.

    Args:
        text: Any message.

    Returns:
        The message with runs of whitespace replaced by single spaces.
    """
    return " ".join(text.split())


def _scrub(text: str, config: OpenAICompatConfig | None) -> str:
    """Remove the configured API key from a message if it ever leaked in.

    Args:
        text: Message about to be logged or returned to a caller.
        config: Config holding the key; ``None`` scrubs nothing.

    Returns:
        ``text`` with every occurrence of the key replaced by ``"***"``.
    """
    if config is None:
        return text
    key = (config.api_key or "").strip()
    if key and key in text:
        return text.replace(key, "***")
    return text


def _present(text: str, config: OpenAICompatConfig | None) -> str:
    """Make an echoed message safe and honestly labelled, in one line.

    The reused Phase 4 guards word their errors for Sarvam (``"sarvam response
    was not JSON"``). A local run must never say *sarvam*, so the word is
    relabelled to this run's provider; the API key is scrubbed as well.

    Args:
        text: Message about to be logged or returned to a caller.
        config: Config holding the honest label and the key; ``None`` relabels
            nothing and scrubs nothing.

    Returns:
        ``text`` with the key removed and the provider word corrected, collapsed
        onto one line.
    """
    text = _scrub(text, config)
    label = _label(config)
    if label != PROVIDER_SARVAM:
        text = text.replace("sarvam", label).replace("Sarvam", label.capitalize())
    return _one_line(text)


def _label(config: OpenAICompatConfig | None) -> str:
    """Return the honest provider label for messages.

    Args:
        config: The run's config; ``None`` for a missing provider.

    Returns:
        ``config.provider_name`` when it is non-blank, otherwise the module
        default ``"local"``.
    """
    if config is None:
        return PROVIDER_NAME
    name = (config.provider_name or "").strip()
    return name or PROVIDER_NAME


# --------------------------------------------------------------------------- #
# Availability
# --------------------------------------------------------------------------- #


def provider_available(config: OpenAICompatConfig | None) -> bool:
    """Report whether the live path can be attempted at all.

    Availability is deliberately config-shaped rather than Settings-shaped: the
    caller (``app.engine``) decides which endpoint the config describes.

    Args:
        config: Config to test; ``None`` means no provider was selected.

    Returns:
        ``True`` only when ``config`` is not ``None`` and both ``base_url`` and
        ``api_key`` are non-blank. The model id is not consulted. Never raises.
    """
    if config is None:
        return False
    has_url = bool((config.base_url or "").strip())
    has_key = bool((config.api_key or "").strip())
    return has_url and has_key


# --------------------------------------------------------------------------- #
# Test seams: client construction and the model call
# --------------------------------------------------------------------------- #


def _build_client(config: OpenAICompatConfig) -> Any:
    """Construct an ``openai.OpenAI`` client for this endpoint.

    The SDK is imported here, not at module import time, so this module loads
    on a machine without ``openai`` installed. ``max_retries=0`` because this
    module owns the single repair retry: an SDK retry would multiply the wait.

    Args:
        config: Endpoint, key, timeout for the client.

    Returns:
        A ready ``openai.OpenAI`` instance.

    Raises:
        SarvamUnavailableError: The key or base URL is blank, the SDK is not
            installed, or the client could not be constructed.
    """
    if not provider_available(config):
        raise SarvamUnavailableError(
            f"no {_label(config)} endpoint configured (blank base_url or api_key)"
        )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SarvamUnavailableError(
            "the openai SDK is not installed (pip install 'openai>=1.40,<4')"
        ) from exc

    try:
        return OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
            max_retries=0,
        )
    except _call_error_types() as exc:
        # Construction failures (bad argument, unusable base URL, SDK-level
        # error) are never repairable: no retry can fix a client that was never
        # built. The message names the class only, never the SDK's text.
        raise SarvamUnavailableError(
            f"could not build the {_label(config)} client ({type(exc).__name__})"
        ) from exc


def _error_names(exc: BaseException) -> frozenset[str]:
    """Return every class name in an exception's MRO.

    Args:
        exc: The exception that escaped the SDK call.

    Returns:
        The names of the exception's class and all its bases.
    """
    return frozenset(cls.__name__ for cls in type(exc).__mro__)


def _describe_call_error(exc: BaseException, config: OpenAICompatConfig) -> str:
    """Summarise a model-call failure in one line, without the key.

    Args:
        exc: The exception that escaped the SDK call.
        config: Config for the provider label and key scrubbing.

    Returns:
        A one-line description built from the exception class name and, when
        present, its HTTP status — never from its message body.
    """
    label = _label(config)
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        text = f"{label} request failed: {type(exc).__name__} ({status})"
    else:
        text = f"{label} request failed: {type(exc).__name__}"
    return _present(text, config)


def _translate_call_error(
    exc: BaseException,
    config: OpenAICompatConfig,
) -> SarvamUnavailableError:
    """Map a raw SDK/transport exception onto this module's exception tree.

    Args:
        exc: The exception that escaped the SDK call.
        config: Config for the provider label and key scrubbing.

    Returns:
        A :class:`_RepairableCallError` when one repair retry could plausibly
        fix the failure, otherwise a plain :class:`SarvamUnavailableError`.
    """
    names = _error_names(exc)
    message = _describe_call_error(exc, config)
    if isinstance(exc, (TypeError, ValueError)):
        return _RepairableCallError(
            f"{_label(config)} rejected response_format ({type(exc).__name__})"
        )
    if names & _REPAIRABLE_ERROR_NAMES:
        return _RepairableCallError(message)
    return SarvamUnavailableError(message)


def _call_error_types() -> tuple[type[BaseException], ...]:
    """Build the ``except`` tuple covering every failure a call can produce.

    Returns:
        The SDK error classes (empty when ``openai`` is not installed) plus the
        builtin transport and argument errors.
    """
    try:
        import openai
    except ImportError:
        return _TRANSPORT_ERRORS + (TypeError, ValueError)

    names = (
        "APIError",
        "APIStatusError",
        "APIConnectionError",
        "APITimeoutError",
        "AuthenticationError",
        "PermissionDeniedError",
        "RateLimitError",
        "InternalServerError",
        "BadRequestError",
    )
    classes = tuple(
        cls
        for cls in (getattr(openai, name, None) for name in names)
        if isinstance(cls, type) and issubclass(cls, BaseException)
    )
    return classes + _TRANSPORT_ERRORS + (TypeError, ValueError)


def _call_model(client: Any, prompt: str, config: OpenAICompatConfig) -> str:
    """Send one review prompt and return the model's raw text.

    The request asks for a JSON object on a first attempt and omits
    ``response_format`` during the single repair retry.

    Args:
        client: A client from :func:`_build_client`, or a test double exposing
            ``client.chat.completions.create(**kwargs)``.
        prompt: The user message, from :func:`build_prompt` or the repair text.
        config: Config supplying the model id and the provider label.

    Returns:
        The raw completion text, exactly as the model produced it.

    Raises:
        _RepairableCallError: The endpoint rejected the request
            (``BadRequestError``, a ``TypeError``/``ValueError`` for an
            unsupported argument) or answered with nothing usable — one repair
            retry is worth attempting.
        SarvamUnavailableError: Credentials, permission, connection, timeout,
            rate limit, 5xx or any other transport failure — not repairable.
    """
    kwargs: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": _MAX_TOKENS,
    }
    if _JSON_MODE.get():
        kwargs["response_format"] = dict(_JSON_RESPONSE_FORMAT)

    try:
        response = client.chat.completions.create(**kwargs)
    except _call_error_types() as exc:
        raise _translate_call_error(exc, config) from exc

    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, KeyError, TypeError) as exc:
        raise _RepairableCallError(
            f"{_label(config)} response had no choices[0].message.content"
        ) from exc

    if not isinstance(content, str) or not content.strip():
        raise _RepairableCallError(f"{_label(config)} returned an empty completion")
    return content


@contextmanager
def _without_json_mode() -> Iterator[None]:
    """Run the enclosed call with ``response_format`` omitted.

    Yields:
        ``None``; the single repair retry runs inside this block.
    """
    token = _JSON_MODE.set(False)
    try:
        yield
    finally:
        _JSON_MODE.reset(token)


# --------------------------------------------------------------------------- #
# Prompt repair text
# --------------------------------------------------------------------------- #


def _repair_prompt(prompt: str, error: str) -> str:
    """Append the previous failure and a bare-array instruction to the prompt.

    Args:
        prompt: The original user message from :func:`build_prompt`.
        error: One-line, key-scrubbed description of what went wrong.

    Returns:
        The user message for the repair retry.
    """
    return (
        f"{prompt}\n"
        f"\n---\n"
        f"Your previous answer was rejected: {error}\n"
        "Answer again with a bare JSON array and nothing else: no prose, no\n"
        "explanation, no markdown code fences, no wrapper object. Each element\n"
        'must be an object with exactly these five keys: "file", "line",\n'
        '"severity", "issue", "suggested_fix". Reply with [] if there is\n'
        "nothing to report.\n"
    )


# --------------------------------------------------------------------------- #
# Live review
# --------------------------------------------------------------------------- #


def review_diff_live(bundle: DiffBundle, config: OpenAICompatConfig) -> list[Finding]:
    """Review a diff with the configured OpenAI-compatible endpoint.

    Budget: at most two model calls. Attempt one asks for a JSON object; if the
    endpoint rejects that request or the answer does not parse, exactly one
    repair retry runs with the error appended and ``response_format`` dropped.
    If the repair also fails, one WARNING is logged and an empty list is
    returned — a live review with zero findings, never an exception and never a
    silent switch to mock.

    Args:
        bundle: Parsed diff to review.
        config: Endpoint, key, model and honest provider label.

    Returns:
        Findings from the model, guarded by :func:`parse_findings_payload`
        against hallucinated files and non-added lines, each carrying
        ``" (source: <provider_name>)"`` in its issue text.

    Raises:
        SarvamUnavailableError: The provider is not configured, the SDK is
            missing, or a non-repairable call failure occurred (credentials,
            permission, connection, timeout, rate limit, 5xx). A raw SDK
            exception never escapes this function.
    """
    if not provider_available(config):
        raise SarvamUnavailableError(
            f"no {_label(config)} endpoint configured (blank base_url or api_key)"
        )

    try:
        client = _build_client(config)
    except SarvamUnavailableError:
        raise
    except _call_error_types() as exc:
        # A replaced or wrapped client factory can still surface a raw SDK
        # error; normalise it here so no SDK exception escapes this function.
        raise SarvamUnavailableError(
            f"could not build the {_label(config)} client ({type(exc).__name__})"
        ) from exc
    prompt = build_prompt(bundle)
    allowed_files = {file.path for file in bundle.files}
    added_lines = {file.path: file.added_line_numbers for file in bundle.files}

    findings: list[Finding] | None = None
    failure = ""

    try:
        raw = _call_model(client, prompt, config)
    except _RepairableCallError as exc:
        failure = _present(str(exc), config) or "the request was rejected"
    except SarvamUnavailableError:
        raise
    else:
        try:
            findings = parse_findings_payload(
                raw,
                allowed_files=allowed_files,
                added_lines=added_lines,
            )
        except SarvamUnavailableError as exc:
            failure = _present(str(exc), config) or "the answer did not parse"

    if findings is None:
        logger.debug("%s answer needed repair: %s", _label(config), failure)
        try:
            with _without_json_mode():
                raw = _call_model(client, _repair_prompt(prompt, failure), config)
        except _RepairableCallError as exc:
            _warn_after_double_failure(_present(str(exc), config), config)
            return []
        except SarvamUnavailableError:
            raise
        try:
            findings = parse_findings_payload(
                raw,
                allowed_files=allowed_files,
                added_lines=added_lines,
            )
        except SarvamUnavailableError as exc:
            _warn_after_double_failure(_present(str(exc), config), config)
            return []

    source = _label(config)
    return [
        finding.model_copy(update={"issue": f"{finding.issue} (source: {source})"})
        for finding in findings
    ]


def _warn_after_double_failure(error: str, config: OpenAICompatConfig) -> None:
    """Log the single WARNING for a run whose repair retry also failed.

    Args:
        error: One-line, key-scrubbed reason the second attempt failed.
        config: Config for the provider label.

    Returns:
        ``None``; the caller then returns an empty live review.
    """
    logger.warning(
        "%s review failed twice; returning an empty review (%s)",
        _label(config),
        error or "the answer did not parse",
    )


# --------------------------------------------------------------------------- #
# Fallback wrapper
# --------------------------------------------------------------------------- #


def _mock_outcome(
    bundle: DiffBundle,
    reason: str,
    *,
    provider_label: str,
    min_severity: Severity | None,
    categories: Iterable[RuleCategory] | None,
    latency_ms: float,
) -> ProviderOutcome:
    """Build the degraded outcome from the one mock implementation in the repo.

    The local rule engine is invoked directly rather than through
    ``app.sarvam_provider.review_with_fallback``: that path logs its own warning
    naming *sarvam*, which would be a lie on a local run and would also mean two
    warnings for one event. Delegating through it and muting its logger is worse —
    ``setLevel`` is process-global and would race between concurrent webhook
    requests. ``offline_diff_findings`` is the same function that module calls, so
    there is still exactly one mock implementation.

    Args:
        bundle: Parsed diff.
        reason: One-line, key-scrubbed explanation of why the live path was not
            used; it becomes the outcome's ``reason``.
        provider_label: Honest label of the provider that was not used.
        min_severity: Drop findings below this severity when set.
        categories: Restrict the rule engine to these categories when set.
        latency_ms: Elapsed wall time for the attempt.

    Returns:
        A :class:`ProviderOutcome` with ``mode="mock"``, ``provider="mock"`` and
        ``model="local-rules"``, carrying this run's reason and latency.
    """
    logger.warning("%s review degraded to the local rule engine: %s", provider_label, reason)
    if categories:
        # Rule categories only exist on local findings, so a category filter has
        # to run inside the rule engine rather than over its output.
        findings = _rule_review(bundle, min_severity=min_severity, categories=categories)
    else:
        findings = _offline_findings(bundle, reason, min_severity=min_severity)
    return ProviderOutcome(
        mode="mock",
        provider="mock",
        model="local-rules",
        findings=findings,
        reason=reason,
        latency_ms=latency_ms,
    )


def review_with_fallback(
    bundle: DiffBundle,
    config: OpenAICompatConfig | None,
    *,
    min_severity: Severity | None = None,
    categories: Iterable[RuleCategory] | None = None,
) -> ProviderOutcome:
    """Review a diff, degrading to the local rule engine instead of failing.

    ``config is None`` or an unusable config short-circuits to the mock path
    with a reason naming what is missing. Otherwise the live path runs, and any
    :class:`SarvamUnavailableError` degrades to the same mock path with a reason
    naming the failure. A parse failure that survives the repair retry is *not*
    one of these: that run stays live with zero findings.

    ``min_severity`` filters both paths. ``categories`` filters the mock path
    only: live findings carry no rule id — the model does not know this
    project's rule taxonomy — so there is nothing to filter them by.

    Args:
        bundle: Parsed diff to review.
        config: Endpoint config, or ``None`` when no provider was selected.
        min_severity: Drop findings below this severity when set.
        categories: Restrict the mock path to these rule categories when set.

    Returns:
        A :class:`ProviderOutcome`; ``mode="live"`` with
        ``provider=config.provider_name`` and ``model=config.model`` on success,
        ``mode="mock"`` with ``provider="mock"`` and ``model="local-rules"`` on
        degradation. Exactly one WARNING is logged per degraded run.
    """
    started = time.perf_counter()

    def _elapsed() -> float:
        """Return the wall time since this function started, in milliseconds.

        Returns:
            Milliseconds elapsed, rounded to three decimals.
        """
        return round((time.perf_counter() - started) * 1000.0, 3)

    if config is None:
        return _mock_outcome(
            bundle,
            "no OpenAI-compatible provider selected; local rule engine used",
            provider_label=PROVIDER_NAME,
            min_severity=min_severity,
            categories=categories,
            latency_ms=_elapsed(),
        )

    if not provider_available(config):
        return _mock_outcome(
            bundle,
            f"the {_label(config)} provider needs a base_url and an api_key; "
            "local rule engine used",
            provider_label=_label(config),
            min_severity=min_severity,
            categories=categories,
            latency_ms=_elapsed(),
        )

    try:
        findings = review_diff_live(bundle, config)
    except SarvamUnavailableError as exc:
        reason = _present(str(exc), config) or f"{_label(config)} review failed"
        return _mock_outcome(
            bundle,
            f"{reason}; local rule engine used",
            provider_label=_label(config),
            min_severity=min_severity,
            categories=categories,
            latency_ms=_elapsed(),
        )

    if min_severity is not None:
        floor = min_severity.rank
        findings = [finding for finding in findings if finding.severity.rank >= floor]

    return ProviderOutcome(
        mode="live",
        provider=_label(config),
        model=config.model,
        findings=sort_findings(findings),
        reason="",
        latency_ms=_elapsed(),
    )
