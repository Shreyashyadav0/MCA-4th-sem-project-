"""Render a benchmark run as CSV, JSON, Markdown and a PNG chart.

Four artifacts, one job each:

``metrics.csv``
    One row per mode, every metric column, and the per-category counts flattened
    to ``cat_tp_<category>`` / ``cat_fp_<category>`` / ``cat_fn_<category>``
    columns. Flat because a spreadsheet is where these numbers get sorted and
    charted, and a nested column cannot be sorted.
``summary.json``
    The same numbers as machine-readable data: sorted keys, one entry per mode,
    the per-category counts nested, plus ``generated_by`` and each mode's note so
    a consumer can tell a skipped mode from a run that scored zero.
``summary.md``
    The human view: a table of modes, a per-category table, and a paragraph
    stating what the numbers do and do not mean.
``chart.png``
    A grouped bar chart of precision / recall / F1 per mode, drawn with the Agg
    backend so it works on a machine with no display.

Graceful degradation
--------------------
matplotlib is optional. When it cannot be imported — a slim container, a broken
font cache, a stripped install — :func:`write_chart` logs exactly one WARNING,
writes nothing, and returns the path it would have used. The other three
artifacts are unaffected and the run still exits successfully: a missing chart is
a missing convenience, not a failed benchmark.

Skipped modes are rendered, not hidden
--------------------------------------
A skipped mode carries an all-zero scorecard. Its row appears in every artifact
with ``skipped`` set and its note attached, so a reader sees "this mode did not
run" instead of an absent row they might read as "this mode scored zero".
"""

from __future__ import annotations

import csv
import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from benchmarks.runner import ModeResult

__all__ = [
    "CSV_NAME",
    "JSON_NAME",
    "MD_NAME",
    "CHART_NAME",
    "ARTIFACT_NAMES",
    "write_csv",
    "write_summary_json",
    "write_summary_md",
    "write_chart",
]

logger = logging.getLogger(__name__)

CSV_NAME: str = "metrics.csv"
JSON_NAME: str = "summary.json"
MD_NAME: str = "summary.md"
CHART_NAME: str = "chart.png"

ARTIFACT_NAMES: tuple[str, ...] = (CSV_NAME, JSON_NAME, MD_NAME, CHART_NAME)
"""Every artifact this module writes, in the order the CLI reports them."""

#: Scalar columns, in contract order, shared by the CSV and the Markdown table.
SCALAR_COLUMNS: tuple[str, ...] = (
    "mode",
    "samples",
    "skipped",
    "precision",
    "recall",
    "f1",
    "fpr",
    "tp",
    "fp",
    "fn",
    "tn",
    "latency_p50_ms",
    "latency_p95_ms",
)

#: Chart series, in the order they appear in each group of bars.
CHART_SERIES: tuple[str, ...] = ("precision", "recall", "f1")


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


def _target(out: Path, default_name: str, suffix: str) -> Path:
    """Resolve the file to write, creating the directory when there is one.

    ``out`` may name a directory — the usual case, ``--out benchmarks/out`` — or,
    for a caller that wants a specific filename, a path already carrying this
    artifact's suffix. Both are accepted so the four writers stay symmetric.

    Args:
        out: Output directory, or a file path ending in ``suffix``.
        default_name: Filename to use inside ``out`` when it is a directory.
        suffix: Extension of this artifact, including the dot, e.g. ``".csv"``.

    Returns:
        The path to write.
    """
    path = Path(out)
    if path.suffix.lower() == suffix:
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    path.mkdir(parents=True, exist_ok=True)
    return path / default_name


def _modes(results: Mapping[str, ModeResult]) -> list[ModeResult]:
    """Return the results in a deterministic order.

    Args:
        results: Results keyed by mode name.

    Returns:
        The results sorted by mode name, so a caller that assembled the mapping
        in a different order still gets byte-identical artifacts.
    """
    return [results[name] for name in sorted(results)]


