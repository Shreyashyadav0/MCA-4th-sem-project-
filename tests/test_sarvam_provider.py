"""Tests for the Phase 4 Sarvam review layer (``app.sarvam_provider``).

Fake-client strategy
--------------------
No test here touches the network or the real ``sarvamai`` SDK transport. The
module deliberately exposes two seams and these tests patch exactly those:

* ``app.sarvam_provider._build_client`` — patched to return a small
  :class:`FakeSarvamClient` (or to record that it was called at all) when the
  test wants the *real* ``_call_model`` exercised;
* ``app.sarvam_provider._call_model`` — patched to return canned model text or
  to raise a specific exception when the test is about a failure mode.

The SDK's own exception classes (``UnauthorizedError``, ``ForbiddenError``,
``BadGatewayError``, ``ApiError``) are constructed directly and raised from the
seam, so the provider's ``except`` clauses are tested against the real types
without any HTTP happening. Diffs are built in memory with
``app.parser.parse_diff`` — no fixture files, no ``sleep``, no I/O.

Two behaviours are pinned to what the module actually does rather than to what
the prose might suggest, and are called out at their tests: a model that
answers ``[]`` (or whose every finding is dropped by the hallucination/line
guards) is a *successful* live review with zero findings, not a failure.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

import httpx
import pytest
from pydantic import ValidationError
from sarvamai import BadGatewayError, ForbiddenError, UnauthorizedError
from sarvamai.core.api_error import ApiError

from app import sarvam_provider as sp
from app.config import Settings
from app.models import Finding, Severity
from app.parser import DiffBundle, parse_diff
from app.rules import RuleCategory, review_diff

TEST_KEY = "sk-test-0000-not-a-real-key"
MODEL_ID = "sarvam-m"

# A two-file diff. app/db.py carries five added lines (2-6) plus one removed
# line whose text must never reach the prompt; app/safe.py carries one added
# line (2) and triggers no rule.
DIFF = """diff --git a/app/db.py b/app/db.py
--- a/app/db.py
+++ b/app/db.py
@@ -1,3 +1,7 @@
 import sqlite3
+API_KEY = "sk-live-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
+def get(uid):
+    return sqlite3.connect("x").execute("SELECT * FROM u WHERE id=" + uid)
+import random
+token = random.random()
-SECRET_REMOVED_MARKER = "gone"
 keep = 2
diff --git a/app/safe.py b/app/safe.py
--- a/app/safe.py
+++ b/app/safe.py
@@ -1,2 +1,3 @@
 x = 1
+y = 2
 z = 3
