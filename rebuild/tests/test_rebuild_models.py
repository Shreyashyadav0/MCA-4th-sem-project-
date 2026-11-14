"""Verification test for track 1 — ``rebuild/models.py``.

Skips cleanly until ``rebuild/models.py`` exists, so the suite is green today and the
first green run here means something. When it exists, every test compares the rebuilt
model against ``app.models`` on the same inputs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # run from anywhere, not just the repo root
    sys.path.insert(0, str(ROOT))

import app.models as real  # noqa: E402  — the reference behaviour

REBUILD_FILE = ROOT / "rebuild" / "models.py"

pytestmark = pytest.mark.skipif(
    not REBUILD_FILE.exists(), reason="rebuild/models.py not written yet"
)

GOOD = {
    "file": "app/x.py",
    "line": "7",
    "severity": "HIGH",
    "issue": "the connection is never closed, so the pool leaks",
    "suggested_fix": "with connect() as conn: ...",
}

BAD_LINES = ["", "   ", "abc", "5-3", "-1", "1-2-3", "7.5", "42-"]


@pytest.fixture(scope="module")
def rebuilt():
    """The rebuilt module, imported only once its file exists."""
    return pytest.importorskip("rebuild.models")


def test_finding_accepts_the_same_good_input(rebuilt):
    theirs = rebuilt.Finding(**GOOD)
    ours = real.Finding(**GOOD)
    assert theirs.as_row() == ours.as_row()
    assert theirs.line == ours.line
    assert theirs.severity.value == ours.severity.value


@pytest.mark.parametrize("line", BAD_LINES)
def test_finding_rejects_the_same_bad_lines(rebuilt, line):
    with pytest.raises(ValidationError):
        real.Finding(**{**GOOD, "line": line})
    with pytest.raises(ValidationError):
        rebuilt.Finding(**{**GOOD, "line": line})


def test_finding_forbids_the_same_extra_field(rebuilt):
    with pytest.raises(ValidationError):
        real.Finding(**GOOD, confidence=0.9)
    with pytest.raises(ValidationError):
        rebuilt.Finding(**GOOD, confidence=0.9)


def test_severity_ladder_matches(rebuilt):
    assert {s.value for s in rebuilt.Severity} == {s.value for s in real.Severity}
    assert [s.rank for s in rebuilt.Severity] == [s.rank for s in real.Severity]


def test_counts_verdict_and_order_match(rebuilt):
    cases = [("HIGH", "10"), ("CRITICAL", "2"), ("LOW", "30"), ("MEDIUM", "5")]
    ours = [real.Finding(**{**GOOD, "severity": s, "line": n}) for s, n in cases]
    theirs = [rebuilt.Finding(**{**GOOD, "severity": s, "line": n}) for s, n in cases]

    assert rebuilt.severity_counts(theirs) == real.severity_counts(ours)
    assert rebuilt.verdict_for(theirs) == real.verdict_for(ours)
    assert [f.line for f in rebuilt.sort_findings(theirs)] == [
        f.line for f in real.sort_findings(ours)
    ]
    assert rebuilt.verdict_for([]) == real.verdict_for([])
