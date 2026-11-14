"""Verification test for track 3 — ``rebuild/rules.py``.

Skips cleanly until the module exists. Then it runs both rule engines over one seeded
snippet and requires the same findings: same lines, same severities, same filtering,
same ``# noqa`` suppression.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.parser as real_parser  # noqa: E402
import app.rules as real  # noqa: E402

REBUILD_FILE = ROOT / "rebuild" / "rules.py"
SAMPLE = ROOT / "samples" / "sample.diff"

pytestmark = pytest.mark.skipif(
    not REBUILD_FILE.exists(), reason="rebuild/rules.py not written yet"
)

#: One seeded snippet: a committed token, eval, an interpolated SQL query and a print.
SEEDED = [
    (1, 'API_TOKEN = "ghp_exampleTokenValue1234567890"'),
    (2, "def run(cmd):"),
    (3, "    return eval(cmd)"),
    (4, '    q = f"SELECT * FROM t WHERE id = {x}"'),
    (5, '    print("debug")'),
]


@pytest.fixture(scope="module")
def rebuilt():
    return pytest.importorskip("rebuild.rules")


def _pairs(findings):
    """The observable identity of a finding: which line, how bad."""
    return sorted((f.line, f.severity.value) for f in findings)


def test_same_findings_on_the_seeded_snippet(rebuilt):
    assert _pairs(rebuilt.review_lines("app/seeded.py", SEEDED)) == _pairs(
        real.review_lines("app/seeded.py", SEEDED)
    )


def test_same_severity_mix(rebuilt):
    ours = Counter(f.severity.value for f in real.review_lines("app/seeded.py", SEEDED))
    theirs = Counter(f.severity.value for f in rebuilt.review_lines("app/seeded.py", SEEDED))
    assert theirs == ours


def test_min_severity_filters_the_same_way(rebuilt):
    floor = real.Severity.HIGH
    assert _pairs(
        rebuilt.review_lines("app/seeded.py", SEEDED, min_severity=floor)
    ) == _pairs(real.review_lines("app/seeded.py", SEEDED, min_severity=floor))


def test_noqa_suppresses_the_same_lines(rebuilt):
    lines = [
        (1, 'API_TOKEN = "ghp_exampleTokenValue1234567890"  # noqa'),
        (2, 'OTHER_TOKEN = "ghp_exampleTokenValue0987654321"'),
    ]
    assert _pairs(rebuilt.review_lines("app/seeded.py", lines)) == _pairs(
        real.review_lines("app/seeded.py", lines)
    )
    assert all(f.line == "2" for f in real.review_lines("app/seeded.py", lines))


def test_same_findings_on_the_sample_diff(rebuilt):
    text = SAMPLE.read_text(encoding="utf-8")
    ours = real.review_diff(real_parser.parse_diff(text))
    theirs = rebuilt.review_diff(real_parser.parse_diff(text))
    assert sorted((f.file, f.line, f.severity.value) for f in theirs) == sorted(
        (f.file, f.line, f.severity.value) for f in ours
    )