"""

DB = "app/db.py"
SAFE = "app/safe.py"

# Severities below/at the ladder, used for the min_severity tests.
MIXED_PAYLOAD = (
    '[{"file": "app/db.py", "line": "3", "severity": "LOW", '
    '"issue": "minor naming", "suggested_fix": "rename it"},'
    ' {"file": "app/db.py", "line": "4", "severity": "CRITICAL", '
    '"issue": "SQL injection", "suggested_fix": "parameterise the query"}]'
)

CONTRACT_FIELDS = {"file", "line", "severity", "issue", "suggested_fix"}


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #


class FakeMessage:
    """Stand-in for ``response.choices[0].message``."""

    def __init__(self, content: str | None) -> None:
        self.content = content


class FakeChoice:
    """Stand-in for one element of ``response.choices``."""

    def __init__(self, content: str | None) -> None:
        self.message = FakeMessage(content)


class FakeResponse:
    """Stand-in for the SDK completion response."""

    def __init__(self, content: str | None) -> None:
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    """Callable that mimics ``client.chat.completions(...)``.

    Records the keyword arguments of every call so tests can assert what the
    provider actually sent, and either returns canned text or raises a prepared
    exception.
    """

    def __init__(self, reply: str | None = None, error: BaseException | None = None) -> None:
        self.reply = reply
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> FakeResponse:
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self.error is not None:
            raise self.error
        return FakeResponse(self.reply)


class FakeChat:
    """Stand-in for ``client.chat``."""

    def __init__(self, completions: FakeCompletions) -> None:
        self.completions = completions


class FakeSarvamClient:
    """Minimal object with the surface ``_call_model`` uses."""

    def __init__(self, reply: str | None = None, error: BaseException | None = None) -> None:
        self.completions = FakeCompletions(reply=reply, error=error)
        self.chat = FakeChat(self.completions)


class CallRecorder:
    """Patch target standing in for ``_build_client``.

    Returns a prepared client and remembers every call, so a test can assert
    both "this client was used" and "no client was ever built".
    """

    def __init__(self, client: FakeSarvamClient | None = None) -> None:
        self.client = client
        self.calls: list[Settings] = []

    def __call__(self, settings: Settings) -> FakeSarvamClient:
        self.calls.append(settings)
        assert self.client is not None, "this test must never build a client"
        return self.client


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def make_settings(**overrides: Any) -> Settings:
    """Build Settings without reading any ``.env`` file or stray environment."""
    values: dict[str, Any] = {
        "sarvam_api_key": TEST_KEY,
        "sarvam_model": MODEL_ID,
        "review_mode": "auto",
        "request_timeout_s": 5.0,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def patch_client(monkeypatch: pytest.MonkeyPatch, client: FakeSarvamClient) -> CallRecorder:
    """Route ``_build_client`` to a fake client and return the call recorder."""
    recorder = CallRecorder(client)
    monkeypatch.setattr(sp, "_build_client", recorder)
    return recorder


def patch_model(
    monkeypatch: pytest.MonkeyPatch,
    *,
    reply: str | None = None,
    error: BaseException | None = None,
) -> None:
    """Replace ``_call_model`` with a canned reply or a prepared exception.

    ``_build_client`` is stubbed too: the failure-mode tests are about what
    happens *after* a client exists, and constructing a real ``SarvamAI``
    object would build an ``httpx`` client (and its SSL context) for nothing.
    """
    monkeypatch.setattr(sp, "_build_client", lambda settings: FakeSarvamClient())

    if error is not None:

        def boom(client: Any, prompt: str, settings: Settings) -> str:
            raise error

        monkeypatch.setattr(sp, "_call_model", boom)
        return

    def reply_with(client: Any, prompt: str, settings: Settings) -> str:
        assert reply is not None
        return reply

    monkeypatch.setattr(sp, "_call_model", reply_with)


@pytest.fixture()
def bundle() -> DiffBundle:
    """The two-file diff above, parsed."""
    return parse_diff(DIFF)


def rule_findings(
    bundle: DiffBundle, min_severity: Severity | None = None
) -> list[Finding]:
    """What the local rule engine says about the diff, for mock-path equality."""
    return review_diff(bundle, min_severity=min_severity)


# --------------------------------------------------------------------------- #
# 1. Missing or blank API key
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("key", [None, "", "   ", "\t\n"])
def test_provider_available_false_for_missing_or_blank_key(key: str | None) -> None:
    settings = make_settings(sarvam_api_key=key)
    assert settings.has_sarvam_key is False
    assert sp.provider_available(settings) is False


def test_provider_available_true_when_key_and_sdk_present() -> None:
    assert sp.provider_available(make_settings()) is True


@pytest.mark.parametrize("key", [None, "", "   "])
def test_missing_key_falls_back_to_mock_with_rule_findings(
    bundle: DiffBundle, key: str | None
) -> None:
    outcome = sp.review_with_fallback(bundle, make_settings(sarvam_api_key=key))

    assert outcome.mode == "mock"
    assert outcome.provider == "mock"
    assert outcome.model == "local-rules"
    assert outcome.reason == "no SARVAM_API_KEY configured; local rule engine used"
    assert len(outcome.findings) == 5
    assert [f.model_dump() for f in outcome.findings] == [
        f.model_dump() for f in rule_findings(bundle)
    ]
    assert outcome.latency_ms >= 0.0


def test_missing_key_never_builds_a_client(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = CallRecorder(None)
    monkeypatch.setattr(sp, "_build_client", recorder)

    outcome = sp.review_with_fallback(bundle, make_settings(sarvam_api_key=None))

    assert outcome.mode == "mock"
    assert recorder.calls == []


def test_review_diff_live_raises_for_missing_key(bundle: DiffBundle) -> None:
    with pytest.raises(sp.SarvamUnavailableError) as excinfo:
        sp.review_diff_live(bundle, make_settings(sarvam_api_key="  "))
    assert str(excinfo.value) == "no SARVAM_API_KEY configured"


# --------------------------------------------------------------------------- #
# 2. force_offline
# --------------------------------------------------------------------------- #


def test_force_offline_with_key_present_never_builds_a_client(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = CallRecorder(None)
    monkeypatch.setattr(sp, "_build_client", recorder)

    outcome = sp.review_with_fallback(bundle, make_settings(), force_offline=True)

    assert outcome.mode == "mock"
    assert outcome.provider == "mock"
    assert outcome.reason == "offline mode requested; local rule engine used"
    assert recorder.calls == []
    assert len(outcome.findings) == 5


def test_review_mode_mock_with_key_present_never_builds_a_client(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = CallRecorder(None)
    monkeypatch.setattr(sp, "_build_client", recorder)

    outcome = sp.review_with_fallback(bundle, make_settings(review_mode="mock"))

    assert outcome.mode == "mock"
    assert outcome.reason == "REVIEW_MODE=mock; local rule engine used"
    assert recorder.calls == []


# --------------------------------------------------------------------------- #
# 3. 401 / 403
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (UnauthorizedError(body={"error": "invalid key"}), 401),
        (ForbiddenError(body={"error": "no access"}), 403),
    ],
    ids=["401", "403"],
)
def test_review_diff_live_raises_sarvam_error_for_auth_failure(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch, error: ApiError, status: int
) -> None:
    patch_model(monkeypatch, error=error)
    settings = make_settings()

    with pytest.raises(sp.SarvamUnavailableError) as excinfo:
        sp.review_diff_live(bundle, settings)

    assert str(excinfo.value) == f"sarvam API error {status}"
    # The raw SDK exception is chained, never surfaced as the raised type.
    assert isinstance(excinfo.value.__cause__, ApiError)
    assert not isinstance(excinfo.value, ApiError)
    assert TEST_KEY not in str(excinfo.value)


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (UnauthorizedError(body={"error": "invalid key"}), 401),
        (ForbiddenError(body={"error": "no access"}), 403),
    ],
    ids=["401", "403"],
)
def test_auth_failure_degrades_to_mock_with_status_in_reason(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch, error: ApiError, status: int
) -> None:
    patch_model(monkeypatch, error=error)

    outcome = sp.review_with_fallback(bundle, make_settings())

    assert outcome.mode == "mock"
    assert outcome.provider == "mock"
    assert outcome.model == "local-rules"
    assert outcome.reason == f"sarvam API error {status}; local rule engine used"
    assert len(outcome.findings) == 5


# --------------------------------------------------------------------------- #
# 4. Timeouts
# --------------------------------------------------------------------------- #

TIMEOUT_ERRORS = [
    httpx.ConnectTimeout("connect timed out"),
    httpx.ReadTimeout("read timed out"),
    TimeoutError("builtin timeout"),
]


@pytest.mark.parametrize("error", TIMEOUT_ERRORS, ids=["connect", "read", "builtin"])
def test_review_diff_live_raises_sarvam_error_for_timeout(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    patch_model(monkeypatch, error=error)

    with pytest.raises(sp.SarvamUnavailableError) as excinfo:
        sp.review_diff_live(bundle, make_settings())

    message = str(excinfo.value)
    assert message.startswith("sarvam request")
    assert TEST_KEY not in message
    assert isinstance(excinfo.value.__cause__, type(error))


@pytest.mark.parametrize("error", TIMEOUT_ERRORS, ids=["connect", "read", "builtin"])
def test_timeout_degrades_to_mock(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    patch_model(monkeypatch, error=error)

    outcome = sp.review_with_fallback(bundle, make_settings())

    assert outcome.mode == "mock"
    assert outcome.reason.startswith("sarvam request")
    assert outcome.reason.endswith("; local rule engine used")
    assert len(outcome.findings) == 5


def test_builtin_timeout_reason_names_the_timeout(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_model(monkeypatch, error=TimeoutError())

    outcome = sp.review_with_fallback(bundle, make_settings())

    assert outcome.reason == "sarvam request timed out; local rule engine used"


# --------------------------------------------------------------------------- #
# 5. 5xx
# --------------------------------------------------------------------------- #

SERVER_ERRORS = [
    BadGatewayError(body={"error": "bad gateway"}),
    ApiError(status_code=500, body="internal error"),
]


@pytest.mark.parametrize("error", SERVER_ERRORS, ids=["502", "500"])
def test_server_error_degrades_to_mock(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch, error: ApiError
) -> None:
    patch_model(monkeypatch, error=error)

    outcome = sp.review_with_fallback(bundle, make_settings())

    assert outcome.mode == "mock"
    assert outcome.reason == (
        f"sarvam API error {error.status_code}; local rule engine used"
    )
    assert len(outcome.findings) == 5


@pytest.mark.parametrize("error", SERVER_ERRORS, ids=["502", "500"])
def test_server_error_raises_from_live_path(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch, error: ApiError
) -> None:
    patch_model(monkeypatch, error=error)

    with pytest.raises(sp.SarvamUnavailableError) as excinfo:
        sp.review_diff_live(bundle, make_settings())

    assert str(excinfo.value) == f"sarvam API error {error.status_code}"


# --------------------------------------------------------------------------- #
# 6. Live success path
# --------------------------------------------------------------------------- #


def test_live_success_contract(bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch) -> None:
    patch_client(monkeypatch, FakeSarvamClient(reply=MIXED_PAYLOAD))

    outcome = sp.review_with_fallback(bundle, make_settings())

    assert outcome.mode == "live"
    assert outcome.provider == "sarvam"
    assert outcome.model == MODEL_ID
    assert outcome.reason == ""
    assert outcome.latency_ms >= 0.0

    # Two findings, CRITICAL first even though the payload listed LOW first.
    assert [f.severity for f in outcome.findings] == [Severity.CRITICAL, Severity.LOW]
    assert [f.line for f in outcome.findings] == ["4", "3"]

    for finding in outcome.findings:
        assert set(finding.model_dump()) == CONTRACT_FIELDS
        assert set(type(finding).model_fields) == CONTRACT_FIELDS
        assert finding.file == DB
        assert finding.issue.endswith(" (source: sarvam)")

    assert outcome.findings[0].issue == "SQL injection (source: sarvam)"
    assert outcome.findings[1].issue == "minor naming (source: sarvam)"
    assert outcome.findings[0].suggested_fix == "parameterise the query"


def test_live_success_sends_model_and_added_lines(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = FakeSarvamClient(reply=MIXED_PAYLOAD)
    patch_client(monkeypatch, client)

    sp.review_with_fallback(bundle, make_settings())

    assert len(client.completions.calls) == 1
    call = client.completions.calls[0]
    assert call["model"] == MODEL_ID
    assert call["temperature"] == 0.0
    assert call["max_tokens"] == 2000
    assert [m["role"] for m in call["messages"]] == ["system", "user"]
    user_prompt = call["messages"][1]["content"]
    assert '2: API_KEY = "sk-live-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"' in user_prompt
    assert "### file: app/db.py" in user_prompt


def test_review_diff_live_appends_source_marker(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_client(monkeypatch, FakeSarvamClient(reply=MIXED_PAYLOAD))

    findings = sp.review_diff_live(bundle, make_settings())

    assert len(findings) == 2
    assert all(f.issue.endswith(" (source: sarvam)") for f in findings)


def test_empty_completion_from_client_is_unavailable(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_client(monkeypatch, FakeSarvamClient(reply=""))

    with pytest.raises(sp.SarvamUnavailableError) as excinfo:
        sp.review_diff_live(bundle, make_settings())

    assert str(excinfo.value) == "sarvam returned an empty completion"


# --------------------------------------------------------------------------- #
# 7. Unparseable / unusable model output
# --------------------------------------------------------------------------- #

UNPARSEABLE = [
    ("The code looks fine to me, no issues found.", "not JSON"),
    ("{not json}", "not JSON"),
    ("", "returned an empty response"),
    ("   \n\t ", "returned an empty response"),
    (
        '[{"file": "app/db.py", "line": "2", "severity": "SEVERE", '
        '"issue": "a", "suggested_fix": "b"}]',
        "matched the required schema",
    ),
    ('"just a string"', "not an array of findings"),
]


@pytest.mark.parametrize(("raw", "fragment"), UNPARSEABLE, ids=lambda v: str(v)[:24])
def test_parse_raises_for_unusable_payload(raw: str, fragment: str) -> None:
    with pytest.raises(sp.SarvamUnavailableError) as excinfo:
        sp.parse_findings_payload(raw, allowed_files={DB})

    assert fragment in str(excinfo.value)


@pytest.mark.parametrize(("raw", "fragment"), UNPARSEABLE, ids=lambda v: str(v)[:24])
def test_unusable_payload_degrades_to_mock(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch, raw: str, fragment: str
) -> None:
    patch_model(monkeypatch, reply=raw)

    outcome = sp.review_with_fallback(bundle, make_settings())

    assert outcome.mode == "mock"
    assert fragment in outcome.reason
    assert outcome.reason.endswith("; local rule engine used")
    assert len(outcome.findings) == 5


def test_empty_array_is_a_successful_live_review_with_no_findings(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pinned behaviour: ``[]`` is valid JSON meaning "nothing to report".

    ``_payload_items`` returns an empty list, ``_validate_items`` returns ``[]``
    without raising, so the live path succeeds with zero findings rather than
    degrading to mock.
    """
    patch_model(monkeypatch, reply="[]")

    assert sp.parse_findings_payload("[]", allowed_files={DB}) == []

    outcome = sp.review_with_fallback(bundle, make_settings())

    assert outcome.mode == "live"
    assert outcome.provider == "sarvam"
    assert outcome.findings == []
    assert outcome.reason == ""


