"""Tests for the Phase 5.5 OpenAI-compatible adapter (``app.openai_compat_provider``).

Fake-client strategy
--------------------
Not one test here touches the network, localhost or the real ``openai``
transport. The adapter exposes two module-level seams and these tests patch the
first one only:

* ``app.openai_compat_provider._build_client`` is replaced by a small
  :class:`FakeClient` whose ``.chat.completions.create(**kwargs)`` records every
  keyword argument and replays a scripted list of replies (a ``str`` becomes
  ``response.choices[0].message.content``; a ``BaseException`` is raised). The
  *real* ``_call_model``, the real retry budget and the real Phase 4 guards all
  run — only the socket is gone. Every test finishes in milliseconds.

SDK exception shapes are built the way the SDK builds them
(``openai.AuthenticationError(message, response=..., body=...)``,
``openai.APIConnectionError(request=...)``) against an ``httpx.Request`` that is
never sent, so the adapter's ``except`` clauses and its MRO-name matching are
exercised against the genuine classes.

Why the last test is skipped by default
---------------------------------------
:func:`test_live_smoke_review_against_a_real_endpoint` is the one test that uses
the real client: it reviews ``samples/sample.diff`` against whatever
``LMSTUDIO_BASE_URL`` points at. CI has no LM Studio server, so the module-level
``@pytest.mark.skipif`` turns it into a skip there; a developer with a local
server opts in just by exporting the variable. It asserts only that the run
completes and returns a ``ProviderOutcome`` — the mode may legitimately be
``live`` or ``mock`` depending on the server.

Provider selection is tested through ``app.engine.select_provider`` and
``app.engine.review`` with ``monkeypatch.setenv``/``delenv`` and a real
:class:`app.config.Settings`, so the precedence under test is the shipped one.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx
import openai
import pytest

import app.openai_compat_provider as ocp
from app import engine
from app import sarvam_provider as sp
from app.config import Settings
from app.models import Finding, Severity
from app.parser import DiffBundle, parse_diff, parse_diff_file
from app.rules import RuleCategory

# A key that must never appear in a finding, a reason, a serialised outcome or a
# log record. It is distinctive enough that a substring search cannot miss it.
API_KEY = "sk-local-DO-NOT-LEAK-0123456789"

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "sample.diff"

# Captured at import time: the smoke test must see the developer's environment,
# not the emptied one an autouse fixture installs for the selection tests.
LIVE_BASE_URL = os.getenv("LMSTUDIO_BASE_URL")

# Two files. ``app/db.py`` has five added lines (2-6) and one removed line whose
# text must never reach the prompt; ``app/safe.py`` has a single added line (2).
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

#: The exact public surface frozen by PHASE55_CONTRACT.md, in contract order.
CONTRACT_ALL: list[str] = [
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

#: The five dataclass fields, in contract order.
CONTRACT_FIELDS: tuple[str, ...] = ("base_url", "api_key", "model", "provider_name", "timeout")

#: One LOW at line 3 and one CRITICAL at line 4, deliberately out of order.
MIXED_PAYLOAD = (
    '[{"file": "app/db.py", "line": "3", "severity": "LOW", '
    '"issue": "minor naming", "suggested_fix": "rename it"},'
    ' {"file": "app/db.py", "line": "4", "severity": "CRITICAL", '
    '"issue": "SQL injection", "suggested_fix": "parameterise the query"}]'
)

#: One CRITICAL finding on an added line of ``app/db.py``.
ONE_FINDING = (
    '[{"file": "app/db.py", "line": "4", "severity": "CRITICAL", '
    '"issue": "SQL injection", "suggested_fix": "parameterise the query"}]'
)

#: Prose, not JSON: the shape a model produces when it ignores the schema.
PROSE = "I had a look and honestly this code seems fine to me."

#: Every SDK failure the adapter must treat as unrepairable, with its HTTP
#: status (``None`` for the two errors that never reach a response).
UNREPAIRABLE: list[tuple[str, int | None]] = [
    ("AuthenticationError", 401),
    ("PermissionDeniedError", 403),
    ("APIConnectionError", None),
    ("APITimeoutError", None),
    ("RateLimitError", 429),
    ("InternalServerError", 500),
]


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
    """Replays scripted replies and records the kwargs of every call.

    A ``str`` reply is returned as ``response.choices[0].message.content``; a
    ``BaseException`` reply is raised. Replies are consumed in order, so a test
    can script "first attempt, then repair attempt" exactly.
    """

    def __init__(self, replies: list[str | BaseException]) -> None:
        self.replies: list[str | BaseException] = list(replies)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeResponse:
        """Record the request and answer with the next scripted reply."""
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return FakeResponse(reply)


class FakeChat:
    """Stand-in for ``client.chat``."""

    def __init__(self, completions: FakeCompletions) -> None:
        self.completions = completions


class FakeClient:
    """Stand-in for ``openai.OpenAI``: only the surface ``_call_model`` uses."""

    def __init__(self, completions: FakeCompletions) -> None:
        self.chat = FakeChat(completions)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def install_client(
    monkeypatch: pytest.MonkeyPatch,
    replies: list[str | BaseException],
) -> FakeCompletions:
    """Patch ``_build_client`` to hand out a fake client with scripted replies.

    Args:
        monkeypatch: pytest's patcher; the seam is restored after the test.
        replies: Model replies in call order.

    Returns:
        The recorder, whose ``.calls`` holds one kwargs dict per model call.
    """
    completions = FakeCompletions(replies)
    monkeypatch.setattr(ocp, "_build_client", lambda config: FakeClient(completions))
    return completions


def local_config() -> ocp.OpenAICompatConfig:
    """Return a valid LM Studio-shaped config labelled ``local``."""
    return ocp.OpenAICompatConfig(
        base_url="http://localhost:1234/v1",
        api_key=API_KEY,
        model="qwen2.5-coder-7b-instruct",
        provider_name=ocp.PROVIDER_LOCAL,
        timeout=5.0,
    )


def sarvam_config() -> ocp.OpenAICompatConfig:
    """Return a valid Sarvam-shaped config labelled ``sarvam``."""
    return ocp.OpenAICompatConfig(
        base_url="https://api.sarvam.ai/v1",
        api_key=API_KEY,
        model="sarvam-m",
        provider_name=ocp.PROVIDER_SARVAM,
        timeout=20.0,
    )


def sdk_error(name: str, status: int | None) -> BaseException:
    """Build a real ``openai`` exception, the way the SDK builds it.

    The message deliberately contains the API key so a test can prove the
    adapter never echoes SDK text verbatim.

    Args:
        name: SDK class name, e.g. ``"AuthenticationError"``.
        status: HTTP status to attach, or ``None`` for errors with no response.

    Returns:
        An instance of the requested ``openai`` error class.
    """
    request = httpx.Request("POST", "http://localhost:1234/v1/chat/completions")
    cls = getattr(openai, name)
    if status is None:
        return cls(request=request)
    return cls(
        f"the endpoint rejected the key {API_KEY}",
        response=httpx.Response(status, request=request),
        body=None,
    )


def warning_records(caplog: pytest.LogCaptureFixture, name: str) -> list[logging.LogRecord]:
    """Return the WARNING records one logger emitted during the test.

    Args:
        caplog: pytest's capture fixture.
        name: Logger name to filter on, e.g. ``"reviewer.openai_compat"``.

    Returns:
        The matching records, in emission order.
    """
    return [record for record in caplog.records if record.name == name and record.levelno == logging.WARNING]


def captured_text(caplog: pytest.LogCaptureFixture) -> str:
    """Join every captured log message into one searchable string."""
    return "\n".join(record.getMessage() for record in caplog.records)


def outcome_text(outcome: ocp.ProviderOutcome) -> str:
    """Join every user-visible surface of an outcome into one string.

    Covers the findings' prose and the whole serialised outcome, which is what
    the CLI prints and the API returns.

    Args:
        outcome: The outcome to flatten.

    Returns:
        A single string with every field that could carry leaked text.
    """
    parts = [outcome.reason, outcome.model_dump_json()]
    for finding in outcome.findings:
        parts.extend((finding.issue, finding.suggested_fix))
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def bundle() -> DiffBundle:
    """The in-memory two-file diff under review."""
    return parse_diff(DIFF)


@pytest.fixture
def cfg() -> ocp.OpenAICompatConfig:
    """A valid local config."""
    return local_config()


@pytest.fixture(autouse=True)
def clean_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every provider variable so selection tests start from nothing."""
    for name in (
        "SARVAM_API_KEY",
        "LMSTUDIO_BASE_URL",
        "LMSTUDIO_MODEL",
        "LMSTUDIO_API_KEY",
        "LMSTUDIO_TIMEOUT",
        "REVIEW_MODE",
    ):
        monkeypatch.delenv(name, raising=False)


