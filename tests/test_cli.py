"""CLI contract tests for Phase 5 — the surface the mutation audit found unguarded.

The CLI had no tests before this file: breaking `--post-to-pr` validation, its exit
codes or the posting report would not have failed the suite. These tests drive
`app.cli.main(argv)` in-process (no subprocess, no network) and pin exactly those
behaviours.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import app.github_client as github_client
from app.cli import main
from app.github_client import PostResult

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "sample.diff"


class _Resp:
    """Minimal httpx.Response stand-in for the fake GitHub client."""

    def __init__(self, status_code: int, body: object | None = None) -> None:
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.headers: dict[str, str] = {}
        self.text = ""

    def json(self) -> object:
        return self._body


class _FakeClient:
    """Records every call and replays a scripted response per method."""

    def __init__(self, get_body: list[dict[str, str]] | None = None, post_status: int = 201) -> None:
        self.calls: list[tuple[str, str]] = []
        self.get_body = get_body or []
        self.post_status = post_status

    def get(self, url: str, **kwargs: object) -> _Resp:
        self.calls.append(("GET", url))
        return _Resp(200, self.get_body)

    def post(self, url: str, **kwargs: object) -> _Resp:
        self.calls.append(("POST", url))
        return _Resp(self.post_status, {"id": 1})

    def close(self) -> None:
        return None


def _install(monkeypatch: pytest.MonkeyPatch, client: _FakeClient) -> None:
    """Point the GitHub seam at ``client``."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_value")
    monkeypatch.setattr(github_client, "_build_github_client", lambda token: client)


@pytest.mark.parametrize(
    "target",
    ["bad-format", "owner/repo", "owner/repo#", "owner/repo#abc", "a/b/c#1", "#12", "owner/repo#0"],
)
def test_malformed_post_target_exits_2(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], target: str) -> None:
    """A malformed --post-to-pr is a usage error, before any review work."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    code = main([str(SAMPLE), "--post-to-pr", target])
    captured = capsys.readouterr()
    assert code == 2
    assert "OWNER/REPO#NUM" in captured.err
    assert "target" not in captured.out, "no review work should happen on a usage error"


def test_single_source_file_cannot_be_posted(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Posting needs diff anchors, so a single file is refused with exit 1."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    code = main(["app/config.py", "--post-to-pr", "owner/repo#1"])
    captured = capsys.readouterr()
    assert code == 1
    assert "diff" in captured.err.lower()


def test_missing_path_exits_2(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """No path and no --list-rules is a usage error."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert main([]) == 2
    assert "path is required" in capsys.readouterr().err


def test_posting_success_exits_0_and_reports(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """A clean post prints the three outcome lines and exits 0."""
    _install(monkeypatch, _FakeClient())
    code = main([str(SAMPLE), "--post-to-pr", "owner/repo#1"])
    captured = capsys.readouterr()
    assert code == 0
    assert "posted   : 4 inline comment(s)" in captured.out
    assert "summary  : yes" in captured.out


def test_posting_duplicate_exits_0_and_says_so(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """A duplicate delivery is a success, not an error."""
    client = _FakeClient()
    _install(monkeypatch, client)

    # Learn the marker the payload will carry, then replay it in the listing.
    from app.github_client import _summary_fingerprint, build_payload
    from app.parser import anchor_findings, parse_diff_file
    from app.rules import review_diff

    bundle = parse_diff_file(SAMPLE)
    payload = build_payload(anchor_findings(bundle, review_diff(bundle)), bundle.files)
    client.get_body = [{"body": f"<!-- ai-code-reviewer:{_summary_fingerprint(payload)} -->"}]

    code = main([str(SAMPLE), "--post-to-pr", "owner/repo#1"])
    captured = capsys.readouterr()
    assert code == 0
    assert "skipped  : duplicate review already present" in captured.out
    assert [call for call in client.calls if call[0] == "POST"] == []


def test_posting_auth_failure_exits_1(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """A 401 is reported as an error line and exit 1, never a traceback."""
    _install(monkeypatch, _FakeClient(post_status=401))
    code = main([str(SAMPLE), "--post-to-pr", "owner/repo#1"])
    captured = capsys.readouterr()
    assert code == 1
    assert "error    :" in captured.out
    assert "401" in captured.out


def test_json_stdout_stays_pure_with_posting(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """--json keeps stdout a single JSON document; posting output goes to stderr."""
    _install(monkeypatch, _FakeClient())
    code = main([str(SAMPLE), "--json", "--post-to-pr", "owner/repo#1"])
    captured = capsys.readouterr()
    assert code == 0
    parsed = json.loads(captured.out)
    assert parsed["mode"] == "mock"
    assert "posted" in captured.err


def test_cli_returns_a_post_result_shaped_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """The exit code is derived from PostResult.ok, including a skipped duplicate."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_value")
    monkeypatch.setattr(
        github_client,
        "_build_github_client",
        lambda token: _FakeClient(),
    )
    assert main([str(SAMPLE), "--post-to-pr", "owner/repo#9"]) == 0

    class _Failing:
        def get(self, url: str, **kwargs: object) -> _Resp:
            return _Resp(200, [])

        def post(self, url: str, **kwargs: object) -> _Resp:
            return _Resp(500, {})

        def close(self) -> None:
            return None

    monkeypatch.setattr(github_client, "_build_github_client", lambda token: _Failing())
    assert main([str(SAMPLE), "--post-to-pr", "owner/repo#9"]) == 1