# --------------------------------------------------------------------------- #
# 8. Fenced and wrapped payloads
# --------------------------------------------------------------------------- #


def test_fenced_json_payload_parses() -> None:
    raw = f"Here is the review you asked for:\n```json\n{MIXED_PAYLOAD}\n```\nThanks!"

    findings = sp.parse_findings_payload(
        raw, allowed_files={DB}, added_lines={DB: {2, 3, 4, 5, 6}}
    )

    assert [f.severity for f in findings] == [Severity.CRITICAL, Severity.LOW]
    assert [f.line for f in findings] == ["4", "3"]
    assert findings[0].issue == "SQL injection"


def test_bare_fence_without_language_tag_parses() -> None:
    raw = f"```\n{MIXED_PAYLOAD}\n```"

    findings = sp.parse_findings_payload(raw, allowed_files={DB})

    assert len(findings) == 2


def test_findings_wrapper_payload_parses() -> None:
    raw = '{"findings": ' + MIXED_PAYLOAD + ", \"summary\": \"two issues\"}"

    findings = sp.parse_findings_payload(raw, allowed_files={DB})

    assert len(findings) == 2
    assert findings[0].severity is Severity.CRITICAL


def test_single_object_payload_parses() -> None:
    raw = (
        '{"file": "app/db.py", "line": "3", "severity": "high", '
        '"issue": "public function", "suggested_fix": "annotate it"}'
    )

    findings = sp.parse_findings_payload(raw, allowed_files={DB})

    assert len(findings) == 1
    assert findings[0].line == "3"
    assert findings[0].severity is Severity.HIGH