# --------------------------------------------------------------------------- #
# A. Contract conformance
# --------------------------------------------------------------------------- #


def test_all_matches_the_frozen_contract() -> None:
    """``__all__`` is exactly the twelve names the contract freezes, in order."""
    assert ocp.__all__ == CONTRACT_ALL


def test_config_is_frozen_with_the_five_contract_fields_in_order() -> None:
    """``OpenAICompatConfig`` is frozen and has exactly five fields, in order."""
    config = local_config()

    assert [field.name for field in dataclasses.fields(ocp.OpenAICompatConfig)] == list(
        CONTRACT_FIELDS
    )
    assert config.__dataclass_params__.frozen is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.model = "something-else"  # type: ignore[misc]


def test_config_repr_hides_the_api_key() -> None:
    """The dataclass repr names the endpoint but never the credential."""
    rendered = repr(local_config())

    assert API_KEY not in rendered
    assert "base_url='http://localhost:1234/v1'" in rendered
    assert "provider_name='local'" in rendered


def test_provider_constants_match_the_contract() -> None:
    """The module default is ``local``; both honest labels are exported."""
    assert ocp.PROVIDER_NAME == "local"
    assert ocp.PROVIDER_LOCAL == "local"
    assert ocp.PROVIDER_SARVAM == "sarvam"


