#!/usr/bin/env python3
"""Learning progress for the rebuild-from-memory tracks.

Two commands, both stdlib only:

    python scripts/learning_progress.py status          # 7-row table
    python scripts/learning_progress.py status --fast   # table from the last run
    python scripts/learning_progress.py check 3         # run track 3's test only

``status`` runs each track's verification test (one ``pytest`` per track) unless
``--fast`` is given, in which case it reports the last recorded result instead.
``check N`` runs exactly one test file and exits with pytest's own exit code.

Results are appended to ``.learning-progress.json`` (gitignored) as one record per
track: outcome, exit code, the pytest summary line and an ISO-8601 UTC timestamp.
There are no streaks, no points and no scoring — the file is a log, and this script
reports what pytest says and nothing more.

This module deliberately does not import the application, so it can never be the
reason an app-level import breaks.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRESS_FILE = ROOT / ".learning-progress.json"
STATE_VERSION = 1


@dataclass(frozen=True)
class Track:
    """One rebuild track: the module you write and the test that verifies it."""

    number: int
    name: str
    module: Path
    test: Path

    @property
    def module_label(self) -> str:
        return self.module.relative_to(ROOT).as_posix()

    @property
    def test_label(self) -> str:
        return self.test.relative_to(ROOT).as_posix()


TRACKS: tuple[Track, ...] = tuple(
    Track(number=index, name=name, module=ROOT / "rebuild" / f"{name}.py",
          test=ROOT / "rebuild" / "tests" / f"test_rebuild_{name}.py")
    for index, name in enumerate(
        ("models", "parser", "rules", "offline", "providers", "engine", "surfaces"),
        start=1,
    )
)

OUTCOME_SKIPPED = "skipped"
OUTCOME_PASSED = "passed"
OUTCOME_FAILED = "failed"
OUTCOME_NO_TEST = "no-test"


def _now() -> str:
    """Current time as an ISO-8601 UTC timestamp, seconds precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _summary_line(output: str) -> str:
    """The last non-blank line of pytest output — its summary."""
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _outcome(exit_code: int, summary: str) -> str:
    """Map a pytest exit code plus its summary to one word."""
    if exit_code == 0:
        if "passed" not in summary and "skipped" in summary:
            return OUTCOME_SKIPPED
        return OUTCOME_PASSED
    if exit_code == 5:  # nothing collected
        return OUTCOME_NO_TEST
    return OUTCOME_FAILED


def run_track(track: Track) -> dict[str, object]:
    """Run one track's verification test and return its record.

    Args:
        track: The track to verify.

    Returns:
        A record dict with ``outcome``, ``exit_code``, ``summary``,
        ``checked_at`` and ``module_exists``.
    """
    module_exists = track.module.exists()
    if not track.test.exists():
        return {
            "outcome": OUTCOME_NO_TEST,
            "exit_code": 5,
            "summary": f"missing test file {track.test_label}",
            "checked_at": _now(),
            "module_exists": module_exists,
        }

    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        "-p",
        "no:cacheprovider",
        track.test_label,
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{completed.stdout}\n{completed.stderr}".strip()
    summary = _summary_line(completed.stdout) or _summary_line(output)
    return {
        "outcome": _outcome(completed.returncode, summary),
        "exit_code": completed.returncode,
        "summary": summary,
        "checked_at": _now(),
        "module_exists": module_exists,
    }


def load_state() -> dict[str, object]:
    """Read the progress log, returning an empty skeleton when absent or broken."""
    try:
        state = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    tracks = state.get("tracks")
    if not isinstance(tracks, dict):
        state["tracks"] = {}
    state.setdefault("version", STATE_VERSION)
    return state


def save_state(state: dict[str, object]) -> None:
    """Write the progress log, stamping ``updated_at``."""
    state["version"] = STATE_VERSION
    state["updated_at"] = _now()
    temporary = PROGRESS_FILE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(PROGRESS_FILE)