def test_fenced_wrapped_payload_parses() -> None:
    raw = "```json\n{\"findings\": " + MIXED_PAYLOAD + "}\n```"

    findings = sp.parse_findings_payload(raw, allowed_files={DB})

    assert [f.line for f in findings] == ["4", "3"]


# --------------------------------------------------------------------------- #
# 9. Hallucination and line guards
# --------------------------------------------------------------------------- #


def test_hallucinated_file_is_dropped() -> None:
    raw = (
        '[{"file": "app/ghost.py", "line": "2", "severity": "HIGH", '
        '"issue": "invented file", "suggested_fix": "n/a"},'
        ' {"file": "app/db.py", "line": "2", "severity": "HIGH", '
        '"issue": "hardcoded key", "suggested_fix": "use env"}]'
    )

    findings = sp.parse_findings_payload(raw, allowed_files={DB, SAFE})

    assert len(findings) == 1
    assert findings[0].file == DB
    assert findings[0].issue == "hardcoded key"


def test_git_prefixed_and_quoted_paths_are_normalised() -> None:
    raw = (
        '[{"file": "b/app/db.py", "line": "2", "severity": "HIGH", '
        '"issue": "hardcoded key", "suggested_fix": "use env"}]'
    )

    findings = sp.parse_findings_payload(raw, allowed_files={DB})

    assert [f.file for f in findings] == [DB]