def test_reexported_guards_are_the_same_objects_as_in_sarvam_provider() -> None:
    """The Phase 4 guards are reused by identity — nobody forked them."""
    for name in (
        "LLMFinding",
        "ProviderOutcome",
        "SarvamUnavailableError",
        "build_prompt",
        "parse_findings_payload",
    ):
        assert getattr(ocp, name) is getattr(sp, name), name


# --------------------------------------------------------------------------- #
# B. Happy path
# --------------------------------------------------------------------------- #


def test_happy_path_makes_exactly_one_json_mode_call(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle, cfg: ocp.OpenAICompatConfig
) -> None:
    """One call, asking for a JSON object, with the system and user messages."""
    completions = install_client(monkeypatch, [MIXED_PAYLOAD])

    ocp.review_diff_live(bundle, cfg)

    assert len(completions.calls) == 1
    sent = completions.calls[0]
    assert sent["response_format"] == {"type": "json_object"}
    assert [message["role"] for message in sent["messages"]] == ["system", "user"]
    assert "app/db.py" in sent["messages"][1]["content"]
    assert "SECRET_REMOVED_MARKER" not in sent["messages"][1]["content"]


def test_happy_path_forwards_model_temperature_and_max_tokens(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle, cfg: ocp.OpenAICompatConfig
) -> None:
    """The request carries the configured model and the fixed sampling knobs."""
    completions = install_client(monkeypatch, [MIXED_PAYLOAD])

    ocp.review_diff_live(bundle, cfg)

    sent = completions.calls[0]
    assert sent["model"] == "qwen2.5-coder-7b-instruct"
    assert sent["temperature"] == 0.0
    assert sent["max_tokens"] == 2000


def test_happy_path_sorts_findings_critical_first(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle, cfg: ocp.OpenAICompatConfig
) -> None:
    """The model answered LOW first; the review still reads CRITICAL first."""
    install_client(monkeypatch, [MIXED_PAYLOAD])

    findings = ocp.review_diff_live(bundle, cfg)

    assert [finding.severity for finding in findings] == [Severity.CRITICAL, Severity.LOW]
    assert [finding.line for finding in findings] == ["4", "3"]


def test_local_config_labels_every_issue_local_and_never_sarvam(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle, cfg: ocp.OpenAICompatConfig
) -> None:
    """A local finding can never be mistaken for a Sarvam one."""
    install_client(monkeypatch, [MIXED_PAYLOAD])

    findings = ocp.review_diff_live(bundle, cfg)

    assert len(findings) == 2
    for finding in findings:
        assert finding.issue.endswith(" (source: local)")
        assert "(source: sarvam)" not in finding.issue
    assert findings[0].issue == "SQL injection (source: local)"


def test_sarvam_config_labels_every_issue_sarvam(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle
) -> None:
    """The same transport, labelled honestly as sarvam."""
    install_client(monkeypatch, [MIXED_PAYLOAD])

    findings = ocp.review_diff_live(bundle, sarvam_config())

    assert len(findings) == 2
    for finding in findings:
        assert finding.issue.endswith(" (source: sarvam)")
        assert "(source: local)" not in finding.issue


