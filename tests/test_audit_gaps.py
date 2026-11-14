"""Regression tests added by the final audit.

Each test pins a defect that the audit found and the merge review fixed, so the fix
cannot be silently reverted. They are deliberately narrow: one behaviour per test.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.github_client as github_client
from app.config import Settings
from app.main import app
from app.models import Finding, ReviewResult, Severity, sort_findings
from app.parser import DiffReviewResult, bundle_from_source, parse_diff

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "sample.diff"


def _finding(file: str = "a.py", line: str = "1", severity: Severity = Severity.LOW) -> Finding:
    return Finding(file=file, line=line, severity=severity, issue="i", suggested_fix="f")


# --------------------------------------------------------------------------- #
# The equivalence map is a documented feature, so it gets pinned explicitly.
# Collapsing it to identity must fail here rather than pass silently.
# --------------------------------------------------------------------------- #


def test_category_equivalence_map_is_pinned() -> None:
    """A collapsed map would make the harness's category tolerance disappear."""
    from benchmarks.matching import CATEGORY_EQUIVALENCE

    expected = {
        "secrets": {"secrets", "crypto"},
        "injection": {"injection"},
        "deserialisation": {"deserialisation", "injection"},
        "crypto": {"crypto", "secrets"},
        "auth": {"auth", "secrets"},
        "config": {"config"},
        "reliability": {"reliability", "quality"},
        "quality": {"quality", "reliability", "complexity", "style"},
        "complexity": {"complexity", "quality", "style"},
        "style": {"style", "quality", "complexity"},
    }
    for category, accepted in expected.items():
        assert CATEGORY_EQUIVALENCE[category] == frozenset(accepted), category
    assert CATEGORY_EQUIVALENCE["llm"] >= frozenset(expected), "llm must accept every category"


# --------------------------------------------------------------------------- #
# The engine note is what a reader is told to quote, so its content is pinned.
# --------------------------------------------------------------------------- #


def test_engine_note_names_the_real_rule_count() -> None:
    from app.mock_provider import ENGINE_NOTE
    from app.rules import RULE_COUNT

    assert str(RULE_COUNT) in ENGINE_NOTE
    assert "deterministic rules" in ENGINE_NOTE


def test_mock_review_carries_the_engine_note() -> None:
    from app.cli import main as cli_main

    assert cli_main([str(SAMPLE), "--offline", "--json"]) == 0


# --------------------------------------------------------------------------- #
# The human report is the CLI's default surface; a smoke test keeps it wired.
# --------------------------------------------------------------------------- #


def test_cli_report_renders_every_field(capsys: pytest.CaptureFixture[str]) -> None:
    from app.cli import main as cli_main

    assert cli_main([str(SAMPLE), "--offline"]) == 0
    out = capsys.readouterr().out
    for label in ("File", "Line", "Severity", "Issue", "Suggested Fix"):
        assert label in out
    assert "verdict" in out and "mode" in out


# --------------------------------------------------------------------------- #
# Regressions for the merge-review fixes.
# --------------------------------------------------------------------------- #


def test_sort_findings_is_a_total_order_across_files() -> None:
    """Equal severity and line in different files must order by file, not input order."""
    findings = [_finding(file="z.py"), _finding(file="a.py"), _finding(file="m.py")]
    assert [f.file for f in sort_findings(findings)] == ["a.py", "m.py", "z.py"]
    assert [f.file for f in sort_findings(list(reversed(findings)))] == ["a.py", "m.py", "z.py"]


def test_truncated_hunk_does_not_swallow_the_next_file() -> None:
    """A hunk header that promises more lines than the patch holds must not eat a file."""
    raw = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,9 @@\n keep\n+added_a\n"
        "diff --git a/b.py b/b.py\n--- a/b.py\n+++ b/b.py\n@@ -1,1 +1,2 @@\n keep\n+added_b\n"
    )
    bundle = parse_diff(raw)
    assert [f.path for f in bundle.files] == ["a.py", "b.py"]
    assert bundle.files[0].added_line_numbers == {2}
    assert bundle.files[1].added_line_numbers == {2}


@pytest.mark.parametrize("model", [ReviewResult, DiffReviewResult])
def test_result_models_read_their_own_json(model: type) -> None:
    """`verdict` is a computed field, so validation must ignore it on the way back in."""
    original = model(mode="mock", target="x")
    restored = model.model_validate_json(original.model_dump_json())
    assert restored.verdict == original.verdict
    assert restored.mode == "mock"


