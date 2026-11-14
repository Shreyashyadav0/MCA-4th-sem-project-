"""Exhaustive tests for the Phase 3 FastAPI surface.

Everything runs in-process through ``TestClient``: no live server, no network, no
credentials. The interesting cases are the degradation paths — no token, a failed
fetch, a bad signature, a hostile path — because those are what the demo and the
examiner will actually hit.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Severity
from app.rules import RULES, RULE_COUNT

client = TestClient(app)

BAD_DIFF = """diff --git a/app/demo.py b/app/demo.py
--- a/app/demo.py
+++ b/app/demo.py
@@ -1,1 +1,3 @@
 import os
+API_TOKEN = "ghp_demoTokenValue1234567890"
+os.system(f"curl {API_TOKEN}")
"""

CLEAN_DIFF = """diff --git a/app/clean.py b/app/clean.py
--- a/app/clean.py
+++ b/app/clean.py
@@ -1,1 +1,2 @@
 import logging
+logger = logging.getLogger(__name__)
"""

PR_PAYLOAD = {
    "action": "opened",
    "number": 7,
    "repository": {"full_name": "shreyash/demo"},
    "pull_request": {"number": 7},
}


# --------------------------------------------------------------------------- #
# Ops endpoints
# --------------------------------------------------------------------------- #


def test_root_banner() -> None:
    body = client.get("/").json()
    assert body["rules"] == RULE_COUNT
    assert body["mode"] == "mock"  # the live provider is Phase 4
    assert "/webhook" in body["endpoints"]


def test_health_reports_credential_state() -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["rules"] == RULE_COUNT
    assert set(body["categories"]) == {rule.category.value for rule in RULES}
    assert body["sarvam_key"] in {"configured", "missing"}
    assert body["github_token"] in {"configured", "missing"}
    assert body["webhook_secret"] in {"configured", "missing"}


def test_health_reflects_configured_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "topsecret")
    assert client.get("/health").json()["webhook_secret"] == "configured"


# --------------------------------------------------------------------------- #
# Rule introspection
# --------------------------------------------------------------------------- #


def test_rules_listing_is_complete_and_ordered() -> None:
    rules = client.get("/rules").json()
    assert len(rules) == RULE_COUNT
    assert {"id", "title", "category", "owasp", "severity"} == set(rules[0])
    severities = [rule["severity"] for rule in rules]
    assert severities == sorted(severities, key=["CRITICAL", "HIGH", "MEDIUM", "LOW"].index)
    assert all(rule["owasp"].startswith("A") for rule in rules)


def test_single_rule_lookup() -> None:
    rule = client.get("/rules/unsafe/sql-injection").json()
    assert rule["id"] == "unsafe/sql-injection"
    assert rule["severity"] == "CRITICAL"
    assert rule["category"] == "injection"


def test_unknown_rule_is_404() -> None:
    assert client.get("/rules/does/not/exist").status_code == 404


# --------------------------------------------------------------------------- #
# /review
# --------------------------------------------------------------------------- #


def test_review_a_diff() -> None:
    body = client.post("/review", json={"diff": BAD_DIFF}).json()
    assert body["source"] == "inline_diff"
    assert body["stats"]["findings"] == len(body["review"]["findings"])
    assert body["stats"]["critical"] >= 2
    assert body["stats"]["verdict"] == "block"
    assert body["stats"]["duration_ms"] >= 0
    assert all(anchor["status"] == "anchored" for anchor in body["review"]["anchors"])


def test_review_raw_code() -> None:
    body = client.post(
        "/review",
        json={"code": 'import os\nAPI_KEY = "AKIAIOSFODNN7EXAMPLE"\nos.system("ls")\n', "filename": "app/run.py"},
    ).json()
    assert body["source"] == "raw_code"
    assert body["review"]["target"] == "app/run.py"
    assert body["stats"]["files"] == 1
    assert body["stats"]["critical"] >= 1
    assert all(finding["file"] == "app/run.py" for finding in body["review"]["findings"])


def test_review_diff_wins_when_both_are_supplied() -> None:
    body = client.post("/review", json={"diff": BAD_DIFF, "code": "print(1)"}).json()
    assert body["source"] == "inline_diff"
    assert "ignored 'code'" in body["notice"]


def test_review_requires_a_body_field() -> None:
    response = client.post("/review", json={})
    assert response.status_code == 422
    assert "diff" in response.json()["detail"]


def test_review_rejects_unknown_fields() -> None:
    assert client.post("/review", json={"diff": BAD_DIFF, "bogus": 1}).status_code == 422


def test_review_rejects_null_bytes() -> None:
    assert client.post("/review", json={"code": "x = 1\x00\n"}).status_code == 422


def test_review_rejects_unparseable_diff() -> None:
    response = client.post("/review", json={"diff": "just prose, no headers\n"})
    assert response.status_code == 422
    assert "cannot parse diff" in response.json()["detail"]


def test_review_min_severity_filter() -> None:
    body = client.post("/review", json={"diff": BAD_DIFF, "min_severity": "CRITICAL"}).json()
    assert all(finding["severity"] == "CRITICAL" for finding in body["review"]["findings"])


def test_review_category_filter() -> None:
    body = client.post("/review", json={"diff": BAD_DIFF, "categories": ["secrets"]}).json()
    assert body["review"]["findings"]
    assert all("(rule: secret/" in finding["issue"] for finding in body["review"]["findings"])


def test_review_clean_diff_approves() -> None:
    body = client.post("/review", json={"diff": CLEAN_DIFF}).json()
    assert body["stats"]["verdict"] in {"approve", "approve with comments"}
    assert body["stats"]["critical"] == 0


def test_review_comment_is_markdown() -> None:
    body = client.post("/review", json={"diff": BAD_DIFF}).json()
    comment = body["comment"]
    assert comment.startswith("## Autonomous AI Code Review")
    assert "**Verdict:**" in comment
    assert "**Suggested fix:**" in comment


def test_review_findings_keep_the_five_field_contract() -> None:
    body = client.post("/review", json={"diff": BAD_DIFF}).json()
    for finding in body["review"]["findings"]:
        assert set(finding) == {"file", "line", "severity", "issue", "suggested_fix"}
        assert finding["severity"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


# --------------------------------------------------------------------------- #
# /test-review — the offline demo
# --------------------------------------------------------------------------- #


def test_test_review_works_offline() -> None:
    response = client.get("/test-review")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "sample_fixture"
    assert body["review"]["mode"] == "mock"
    assert len(body["review"]["files"]) == 2
    assert body["stats"]["findings"] >= 3
    assert body["review"]["findings"][0]["severity"] == "CRITICAL"
    assert all(anchor["status"] == "anchored" for anchor in body["review"]["anchors"])
    assert body["stats"]["rules_evaluated"] == RULE_COUNT


def test_test_review_reads_a_path_inside_the_project() -> None:
    body = client.get("/test-review", params={"path": "samples/sample.diff"}).json()
    assert body["source"] == "inline_diff"
    assert body["stats"]["findings"] >= 3


@pytest.mark.parametrize("hostile", ["../etc/passwd", "/etc/passwd", "../../../etc/passwd"])
def test_test_review_refuses_paths_outside_the_project(hostile: str) -> None:
    response = client.get("/test-review", params={"path": hostile})
    assert response.status_code == 403


def test_test_review_missing_path_is_404() -> None:
    assert client.get("/test-review", params={"path": "nope.diff"}).status_code == 404


def test_test_review_rejects_a_non_diff_file() -> None:
    assert client.get("/test-review", params={"path": "app/config.py"}).status_code == 422


def test_test_review_body_variant() -> None:
    body = client.post("/test-review", json={"diff": BAD_DIFF}).json()
    assert body["source"] == "inline_diff"
    assert body["stats"]["findings"] >= 2


def test_test_review_body_without_diff_falls_back() -> None:
    body = client.post("/test-review", json={}).json()
    assert body["source"] == "sample_fixture"


def test_test_review_min_severity_query() -> None:
    body = client.get("/test-review", params={"min_severity": "CRITICAL"}).json()
    assert all(finding["severity"] == "CRITICAL" for finding in body["review"]["findings"])


# --------------------------------------------------------------------------- #
# /webhook — degradation paths
# --------------------------------------------------------------------------- #


def test_webhook_ignores_non_pr_events() -> None:
    response = client.post("/webhook", json={"action": "created"}, headers={"X-GitHub-Event": "issue_comment"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ignored"
    assert body["event"] == "issue_comment"


def test_webhook_ignores_closed_prs() -> None:
    payload = {**PR_PAYLOAD, "action": "closed"}
    body = client.post("/webhook", json=payload).json()
    assert body["status"] == "ignored"
    assert "closed" in body["detail"]


def test_webhook_without_token_degrades_to_fixture() -> None:
    body = client.post("/webhook", json=PR_PAYLOAD).json()
    assert body["source"] == "sample_fixture"
    assert "GITHUB_TOKEN" in body["notice"]
    assert body["stats"]["findings"] >= 3


def test_webhook_fetch_failure_degrades_to_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_faketokenvalue1234567890")

    class Boom:
        def __init__(self, *args, **kwargs) -> None:
            raise httpx.ConnectError("no route to host")

    monkeypatch.setattr("app.main.httpx.Client", Boom)
    body = client.post("/webhook", json=PR_PAYLOAD).json()
    assert body["source"] == "sample_fixture"
    assert "github fetch failed" in body["notice"]


def test_webhook_accepts_inline_diff() -> None:
    payload = {**PR_PAYLOAD, "action": "synchronize", "diff": BAD_DIFF}
    body = client.post("/webhook", json=payload).json()
    assert body["source"] == "inline_diff"
    assert body["review"]["target"] == "shreyash/demo#7"
    assert body["stats"]["critical"] >= 1


def test_webhook_rejects_unparseable_diff() -> None:
    payload = {**PR_PAYLOAD, "diff": "not a diff\n"}
    assert client.post("/webhook", json=payload).status_code == 422


def test_webhook_rejects_invalid_json() -> None:
    response = client.post(
        "/webhook",
        content=b"not json at all",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


def test_webhook_signature_required_when_secret_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "topsecret")
    raw = json.dumps(PR_PAYLOAD).encode()
    response = client.post(
        "/webhook",
        content=raw,
        headers={"Content-Type": "application/json", "X-GitHub-Event": "pull_request"},
    )
    assert response.status_code == 401


def test_webhook_rejects_a_wrong_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "topsecret")
    raw = json.dumps(PR_PAYLOAD).encode()
    response = client.post(
        "/webhook",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=" + "0" * 64,
        },
    )
    assert response.status_code == 401


def test_webhook_accepts_a_valid_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "topsecret")
    raw = json.dumps({**PR_PAYLOAD, "diff": BAD_DIFF}).encode()
    signature = "sha256=" + hmac.new(b"topsecret", raw, hashlib.sha256).hexdigest()
    response = client.post(
        "/webhook",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": signature,
        },
    )
    assert response.status_code == 200
    assert response.json()["source"] == "inline_diff"


def test_webhook_tolerates_hostile_payload_shapes() -> None:
    payload = {"action": "opened", "number": None, "repository": {}, "pull_request": {}}
    response = client.post("/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["source"] == "sample_fixture"


# --------------------------------------------------------------------------- #
# OpenAPI / Swagger documentation
# --------------------------------------------------------------------------- #


def test_openapi_documents_every_endpoint() -> None:
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    for expected in ["/review", "/test-review", "/webhook", "/rules", "/health", "/"]:
        assert expected in paths
    assert {"get", "post"} <= set(paths["/test-review"])
    assert {"get", "post"} & set(paths["/webhook"])


def test_openapi_carries_examples_and_descriptions() -> None:
    schema = client.get("/openapi.json").json()
    review_post = schema["paths"]["/review"]["post"]
    assert review_post["summary"]
    assert review_post["description"]
    examples = review_post["requestBody"]["content"]["application/json"].get("examples", {})
    assert {"diff", "code"} <= set(examples)

    review_schema = schema["components"]["schemas"]["ReviewResponse"]
    assert review_schema["description"]
    assert review_schema["properties"]["source"]["description"]
    assert review_schema["properties"]["stats"]["description"]

    rule_schema = schema["components"]["schemas"]["RuleInfo"]
    assert rule_schema["properties"]["owasp"]["examples"] == ["A03:2021-Injection"]


def test_openapi_documents_error_responses() -> None:
    schema = client.get("/openapi.json").json()
    responses = schema["paths"]["/webhook"]["post"]["responses"]
    assert {"200", "400", "401", "422"} <= set(responses)


def test_docs_ui_is_served() -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200


# --------------------------------------------------------------------------- #
# Cross-cutting guarantees
# --------------------------------------------------------------------------- #


def test_no_endpoint_requires_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in ("SARVAM_API_KEY", "GITHUB_TOKEN", "GITHUB_WEBHOOK_SECRET"):
        monkeypatch.delenv(variable, raising=False)
    assert client.get("/health").status_code == 200
    assert client.get("/test-review").status_code == 200
    assert client.post("/review", json={"code": "x = 1\n"}).status_code == 200
    assert client.post("/webhook", json=PR_PAYLOAD).status_code == 200


def test_review_is_deterministic_across_requests() -> None:
    first = client.post("/review", json={"diff": BAD_DIFF}).json()["review"]["findings"]
    second = client.post("/review", json={"diff": BAD_DIFF}).json()["review"]["findings"]
    assert first == second


def test_stats_counts_match_findings() -> None:
    body = client.post("/review", json={"diff": BAD_DIFF}).json()
    findings = body["review"]["findings"]
    stats = body["stats"]
    assert stats["findings"] == len(findings)
    assert stats["critical"] == sum(1 for f in findings if f["severity"] == "CRITICAL")
    assert stats["high"] == sum(1 for f in findings if f["severity"] == "HIGH")
    assert stats["medium"] == sum(1 for f in findings if f["severity"] == "MEDIUM")
    assert stats["low"] == sum(1 for f in findings if f["severity"] == "LOW")
    assert stats["verdict"] == body["review"]["verdict"]


def test_severity_enum_matches_contract() -> None:
    assert [severity.value for severity in Severity] == ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