# --------------------------------------------------------------------------- #
# C. The reused Phase 4 guards are actually applied
# --------------------------------------------------------------------------- #


def test_hallucinated_file_is_dropped(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle, cfg: ocp.OpenAICompatConfig
) -> None:
    """A finding for a file outside the diff never reaches the caller."""
    payload = (
        '[{"file": "app/ghost.py", "line": "3", "severity": "HIGH", '
        '"issue": "invented", "suggested_fix": "invented"}]'
    )
    completions = install_client(monkeypatch, [payload])

    findings = ocp.review_diff_live(bundle, cfg)

    assert findings == []
    assert len(completions.calls) == 1


def test_line_outside_the_added_lines_is_snapped_to_the_nearest_added_line(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle, cfg: ocp.OpenAICompatConfig
) -> None:
    """``app/safe.py`` only added line 2, so a claim of 999 snaps to it."""
    payload = (
        '[{"file": "app/safe.py", "line": "999", "severity": "LOW", '
        '"issue": "off by a mile", "suggested_fix": "look here"}]'
    )
    install_client(monkeypatch, [payload])

    findings = ocp.review_diff_live(bundle, cfg)

    assert len(findings) == 1
    assert findings[0].file == SAFE
    assert findings[0].line == "2"


def test_fenced_json_is_parsed_without_a_repair_call(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle, cfg: ocp.OpenAICompatConfig
) -> None:
    """A ```json fence is stripped by the reused parser, not by a retry."""
    completions = install_client(monkeypatch, [f"```json\n{ONE_FINDING}\n```"])

    findings = ocp.review_diff_live(bundle, cfg)

    assert len(completions.calls) == 1
    assert [finding.line for finding in findings] == ["4"]


def test_extra_field_on_a_finding_is_rejected(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle, cfg: ocp.OpenAICompatConfig
) -> None:
    """A sixth key fails the strict wire model; the valid sibling survives."""
    payload = json.dumps(
        [
            {
                "file": DB,
                "line": "3",
                "severity": "LOW",
                "issue": "has a stray key",
                "suggested_fix": "drop it",
                "confidence": 0.9,
            },
            {
                "file": DB,
                "line": "4",
                "severity": "CRITICAL",
                "issue": "SQL injection",
                "suggested_fix": "parameterise the query",
            },
        ]
    )
    completions = install_client(monkeypatch, [payload])

    findings = ocp.review_diff_live(bundle, cfg)

    assert len(completions.calls) == 1
    assert [finding.issue for finding in findings] == ["SQL injection (source: local)"]


def test_findings_are_capped_at_fifty(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle, cfg: ocp.OpenAICompatConfig
) -> None:
    """Sixty distinct findings come back as fifty."""
    payload = json.dumps(
        [
            {
                "file": DB,
                "line": "3",
                "severity": "LOW",
                "issue": f"distinct problem number {index}",
                "suggested_fix": "fix it",
            }
            for index in range(60)
        ]
    )
    install_client(monkeypatch, [payload])

    findings = ocp.review_diff_live(bundle, cfg)

    assert len(findings) == 50


# --------------------------------------------------------------------------- #
# D. The single repair retry
# --------------------------------------------------------------------------- #


def test_prose_then_valid_json_repairs_without_response_format(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle, cfg: ocp.OpenAICompatConfig
) -> None:
    """A parse failure costs exactly one repair call, which drops JSON mode."""
    completions = install_client(monkeypatch, [PROSE, ONE_FINDING])

    findings = ocp.review_diff_live(bundle, cfg)

    assert len(completions.calls) == 2
    assert "response_format" in completions.calls[0]
    assert "response_format" not in completions.calls[1]
    assert len(findings) == 1
    assert findings[0].issue == "SQL injection (source: local)"


def test_repair_prompt_appends_the_error_and_asks_for_a_bare_array(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle, cfg: ocp.OpenAICompatConfig
) -> None:
    """The repair message is the original prompt plus the one-line failure."""
    completions = install_client(monkeypatch, [PROSE, ONE_FINDING])

    ocp.review_diff_live(bundle, cfg)

    original = completions.calls[0]["messages"][1]["content"]
    repair = completions.calls[1]["messages"][1]["content"]
    assert repair.startswith(original)
    assert "was not JSON" in repair
    assert "Answer again with a bare JSON array" in repair
    assert "was not JSON" not in original