@pytest.mark.parametrize(
    ("reported", "expected"),
    [("999", "6"), ("1", "2"), ("1-3", "2-3"), ("lines 40 to 45", "6")],
)
def test_line_outside_added_lines_is_snapped(reported: str, expected: str) -> None:
    raw = (
        f'[{{"file": "app/db.py", "line": "{reported}", "severity": "MEDIUM", '
        '"issue": "something", "suggested_fix": "fix it"}]'
    )

    findings = sp.parse_findings_payload(
        raw, allowed_files={DB}, added_lines={DB: {2, 3, 4, 5, 6}}
    )

    assert [f.line for f in findings] == [expected]


def test_line_already_on_added_line_is_kept() -> None:
    raw = (
        '[{"file": "app/db.py", "line": "4", "severity": "HIGH", '
        '"issue": "sql concat", "suggested_fix": "parameterise"}]'
    )

    findings = sp.parse_findings_payload(
        raw, allowed_files={DB}, added_lines={DB: {2, 3, 4, 5, 6}}
    )

    assert [f.line for f in findings] == ["4"]


def test_finding_dropped_when_file_has_no_added_lines() -> None:
    """A file in the diff with no added lines has nothing to anchor to.

    Pinned behaviour: the guard drops the finding and, when it was the only
    one, the function returns an empty list rather than raising.
    """
    raw = (
        '[{"file": "app/db.py", "line": "2", "severity": "HIGH", '
        '"issue": "x", "suggested_fix": "y"}]'
    )

    findings = sp.parse_findings_payload(raw, allowed_files={DB}, added_lines={DB: set()})

    assert findings == []


