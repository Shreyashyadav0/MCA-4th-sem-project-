"""Command-line entry point for the offline benchmark harness.

Usage::

    python -m benchmarks.eval --modes rules local merged \\
        --dataset benchmarks/golden --out benchmarks/out

The command loads the golden dataset once, runs each requested mode over it,
prints a compact table of the scorecards and writes four artifacts —
``metrics.csv``, ``summary.json``, ``summary.md`` and ``chart.png`` — into the
output directory.

Exit codes
----------
``0``
    The run completed. A mode that skipped cleanly still counts as completed: an
    unconfigured LM Studio is a fact about the machine, not a failure of the
    benchmark, and CI on a box with no local model must stay green.
``1``
    No mode produced a result at all, so there is nothing to report.
``2``
    The dataset could not be loaded — a missing root, a missing
    ``manifest.json``, or a sample whose labels fail validation. Reported on
    stderr with the loader's own message, which names the sample and the file.

Isolation
---------
Nothing here imports the application's HTTP entry points: the harness measures
the review engine, not the API surface, and a benchmark that booted the server
would measure the server too.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from benchmarks.loader import DatasetError
from benchmarks.report import (
    CHART_NAME,
    CSV_NAME,
    JSON_NAME,
    MD_NAME,
    write_chart,
    write_csv,
    write_summary_json,
    write_summary_md,
)
from benchmarks.runner import MODE_NAMES, ModeResult, run_all

__all__ = ["build_parser", "main"]

PROG: str = "python -m benchmarks.eval"
"""Program name shown in ``--help`` and in error messages."""

DEFAULT_DATASET: str = "benchmarks/golden"
"""Dataset root used when ``--dataset`` is omitted."""

DEFAULT_OUT: str = "benchmarks/out"
"""Output directory used when ``--out`` is omitted."""

EXIT_OK: int = 0
"""The run completed; clean skips included."""

EXIT_NO_RESULTS: int = 1
"""No mode produced a result."""

EXIT_DATASET_ERROR: int = 2
"""The dataset could not be loaded."""

#: Column widths for the stdout table, in the order the columns are printed.
_TABLE_HEADERS: tuple[str, ...] = (
    "mode",
    "samples",
    "skipped",
    "precision",
    "recall",
    "f1",
    "fpr",
    "p50ms",
    "p95ms",
)
_TABLE_WIDTHS: tuple[int, ...] = (9, 7, 7, 9, 9, 9, 9, 9, 9)

#: Characters of a mode note shown in the table; the full text lives in the
#: artifacts, and an unbounded note would destroy the table's alignment.
_NOTE_WIDTH: int = 64


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser.

    Returns:
        A parser accepting ``--modes``, ``--dataset``, ``--out`` and ``--quiet``.
    """
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Run the offline review benchmark over a labelled dataset and write "
            "CSV, JSON, Markdown and PNG artifacts."
        ),
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=MODE_NAMES,
        default=list(MODE_NAMES),
        metavar="MODE",
        help=(
            "review modes to run, in report order: "
            f"{', '.join(MODE_NAMES)} (default: all three)"
        ),
    )
    parser.add_argument(
        "--dataset",
        default=DEFAULT_DATASET,
        metavar="PATH",
        help=f"dataset root holding manifest.json and the sample directories (default: {DEFAULT_DATASET})",
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        metavar="PATH",
        help=f"directory for metrics.csv, summary.json, summary.md and chart.png (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="write the artifacts but print nothing to stdout",
    )
    return parser


def _note_cell(note: str) -> str:
    """Shorten a mode note so it fits one table cell.

    Args:
        note: The mode's full note, possibly empty.

    Returns:
        The note on one line, truncated with an ellipsis past
        :data:`_NOTE_WIDTH` characters; ``"-"`` when there is no note.
    """
    text = " ".join((note or "").split())
    if not text:
        return "-"
    if len(text) <= _NOTE_WIDTH:
        return text
    return text[: _NOTE_WIDTH - 3].rstrip() + "..."


def _table(results: dict[str, ModeResult]) -> str:
    """Render the compact stdout table.

    Args:
        results: Results keyed by mode name.

    Returns:
        The header row, a rule, and one row per mode in name order. Ratios keep
        four decimals and latencies three, matching the artifacts exactly.
    """
    header = "  ".join(
        name.ljust(width) if index == 0 else name.rjust(width)
        for index, (name, width) in enumerate(zip(_TABLE_HEADERS, _TABLE_WIDTHS))
    )
    rule = "  ".join("-" * width for width in _TABLE_WIDTHS)
    lines = [f"{header}  note", f"{rule}  {'-' * 8}"]

    for name in sorted(results):
        result = results[name]
        metrics = result.metrics
        cells = (
            result.mode.ljust(_TABLE_WIDTHS[0]),
            str(result.samples).rjust(_TABLE_WIDTHS[1]),
            str(result.skipped).rjust(_TABLE_WIDTHS[2]),
            f"{metrics.precision:.4f}".rjust(_TABLE_WIDTHS[3]),
            f"{metrics.recall:.4f}".rjust(_TABLE_WIDTHS[4]),
            f"{metrics.f1:.4f}".rjust(_TABLE_WIDTHS[5]),
            f"{metrics.fpr:.4f}".rjust(_TABLE_WIDTHS[6]),
            f"{metrics.latency_p50:.3f}".rjust(_TABLE_WIDTHS[7]),
            f"{metrics.latency_p95:.3f}".rjust(_TABLE_WIDTHS[8]),
        )
        lines.append(f"{'  '.join(cells)}  {_note_cell(result.note)}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the benchmark: load, score, write artifacts, report.

    Args:
        argv: Arguments to parse, defaulting to :data:`sys.argv`.

    Returns:
        :data:`EXIT_OK` when the run completed — a clean skip is a completed run
        — :data:`EXIT_NO_RESULTS` when no mode produced a result, or
        :data:`EXIT_DATASET_ERROR` when the dataset could not be loaded.
    """
    args = build_parser().parse_args(argv)
    dataset = Path(args.dataset)
    out = Path(args.out)

    try:
        results = run_all(args.modes, dataset_root=dataset)
    except DatasetError as exc:
        print(f"{PROG}: dataset error: {exc}", file=sys.stderr)
        return EXIT_DATASET_ERROR

    if not results:
        print(f"{PROG}: no mode produced a result", file=sys.stderr)
        return EXIT_NO_RESULTS

    csv_path = write_csv(results, out)
    json_path = write_summary_json(results, out)
    md_path = write_summary_md(results, out)
    chart_path = write_chart(results, out)

    if not args.quiet:
        print(
            f"benchmark: dataset={dataset} modes={','.join(results)} "
            f"samples={max(result.samples for result in results.values())}"
        )
        print()
        print(_table(results))
        print()
        written = (csv_path, json_path, md_path, chart_path)
        for path, name in zip(
            written, (CSV_NAME, JSON_NAME, MD_NAME, CHART_NAME)
        ):
            state = "written" if path.exists() else "NOT written"
            print(f"  {name:<12} {state:<12} {path}")
        print()

    return EXIT_OK


def _configure_logging() -> None:
    """Route the harness loggers to stderr at INFO, without touching the root.

    A library should not configure logging for its host, but this module *is* the
    host: it is the entry point. The level stays at INFO so a skip explains
    itself on stderr, and no handler is added for the ``app`` loggers, whose
    WARNINGs already reach stderr through the logging module's last-resort
    handler.
    """
    logger = logging.getLogger("benchmarks")
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


if __name__ == "__main__":
    _configure_logging()
    raise SystemExit(main())