def test_bad_request_error_then_valid_json_repairs(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle, cfg: ocp.OpenAICompatConfig
) -> None:
    """An endpoint rejecting ``response_format`` gets one retry without it."""
    completions = install_client(monkeypatch, [sdk_error("BadRequestError", 400), ONE_FINDING])

    findings = ocp.review_diff_live(bundle, cfg)

    assert len(completions.calls) == 2
    assert "response_format" in completions.calls[0]
    assert "response_format" not in completions.calls[1]
    assert "BadRequestError" in completions.calls[1]["messages"][1]["content"]
    assert len(findings) == 1


def test_empty_completion_then_valid_json_repairs(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle, cfg: ocp.OpenAICompatConfig
) -> None:
    """An empty first completion is repairable, not fatal."""
    completions = install_client(monkeypatch, ["   ", ONE_FINDING])

    findings = ocp.review_diff_live(bundle, cfg)

    assert len(completions.calls) == 2
    assert "response_format" not in completions.calls[1]
    assert "empty completion" in completions.calls[1]["messages"][1]["content"]
    assert len(findings) == 1


# --------------------------------------------------------------------------- #
# E. Double failure: an empty live review, never a fallback
# --------------------------------------------------------------------------- #


def test_double_failure_returns_an_empty_list(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle, cfg: ocp.OpenAICompatConfig
) -> None:
    """Prose twice: no findings, no exception, exactly two calls."""
    completions = install_client(monkeypatch, [PROSE, PROSE])

    findings = ocp.review_diff_live(bundle, cfg)

    assert findings == []
    assert len(completions.calls) == 2


def test_double_failure_logs_exactly_one_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    bundle: DiffBundle,
    cfg: ocp.OpenAICompatConfig,
) -> None:
    """One WARNING on ``reviewer.openai_compat`` and nothing from ``reviewer.sarvam``."""
    install_client(monkeypatch, [PROSE, PROSE])
    caplog.set_level(logging.DEBUG, logger="reviewer.openai_compat")

    ocp.review_diff_live(bundle, cfg)

    warnings = warning_records(caplog, "reviewer.openai_compat")
    assert len(warnings) == 1
    assert "returning an empty review" in warnings[0].getMessage()
    assert "local review failed twice" in warnings[0].getMessage()
    assert warning_records(caplog, "reviewer.sarvam") == []


def test_double_failure_stays_live_with_zero_findings(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle, cfg: ocp.OpenAICompatConfig
) -> None:
    """The review is still live: a parse failure never switches to mock."""
    install_client(monkeypatch, [PROSE, PROSE])

    outcome = ocp.review_with_fallback(bundle, cfg)

    assert outcome.mode == "live"
    assert outcome.provider == "local"
    assert outcome.model == "qwen2.5-coder-7b-instruct"
    assert outcome.findings == []
    assert outcome.reason == ""


# --------------------------------------------------------------------------- #
# F. Unrepairable failures raise, then degrade to mock
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("error_name", "status"), UNREPAIRABLE)
def test_unrepairable_failure_raises_after_one_call_then_degrades_to_mock(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    bundle: DiffBundle,
    cfg: ocp.OpenAICompatConfig,
    error_name: str,
    status: int | None,
) -> None:
    """No repair retry: one call, a raise, then exactly one WARNING on fallback."""
    error = sdk_error(error_name, status)
    completions = install_client(monkeypatch, [error, ONE_FINDING])

    with pytest.raises(ocp.SarvamUnavailableError) as raised:
        ocp.review_diff_live(bundle, cfg)

    assert len(completions.calls) == 1
    assert error_name in str(raised.value)
    assert API_KEY not in str(raised.value)

    completions = install_client(monkeypatch, [error, ONE_FINDING])
    caplog.set_level(logging.DEBUG, logger="reviewer.openai_compat")

    outcome = ocp.review_with_fallback(bundle, cfg)

    assert len(completions.calls) == 1
    assert (outcome.mode, outcome.provider, outcome.model) == ("mock", "mock", "local-rules")
    assert outcome.reason.endswith("; local rule engine used")
    assert error_name in outcome.reason
    assert len(warning_records(caplog, "reviewer.openai_compat")) == 1


# --------------------------------------------------------------------------- #
# G. Credential hygiene
# --------------------------------------------------------------------------- #