def _categories(modes: Sequence[ModeResult]) -> list[str]:
    """Collect every category appearing in any mode's per-category counts.

    Args:
        modes: Results to scan.

    Returns:
        Category names in ascending sort order. Empty when no mode carried any
        category, which happens when every mode was skipped.
    """
    found: set[str] = set()
    for result in modes:
        found.update(result.metrics.per_category)
    return sorted(found)


def _ratio(value: float) -> str:
    """Render a ratio with four decimals, matching the metrics module's rounding.

    Args:
        value: Precision, recall, F1 or FPR.

    Returns:
        A fixed-point string, so a CSV column is numeric and a Markdown cell is
        aligned without the caller formatting it.
    """
    return f"{value:.4f}"


def _latency(value: float) -> str:
    """Render a latency with three decimals, matching the metrics rounding.

    Args:
        value: A p50 or p95 latency in milliseconds.

    Returns:
        A fixed-point string.
    """
    return f"{value:.3f}"


def _scalar_row(result: ModeResult) -> dict[str, str]:
    """Flatten one mode's scalar metrics into display-ready strings.

    Args:
        result: The mode's result.

    Returns:
        One value per :data:`SCALAR_COLUMNS`, in that order. Ratios and latencies
        are fixed-point strings; counts are plain integers.
    """
    metrics = result.metrics
    return {
        "mode": result.mode,
        "samples": str(result.samples),
        "skipped": str(result.skipped),
        "precision": _ratio(metrics.precision),
        "recall": _ratio(metrics.recall),
        "f1": _ratio(metrics.f1),
        "fpr": _ratio(metrics.fpr),
        "tp": str(metrics.tp),
        "fp": str(metrics.fp),
        "fn": str(metrics.fn),
        "tn": str(metrics.tn),
        "latency_p50_ms": _latency(metrics.latency_p50),
        "latency_p95_ms": _latency(metrics.latency_p95),
    }


def _category_columns(categories: Iterable[str]) -> list[str]:
    """Build the flattened per-category column names.

    Args:
        categories: Category names, already sorted.

    Returns:
        ``cat_tp_<category>``, ``cat_fp_<category>``, ``cat_fn_<category>`` for
        each category, in that per-category order.
    """
    columns: list[str] = []
    for category in categories:
        columns.extend(
            (f"cat_tp_{category}", f"cat_fp_{category}", f"cat_fn_{category}")
        )
    return columns


def _category_row(result: ModeResult, categories: Sequence[str]) -> dict[str, str]:
    """Flatten one mode's per-category counts into ``cat_*`` columns.

    Args:
        result: The mode's result.
        categories: Every category in the run, sorted.

    Returns:
        One value per :func:`_category_columns` name; a category this mode never
        saw is reported as ``0`` rather than left blank, so a spreadsheet sum
        cannot silently skip it.
    """
    row: dict[str, str] = {}
    for category in categories:
        score = result.metrics.per_category.get(category)
        row[f"cat_tp_{category}"] = str(score.tp if score else 0)
        row[f"cat_fp_{category}"] = str(score.fp if score else 0)
        row[f"cat_fn_{category}"] = str(score.fn if score else 0)
    return row


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #


def write_csv(results: dict[str, ModeResult], out: Path) -> Path:
    """Write one CSV row per mode, with per-category counts flattened.

    Args:
        results: Results keyed by mode name.
        out: Output directory, or a ``.csv`` file path.

    Returns:
        The path written.

    Raises:
        OSError: The file cannot be written. A permissions problem is not a
            benchmark outcome, so it is not swallowed here.
    """
    path = _target(out, CSV_NAME, ".csv")
    modes = _modes(results)
    categories = _categories(modes)
    header = [*SCALAR_COLUMNS, "note", *_category_columns(categories)]

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        for result in modes:
            row = {
                **_scalar_row(result),
                "note": result.note,
                **_category_row(result, categories),
            }
            writer.writerow(row)
    return path


# --------------------------------------------------------------------------- #
# JSON
# --------------------------------------------------------------------------- #


