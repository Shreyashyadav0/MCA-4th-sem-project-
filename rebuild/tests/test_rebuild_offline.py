"""Verification test for track 4 — ``rebuild/offline.py`` (mock_provider + config).

Skips cleanly until the module exists. Then it requires the rebuilt offline path to
produce the same result shape, the same findings and the same notes as
``app.mock_provider``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.config as real_config  # noqa: E402
import app.mock_provider as real  # noqa: E402
import app.parser as real_parser  # noqa: E402

REBUILD_FILE = ROOT / "rebuild" / "offline.py"
SAMPLE = ROOT / "samples" / "sample.diff"

pytestmark = pytest.mark.skipif(
    not REBUILD_FILE.exists(), reason="rebuild/offline.py not written yet"
)

RISKY = '''\
API_TOKEN = "ghp_exampleTokenValue1234567890"


def get_user(uid):
    return eval(f"load({uid})")
'''

CLEAN = '''\
def add(a: int, b: int) -> int:
    """Return the sum of two integers."""
    return a + b
'''


@pytest.fixture(scope="module")
def rebuilt():
    return pytest.importorskip("rebuild.offline")


def _pairs(findings):
    return sorted((f.line, f.severity.value) for f in findings)


def test_offline_review_matches_on_a_risky_file(rebuilt, tmp_path):
    target = tmp_path / "risky.py"
    target.write_text(RISKY, encoding="utf-8")
    ours = real.offline_review(target, RISKY, "no key configured")
    theirs = rebuilt.offline_review(target, RISKY, "no key configured")
    assert theirs.mode == ours.mode == "mock"
    assert theirs.target == ours.target == str(target)
    assert _pairs(theirs.findings) == _pairs(ours.findings)
    assert theirs.verdict == ours.verdict


def test_offline_review_is_quiet_on_a_clean_file(rebuilt, tmp_path):
    target = tmp_path / "clean.py"
    target.write_text(CLEAN, encoding="utf-8")
    ours = real.offline_review(target, CLEAN, "no key configured")
    theirs = rebuilt.offline_review(target, CLEAN, "no key configured")
    assert _pairs(theirs.findings) == _pairs(ours.findings)
    assert theirs.verdict == ours.verdict


def test_notes_carry_the_reason_and_the_engine_label(rebuilt, tmp_path):
    target = tmp_path / "risky.py"
    target.write_text(RISKY, encoding="utf-8")
    ours = real.offline_review(target, RISKY, "no key configured")
    theirs = rebuilt.offline_review(target, RISKY, "no key configured")
    assert len(theirs.notes) == len(ours.notes)
    assert "no key configured" in " ".join(theirs.notes)
    assert "local rule engine" in " ".join(theirs.notes)


def test_offline_diff_findings_match(rebuilt):
    text = SAMPLE.read_text(encoding="utf-8")
    ours = real.offline_diff_findings(real_parser.parse_diff(text), "no key configured")
    theirs = rebuilt.offline_diff_findings(
        rebuilt.parse_diff(text), "no key configured"
    )
    assert sorted((f.file, f.line, f.severity.value) for f in theirs) == sorted(
        (f.file, f.line, f.severity.value) for f in ours
    )


def test_settings_degrades_the_same_way(rebuilt):
    cases = [
        {},
        {"sarvam_api_key": "key"},
        {"sarvam_api_key": "  "},
        {"review_mode": "mock", "sarvam_api_key": "key"},
    ]
    for kwargs in cases:
        ours = real_config.Settings(_env_file=None, **kwargs)
        theirs = rebuilt.Settings(_env_file=None, **kwargs)
        assert theirs.has_sarvam_key == ours.has_sarvam_key
        assert theirs.resolve_mode() == ours.resolve_mode()
        assert theirs.resolve_mode(force_offline=True) == ours.resolve_mode(
            force_offline=True
        )