def test_settings_repr_hides_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SARVAM_API_KEY", "sk-must-not-appear")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_must_not_appear")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "whsec_must_not_appear")
    text = repr(Settings())
    for secret in ("sk-must-not-appear", "ghp_must_not_appear", "whsec_must_not_appear"):
        assert secret not in text


def test_webhook_refuses_to_post_an_unauthenticated_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Token set + no webhook secret means the delivery cannot be trusted: review, don't post."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_value")
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("WEBHOOK_ALLOW_UNSIGNED", raising=False)

    calls: list[str] = []

    class _Resp:
        status_code = 201
        headers: dict[str, str] = {}
        text = ""

        def json(self) -> object:
            return {"id": 1}

    class _Client:
        def get(self, url: str, **kwargs: object) -> _Resp:
            calls.append("GET")
            return _Resp()

        def post(self, url: str, **kwargs: object) -> _Resp:
            calls.append("POST")
            return _Resp()

        def close(self) -> None:
            return None

    monkeypatch.setattr(github_client, "_build_github_client", lambda token: _Client())
    payload = {
        "action": "opened",
        "number": 5,
        "repository": {"full_name": "a/b"},
        "diff": "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1,2 @@\n x\n+y = 1\n",
    }
    body = TestClient(app).post("/webhook", json=payload).json()
    assert body["posting"] is None
    assert calls == []


def test_webhook_posts_when_the_opt_in_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """The opt-in must actually work, or the guard would be a silent outage."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_value")
    monkeypatch.setenv("WEBHOOK_ALLOW_UNSIGNED", "1")
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)

    class _Resp:
        status_code = 201
        headers: dict[str, str] = {}
        text = ""

        def json(self) -> object:
            return {"id": 1}

    class _Client:
        def get(self, url: str, **kwargs: object) -> _Resp:
            return _Resp()

        def post(self, url: str, **kwargs: object) -> _Resp:
            return _Resp()

        def close(self) -> None:
            return None

    monkeypatch.setattr(github_client, "_build_github_client", lambda token: _Client())
    payload = {
        "action": "opened",
        "number": 5,
        "repository": {"full_name": "a/b"},
        "diff": "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1,2 @@\n x\n+y = 1\n",
    }
    body = TestClient(app).post("/webhook", json=payload).json()
    assert body["posting"] is not None


def test_webhook_never_publishes_fixture_content(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the PR diff cannot be fetched, the fixture is reviewed but never posted."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_value")
    monkeypatch.setenv("WEBHOOK_ALLOW_UNSIGNED", "1")
    calls: list[str] = []

    class _Boom:
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("no route to GitHub")

    monkeypatch.setattr("app.main.httpx.Client", _Boom)
    monkeypatch.setattr(
        github_client,
        "_build_github_client",
        lambda token: calls.append("built") or None,
    )
    body = TestClient(app).post(
        "/webhook",
        json={"action": "opened", "number": 9, "repository": {"full_name": "a/b"}},
    ).json()
    assert body["source"] == "sample_fixture"
    assert "not posted" in body["notice"]
    assert body["posting"] is None
    assert calls == []


def test_payload_json_is_still_serialisable() -> None:
    """The API contract is JSON; a computed field must not break dumping."""
    from app.parser import anchor_findings
    from app.rules import review_diff

    bundle = parse_diff(SAMPLE.read_text(encoding="utf-8"))
    findings = review_diff(bundle)
    review = DiffReviewResult(
        mode="mock",
        target="samples/sample.diff",
        files=bundle.summaries(),
        findings=findings,
        anchors=anchor_findings(bundle, findings),
    )
    assert json.loads(review.model_dump_json())["verdict"] == review.verdict


def test_a_hostile_path_cannot_break_out_of_the_code_span() -> None:
    """A backtick in a diff path must not turn the bot's own comment into a link."""
    from app.github_client import render_inline_body

    hostile = "x`[click](https://evil.example)`"
    head = render_inline_body(
        Finding(file=hostile, line="1", severity=Severity.HIGH, issue="i", suggested_fix="f")
    ).splitlines()[0]
    assert head.startswith("**HIGH** — ``"), head
    assert head.endswith(":1``"), head
    # A single-backtick span would end at the first inner backtick; a double fence cannot.
    assert head.count("``") >= 1 and "```" not in head


def test_code_span_fence_grows_with_the_longest_backtick_run() -> None:
    from app.github_client import _md_code

    assert _md_code("a``b") == "```a``b```"
    assert _md_code("`lead") == "`` `lead ``"
    assert _md_code("plain") == "`plain`"
