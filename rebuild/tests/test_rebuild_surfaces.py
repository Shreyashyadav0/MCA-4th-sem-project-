"""Verification test for track 7 — ``rebuild/surfaces.py`` (cli + main + github_client).

Skips cleanly until the module exists. Then it requires the rebuilt CLI to answer with
the same process exit codes as ``app.cli`` for the same argv: 0 for a produced review,
1 for bad input, 2 for a usage error. Everything runs in-process, offline.
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.cli as real  # noqa: E402

REBUILD_FILE = ROOT / "rebuild" / "surfaces.py"
SAMPLE = ROOT / "samples" / "sample.diff"

pytestmark = pytest.mark.skipif(
    not REBUILD_FILE.exists(), reason="rebuild/surfaces.py not written yet"
)


@pytest.fixture(scope="module")
def rebuilt():
    return pytest.importorskip("rebuild.surfaces")


def _exit_code(main, argv):
    """Run one CLI invocation in-process and return only its exit code."""
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        return main(argv)


def test_usage_error_is_exit_2(rebuilt, tmp_path):
    missing = str(tmp_path / "nope.py")
    assert _exit_code(rebuilt.main, []) == _exit_code(real.main, []) == 2
    assert (
        _exit_code(rebuilt.main, [missing, "--post-to-pr", "not-a-target"])
        == _exit_code(real.main, [missing, "--post-to-pr", "not-a-target"])
        == 2
    )


def test_unreadable_input_is_exit_1(rebuilt, tmp_path):
    missing = str(tmp_path / "nope.py")
    assert _exit_code(rebuilt.main, [missing]) == _exit_code(real.main, [missing]) == 1


def test_list_rules_is_exit_0(rebuilt):
    assert _exit_code(rebuilt.main, ["--list-rules"]) == _exit_code(
        real.main, ["--list-rules"]
    ) == 0


def test_offline_diff_review_is_exit_0(rebuilt):
    argv = [str(SAMPLE), "--offline", "--json"]
    assert _exit_code(rebuilt.main, argv) == _exit_code(real.main, argv) == 0


def test_offline_single_file_review_is_exit_0(rebuilt, tmp_path):
    target = tmp_path / "risky.py"
    target.write_text('API_TOKEN = "ghp_exampleTokenValue1234567890"\n', encoding="utf-8")
    argv = [str(target), "--offline"]
    assert _exit_code(rebuilt.main, argv) == _exit_code(real.main, argv) == 0


def test_parser_and_entry_points_are_exposed(rebuilt):
    # The surface track is cli + main + github_client: the entry point and the
    # GitHub payload builder must both exist and be callable.
    assert callable(rebuilt.main)
    assert hasattr(rebuilt, "app")  # the ASGI app object
    assert callable(rebuilt.render_inline_body)
