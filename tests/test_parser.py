"""Phase 2 parser tests — pure, offline, no network, no credentials.

Run with ``pytest -q``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models import AnchorStatus, Finding, Severity
from app.parser import (
    DiffParseError,
    anchor_findings,
    normalize_path,
    parse_diff,
    parse_diff_file,
)

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "sample.diff"

PLAIN_DIFF = """--- app/util.py
+++ app/util.py
@@ -10,3 +10,4 @@
 def total(rows):
-    return sum(rows)
+    return sum(int(r) for r in rows)
+
"""


def test_sample_diff_parses_two_files() -> None:
    bundle = parse_diff_file(SAMPLE)
    assert [f.path for f in bundle.files] == ["app/db.py", "app/report.py"]
    assert [f.change for f in bundle.files] == ["modified", "added"]
    assert bundle.files_changed == 2


def test_added_line_numbers_come_from_hunk_header() -> None:
    bundle = parse_diff_file(SAMPLE)
    db = bundle.files[0]
    # hunk is @@ -1,5 +1,8 @@: added lines land on the new-side numbering.
    assert db.added_spans == ["3-4", "7-8"]
    assert db.hunk_for_line(8) is not None
    assert db.hunk_for_line(99) is None


def test_plain_unified_diff_without_git_header() -> None:
    bundle = parse_diff(PLAIN_DIFF)
    assert len(bundle.files) == 1
    util = bundle.files[0]
    assert util.path == "app/util.py"
    # -10,3 +10,4 starting at 10: context 10, removed 11, added 11, context 12.
    assert util.added_line_numbers == {11, 12}


def test_anchor_statuses() -> None:
    bundle = parse_diff_file(SAMPLE)
    findings = [
        Finding(file="app/db.py", line="3", severity=Severity.CRITICAL, issue="secret", suggested_fix="use env"),
        Finding(file="app/db.py", line="1", severity=Severity.LOW, issue="old line", suggested_fix="n/a"),
        Finding(file="app/other.py", line="7", severity=Severity.HIGH, issue="elsewhere", suggested_fix="n/a"),
        Finding(file="app/report.py", line="1-5", severity=Severity.MEDIUM, issue="range", suggested_fix="n/a"),
    ]
    anchors = anchor_findings(bundle, findings)
    by_issue = {a.finding.issue: a for a in anchors}
    assert by_issue["secret"].status is AnchorStatus.ANCHORED
    assert by_issue["secret"].hunk_header == "@@ -1,5 +1,8 @@"
    assert by_issue["old line"].status is AnchorStatus.FILE_ONLY
    assert by_issue["elsewhere"].status is AnchorStatus.UNANCHORED
    assert by_issue["range"].status is AnchorStatus.ANCHORED
    # Severity order is preserved: CRITICAL first.
    assert anchors[0].finding.severity is Severity.CRITICAL


def test_no_newline_marker_and_binary_file() -> None:
    raw = (
        "diff --git a/x.txt b/x.txt\n"
        "--- a/x.txt\n+++ b/x.txt\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "\\ No newline at end of file\n"
        "+new\n"
        "\\ No newline at end of file\n"
        "diff --git a/logo.png b/logo.png\n"
        "Binary files a/logo.png and b/logo.png differ\n"
    )
    bundle = parse_diff(raw)
    assert len(bundle.files) == 2
    assert bundle.files[0].added_line_numbers == {1}
    assert bundle.files[1].binary is True
    assert bundle.files[1].added_spans == []


def test_deleted_file_and_mode_only_change() -> None:
    raw = (
        "diff --git a/gone.py b/gone.py\n"
        "deleted file mode 100644\n"
        "--- a/gone.py\n+++ /dev/null\n"
        "@@ -1,2 +0,0 @@\n"
        "-a = 1\n"
        "-b = 2\n"
        "diff --git a/run.sh b/run.sh\n"
        "old mode 100644\nnew mode 100755\n"
    )
    bundle = parse_diff(raw)
    assert bundle.files[0].change == "deleted"
    assert bundle.files[0].path == "gone.py"
    assert bundle.files[0].added_line_numbers == set()
    assert bundle.files[1].change == "modified"
    assert bundle.files[1].hunks == []


@pytest.mark.parametrize("bad", ["", "   \n\n", "just some prose\nno headers here\n"])
def test_bad_input_raises(bad: str) -> None:
    with pytest.raises(DiffParseError):
        parse_diff(bad)


def test_normalize_path_keeps_real_prefixes() -> None:
    assert normalize_path("b/app/config.py") == "app/config.py"
    assert normalize_path("a/app/config.py") == "app/config.py"
    assert normalize_path("app/config.py") == "app/config.py"
    assert normalize_path("/dev/null") == "/dev/null"


def test_unanchored_when_diff_empty_of_that_file() -> None:
    bundle = parse_diff(PLAIN_DIFF)
    anchors = anchor_findings(
        bundle,
        [Finding(file="nope.py", line="1", severity=Severity.LOW, issue="x", suggested_fix="y")],
    )
    assert anchors[0].status is AnchorStatus.UNANCHORED
