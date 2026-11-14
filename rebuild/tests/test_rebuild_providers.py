"""Verification test for track 5 — ``rebuild/providers.py`` (sarvam + openai_compat).

Skips cleanly until the module exists. Then it requires the rebuilt adapter to parse
the same model payload into the same findings, refuse non-JSON the same way, build the
same prompt and validate its config identically. No network: everything here is pure.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.openai_compat_provider as real_compat  # noqa: E402
import app.parser as real_parser  # noqa: E402

REBUILD_FILE = ROOT / "rebuild" / "providers.py"
SAMPLE = ROOT / "samples" / "sample.diff"

pytestmark = pytest.mark.skipif(
    not REBUILD_FILE.exists(), reason="rebuild/providers.py not written yet"
)

#: Two legal findings and one illegal one — the illegal entry must be dropped.
PAYLOAD = """
{
  "findings": [
    {"file": "app/db.py", "line": "3", "severity": "CRITICAL",
     "issue": "a token literal is committed", "suggested_fix": "read it from the env"},
    {"file": "app/db.py", "line": "7-8", "severity": "HIGH",
     "issue": "SQL is interpolated", "suggested_fix": "use a parameterised query"},
    {"file": "app/db.py", "line": "not-a-line", "severity": "LOW",
     "issue": "bad", "suggested_fix": "bad"}
  ]
}
"""


@pytest.fixture(scope="module")
def rebuilt():
    return pytest.importorskip("rebuild.providers")


def test_same_findings_are_parsed_from_the_same_payload(rebuilt):
    ours = real_compat.parse_findings_payload(PAYLOAD)
    theirs = rebuilt.parse_findings_payload(PAYLOAD)
    assert [(f.file, f.line, f.severity.value, f.issue) for f in theirs] == [
        (f.file, f.line, f.severity.value, f.issue) for f in ours
    ]
    assert len(theirs) == 2  # the illegal third entry is dropped, not repaired


@pytest.mark.parametrize("raw", ["", "not json at all", "{'single': 'quotes'}"])
def test_non_json_is_refused_the_same_way(rebuilt, raw):
    with pytest.raises(Exception) as ours:
        real_compat.parse_findings_payload(raw)
    with pytest.raises(Exception) as theirs:
        rebuilt.parse_findings_payload(raw)
    assert type(theirs.value).__name__ == type(ours.value).__name__


def test_build_prompt_matches(rebuilt):
    bundle = real_parser.parse_diff(SAMPLE.read_text(encoding="utf-8"))
    assert rebuilt.build_prompt(bundle) == real_compat.build_prompt(bundle)


def test_config_holds_the_same_fields(rebuilt):
    kwargs = {
        "base_url": "http://localhost:1234/v1",
        "api_key": "lm-studio",
        "model": "qwen2.5-coder-7b-instruct",
        "provider_name": "local",
        "timeout": 120.0,
    }
    ours = real_compat.OpenAICompatConfig(**kwargs)
    theirs = rebuilt.OpenAICompatConfig(**kwargs)
    assert (theirs.base_url, theirs.model, theirs.provider_name, theirs.timeout) == (
        ours.base_url,
        ours.model,
        ours.provider_name,
        ours.timeout,
    )
    # The key is carried but must never reach a repr or a log line.
    assert "lm-studio" not in repr(theirs)
    assert "lm-studio" not in repr(ours)


def test_config_requires_the_same_arguments(rebuilt):
    with pytest.raises(TypeError):
        real_compat.OpenAICompatConfig(base_url="http://localhost:1234/v1")
    with pytest.raises(TypeError):
        rebuilt.OpenAICompatConfig(base_url="http://localhost:1234/v1")


def test_provider_names_match(rebuilt):
    assert rebuilt.PROVIDER_NAME == real_compat.PROVIDER_NAME
    assert rebuilt.PROVIDER_LOCAL == real_compat.PROVIDER_LOCAL
    assert rebuilt.PROVIDER_SARVAM == real_compat.PROVIDER_SARVAM
