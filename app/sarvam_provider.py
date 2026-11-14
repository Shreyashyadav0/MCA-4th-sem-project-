"""Sarvam LLM review layer with a guaranteed fallback to the local rule engine.

Phase 4 sits one optional network call beside the deterministic engine that
already exists. The shape of this module is the fallback contract from the
project README, made concrete:

* a missing key, a missing SDK, a 401, a timeout, a 5xx, prose instead of JSON
  and a schema violation all collapse into **one** exception type,
  :class:`SarvamUnavailableError`, so callers never meet a raw SDK error;
* :func:`review_with_fallback` never raises for those failures — it logs one
  WARNING on ``reviewer.sarvam`` and returns the rule engine's findings with
  ``mode="mock"``;
* the model's output is untrusted input. :func:`parse_findings_payload` strips
  fences, finds one balanced JSON value, validates it against a strict Pydantic
  wire model, then drops hallucinations (files that are not in the diff) and
  snaps or drops line numbers that do not land on an added line.

Nothing here imports ``sarvamai`` at module import time: the SDK is imported
inside :func:`_build_client`, so ``import app.sarvam_provider`` works on a
machine with neither the SDK nor a key installed.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Iterable, Iterator
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    TypeAdapter,
    ValidationError,
    field_validator,
)

from app.config import Settings
from app.mock_provider import offline_diff_findings
from app.models import Finding, Severity, sort_findings
from app.parser import DiffBundle, normalize_path
from app.rules import RuleCategory, review_diff

__all__ = [
    "PROVIDER_NAME",
    "SarvamUnavailableError",
    "LLMFinding",
    "ProviderOutcome",
    "provider_available",
    "build_prompt",
    "parse_findings_payload",
    "review_diff_live",
    "review_with_fallback",
]

PROVIDER_NAME: str = "sarvam"

logger = logging.getLogger("reviewer.sarvam")


class SarvamUnavailableError(RuntimeError):
    """The live Sarvam path cannot be used, for any reason.

    Every failure mode — no key, no SDK, 401/403, timeout, 5xx, unparseable
    JSON, schema violation — is normalised to this one type so the caller has a
    single ``except`` to write and never has to know the SDK's exception tree.
    """


class LLMFinding(BaseModel):
    """One review finding as the model is asked to return it.

    ``line`` is deliberately ``str | int``: models answer ``42`` and ``"42"``
    interchangeably, and both are normalised to the ``Finding`` contract later.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    file: str
    line: str | int
    severity: Severity
    issue: str
    suggested_fix: str

    @field_validator("severity", mode="before")
    @classmethod
    def _normalise_severity(cls, value: object) -> object:
        """Accept a lowercased severity, still rejecting anything off the ladder.

        Args:
            value: Raw severity from the payload.

        Returns:
            The value upper-cased when it is a string, otherwise unchanged so
            normal validation can reject it.
        """
        return value.strip().upper() if isinstance(value, str) else value