def test_api_key_never_leaks_on_the_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    bundle: DiffBundle,
    cfg: ocp.OpenAICompatConfig,
) -> None:
    """A successful run carries the key nowhere a user can see it."""
    install_client(monkeypatch, [MIXED_PAYLOAD])
    caplog.set_level(logging.DEBUG)

    outcome = ocp.review_with_fallback(bundle, cfg)

    assert outcome.mode == "live"
    assert API_KEY not in outcome_text(outcome)
    assert API_KEY not in captured_text(caplog)


def test_api_key_never_leaks_on_the_repair_path(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    bundle: DiffBundle,
    cfg: ocp.OpenAICompatConfig,
) -> None:
    """The repair prompt and its findings are clean too."""
    completions = install_client(monkeypatch, [PROSE, ONE_FINDING])
    caplog.set_level(logging.DEBUG)

    outcome = ocp.review_with_fallback(bundle, cfg)

    assert outcome.mode == "live"
    assert API_KEY not in outcome_text(outcome)
    assert API_KEY not in captured_text(caplog)
    assert API_KEY not in json.dumps(completions.calls)


def test_api_key_never_leaks_on_the_double_failure_path(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    bundle: DiffBundle,
    cfg: ocp.OpenAICompatConfig,
) -> None:
    """Even the two-failure WARNING is built from class names only."""
    install_client(monkeypatch, [PROSE, PROSE])
    caplog.set_level(logging.DEBUG, logger="reviewer.openai_compat")

    outcome = ocp.review_with_fallback(bundle, cfg)

    assert outcome.mode == "live"
    assert len(warning_records(caplog, "reviewer.openai_compat")) == 1
    assert API_KEY not in outcome_text(outcome)
    assert API_KEY not in captured_text(caplog)


def test_api_key_never_leaks_on_the_auth_failure_path(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    bundle: DiffBundle,
    cfg: ocp.OpenAICompatConfig,
) -> None:
    """The SDK error text contains the key; the reason and the log must not."""
    error = sdk_error("AuthenticationError", 401)
    assert API_KEY in str(error)
    install_client(monkeypatch, [error])
    caplog.set_level(logging.DEBUG, logger="reviewer.openai_compat")

    outcome = ocp.review_with_fallback(bundle, cfg)

    assert outcome.mode == "mock"
    assert len(warning_records(caplog, "reviewer.openai_compat")) == 1
    assert API_KEY not in outcome_text(outcome)
    assert API_KEY not in captured_text(caplog)


# --------------------------------------------------------------------------- #
# H. provider_available
# --------------------------------------------------------------------------- #


def test_provider_available_is_false_for_missing_or_blank_fields() -> None:
    """``None``, a blank base URL, a blank key and whitespace are all unusable."""
    base = {
        "base_url": "http://localhost:1234/v1",
        "api_key": API_KEY,
        "model": "qwen2.5-coder-7b-instruct",
        "provider_name": ocp.PROVIDER_LOCAL,
        "timeout": 5.0,
    }

    assert ocp.provider_available(None) is False
    assert ocp.provider_available(ocp.OpenAICompatConfig(**{**base, "base_url": ""})) is False
    assert ocp.provider_available(ocp.OpenAICompatConfig(**{**base, "api_key": ""})) is False
    assert ocp.provider_available(ocp.OpenAICompatConfig(**{**base, "base_url": "   "})) is False
    assert ocp.provider_available(ocp.OpenAICompatConfig(**{**base, "api_key": " \t "})) is False


def test_provider_available_is_true_for_a_valid_config() -> None:
    """Availability needs a URL and a key; the model id is not consulted."""
    base = {
        "base_url": "http://localhost:1234/v1",
        "api_key": API_KEY,
        "model": "qwen2.5-coder-7b-instruct",
        "provider_name": ocp.PROVIDER_LOCAL,
        "timeout": 5.0,
    }

    assert ocp.provider_available(ocp.OpenAICompatConfig(**base)) is True
    assert ocp.provider_available(ocp.OpenAICompatConfig(**{**base, "model": ""})) is True


# --------------------------------------------------------------------------- #
# I. review_with_fallback: reasons and the two filters
# --------------------------------------------------------------------------- #


def test_none_config_degrades_to_mock_with_a_reason(
    caplog: pytest.LogCaptureFixture, bundle: DiffBundle
) -> None:
    """No config means the rule engine, with a reason that says so."""
    caplog.set_level(logging.DEBUG, logger="reviewer.openai_compat")

    outcome = ocp.review_with_fallback(bundle, None)

    assert (outcome.mode, outcome.provider, outcome.model) == ("mock", "mock", "local-rules")
    assert "no OpenAI-compatible provider selected" in outcome.reason
    assert len(warning_records(caplog, "reviewer.openai_compat")) == 1