def test_unusable_line_is_dropped() -> None:
    raw = (
        '[{"file": "app/db.py", "line": "somewhere", "severity": "HIGH", '
        '"issue": "x", "suggested_fix": "y"},'
        ' {"file": "app/db.py", "line": "3", "severity": "LOW", '
        '"issue": "kept", "suggested_fix": "y"}]'
    )

    findings = sp.parse_findings_payload(raw, allowed_files={DB})

    assert [f.line for f in findings] == ["3"]


def test_live_path_applies_both_guards(bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch) -> None:
    raw = (
        '[{"file": "app/ghost.py", "line": "1", "severity": "CRITICAL", '
        '"issue": "ghost", "suggested_fix": "n/a"},'
        ' {"file": "app/db.py", "line": "900", "severity": "HIGH", '
        '"issue": "snapped", "suggested_fix": "fix"}]'
    )
    patch_model(monkeypatch, reply=raw)

    findings = sp.review_diff_live(bundle, make_settings())

    assert len(findings) == 1
    assert findings[0].file == DB
    assert findings[0].line == "6"
    assert findings[0].issue == "snapped (source: sarvam)"


# --------------------------------------------------------------------------- #
# 10. build_prompt
# --------------------------------------------------------------------------- #


def test_build_prompt_lists_added_lines_with_numbers(bundle: DiffBundle) -> None:
    prompt = sp.build_prompt(bundle)

    assert "### file: app/db.py" in prompt
    assert "### file: app/safe.py" in prompt
    assert '2: API_KEY = "sk-live-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"' in prompt
    assert "3: def get(uid):" in prompt
    assert "6: token = random.random()" in prompt
    assert "2: y = 2" in prompt
    assert len(prompt) <= 12000


def test_build_prompt_excludes_removed_lines(bundle: DiffBundle) -> None:
    prompt = sp.build_prompt(bundle)

    assert "SECRET_REMOVED_MARKER" not in prompt
    assert "-SECRET_REMOVED_MARKER" not in prompt
    # Context lines are not listed either: only "keep = 2" would appear as "7:".
    assert "7: keep = 2" not in prompt
    assert "keep = 2" not in prompt


def test_build_prompt_respects_small_cap(bundle: DiffBundle) -> None:
    cap = 1260
    prompt = sp.build_prompt(bundle, max_chars=cap)

    assert len(prompt) <= cap
    assert "... prompt truncated at 1260 characters;" in prompt
    assert "app/safe.py" not in prompt
    assert prompt.startswith('You are reviewing the added lines of a pull request.')


def test_build_prompt_cap_below_header_returns_header_prefix(bundle: DiffBundle) -> None:
    prompt = sp.build_prompt(bundle, max_chars=400)

    assert len(prompt) == 400
    assert "API_KEY" not in prompt
    assert prompt == sp._PROMPT_HEADER[:400]


