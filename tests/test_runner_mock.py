"""Offline tests for the benchmark harness: runner, report writers and the CLI.

Everything here runs with no network, no model and no LM Studio server. The three
benchmark modes are exercised against the two ``example_*`` samples in
``benchmarks/golden``, which the dataset manifest defines as **format examples**,
not evaluation data — so these tests pin the *plumbing* (counts, skip behaviour,
notes, artifact shapes, exit codes) and never a quality number.

That distinction matters for the rule findings: the classifier infers a category
from the issue text, and one of the golden samples has a ``DEBUG = True`` line
that lands in the ``secrets`` bucket. Hard-coding ``tp=4, fp=1, fn=0`` would
therefore pin an inference quirk rather than the harness. Instead the expected
counts are recomputed inside the test from :func:`benchmarks.matching.match_sample`
and :func:`benchmarks.metrics.compute_metrics` over the same rule findings, and the
runner's scorecard must agree with that independent computation. The rule engine
may change its mind about a keyword; the runner may not change its arithmetic.
"""

from __future__ import annotations

import ast
import builtins
import csv
import json
import logging
from dataclasses import replace
from pathlib import Path

import pytest

from app.parser import parse_diff
from app.rules import review_diff
from benchmarks import eval as benchmark_eval
from benchmarks.loader import load_dataset
from benchmarks.matching import match_sample
from benchmarks.metrics import ModeMetrics, compute_metrics
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
from benchmarks.runner import (
    MERGED_RULES_ONLY_NOTE,
    MODE_LOCAL,
    MODE_MERGED,
    MODE_NAMES,
    MODE_RULES,
    ModeResult,
    run_all,
    run_mode,
)

#: Project root, so the dataset path does not depend on pytest's cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

#: The golden dataset root; two ``example_*`` samples.
GOLDEN = PROJECT_ROOT / "benchmarks" / "golden"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def golden_samples():
    """Load the golden dataset once per module.

    Returns:
        The two :class:`benchmarks.loader.Sample` objects, sorted by id.
    """
    return load_dataset(GOLDEN)


@pytest.fixture()
def no_local_endpoint(monkeypatch):
    """Remove every environment variable that could configure a local model.

    ``LMSTUDIO_BASE_URL`` is the switch: :func:`app.engine.select_provider` falls
    back to the rule engine when it is blank, which is the state a CI box with no
    LM Studio is in. ``LMSTUDIO_API_KEY`` is cleared too so the note under test is
    unambiguously about the base URL.
    """
    monkeypatch.delenv("LMSTUDIO_BASE_URL", raising=False)
    monkeypatch.delenv("LMSTUDIO_API_KEY", raising=False)


@pytest.fixture()
def report_results(no_local_endpoint):
    """Run all three modes over the golden dataset with no local endpoint.

    Returns:
        The ``{mode: ModeResult}`` mapping: one scored mode and two that report
        the rules-only / skipped outcomes.
    """
    return run_all(list(MODE_NAMES), dataset_root=GOLDEN)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _expected_rules_metrics(samples) -> ModeMetrics:
    """Recompute the rules scorecard from scratch, outside the runner.

    Args:
        samples: The samples the runner scored.

    Returns:
        The scorecard that :func:`benchmarks.metrics.compute_metrics` produces
        for the rule findings of every sample, with a placeholder latency (the
        runner's real timings are not reproducible and are not compared here).
    """
    results = []
    for sample in samples:
        findings = list(review_diff(parse_diff(sample.diff_text, source=sample.id)))
        results.append(match_sample(sample, findings))
    return compute_metrics(results, [1.0] * len(results))


def _without_latency(metrics: ModeMetrics) -> ModeMetrics:
    """Blank the timing fields so two scorecards can be compared for equality.

    Args:
        metrics: Any scorecard.

    Returns:
        A copy with ``latency_p50`` and ``latency_p95`` zeroed — wall-clock time
        is the one field two runs of the same work cannot share.
    """
    return replace(metrics, latency_p50=0.0, latency_p95=0.0)


# --------------------------------------------------------------------------- #
# Mode: rules
# --------------------------------------------------------------------------- #


def test_rules_mode_scores_every_sample(golden_samples):
    """The always-available mode scores both samples and skips none."""
    result = run_mode(MODE_RULES, golden_samples, dataset_root=GOLDEN)

    assert isinstance(result, ModeResult)
    assert result.mode == MODE_RULES
    assert result.samples == 2
    assert result.skipped == 0