def record(state: dict[str, object], track: Track, result: dict[str, object]) -> None:
    """Store one track's latest result in the in-memory state."""
    tracks = state.setdefault("tracks", {})
    assert isinstance(tracks, dict)
    tracks[track.name] = {**result, "track": track.number, "test": track.test_label}


def _cell(value: str, width: int) -> str:
    return value.ljust(width)


def print_status(fast: bool) -> int:
    """Print the seven-row status table.

    Args:
        fast: When true, do not run pytest; show the last recorded result instead.

    Returns:
        Process exit code: always 0 — this is a report, not a gate.
    """
    state = load_state()
    recorded = state.get("tracks")
    if not isinstance(recorded, dict):
        recorded = {}

    rows: list[tuple[str, ...]] = []
    for track in TRACKS:
        if fast:
            previous = recorded.get(track.name) or {}
            outcome = str(previous.get("outcome", "-"))
            checked = str(previous.get("checked_at", "-"))
        else:
            result = run_track(track)
            record(state, track, result)
            outcome = str(result["outcome"])
            checked = str(result["checked_at"])
        rows.append(
            (
                str(track.number),
                track.name,
                track.module_label,
                "yes" if track.module.exists() else "no",
                outcome,
                checked,
            )
        )

    if not fast:
        save_state(state)

    headers = ("#", "track", "module", "exists", "test", "checked (UTC)")
    widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(len(headers))]

    def render(values: tuple[str, ...]) -> str:
        return "  ".join(_cell(values[i], widths[i]) for i in range(len(headers))).rstrip()

    print(render(headers))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print(render(row))

    counts: dict[str, int] = {}
    for row in rows:
        counts[row[4]] = counts.get(row[4], 0) + 1
    print()
    print(
        "  ".join(f"{name}: {count}" for name, count in sorted(counts.items()))
        + ("" if fast else f"   (log: {PROGRESS_FILE.name})")
    )
    if fast:
        print("--fast: results are the last recorded run; nothing was executed.")
    return 0


def check(number: int) -> int:
    """Run one track's verification test and return pytest's exit code.

    Args:
        number: 1-based track number.

    Returns:
        pytest's own exit code: 0 when the track is green (including a clean skip),
        1 when it fails, 5 when nothing was collected.
    """
    if not 1 <= number <= len(TRACKS):
        print(
            f"error: track {number} does not exist; expected 1-{len(TRACKS)}",
            file=sys.stderr,
        )
        return 2
    track = TRACKS[number - 1]

    print(f"track {track.number}: {track.name} -> {track.test_label}")
    if not track.module.exists():
        print(f"note: {track.module_label} does not exist yet, so this test will skip.")
    print()

    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        "-p",
        "no:cacheprovider",
        track.test_label,
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    output = f"{completed.stdout}{completed.stderr}"
    sys.stdout.write(output if output.endswith("\n") else output + "\n")

    summary = _summary_line(completed.stdout)
    result = {
        "outcome": _outcome(completed.returncode, summary),
        "exit_code": completed.returncode,
        "summary": summary,
        "checked_at": _now(),
        "module_exists": track.module.exists(),
    }
    state = load_state()
    record(state, track, result)
    save_state(state)

    print()
    print(f"exit {completed.returncode} ({result['outcome']}) — recorded in {PROGRESS_FILE.name}")
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="learning_progress",
        description="Report rebuild-track progress from real pytest exit codes.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    status = subcommands.add_parser("status", help="Print the seven-track status table.")
    status.add_argument(
        "--fast",
        action="store_true",
        help="Do not run pytest; report the last recorded result per track.",
    )

    check_parser = subcommands.add_parser(
        "check", help="Run only one track's verification test; exit with pytest's code."
    )
    check_parser.add_argument("track", type=int, metavar="N", help=f"Track number, 1-{len(TRACKS)}.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = build_parser().parse_args(argv)
    if args.command == "status":
        return print_status(fast=args.fast)
    return check(args.track)


if __name__ == "__main__":
    raise SystemExit(main())