class ProviderOutcome(BaseModel):
    """The result of one review attempt, live or degraded.

    ``mode`` is always visible so a caller (CLI, API, JSON output) can never
    mistake a fallback for a live review. ``reason`` explains a degraded run in
    one line; ``latency_ms`` is wall time for the attempt.
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["live", "mock"]
    provider: str
    model: str
    findings: list[Finding]
    reason: str = ""
    latency_ms: float = 0.0


_LLM_ADAPTER: TypeAdapter[list[LLMFinding]] = TypeAdapter(list[LLMFinding])

_MAX_FINDINGS = 50
_MAX_LINE_SPAN = 500
_TRUNCATION_MARK = " ... [truncated]"
_NOTE_RESERVE = 200
_MIN_LINE_ROOM = 20

_SYSTEM_PROMPT = (
    "You are a senior code reviewer performing a security and correctness review "
    "of a pull request. You only see added lines."
)

_PROMPT_HEADER = (
    "You are reviewing the added lines of a pull request.\n"
    "Reply with a JSON array and nothing else. No prose, no explanation, no "
    "markdown code fences.\n"
    "\n"
    "Schema — one object per finding, exactly these five keys, no extras:\n"
    '[{"file": str, "line": "42" or "42-45", "severity": "LOW|MEDIUM|HIGH|CRITICAL", '
    '"issue": str, "suggested_fix": str}]\n'
    "\n"
    "Rules:\n"
    "- \"file\" must be one of the paths listed below, copied character for character.\n"
    "- \"line\" must be a line number that appears in that file's listing, or an "
    "ascending range of such numbers.\n"
    "- \"severity\" is exactly one of LOW, MEDIUM, HIGH, CRITICAL.\n"
    "- \"issue\": one sentence — what is wrong and why it bites.\n"
    "- \"suggested_fix\": concrete replacement code or the exact change to make.\n"
    "- Report only defects you can point at in the listed lines. Never invent a "
    "file, a line number or a problem that is not there.\n"
    "- If there is nothing worth reporting, reply with [].\n"
    "\n"
    "Added lines, grouped by file, as \"<line number>: <code>\":\n"
)

_FENCE_RE = re.compile(
    r"```[ \t]*(?P<lang>[A-Za-z0-9_+.-]*)[ \t]*\r?\n(?P<body>.*?)(?:```|\Z)",
    re.DOTALL,
)
_RANGE_RE = re.compile(r"(\d+)\s*(?:-|--|–|—|\.\.+|to)\s*(\d+)", re.IGNORECASE)
_NUMBER_RE = re.compile(r"\d+")


# --------------------------------------------------------------------------- #
# Availability
# --------------------------------------------------------------------------- #


def _sdk_available() -> bool:
    """Report whether ``sarvamai`` can be imported, without ever raising.

    Returns:
        ``True`` when the SDK imports cleanly, ``False`` when it is missing or
        broken.
    """
    try:
        __import__("sarvamai")
    except ImportError:
        return False
    except Exception:  # noqa: BLE001 - a broken SDK must degrade, not crash the review
        # DEBUG, not WARNING: the caller that acts on this already logs the single
        # WARNING for the degraded run. Logging here too would report one event twice.
        logger.debug("sarvamai is installed but failed to import")
        return False
    return True


def provider_available(settings: Settings) -> bool:
    """Report whether the live path can be attempted at all.

    Args:
        settings: Application settings; only ``has_sarvam_key`` is consulted.

    Returns:
        ``True`` when a non-blank key is configured *and* the ``sarvamai`` SDK
        imports. Never raises when the SDK is absent.
    """
    return bool(settings.has_sarvam_key) and _sdk_available()


def _api_error_type() -> type[BaseException] | None:
    """Return the SDK's ``ApiError`` base class, or ``None`` when unavailable.

    Imported lazily so this module never needs the SDK at import time, and so a
    test that removes the SDK from ``sys.modules`` still sees the fallback.

    Returns:
        ``sarvamai.core.api_error.ApiError`` when the SDK is importable.
    """
    try:
        from sarvamai.core.api_error import ApiError
    except ImportError:
        return None
    return ApiError


def _sdk_error_types() -> tuple[type[BaseException], ...]:
    """Build the ``except`` tuple covering every SDK-side failure we expect.

    Returns:
        A tuple usable directly in an ``except`` clause; empty when the SDK is
        not installed, which makes the clause match nothing.
    """
    error_type = _api_error_type()
    return () if error_type is None else (error_type,)


def _httpx_error_type() -> tuple[type[BaseException], ...]:
    """Return the ``httpx`` transport error class, or nothing when absent.

    ``httpx`` is a hard dependency of the API layer, but the import is guarded so
    this module still loads on a machine that has neither it nor the SDK.

    Returns:
        ``(httpx.HTTPError,)`` when importable, otherwise an empty tuple.
    """
    try:
        from httpx import HTTPError
    except ImportError:
        return ()
    return (HTTPError,)


def _call_error_types() -> tuple[type[BaseException], ...]:
    """Return every exception the model call is expected to raise.

    Returns:
        SDK API errors, ``httpx`` errors, ``TimeoutError`` and ``OSError``,
        ready to use in an ``except`` clause.
    """
    return _sdk_error_types() + _httpx_error_type() + (TimeoutError, OSError)


def _client_error_types() -> tuple[type[BaseException], ...]:
    """Return every exception client construction is expected to raise.

    Returns:
        The call-error tuple plus the argument-validation errors a misconfigured
        timeout or key can produce.
    """
    return _call_error_types() + (ValueError, TypeError)


def _describe_api_error(exc: BaseException) -> str:
    """Summarise an SDK error without its headers or body.

    Args:
        exc: An ``ApiError`` instance or subclass.

    Returns:
        A one-line description such as ``"sarvam API error 401"``. The API key
        is never part of the message.
    """
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return f"sarvam API error {status}"
    return f"sarvam API error ({type(exc).__name__})"


def _one_line(text: str) -> str:
    """Collapse whitespace so a reason fits on one log line.

    Args:
        text: Any message.

    Returns:
        The message with runs of whitespace replaced by single spaces.
    """
    return " ".join(text.split())


def _scrub(text: str, settings: Settings) -> str:
    """Remove the configured API key from a message if it ever leaked in.

    Args:
        text: Message about to be logged or returned.
        settings: Settings holding the key.

    Returns:
        ``text`` with any occurrence of the key replaced by ``"***"``.
    """
    key = (settings.sarvam_api_key or "").strip()
    if key and key in text:
        return text.replace(key, "***")
    return text


# --------------------------------------------------------------------------- #
# Test seams: client construction and the model call
# --------------------------------------------------------------------------- #


def _build_client(settings: Settings) -> Any:
    """Construct a Sarvam SDK client.

    Args:
        settings: Settings carrying the API key and the request timeout.

    Returns:
        A ``sarvamai.SarvamAI`` instance.

    Raises:
        SarvamUnavailableError: The key is blank, the SDK is not installed, or
            the client could not be constructed.
    """
    key = (settings.sarvam_api_key or "").strip()
    if not key:
        raise SarvamUnavailableError("no SARVAM_API_KEY configured")

    try:
        from sarvamai import SarvamAI
    except ImportError as exc:
        raise SarvamUnavailableError(
            "the sarvamai SDK is not installed (pip install sarvamai)"
        ) from exc

    try:
        return SarvamAI(
            api_subscription_key=key,
            timeout=settings.request_timeout_s,
        )
    except _client_error_types() as exc:
        raise SarvamUnavailableError(f"could not build the sarvam client: {exc}") from exc


def _call_model(client: Any, prompt: str, settings: Settings) -> str:
    """Send one review prompt and return the model's raw text.

    Args:
        client: A client from :func:`_build_client` (or a test double with the
            same ``client.chat.completions(...)`` surface).
        prompt: The user message built by :func:`build_prompt`.
        settings: Settings supplying the model id.

    Returns:
        The raw completion text, exactly as the model produced it.

    Raises:
        SarvamUnavailableError: The call failed (API error, timeout, transport
            error) or the response carried no text.
    """
    try:
        response = client.chat.completions(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            model=settings.sarvam_model,
            temperature=0.0,
            max_tokens=2000,
        )
    except _call_error_types() as exc:
        raise SarvamUnavailableError(_describe_call_error(exc)) from exc

    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, KeyError, TypeError) as exc:
        raise SarvamUnavailableError(
            "sarvam response had no choices[0].message.content"
        ) from exc

    if not isinstance(content, str) or not content.strip():
        raise SarvamUnavailableError("sarvam returned an empty completion")
    return content


def _describe_call_error(exc: BaseException) -> str:
    """Summarise any expected model-call failure in one line.

    Args:
        exc: An SDK API error, an ``httpx`` error, a timeout or an OS error.

    Returns:
        A one-line description; the API key is never included.
    """
    api_error = _api_error_type()
    if api_error is not None and isinstance(exc, api_error):
        return _describe_api_error(exc)
    if isinstance(exc, TimeoutError):
        return "sarvam request timed out"
    return f"sarvam request failed ({type(exc).__name__})"


# --------------------------------------------------------------------------- #
# Prompt construction
# --------------------------------------------------------------------------- #


def _added_lines_of(bundle: DiffBundle) -> Iterator[tuple[str, list[tuple[int, str]]]]:
    """Yield ``(path, [(lineno, text), ...])`` for files with added lines.

    Args:
        bundle: Parsed diff.

    Yields:
        One pair per file that has at least one added line, in diff order.
    """
    for file in bundle.files:
        added = [
            (line.new_lineno, line.text)
            for hunk in file.hunks
            for line in hunk.lines
            if line.kind == "added" and line.new_lineno is not None
        ]
        if added:
            yield file.path, added


def build_prompt(bundle: DiffBundle, *, max_chars: int = 12000) -> str:
    """Render the review prompt from a diff's added lines only.

    Removed and context lines are never shown: a reviewer that cannot see what
    was deleted cannot be blamed for reviewing it, and it keeps the prompt
    small. The total is capped at ``max_chars``; when the diff does not fit, the
    listing is cut at a line boundary and the prompt says so in its own text.

    Args:
        bundle: Parsed diff to review.
        max_chars: Hard cap on the returned prompt length, in characters.

    Returns:
        The user-message text: instructions, the exact JSON schema the model
        must answer with, and the added lines grouped by file.
    """
    if max_chars <= 0:
        return ""
    if len(_PROMPT_HEADER) >= max_chars:
        return _PROMPT_HEADER[:max_chars]

    budget = max_chars - _NOTE_RESERVE
    parts: list[str] = [_PROMPT_HEADER]
    used = len(_PROMPT_HEADER)
    omitted = 0
    truncated = False

    for path, added in _added_lines_of(bundle):
        header = f"\n### file: {path}\n"
        if used + len(header) > budget:
            omitted += len(added)
            truncated = True
            break
        parts.append(header)
        used += len(header)

        for lineno, text in added:
            entry = f"{lineno}: {text}\n"
            if used + len(entry) <= budget:
                parts.append(entry)
                used += len(entry)
                continue

            prefix = f"{lineno}: "
            room = budget - used - len(prefix) - len(_TRUNCATION_MARK) - 1
            if room >= _MIN_LINE_ROOM:
                cut = f"{prefix}{text[:room]}{_TRUNCATION_MARK}\n"
                parts.append(cut)
                used += len(cut)
            truncated = True
            omitted += 1
            break

        if truncated:
            break

    if truncated:
        note = (
            f"\n... prompt truncated at {max_chars} characters; "
            f"{omitted} further added line(s) omitted.\n"
        )
        room = max_chars - used
        if room > 0:
            parts.append(note[:room])

    return "".join(parts)[:max_chars]


# --------------------------------------------------------------------------- #
# Payload parsing
# --------------------------------------------------------------------------- #


def _strip_fences(raw: str) -> str:
    """Return the first fenced block if the model wrapped its JSON in fences.

    Args:
        raw: Raw model text, possibly containing ```json ... ```.

    Returns:
        The fenced body when a fence is present and looks like JSON, otherwise
        ``raw`` unchanged.
    """
    bodies = [match.group("body") for match in _FENCE_RE.finditer(raw)]
    for body in bodies:
        stripped = body.strip()
        if stripped.startswith(("[", "{")):
            return stripped
    return raw


def _json_candidates(text: str, *, limit: int = 32) -> Iterator[str]:
    """Yield balanced JSON-looking substrings of ``text``, left to right.

    Scans for each ``[`` or ``{`` and returns the substring up to its matching
    closer, honouring string literals and escapes so a bracket inside a string
    does not end the candidate early.

    Args:
        text: Text to scan.
        limit: Maximum number of candidates to yield, to bound the work.

    Yields:
        Candidate substrings, each syntactically balanced.
    """
    emitted = 0
    for start, char in enumerate(text):
        if char not in "[{":
            continue
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            current = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    in_string = False
                continue
            if current == '"':
                in_string = True
            elif current in "[{":
                depth += 1
            elif current in "]}":
                depth -= 1
                if depth == 0:
                    yield text[start : index + 1]
                    emitted += 1
                    break
        if emitted >= limit:
            return


def _load_payload(raw: str) -> Any:
    """Turn raw model text into a parsed JSON value.

    Args:
        raw: Raw model text.

    Returns:
        The first JSON value that parses out of the text.

    Raises:
        SarvamUnavailableError: The text contains no parseable JSON.
    """
    if not raw or not raw.strip():
        raise SarvamUnavailableError("sarvam returned an empty response")

    text = _strip_fences(raw)
    for candidate in _json_candidates(text):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as exc:
        raise SarvamUnavailableError(
            f"sarvam response was not JSON ({exc.msg} at column {exc.colno})"
        ) from exc


def _payload_items(payload: Any) -> list[Any]:
    """Normalise a parsed payload into the list of candidate finding objects.

    Accepts a bare array, a single object, and the ``{"findings": [...]}``
    wrapper some models add unprompted.

    Args:
        payload: Parsed JSON value.

    Returns:
        A list of raw items to validate; empty when the model reported nothing.

    Raises:
        SarvamUnavailableError: The payload is JSON but not a findings shape.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("findings", "results", "issues"):
            wrapped = payload.get(key)
            if isinstance(wrapped, list):
                return wrapped
            if isinstance(wrapped, dict):
                return [wrapped]
        return [payload]
    raise SarvamUnavailableError(
        f"sarvam response JSON was a {type(payload).__name__}, not an array of findings"
    )


def _validate_items(items: list[Any]) -> list[LLMFinding]:
    """Validate raw items against the strict wire model.

    The whole list is validated first. When that fails, items are validated one
    at a time so a single malformed object does not discard a good review;
    every dropped item is logged at DEBUG.

    Args:
        items: Raw finding objects.

    Returns:
        The findings that satisfied :class:`LLMFinding`.

    Raises:
        SarvamUnavailableError: No item was valid.
    """
    if not items:
        return []
    try:
        return _LLM_ADAPTER.validate_python(items)
    except ValidationError as exc:
        logger.debug("sarvam payload failed whole-list validation: %s", exc)

    valid: list[LLMFinding] = []
    for item in items:
        try:
            valid.append(LLMFinding.model_validate(item))
        except ValidationError as exc:
            logger.debug("dropping invalid sarvam finding: %s", exc)
    if not valid:
        raise SarvamUnavailableError(
            f"none of the {len(items)} sarvam finding(s) matched the required schema"
        )
    return valid


def _normalise_line(raw: str | int) -> tuple[int, int] | None:
    """Turn a reported line into ``(start, end)``.

    Args:
        raw: An int, ``"42"``, ``"42-45"`` or a looser form such as
            ``"lines 42 to 45"``.

    Returns:
        ``(start, end)`` for a valid, ascending, positive range, or ``None``
        when the value cannot be read as one.
    """
    text = str(raw).strip()
    if not text:
        return None

    range_match = _RANGE_RE.search(text)
    if range_match is not None:
        start = int(range_match.group(1))
        end = int(range_match.group(2))
    else:
        number_match = _NUMBER_RE.search(text)
        if number_match is None:
            return None
        start = end = int(number_match.group(0))

    if start <= 0 or end < start:
        return None
    if end - start > _MAX_LINE_SPAN:
        end = start + _MAX_LINE_SPAN
    return start, end


def _nearest(target: int, candidates: set[int]) -> int:
    """Return the added line closest to ``target``, breaking ties downwards.

    Args:
        target: Line number the model claimed.
        candidates: Added line numbers in that file.

    Returns:
        The nearest candidate; ties go to the smaller line number so the result
        is deterministic.
    """
    return min(candidates, key=lambda number: (abs(number - target), number))


def _snap_to_added(start: int, end: int, added: set[int]) -> str | None:
    """Snap a reported range onto the file's added lines.

    Args:
        start: First reported line.
        end: Last reported line.
        added: Added line numbers in that file.

    Returns:
        ``"42"`` or ``"42-45"`` on added lines, or ``None`` when the file has no
        added lines to attach a comment to.
    """
    if not added:
        return None
    snapped_start = _nearest(start, added)
    snapped_end = _nearest(end, added)
    low, high = sorted((snapped_start, snapped_end))
    return str(low) if low == high else f"{low}-{high}"


def parse_findings_payload(
    raw: str,
    *,
    allowed_files: set[str] | None = None,
    added_lines: dict[str, set[int]] | None = None,
) -> list[Finding]:
    """Parse model text into findings, dropping everything it cannot vouch for.

    Defensive and deterministic, in this order: strip markdown fences, find the
    first balanced JSON array or object, validate against :class:`LLMFinding`
    (a bare object and ``{"findings": [...]}`` are accepted too), then apply the
    guards —

    * **hallucination guard** — a finding for a file that is not in
      ``allowed_files`` is dropped;
    * **line guard** — when ``added_lines`` is given, a reported line is snapped
      to the nearest added line in that file, and the finding is dropped when
      that file has no added lines at all;
    * non-ascending or non-numeric line ranges are rejected;
    * findings are deduplicated by ``(file, line, issue)`` and capped at 50.

    Args:
        raw: Raw model text.
        allowed_files: Paths present in the diff; ``None`` disables the guard.
        added_lines: Added line numbers per path; ``None`` disables snapping.

    Returns:
        Findings in severity order (CRITICAL first), each with the five
        contract fields and no others.

    Raises:
        SarvamUnavailableError: The payload is empty, contains no JSON, has the
            wrong shape, or contains no object that satisfies the schema.

    Note:
        A guard that drops every candidate (all files hallucinated, every line
        unusable) returns an empty list rather than raising: an empty review is a
        legitimate live answer, and calling it a failure would push a clean PR
        into the degraded path.
    """
    payload = _load_payload(raw)
    items = _payload_items(payload)
    candidates = _validate_items(items)

    allowed = (
        {normalize_path(path) for path in allowed_files} if allowed_files is not None else None
    )

    findings: list[Finding] = []
    seen: set[tuple[str, str, str]] = set()

    for candidate in candidates:
        path = normalize_path(candidate.file)
        if not path:
            continue
        if allowed is not None and path not in allowed:
            logger.debug("dropping hallucinated finding for %r (not in the diff)", candidate.file)
            continue

        line_range = _normalise_line(candidate.line)
        if line_range is None:
            logger.debug("dropping finding with unusable line %r", candidate.line)
            continue
        start, end = line_range

        if added_lines is not None:
            file_added = added_lines.get(path)
            snapped = _snap_to_added(start, end, file_added or set())
            if snapped is None:
                logger.debug("dropping finding for %r: no added lines to anchor to", path)
                continue
            line = snapped
        else:
            line = str(start) if start == end else f"{start}-{end}"

        issue = candidate.issue.strip()
        suggested_fix = candidate.suggested_fix.strip()
        if not issue or not suggested_fix:
            logger.debug("dropping finding for %r line %s: empty issue or fix", path, line)
            continue

        key = (path, line, issue)
        if key in seen:
            continue
        seen.add(key)

        try:
            findings.append(
                Finding(
                    file=path,
                    line=line,
                    severity=candidate.severity,
                    issue=issue,
                    suggested_fix=suggested_fix,
                )
            )
        except ValidationError as exc:
            logger.debug("dropping finding that failed the contract: %s", exc)

    return sort_findings(findings)[:_MAX_FINDINGS]


# --------------------------------------------------------------------------- #
# Live review
# --------------------------------------------------------------------------- #


def review_diff_live(bundle: DiffBundle, settings: Settings) -> list[Finding]:
    """Review a diff with the Sarvam model.

    Args:
        bundle: Parsed diff to review.
        settings: Settings carrying the key, model id and timeout.

    Returns:
        Findings from the model, guarded against hallucinated files and lines,
        each carrying ``(source: sarvam)`` in its issue text.

    Raises:
        SarvamUnavailableError: For every failure mode — missing key, missing
            SDK, 401/403, timeout, 5xx, unparseable JSON or a schema violation.
            A raw SDK exception never escapes this function.
    """
    if not settings.has_sarvam_key:
        raise SarvamUnavailableError("no SARVAM_API_KEY configured")

    try:
        client = _build_client(settings)
        prompt = build_prompt(bundle)
        raw = _call_model(client, prompt, settings)
        findings = parse_findings_payload(
            raw,
            allowed_files={file.path for file in bundle.files},
            added_lines={file.path: file.added_line_numbers for file in bundle.files},
        )
    except SarvamUnavailableError:
        raise
    except _call_error_types() as exc:
        raise SarvamUnavailableError(_describe_call_error(exc)) from exc

    return [
        finding.model_copy(update={"issue": f"{finding.issue} (source: sarvam)"})
        for finding in findings
    ]


# --------------------------------------------------------------------------- #
# Fallback wrapper
# --------------------------------------------------------------------------- #


def _mock_outcome(
    bundle: DiffBundle,
    reason: str,
    *,
    min_severity: Severity | None,
    categories: Iterable[RuleCategory] | None,
    latency_ms: float,
) -> ProviderOutcome:
    """Build the degraded outcome from the local rule engine.

    Args:
        bundle: Parsed diff.
        reason: One-line explanation of why the live path was not used.
        min_severity: Drop findings below this severity when set.
        categories: Restrict the rule engine to these categories when set.
        latency_ms: Elapsed wall time for the attempt.

    Returns:
        A :class:`ProviderOutcome` with ``mode="mock"``.
    """
    if categories is None:
        findings = offline_diff_findings(bundle, reason, min_severity=min_severity)
    else:
        # ``offline_diff_findings`` has no category filter, so the same rule
        # engine is called directly with one. Same rules, same order.
        findings = review_diff(bundle, min_severity=min_severity, categories=categories)
    return ProviderOutcome(
        mode="mock",
        provider="mock",
        model="local-rules",
        findings=sort_findings(findings),
        reason=reason,
        latency_ms=latency_ms,
    )


def review_with_fallback(
    bundle: DiffBundle,
    settings: Settings,
    *,
    force_offline: bool = False,
    min_severity: Severity | None = None,
    categories: Iterable[RuleCategory] | None = None,
) -> ProviderOutcome:
    """Review a diff, degrading to the local rule engine instead of failing.

    ``force_offline=True``, a missing key, a missing SDK or ``REVIEW_MODE=mock``
    short-circuit to the local path without any network attempt. Otherwise the
    live path runs, and *any* failure (credential, transport, timeout, bad JSON,
    schema violation) degrades to the same local path with one WARNING logged on
    ``reviewer.sarvam``. This function never raises for those failures.

    ``min_severity`` filters both paths. ``categories`` filters the mock path
    only: live findings carry no rule id — the model does not know this
    project's rule taxonomy — so there is nothing to filter them by.

    Args:
        bundle: Parsed diff to review.
        settings: Application settings.
        force_offline: Skip the live path entirely (the ``--offline`` flag).
        min_severity: Drop findings below this severity when set.
        categories: Restrict the mock path to these rule categories when set.

    Returns:
        A :class:`ProviderOutcome`; ``mode="live"`` with ``provider="sarvam"``
        on success, ``mode="mock"`` with ``provider="mock"`` on degradation.
    """
    started = time.perf_counter()

    if force_offline:
        reason = "offline mode requested; local rule engine used"
    elif not settings.has_sarvam_key:
        reason = "no SARVAM_API_KEY configured; local rule engine used"
    elif not _sdk_available():
        reason = "the sarvamai SDK is not installed; local rule engine used"
    elif settings.resolve_mode(force_offline=False) == "mock":
        reason = "REVIEW_MODE=mock; local rule engine used"
    else:
        reason = ""

    if reason:
        logger.warning("sarvam unavailable: %s", reason)
        return _mock_outcome(
            bundle,
            reason,
            min_severity=min_severity,
            categories=categories,
            latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
        )

    try:
        findings = review_diff_live(bundle, settings)
    except SarvamUnavailableError as exc:
        reason = _one_line(_scrub(str(exc), settings)) or "sarvam review failed"
        reason = f"{reason}; local rule engine used"
        logger.warning("sarvam review failed: %s", reason)
        return _mock_outcome(
            bundle,
            reason,
            min_severity=min_severity,
            categories=categories,
            latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
        )

    if min_severity is not None:
        floor = min_severity.rank
        findings = [finding for finding in findings if finding.severity.rank >= floor]

    return ProviderOutcome(
        mode="live",
        provider=PROVIDER_NAME,
        model=settings.sarvam_model,
        findings=sort_findings(findings),
        reason="",
        latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
    )