@pytest.mark.parametrize("cap", [0, -1])
def test_build_prompt_zero_or_negative_cap_is_empty(bundle: DiffBundle, cap: int) -> None:
    assert sp.build_prompt(bundle, max_chars=cap) == ""


# --------------------------------------------------------------------------- #
# 11. SDK absent
# --------------------------------------------------------------------------- #


def test_sdk_absent_disables_provider(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "sarvamai", None)
    settings = make_settings()

    assert sp.provider_available(settings) is False

    outcome = sp.review_with_fallback(bundle, settings)

    assert outcome.mode == "mock"
    assert outcome.provider == "mock"
    assert outcome.reason == "the sarvamai SDK is not installed; local rule engine used"
    assert len(outcome.findings) == 5


def test_sdk_absent_raises_from_live_path(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "sarvamai", None)

    with pytest.raises(sp.SarvamUnavailableError) as excinfo:
        sp.review_diff_live(bundle, make_settings())

    assert "the sarvamai SDK is not installed" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# 12. min_severity on both paths
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("floor", "expected"),
    [
        (None, ["CRITICAL", "CRITICAL", "HIGH", "MEDIUM", "MEDIUM"]),
        (Severity.HIGH, ["CRITICAL", "CRITICAL", "HIGH"]),
        (Severity.CRITICAL, ["CRITICAL", "CRITICAL"]),
    ],
    ids=["none", "high", "critical"],
)
def test_min_severity_filters_mock_path(
    bundle: DiffBundle, floor: Severity | None, expected: list[str]
) -> None:
    outcome = sp.review_with_fallback(
        bundle, make_settings(sarvam_api_key=None), min_severity=floor
    )

    assert outcome.mode == "mock"
    assert [f.severity.value for f in outcome.findings] == expected


@pytest.mark.parametrize(
    ("floor", "expected"),
    [(None, ["CRITICAL", "LOW"]), (Severity.HIGH, ["CRITICAL"]), (Severity.LOW, ["CRITICAL", "LOW"])],
    ids=["none", "high", "low"],
)
def test_min_severity_filters_live_path(
    bundle: DiffBundle,
    monkeypatch: pytest.MonkeyPatch,
    floor: Severity | None,
    expected: list[str],
) -> None:
    patch_model(monkeypatch, reply=MIXED_PAYLOAD)

    outcome = sp.review_with_fallback(bundle, make_settings(), min_severity=floor)

    assert outcome.mode == "live"
    assert [f.severity.value for f in outcome.findings] == expected


def test_categories_filter_applies_to_mock_path_only(bundle: DiffBundle) -> None:
    outcome = sp.review_with_fallback(
        bundle,
        make_settings(sarvam_api_key=None),
        categories=[RuleCategory.SECRETS],
    )

    assert outcome.mode == "mock"
    # Only the two SECRETS-category findings survive: the literal credential
    # (CRITICAL) and the high-entropy string (MEDIUM).
    assert len(outcome.findings) == 2
    assert {f.severity.value for f in outcome.findings} == {"CRITICAL", "MEDIUM"}
    assert all(f.file == DB and f.line == "2" for f in outcome.findings)


# --------------------------------------------------------------------------- #
# 13. Determinism and ProviderOutcome validation
# --------------------------------------------------------------------------- #


def test_two_live_runs_are_identical(bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch) -> None:
    patch_model(monkeypatch, reply=MIXED_PAYLOAD)
    settings = make_settings()

    first = sp.review_with_fallback(bundle, settings)
    second = sp.review_with_fallback(bundle, settings)

    assert [f.model_dump() for f in first.findings] == [
        f.model_dump() for f in second.findings
    ]
    assert first.mode == second.mode == "live"


def test_two_mock_runs_are_identical(bundle: DiffBundle) -> None:
    settings = make_settings(sarvam_api_key=None)

    first = sp.review_with_fallback(bundle, settings)
    second = sp.review_with_fallback(bundle, settings)

    assert [f.model_dump() for f in first.findings] == [
        f.model_dump() for f in second.findings
    ]
    assert first.reason == second.reason


def test_provider_outcome_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError) as excinfo:
        sp.ProviderOutcome(
            mode="mock",
            provider="mock",
            model="local-rules",
            findings=[],
            api_key=TEST_KEY,  # type: ignore[call-arg]
        )

    assert "api_key" in str(excinfo.value)
    assert "extra_forbidden" in str(excinfo.value)


