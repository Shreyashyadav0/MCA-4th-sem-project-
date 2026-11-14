"""Verification test for track 2 — ``rebuild/parser.py``.

Skips cleanly until the module exists. Then it feeds the same diff to your parser and
to ``app.parser`` and requires the same added-line sets, spans and file counts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.parser as real  # noqa: E402

REBUILD_FILE = ROOT / "rebuild" / "parser.py"
SAMPLE = ROOT / "samples" / "sample.diff"

pytestmark = pytest.mark.skipif(
    not REBUILD_FILE.exists(), reason="rebuild/parser.py not written yet"
)


@pytest.fixture(scope="module")
def rebuilt():
    return pytest.importorskip("rebuild.parser")


@pytest.fixture(scope="module")
def sample_text():
    return SAMPLE.read_text(encoding="utf-8")


def test_added_line_sets_match(rebuilt, sample_text):
    ours = real.parse_diff(sample_text)
    theirs = rebuilt.parse_diff(sample_text)
    assert {
        f.path: sorted(f.added_line_numbers) for f in theirs.files
    } == {f.path: sorted(f.added_line_numbers) for f in ours.files}


def test_added_spans_match(rebuilt, sample_text):
    ours = real.parse_diff(sample_text)
    theirs = rebuilt.parse_diff(sample_text)
    assert {f.path: f.added_spans for f in theirs.files} == {
        f.path: f.added_spans for f in ours.files
    }


def test_file_and_line_counts_match(rebuilt, sample_text):
    ours = real.parse_diff(sample_text)
    theirs = rebuilt.parse_diff(sample_text)
    assert theirs.files_changed == ours.files_changed
    assert theirs.added_line_count == ours.added_line_count
    assert theirs.is_empty == ours.is_empty


@pytest.mark.parametrize(
    "raw",
    ["a/app/x.py", "b/app/x.py", "./app/x.py", '"a/app/x.py"', "app/config.py"],
)
def test_normalize_path_matches(rebuilt, raw):
    assert rebuilt.normalize_path(raw) == real.normalize_path(raw)


@pytest.mark.parametrize("raw", ["", "\n\n", "this is not a diff\n"])
def test_bad_input_is_refused_the_same_way(rebuilt, raw):
    # app.parser raises DiffParseError, which is a ValueError subclass.
    with pytest.raises(ValueError):
        real.parse_diff(raw)
    with pytest.raises(ValueError):
        rebuilt.parse_diff(raw)