def _mode_payload(result: ModeResult) -> dict[str, Any]:
    """Build one mode's JSON object.

    Args:
        result: The mode's result.

    Returns:
        A plain-dict payload: counts as ints, ratios and latencies as floats
        exactly as ``compute_metrics`` rounded them, the per-category counts
        nested, and the mode's note so a skip is self-describing.
    """
    metrics = result.metrics
    return {
        "mode": result.mode,
        "samples": result.samples,
        "skipped": result.skipped,
        "note": result.note,
        "precision": metrics.precision,
        "recall": metrics.recall,
        "f1": metrics.f1,
        "fpr": metrics.fpr,
        "tp": metrics.tp,
        "fp": metrics.fp,
        "fn": metrics.fn,
        "tn": metrics.tn,
        "latency_p50_ms": metrics.latency_p50,
        "latency_p95_ms": metrics.latency_p95,
        "per_category": {
            category: {"tp": score.tp, "fp": score.fp, "fn": score.fn}
            for category, score in sorted(metrics.per_category.items())
        },
    }


def write_summary_json(results: dict[str, ModeResult], out: Path) -> Path:
    """Write the run summary as stable, sorted-key JSON.

    Args:
        results: Results keyed by mode name.
        out: Output directory, or a ``.json`` file path.

    Returns:
        The path written.

    Raises:
        OSError: The file cannot be written.
    """
    path = _target(out, JSON_NAME, ".json")
    modes = _modes(results)
    payload: dict[str, Any] = {
        "generated_by": "benchmarks.eval",
        "mode_order": [result.mode for result in modes],
        "modes": {result.mode: _mode_payload(result) for result in modes},
        "categories": _categories(modes),
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------------------------- #
# Markdown
# --------------------------------------------------------------------------- #

_HOW_TO_READ: str = (
    "`precision` is the share of reported findings that a "
    "human label asked for, `recall` the share of labels some finding reproduced, "
    "and `F1` their harmonic mean; read precision and recall as a pair, never "
    "precision alone, because a mode that reports nothing scores a conventional "
    "precision of 1.0 beside a recall of 0.0 and an F1 of 0.0. Matching is "
    "**greedy, one-to-one** on the same file with overlapping line ranges and a "
    "compatible category, largest overlap first with ties broken "
    "deterministically — a documented limitation, since greedy matching can score "
    "lower than an optimal assignment would and the category of a finding is "
    "inferred from its issue text rather than read from a field. `FPR` divides "
    "false positives by clean samples, so it is only meaningful when the dataset "
    "contains labelled-clean samples. `p50`/`p95` are nearest-rank percentiles of "
    "per-sample wall time in milliseconds, and with fewer than 20 samples p95 is "
    "effectively the slowest sample. A row with `skipped` set did not run: its "
    "metrics are zero by construction, and its note says what was missing. "
    "Finally, every `example_*` sample is a **format example, not evaluation "
    "data** — it exists to demonstrate the file layout and is excluded from any "
    "published metric, so a run over this dataset is a smoke test of the harness, "
    "not a measurement of the reviewer."
)


def write_summary_md(results: dict[str, ModeResult], out: Path) -> Path:
    """Write the human-readable summary: mode table, category table, caveats.

    Args:
        results: Results keyed by mode name.
        out: Output directory, or a ``.md`` file path.

    Returns:
        The path written.

    Raises:
        OSError: The file cannot be written.
    """
    path = _target(out, MD_NAME, ".md")
    modes = _modes(results)
    categories = _categories(modes)

    lines: list[str] = [
        "# Benchmark summary",
        "",
        f"Modes reported: {', '.join(result.mode for result in modes) or 'none'}.",
        "",
        "## Modes",
        "",
        "| Mode | Samples | Skipped | Precision | Recall | F1 | FPR | TP | FP | FN | TN | p50 (ms) | p95 (ms) | Note |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for result in modes:
        row = _scalar_row(result)
        note = result.note.replace("|", "\\|") if result.note else "—"
        lines.append(
            "| {mode} | {samples} | {skipped} | {precision} | {recall} | {f1} | "
            "{fpr} | {tp} | {fp} | {fn} | {tn} | {latency_p50_ms} | "
            "{latency_p95_ms} | {note} |".format(note=note, **row)
        )

    lines.extend(["", "## Per category", ""])
    if categories:
        lines.extend(
            [
                "| Category | Mode | TP | FP | FN |",
                "| --- | --- | ---: | ---: | ---: |",
            ]
        )
        for category in categories:
            for result in modes:
                score = result.metrics.per_category.get(category)
                if score is None:
                    continue
                lines.append(
                    f"| {category} | {result.mode} | {score.tp} | {score.fp} | {score.fn} |"
                )
    else:
        lines.append("No category counts were recorded — no mode scored a sample.")

    lines.extend(["", "## How to read this", "", _HOW_TO_READ, ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Chart
# --------------------------------------------------------------------------- #


def write_chart(results: dict[str, ModeResult], out: Path) -> Path:
    """Write a grouped bar chart of precision, recall and F1 per mode.

    The Agg backend is forced before ``pyplot`` is imported, so the chart renders
    with no display attached. Any failure — matplotlib missing, a broken backend,
    a font cache that cannot be built — is caught, logged as exactly one WARNING
    and turned into a missing file rather than a crashed report.

    Args:
        results: Results keyed by mode name.
        out: Output directory, or a ``.png`` file path.

    Returns:
        The path written, or — when matplotlib is unavailable — the path it would
        have been written to, so the caller can still report the intended
        artifact name.
    """
    path = _target(out, CHART_NAME, ".png")
    modes = _modes(results)
    if not modes:
        logger.warning("no benchmark modes to chart; %s not written", path)
        return path

    try:
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
    except Exception as exc:  # ImportError, or a backend that refuses to load.
        logger.warning(
            "matplotlib unavailable (%s: %s); %s not written",
            type(exc).__name__,
            exc,
            path,
        )
        return path

    try:
        figure, axes = plt.subplots(figsize=(7.5, 4.5))
        labels = [
            result.mode + (" (skipped)" if result.samples == 0 else "")
            for result in modes
        ]
        positions = list(range(len(modes)))
        width = 0.8 / len(CHART_SERIES)
        colors = ("#1f4e79", "#2e75b6", "#9dc3e6")

        for offset, (series, color) in enumerate(zip(CHART_SERIES, colors)):
            values = [float(getattr(result.metrics, series)) for result in modes]
            shifted = [position + (offset - (len(CHART_SERIES) - 1) / 2) * width for position in positions]
            bars = axes.bar(
                shifted,
                values,
                width=width,
                label=series.upper() if series == "f1" else series.capitalize(),
                color=color,
                edgecolor="white",
                linewidth=0.5,
            )
            axes.bar_label(bars, fmt="%.2f", fontsize=6, padding=1)

        axes.set_title("Review mode quality: precision / recall / F1")
        axes.set_ylabel("score")
        axes.set_ylim(0.0, 1.1)
        axes.set_xticks(positions)
        axes.set_xticklabels(labels)
        axes.grid(axis="y", linestyle=":", linewidth=0.5, alpha=0.6)
        axes.set_axisbelow(True)
        # Below the axes, one row: the bars reach 1.0, so any in-axes
        # legend would sit on top of a bar or its value label.
        axes.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, -0.12),
            ncol=len(CHART_SERIES),
            fontsize=9,
            frameon=False,
        )
        figure.tight_layout()
        figure.savefig(path, dpi=150)
        plt.close(figure)
    except Exception as exc:  # A rendering failure must not kill the report.
        logger.warning(
            "could not render %s (%s: %s); chart skipped",
            path,
            type(exc).__name__,
            exc,
        )
        try:
            plt.close("all")
        except Exception:  # pragma: no cover - nothing left to clean up.
            pass
        return path
    return path