def test_provider_outcome_rejects_invalid_mode() -> None:
    with pytest.raises(ValidationError) as excinfo:
        sp.ProviderOutcome(
            mode="offline",  # type: ignore[arg-type]
            provider="mock",
            model="local-rules",
            findings=[],
        )

    assert "offline" in str(excinfo.value)


def test_provider_outcome_defaults() -> None:
    outcome = sp.ProviderOutcome(
        mode="mock", provider="mock", model="local-rules", findings=[]
    )

    assert outcome.reason == ""
    assert outcome.latency_ms == 0.0


def test_llm_finding_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError) as excinfo:
        sp.LLMFinding(
            file=DB,
            line="2",
            severity="HIGH",
            issue="x",
            suggested_fix="y",
            confidence=0.9,  # type: ignore[call-arg]
        )

    assert "confidence" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# 14. Credential hygiene
# --------------------------------------------------------------------------- #


def test_api_key_never_appears_in_outcome_reason_or_logs(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="reviewer.sarvam")
    monkeypatch.setattr(sp, "_build_client", lambda settings: FakeSarvamClient())
    monkeypatch.setattr(sp, "_call_model", _raise_with_key)
    settings = make_settings()

    outcome = sp.review_with_fallback(bundle, settings)

    serialised = outcome.model_dump_json()
    assert TEST_KEY not in serialised
    assert TEST_KEY not in outcome.reason
    assert TEST_KEY not in outcome.model
    assert TEST_KEY not in str(outcome.findings)
    assert "***" in outcome.reason
    assert outcome.mode == "mock"
    assert len(caplog.records) >= 1
    assert all(TEST_KEY not in record.getMessage() for record in caplog.records)
    assert any("reviewer.sarvam" == record.name for record in caplog.records)


def _raise_with_key(client: Any, prompt: str, settings: Settings) -> str:
    """Raise an unavailable error that (wrongly) carries the API key."""
    raise sp.SarvamUnavailableError(f"upstream rejected the key {TEST_KEY}")


def test_api_key_never_appears_in_live_findings(
    bundle: DiffBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_client(monkeypatch, FakeSarvamClient(reply=MIXED_PAYLOAD))

    outcome = sp.review_with_fallback(bundle, make_settings())

    assert outcome.mode == "live"
    assert TEST_KEY not in outcome.model_dump_json()


def test_missing_key_reason_does_not_echo_a_blank_key(bundle: DiffBundle) -> None:
    outcome = sp.review_with_fallback(bundle, make_settings(sarvam_api_key="   "))

    assert outcome.reason == "no SARVAM_API_KEY configured; local rule engine used"


# --------------------------------------------------------------------------- #
# Extra parser contract: dedupe and cap
# --------------------------------------------------------------------------- #


def test_duplicate_findings_are_deduped() -> None:
    one = (
        '{"file": "app/db.py", "line": "3", "severity": "HIGH", '
        '"issue": "same", "suggested_fix": "fix"}'
    )
    raw = f"[{one}, {one}, {one}]"

    findings = sp.parse_findings_payload(raw, allowed_files={DB})

    assert len(findings) == 1


def test_findings_are_capped_at_fifty() -> None:
    items = ",".join(
        '{"file": "app/db.py", "line": "%d", "severity": "LOW", '
        '"issue": "issue %d", "suggested_fix": "fix"}' % (n, n)
        for n in range(2, 62)
    )

    findings = sp.parse_findings_payload("[" + items + "]", allowed_files={DB})

    assert len(findings) == 50


def test_partially_invalid_list_keeps_the_valid_items() -> None:
    raw = (
        '[{"file": "app/db.py", "line": "3", "severity": "HIGH", '
        '"issue": "kept", "suggested_fix": "fix"},'
        ' {"file": "app/db.py", "line": "4", "severity": "HIGH"}]'
    )

    findings = sp.parse_findings_payload(raw, allowed_files={DB})

    assert [f.issue for f in findings] == ["kept"]


def test_findings_payload_json_is_serialisable() -> None:
    findings = sp.parse_findings_payload(MIXED_PAYLOAD, allowed_files={DB})

    payload = json.loads(json.dumps([f.model_dump(mode="json") for f in findings]))

    assert payload[0]["severity"] == "CRITICAL"
    assert set(payload[0]) == CONTRACT_FIELDS