def test_rules_mode_counts_match_independent_recomputation(golden_samples):
    """Confusion counts equal a from-scratch match + aggregate, not a literal.

    The expectation is computed here from
    :func:`benchmarks.matching.match_sample` and
    :func:`benchmarks.metrics.compute_metrics` rather than written as constants,
    because the rule engine's category inference — and therefore the number of
    unmatched findings — is free to change without the runner being wrong.
    """
    expected = _expected_rules_metrics(golden_samples)
    result = run_mode(MODE_RULES, golden_samples, dataset_root=GOLDEN)

    assert (result.metrics.tp, result.metrics.fp, result.metrics.fn) == (
        expected.tp,
        expected.fp,
        expected.fn,
    )
    assert result.metrics.tn == expected.tn
    # Every label the two examples carry must be reproduced by some rule: a rule
    # engine that misses a label on a *format example* is a broken harness.
    assert result.metrics.fn == 0
    # And the counts must be arithmetically consistent with the ratios reported
    # beside them, which is the property a reader relies on.
    assert result.metrics.tp + result.metrics.fp >= result.metrics.tp
    if result.metrics.tp + result.metrics.fp:
        assert result.metrics.precision == pytest.approx(
            result.metrics.tp / (result.metrics.tp + result.metrics.fp), abs=1e-4
        )


def test_rules_mode_reports_the_format_example_caveat(golden_samples):
    """The note discloses that both scored samples are format examples."""
    result = run_mode(MODE_RULES, golden_samples, dataset_root=GOLDEN)

    assert result.note
    assert "format example" in result.note


# --------------------------------------------------------------------------- #
# Mode: local
# --------------------------------------------------------------------------- #


def test_local_mode_skips_cleanly_without_an_endpoint(golden_samples, no_local_endpoint):
    """No ``LMSTUDIO_BASE_URL`` means a clean skip, never an exception."""
    result = run_mode(MODE_LOCAL, golden_samples, dataset_root=GOLDEN)

    assert result.mode == MODE_LOCAL
    assert result.samples == 0
    assert result.skipped == 2


def test_local_skip_metrics_are_all_zero(golden_samples, no_local_endpoint):
    """A skipped mode reports zeros, not the conventional precision of 1.0."""
    metrics = run_mode(MODE_LOCAL, golden_samples, dataset_root=GOLDEN).metrics

    assert (metrics.tp, metrics.fp, metrics.fn, metrics.tn) == (0, 0, 0, 0)
    assert metrics.precision == 0.0
    assert metrics.recall == 0.0
    assert metrics.f1 == 0.0
    assert metrics.fpr == 0.0
    assert metrics.latency_p50 == 0.0
    assert metrics.latency_p95 == 0.0
    assert metrics.per_category == {}


def test_local_skip_note_names_the_missing_variable(golden_samples, no_local_endpoint):
    """The note says which variable to set, so the skip is actionable."""
    result = run_mode(MODE_LOCAL, golden_samples, dataset_root=GOLDEN)

    assert "LMSTUDIO_BASE_URL" in result.note
    assert result.note.startswith("skipped:")


# --------------------------------------------------------------------------- #
# Mode: merged
# --------------------------------------------------------------------------- #


def test_merged_mode_without_local_is_rules_only(golden_samples, no_local_endpoint):
    """The merged note is exactly the documented constant."""
    result = run_mode(MODE_MERGED, golden_samples, dataset_root=GOLDEN)

    assert result.note == MERGED_RULES_ONLY_NOTE
    assert result.note == "local unavailable; merged is rules-only"
    assert result.samples == 2
    assert result.skipped == 0


def test_merged_metrics_equal_the_rules_run(golden_samples, no_local_endpoint):
    """Rules-only merged reproduces the rules scorecard, timing aside."""
    rules = run_mode(MODE_RULES, golden_samples, dataset_root=GOLDEN)
    merged = run_mode(MODE_MERGED, golden_samples, dataset_root=GOLDEN)

    assert _without_latency(merged.metrics) == _without_latency(rules.metrics)


# --------------------------------------------------------------------------- #
# Runner plumbing
# --------------------------------------------------------------------------- #


def test_every_mode_name_returns_a_result(golden_samples, no_local_endpoint):
    """Each mode name yields a ModeResult whose counts partition the dataset."""
    for mode in MODE_NAMES:
        result = run_mode(mode, golden_samples, dataset_root=GOLDEN)

        assert isinstance(result, ModeResult)
        assert result.mode == mode
        assert result.samples + result.skipped == len(golden_samples)


def test_unknown_mode_is_a_programming_error(golden_samples):
    """An unrecognised mode name raises rather than silently scoring nothing."""
    with pytest.raises(ValueError):
        run_mode("sarvam", golden_samples, dataset_root=GOLDEN)


def test_run_all_preserves_request_order(no_local_endpoint):
    """``run_all`` keys its dict in the order the modes were asked for."""
    results = run_all([MODE_RULES, MODE_LOCAL], dataset_root=GOLDEN)

    assert list(results) == [MODE_RULES, MODE_LOCAL]
    assert results[MODE_RULES].samples == 2
    assert results[MODE_LOCAL].skipped == 2