def test_min_severity_filters_the_live_path(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle, cfg: ocp.OpenAICompatConfig
) -> None:
    """The LOW finding is dropped on the live path."""
    install_client(monkeypatch, [MIXED_PAYLOAD])

    outcome = ocp.review_with_fallback(bundle, cfg, min_severity=Severity.HIGH)

    assert outcome.mode == "live"
    assert [finding.severity for finding in outcome.findings] == [Severity.CRITICAL]


def test_min_severity_filters_the_mock_path(bundle: DiffBundle) -> None:
    """The same floor applies to the rule engine's findings."""
    unfiltered = ocp.review_with_fallback(bundle, None)
    filtered = ocp.review_with_fallback(bundle, None, min_severity=Severity.CRITICAL)

    assert unfiltered.findings
    assert len(filtered.findings) < len(unfiltered.findings)
    assert all(finding.severity is Severity.CRITICAL for finding in filtered.findings)


def test_categories_filter_the_mock_path(bundle: DiffBundle) -> None:
    """A category filter narrows the rule engine to those rules."""
    unfiltered = ocp.review_with_fallback(bundle, None)
    filtered = ocp.review_with_fallback(bundle, None, categories=[RuleCategory.SECRETS])

    assert filtered.mode == "mock"
    assert filtered.findings
    assert len(filtered.findings) < len(unfiltered.findings)
    kept = {(finding.file, finding.line, finding.issue) for finding in filtered.findings}
    assert kept <= {(finding.file, finding.line, finding.issue) for finding in unfiltered.findings}


def test_categories_do_not_filter_the_live_path(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle, cfg: ocp.OpenAICompatConfig
) -> None:
    """Live findings carry no rule id, so the category filter is ignored there."""
    install_client(monkeypatch, [MIXED_PAYLOAD])

    outcome = ocp.review_with_fallback(bundle, cfg, categories=[RuleCategory.STYLE])

    assert outcome.mode == "live"
    assert len(outcome.findings) == 2


# --------------------------------------------------------------------------- #
# J. Provider selection precedence, through app.engine
# --------------------------------------------------------------------------- #


def test_auto_with_neither_variable_selects_mock() -> None:
    """No configuration at all: the rule engine, with a reason naming both vars."""
    selection = engine.select_provider(Settings())

    assert selection.provider == "mock"
    assert selection.config is None
    assert "no SARVAM_API_KEY or LMSTUDIO_BASE_URL configured" in selection.reason


def test_auto_with_lmstudio_base_url_selects_local_with_the_configured_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``LMSTUDIO_BASE_URL`` alone is enough, and the model comes from the env."""
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://localhost:4321/v1")
    monkeypatch.setenv("LMSTUDIO_MODEL", "my-local-coder")

    selection = engine.select_provider(Settings())

    assert selection.provider == "local"
    assert selection.config is not None
    assert selection.config.base_url == "http://localhost:4321/v1"
    assert selection.config.model == "my-local-coder"
    assert selection.config.provider_name == "local"


def test_auto_with_sarvam_key_selects_sarvam_with_model_sarvam_m(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``SARVAM_API_KEY`` alone selects the hosted endpoint."""
    monkeypatch.setenv("SARVAM_API_KEY", "sk-sarvam-test")

    selection = engine.select_provider(Settings())

    assert selection.provider == "sarvam"
    assert selection.config is not None
    assert selection.config.model == "sarvam-m"
    assert selection.config.base_url == "https://api.sarvam.ai/v1"
    assert selection.config.provider_name == "sarvam"


def test_auto_with_both_configured_sarvam_wins_over_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Locked precedence: both set means sarvam, and the reason says so."""
    monkeypatch.setenv("SARVAM_API_KEY", "sk-sarvam-test")
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")

    selection = engine.select_provider(Settings())

    assert selection.provider == "sarvam"
    assert selection.config is not None
    assert selection.config.provider_name == "sarvam"
    assert selection.reason == "SARVAM_API_KEY is set; sarvam selected"
    assert "LMSTUDIO" not in selection.reason


def test_forced_local_without_the_url_degrades_to_mock_naming_lmstudio_base_url() -> None:
    """A forced provider never crashes the run; the reason names the variable."""
    selection = engine.select_provider(Settings(), requested="local")

    assert selection.provider == "mock"
    assert selection.config is None
    assert "LMSTUDIO_BASE_URL" in selection.reason


def test_forced_sarvam_without_the_key_degrades_to_mock_naming_sarvam_api_key() -> None:
    """Same rule for the hosted provider."""
    selection = engine.select_provider(Settings(), requested="sarvam")

    assert selection.provider == "mock"
    assert selection.config is None
    assert "SARVAM_API_KEY" in selection.reason


def test_forced_mock_selects_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    """``mock`` wins even when a live provider is fully configured."""
    monkeypatch.setenv("SARVAM_API_KEY", "sk-sarvam-test")
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")

    selection = engine.select_provider(Settings(), requested="mock")

    assert selection.provider == "mock"
    assert selection.config is None
    assert selection.reason == "provider forced to mock"


def test_unknown_provider_raises_value_error() -> None:
    """An unknown name is a programming error, not a configuration state."""
    with pytest.raises(ValueError) as raised:
        engine.select_provider(Settings(), requested="telepathy")

    assert "telepathy" in str(raised.value)


# --------------------------------------------------------------------------- #
# K. app.engine.review end to end
# --------------------------------------------------------------------------- #


def test_engine_review_runs_live_with_the_local_config(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle
) -> None:
    """The whole path: env -> selection -> adapter -> honest labels."""
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
    completions = install_client(monkeypatch, [ONE_FINDING])

    outcome = engine.review(bundle, Settings())

    assert len(completions.calls) == 1
    assert outcome.mode == "live"
    assert outcome.provider == "local"
    assert outcome.model == "qwen2.5-coder-7b-instruct"
    assert [finding.issue for finding in outcome.findings] == ["SQL injection (source: local)"]


def test_engine_review_degrades_to_mock_when_the_adapter_raises(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle
) -> None:
    """An unrepairable adapter failure reaches the caller as an honest mock run."""
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")

    def refuse(config: ocp.OpenAICompatConfig) -> Any:
        raise ocp.SarvamUnavailableError("local endpoint refused the connection")

    monkeypatch.setattr(ocp, "_build_client", refuse)

    outcome = engine.review(bundle, Settings())

    assert (outcome.mode, outcome.provider, outcome.model) == ("mock", "mock", "local-rules")
    assert "local endpoint refused the connection" in outcome.reason


def test_engine_review_force_offline_never_builds_a_client(
    monkeypatch: pytest.MonkeyPatch, bundle: DiffBundle
) -> None:
    """``force_offline=True`` wins over a fully configured live provider."""
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
    built: list[ocp.OpenAICompatConfig] = []

    def record(config: ocp.OpenAICompatConfig) -> Any:
        built.append(config)
        raise AssertionError("force_offline must not build a client")

    monkeypatch.setattr(ocp, "_build_client", record)

    outcome = engine.review(bundle, Settings(), force_offline=True)

    assert built == []
    assert (outcome.mode, outcome.provider, outcome.model) == ("mock", "mock", "local-rules")
    assert "offline mode requested" in outcome.reason


# --------------------------------------------------------------------------- #
# L. Live smoke test — skipped unless a real server is configured
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(not LIVE_BASE_URL, reason="needs a live LM Studio server")
def test_live_smoke_review_against_a_real_endpoint() -> None:
    """One real review of ``samples/sample.diff`` against the configured server.

    Skipped in CI, where ``LMSTUDIO_BASE_URL`` is unset. The mode is allowed to
    be ``live`` or ``mock``: a server that is configured but not answering is a
    legitimate degradation, and this test only proves the run completes.
    """
    assert LIVE_BASE_URL is not None
    config = ocp.OpenAICompatConfig(
        base_url=LIVE_BASE_URL,
        api_key=os.getenv("LMSTUDIO_API_KEY", "lm-studio"),
        model=os.getenv("LMSTUDIO_MODEL", "qwen2.5-coder-7b-instruct"),
        provider_name=ocp.PROVIDER_LOCAL,
        timeout=float(os.getenv("LMSTUDIO_TIMEOUT", "120")),
    )
    bundle = parse_diff_file(SAMPLE)

    outcome = ocp.review_with_fallback(bundle, config)

    assert isinstance(outcome, ocp.ProviderOutcome)
    assert outcome.mode in ("live", "mock")
    assert isinstance(outcome.findings, list)
    assert all(isinstance(finding, Finding) for finding in outcome.findings)