# --------------------------------------------------------------------------- #
# Report writers
# --------------------------------------------------------------------------- #


def test_write_csv_has_one_row_per_mode(report_results, tmp_path):
    """The CSV parses with DictReader and carries a row for every mode."""
    path = write_csv(report_results, tmp_path)

    assert path == tmp_path / CSV_NAME
    assert path.exists()
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == len(report_results)
    assert {row["mode"] for row in rows} == set(report_results)
    assert {"mode", "samples", "skipped", "precision", "recall", "f1", "note"} <= set(
        rows[0]
    )


def test_write_summary_json_carries_provenance_and_notes(report_results, tmp_path):
    """The JSON names its generator and keeps each mode's note."""
    path = write_summary_json(report_results, tmp_path)

    assert path == tmp_path / JSON_NAME
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["generated_by"] == "benchmarks.eval"
    assert set(payload["modes"]) == set(report_results)
    assert payload["modes"][MODE_MERGED]["note"] == MERGED_RULES_ONLY_NOTE
    assert "LMSTUDIO_BASE_URL" in payload["modes"][MODE_LOCAL]["note"]


def test_write_summary_md_has_a_table_row_per_mode(report_results, tmp_path):
    """The Markdown summary contains one mode-table row per mode."""
    path = write_summary_md(report_results, tmp_path)

    assert path == tmp_path / MD_NAME
    text = path.read_text(encoding="utf-8")

    assert "| Mode |" in text
    for mode in report_results:
        assert any(line.startswith(f"| {mode} |") for line in text.splitlines())


def test_write_chart_degrades_without_matplotlib(
    report_results, tmp_path, monkeypatch, caplog
):
    """A missing matplotlib is one WARNING and no file, not a failed report."""
    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name == "matplotlib" or name.startswith("matplotlib."):
            raise ImportError("matplotlib blocked for this test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)
    caplog.set_level(logging.WARNING, logger="benchmarks.report")

    path = write_chart(report_results, tmp_path)

    assert path == tmp_path / CHART_NAME
    assert not path.exists()
    warnings = [
        record
        for record in caplog.records
        if record.name == "benchmarks.report" and record.levelno == logging.WARNING
    ]
    assert len(warnings) == 1
    assert "matplotlib" in warnings[0].getMessage()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def test_eval_main_reports_a_dataset_error(tmp_path):
    """A missing dataset root is exit code 2, not a traceback."""
    assert benchmark_eval.main(["--dataset", "/nonexistent", "--modes", "rules"]) == 2


def test_eval_main_writes_every_artifact(tmp_path):
    """A real run exits 0 and leaves the four artifacts behind."""
    code = benchmark_eval.main(
        [
            "--dataset",
            str(GOLDEN),
            "--modes",
            "rules",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )

    assert code == 0
    for name in (CSV_NAME, JSON_NAME, MD_NAME):
        assert (tmp_path / name).exists(), name
    # The chart is optional by design; assert it only where matplotlib exists.
    try:
        import matplotlib  # noqa: F401
    except ImportError:  # pragma: no cover - depends on the machine
        assert not (tmp_path / CHART_NAME).exists()
    else:
        assert (tmp_path / CHART_NAME).exists()


# --------------------------------------------------------------------------- #
# Package isolation
# --------------------------------------------------------------------------- #


def _imported_modules(tree: ast.AST) -> set[str]:
    """Collect every dotted module name an AST imports.

    Handles ``import a.b``, ``from a.b import c`` and ``from a import b`` — the
    last form spelled out to ``a.b`` so a package-level import of a submodule is
    caught as well.

    Args:
        tree: A parsed module.

    Returns:
        Module names, e.g. ``{"app.rules", "app.main"}``.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            found.add(module)
            if module:
                found.update(f"{module}.{alias.name}" for alias in node.names)
            else:  # pragma: no cover - relative imports carry a level instead
                found.update(alias.name for alias in node.names)
    return found


def test_benchmarks_never_import_the_app_entry_points():
    """The harness measures the engine, not the HTTP surface.

    A benchmark module that imported ``app.main`` or ``app.cli`` would boot the
    server into the measurement; this walks the package's ASTs and forbids it.
    """
    files = sorted((PROJECT_ROOT / "benchmarks").glob("*.py"))
    assert files, "no benchmark modules found to inspect"

    offenders: dict[str, set[str]] = {}
    for path in files:
        modules = _imported_modules(ast.parse(path.read_text(encoding="utf-8")))
        banned = {
            name
            for name in modules
            if name == "app.main"
            or name.startswith("app.main.")
            or name == "app.cli"
            or name.startswith("app.cli.")
        }
        if banned:
            offenders[path.name] = banned

    assert offenders == {}
