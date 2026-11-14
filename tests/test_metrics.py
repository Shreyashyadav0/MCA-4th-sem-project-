"""Offline unit tests for :mod:`benchmarks.metrics`.

The arithmetic here is *hand-computed*, never copied from a run: every expected
number in this file can be checked with a pencil from the counts stated in the
test's name or docstring. That is the point — a metrics module that is only
tested against its own output pins nothing, because a wrong formula reproduces
itself perfectly.

Two fixtures are used:

* :func:`make_result` builds a :class:`~benchmarks.matching.MatchResult` with an
  exact ``tp``/``fp``/``fn``/``tn`` by padding the tuples the counts are derived
  from. ``compute_metrics`` reads only those counts and ``per_category``, so the
  padding's identities are irrelevant — which is what makes the confusion-matrix
  cases in this file readable.
* :func:`test_metrics_over_real_match_results` goes through
  :func:`~benchmarks.matching.match_sample` instead, so at least one case proves
  the numbers survive a real matching pass rather than only synthetic counts.

The conventions asserted here are the ones the module documents at length, and
each is commented at the assertion that depends on it: ``precision = 1.0`` when
nothing was reported (the single zero-denominator exception), every other ratio
``0.0`` on an empty denominator, nearest-rank percentiles, and ``f1`` computed
from the *unrounded* precision/recall pair.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.models import Finding, Severity
from benchmarks.loader import ExpectedFinding, Sample
from benchmarks.matching import CategoryScore, Match, MatchResult, match_sample
from benchmarks.metrics import (
    LATENCY_PRECISION,
    RATIO_PRECISION,
    ModeMetrics,
    compute_metrics,
    percentile,
)

FILE = "app/users.py"


def make_label(
    line_start: int,
    line_end: int | None = None,
    *,
    category: str = "injection",
    file: str = FILE,
) -> ExpectedFinding:
    """Build one label; only its position and category matter to ``metrics``.

    Args:
        line_start: First new-side line, inclusive.
        line_end: Last new-side line, inclusive; defaults to ``line_start``.
        category: Labelled category.
        file: Path the label refers to.

    Returns:
        A frozen :class:`~benchmarks.loader.ExpectedFinding`.
    """
    return ExpectedFinding(
        file=file,
        line_start=line_start,
        line_end=line_start if line_end is None else line_end,
        category=category,
        severity="HIGH",
    )


def make_finding(line: str, *, issue: str = "sql injection via concatenation") -> Finding:
    """Build one finding, anchored at ``line``.

    Args:
        line: The finding's ``line`` field, ``"42"`` or ``"42-45"``.
        issue: Prose; irrelevant to ``metrics``, which never reads it.

    Returns:
        A frozen :class:`app.models.Finding`.
    """
    return Finding(
        file=FILE,
        line=line,
        severity=Severity.HIGH,
        issue=issue,
        suggested_fix="apply the documented fix",
    )


def make_result(
    tp: int = 0,
    fp: int = 0,
    fn: int = 0,
    tn: int = 0,
    *,
    per_category: dict[str, CategoryScore] | None = None,
) -> MatchResult:
    """Build a match result carrying exactly these confusion counts.

    ``MatchResult.tp``/``fp``/``fn`` are properties over the lengths of
    ``matched``/``false_positives``/``false_negatives``, so the counts are
    produced by padding those tuples with distinct, meaningless entries. Nothing
    downstream reads their file, line or category — ``compute_metrics`` sums the
    counts and merges ``per_category`` — which is why the padding is safe and the
    test stays about arithmetic.

    Args:
        tp: Matched labels to synthesise.
        fp: Unmatched findings to synthesise.
        fn: Unmatched labels to synthesise.
        tn: The ``true_negatives`` flag to record.
        per_category: Per-category counts to attach, or ``None`` for none.

    Returns:
        A :class:`~benchmarks.matching.MatchResult` with the requested counts.
    """
    matched = tuple(
        Match(
            expected=make_label(10 + index),
            actual=make_finding(str(10 + index)),
            overlap=1,
        )
        for index in range(tp)
    )
    false_positives = tuple(make_label(500 + index) for index in range(fp))
    false_negatives = tuple(make_label(900 + index) for index in range(fn))
    return MatchResult(
        matched=matched,
        false_positives=false_positives,
        false_negatives=false_negatives,
        true_negatives=tn,
        per_category={} if per_category is None else per_category,
    )


# --------------------------------------------------------------------------- #
# Confusion counts -> ratios, hand-computed
# --------------------------------------------------------------------------- #


def test_hand_computed_counts_produce_the_expected_four_ratios() -> None:
    """tp=3, fp=1, fn=2, tn=4 scores 0.75 / 0.6 / 0.6667 / 0.2.

    precision = 3 / (3 + 1) = 0.75
    recall    = 3 / (3 + 2) = 0.6
    f1        = 2 * 0.75 * 0.6 / (0.75 + 0.6) = 0.9 / 1.35 = 0.66666... -> 0.6667
    fpr       = 1 / (1 + 4) = 0.2
    """
    metrics = compute_metrics([make_result(tp=3, fp=1, fn=2, tn=4)], [])

    assert (metrics.tp, metrics.fp, metrics.fn, metrics.tn) == (3, 1, 2, 4)
    assert metrics.precision == 0.75
    assert metrics.recall == 0.6
    assert metrics.f1 == 0.6667
    assert metrics.fpr == 0.2


def test_perfect_run_scores_one_and_no_false_positive_rate() -> None:
    """tp=2, fp=0, fn=0, tn=5 is a perfect run: 1.0 / 1.0 / 1.0 / 0.0."""
    metrics = compute_metrics([make_result(tp=2, fp=0, fn=0, tn=5)], [])

    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0
    # fpr = 0 / (0 + 5) = 0.0 — the honest zero, not the empty-denominator one.
    assert metrics.fpr == 0.0


def test_all_wrong_run_has_zero_precision_zero_recall_and_fpr_of_one() -> None:
    """tp=0, fp=3, fn=2, tn=0: everything reported was wrong and nothing was found.

    fpr is asserted as the *implemented* formula, ``fp / (fp + tn)``, not as a
    percentage of clean samples: with ``tn == 0`` the denominator is the three
    false positives alone, so ``3 / (3 + 0) == 1.0``. That 1.0 means "every
    reported finding was wrong", not "every clean sample was flagged" — the
    ratio only means the latter once the dataset contains labelled-clean
    samples, which is exactly what ``tn == 0`` flags as missing.
    """
    metrics = compute_metrics([make_result(tp=0, fp=3, fn=2, tn=0)], [])

    assert metrics.precision == 0.0
    assert metrics.recall == 0.0
    # f1 = 0.0: the harmonic mean of two zeros has an empty denominator.
    assert metrics.f1 == 0.0
    assert metrics.fpr == 1.0


def test_nothing_reported_scores_precision_one_by_the_documented_exception() -> None:
    """tp=0, fp=0, fn=2, tn=5: the mode said nothing, so precision is 1.0.

    This is the module's single documented exception: with ``tp + fp == 0``
    precision is **1.0**, not 0.0 — "of the findings you made, none were wrong".
    It must be read beside ``recall == 0.0`` and ``f1 == 0.0``, which is why both
    are asserted here: the exception cannot leak into a headline score.
    """
    metrics = compute_metrics([make_result(tp=0, fp=0, fn=2, tn=5)], [])

    assert metrics.precision == 1.0
    assert metrics.recall == 0.0
    assert metrics.f1 == 0.0


def test_nothing_reported_and_nothing_labelled_is_vacuously_precise() -> None:
    """A fully vacuous run (no labels, no findings, only clean samples) is 1.0 / 0.0.

    With ``fn == 0`` as well, recall's denominator is empty and takes its own
    convention of 0.0, so even the vacuous case reports a (1.0, 0.0) pair rather
    than a meaningless perfect score.
    """
    metrics = compute_metrics([make_result(tn=4)], [])

    assert metrics.precision == 1.0
    assert metrics.recall == 0.0
    assert metrics.f1 == 0.0
    assert metrics.fpr == 0.0
    assert metrics.tn == 4


def test_empty_result_sequence_is_all_zero_except_the_precision_exception() -> None:
    """No results at all: every count is 0 and only precision is 1.0.

    An empty run is legal — the caller may have scored nothing — and must not
    raise or produce ``nan``, which would poison every downstream average.
    """
    metrics = compute_metrics([], [])

    assert (metrics.tp, metrics.fp, metrics.fn, metrics.tn) == (0, 0, 0, 0)
    assert metrics.precision == 1.0
    assert (metrics.recall, metrics.f1, metrics.fpr) == (0.0, 0.0, 0.0)
    assert metrics.per_category == {}
    assert (metrics.latency_p50, metrics.latency_p95) == (0.0, 0.0)


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #


def test_counts_sum_over_results_and_ratios_are_not_averaged_per_sample() -> None:
    """One sample with 3 labels and one with 10 missed labels weigh 3 and 10.

    A per-sample average of recall would report ``(1.0 + 0.0) / 2 == 0.5``; the
    pooled total is ``3 / (3 + 10) == 0.2308``, which is the honest number.
    """
    metrics = compute_metrics(
        [
            make_result(tp=3, fp=0, fn=0),
            make_result(tp=0, fp=0, fn=10),
        ],
        [],
    )

    assert (metrics.tp, metrics.fp, metrics.fn) == (3, 0, 10)
    assert metrics.precision == 1.0
    assert metrics.recall == 0.2308
    assert metrics.recall != 0.5


def test_true_negatives_count_samples_not_labels() -> None:
    """``tn`` sums the per-sample flag, so two clean samples are ``tn == 2``.

    ``fpr = fp / (fp + tn)`` therefore mixes finding counts with sample counts,
    which is why it is only meaningful on a dataset with labelled-clean samples.
    Here ``1 / (1 + 2) = 0.3333``.
    """
    metrics = compute_metrics(
        [make_result(tn=1), make_result(tp=1, fp=1, tn=1)],
        [],
    )

    assert metrics.tn == 2
    assert metrics.fpr == 0.3333


def test_f1_is_the_harmonic_mean_of_the_unrounded_pair() -> None:
    """tp=7, fp=3, fn=5 rounds differently if f1 is taken from rounded inputs.

    Unrounded: p = 0.7, r = 7/12 = 0.583333..., f1 = 0.9/1.283333... = 0.636363...
    -> 0.6364. Rounding first gives 2*0.7*0.5833/1.2833 = 0.636343 -> 0.6363, one
    unit off in the last place, so this pins the documented ordering.
    """
    metrics = compute_metrics([make_result(tp=7, fp=3, fn=5)], [])

    assert metrics.precision == 0.7
    assert metrics.recall == 0.5833
    assert metrics.f1 == 0.6364


def test_per_category_counts_merge_across_two_match_results() -> None:
    """Categories are summed by key across results, not kept per result.

    ``injection`` appears in both results (tp 2 + 1, fn 0 + 1) and ``quality``
    only in the second, so the merged map has exactly two keys in sorted order.
    """
    first = make_result(
        tp=2,
        fn=0,
        per_category={"injection": CategoryScore(tp=2, fp=0, fn=0)},
    )
    second = make_result(
        tp=1,
        fp=1,
        fn=2,
        per_category={
            "injection": CategoryScore(tp=1, fp=0, fn=1),
            "quality": CategoryScore(tp=0, fp=1, fn=1),
        },
    )

    metrics = compute_metrics([first, second], [])

    assert list(metrics.per_category) == ["injection", "quality"]
    merged = metrics.per_category["injection"]
    assert (merged.tp, merged.fp, merged.fn) == (3, 0, 1)
    quality = metrics.per_category["quality"]
    assert (quality.tp, quality.fp, quality.fn) == (0, 1, 1)
    # The merged map reconciles with the scalar totals.
    assert sum(score.tp for score in metrics.per_category.values()) == metrics.tp
    assert sum(score.fp for score in metrics.per_category.values()) == metrics.fp
    assert sum(score.fn for score in metrics.per_category.values()) == metrics.fn


def test_per_category_keeps_a_category_that_only_ever_carries_zeros() -> None:
    """A zero-only category is preserved, so a report can show it at 0%."""
    metrics = compute_metrics(
        [make_result(per_category={"style": CategoryScore()})],
        [],
    )

    assert metrics.per_category == {"style": CategoryScore(tp=0, fp=0, fn=0)}


def test_metrics_over_real_match_results() -> None:
    """End-to-end: two samples through ``match_sample`` score 0.6667 / 0.6667 / 0.5.

    Sample ``a``: a label on lines 10-12 matched by a finding, and a ``quality``
    label on 20-22 with nothing on it -> tp=1, fn=1.
    Sample ``b``: labelled clean, no findings -> tn=1.
    Sample ``c``: a ``secrets`` label matched, plus an unasked-for ``quality``
    finding on 50-51 -> tp=1, fp=1.

    Pooled: tp=2, fp=1, fn=1, tn=1 -> precision 2/3, recall 2/3, f1 2/3,
    fpr 1/(1+1) = 0.5.
    """
    sample_a = Sample(
        id="a",
        diff_text="--- a/app/users.py\n+++ b/app/users.py\n",
        expected=(
            make_label(10, 12, category="injection"),
            make_label(20, 22, category="quality"),
        ),
        meta={"format_example": False},
    )
    sample_b = Sample(
        id="b",
        diff_text="--- a/app/users.py\n+++ b/app/users.py\n",
        expected=(),
        meta={"format_example": False},
    )
    sample_c = Sample(
        id="c",
        diff_text="--- a/app/users.py\n+++ b/app/users.py\n",
        expected=(make_label(5, 5, category="secrets"),),
        meta={"format_example": False},
    )

    results = [
        match_sample(sample_a, [make_finding("10-12")]),
        match_sample(sample_b, []),
        match_sample(
            sample_c,
            [
                make_finding("5", issue="hardcoded password committed to source"),
                make_finding("50-51", issue="duplicate dead code left in the module"),
            ],
        ),
    ]
    metrics = compute_metrics(results, [1.0, 2.0, 3.0])

    assert (metrics.tp, metrics.fp, metrics.fn, metrics.tn) == (2, 1, 1, 1)
    assert metrics.precision == 0.6667
    assert metrics.recall == 0.6667
    assert metrics.f1 == 0.6667
    assert metrics.fpr == 0.5


# --------------------------------------------------------------------------- #
# Latency percentiles
# --------------------------------------------------------------------------- #


def test_nearest_rank_percentiles_of_five_samples() -> None:
    """[10, 20, 30, 40, 50] -> p50 30.0 and p95 50.0, both observed values.

    p50: ``ceil(0.5 * 5) - 1 == 2`` -> the third sample, 30.
    p95: ``ceil(0.95 * 5) - 1 == 4`` -> the fifth sample, 50. With fewer than 20
    samples p95 is effectively the maximum, which is exactly what this shows.
    """
    metrics = compute_metrics([make_result(tp=1)], [10.0, 20.0, 30.0, 40.0, 50.0])

    assert metrics.latency_p50 == 30.0
    assert metrics.latency_p95 == 50.0


def test_latency_input_order_does_not_matter() -> None:
    """Percentiles sort their input, so a shuffled sample list scores the same."""
    shuffled = compute_metrics([make_result(tp=1)], [50.0, 10.0, 40.0, 30.0, 20.0])

    assert (shuffled.latency_p50, shuffled.latency_p95) == (30.0, 50.0)


def test_single_sample_is_both_percentiles() -> None:
    """One measurement is the p50 and the p95, and keeps its 12.5 ms precision."""
    metrics = compute_metrics([make_result(tp=1)], [12.5])

    assert metrics.latency_p50 == 12.5
    assert metrics.latency_p95 == 12.5


def test_empty_latencies_give_zero_percentiles() -> None:
    """No timing -> 0.0, the documented stand-in that keeps averages finite."""
    metrics = compute_metrics([make_result(tp=1)], [])

    assert metrics.latency_p50 == 0.0
    assert metrics.latency_p95 == 0.0


def test_percentile_helper_clamps_and_returns_an_observed_value() -> None:
    """``percentile`` never interpolates: 0 -> min, 100 -> max, empty -> 0.0."""
    values = [4.0, 1.0, 3.0, 2.0]

    assert percentile(values, 0.0) == 1.0
    assert percentile(values, 100.0) == 4.0
    assert percentile(values, 50.0) == 2.0
    # Out-of-range percents are clamped by the rank, not raised on.
    assert percentile(values, -10.0) == 1.0
    assert percentile(values, 250.0) == 4.0
    assert percentile([], 50.0) == 0.0


def test_latencies_are_rounded_to_three_places() -> None:
    """A measurement is reported to ``LATENCY_PRECISION`` places and no further."""
    metrics = compute_metrics([make_result(tp=1)], [1.23456])

    assert LATENCY_PRECISION == 3
    assert metrics.latency_p50 == 1.235
    assert RATIO_PRECISION == 4


# --------------------------------------------------------------------------- #
# Shape
# --------------------------------------------------------------------------- #


def test_mode_metrics_is_frozen() -> None:
    """A scorecard cannot be edited after it has been reported."""
    metrics = compute_metrics([make_result(tp=1)], [1.0])

    with pytest.raises(FrozenInstanceError):
        metrics.precision = 0.0  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        metrics.tp = 99  # type: ignore[misc]

    assert isinstance(metrics, ModeMetrics)
    assert metrics.precision == 1.0


def test_identical_inputs_produce_an_equal_scorecard() -> None:
    """``compute_metrics`` is pure: same inputs, equal frozen result.

    Only equality is asserted, not hashing: ``ModeMetrics`` is a frozen dataclass
    whose ``per_category`` field is a plain dict, so ``__hash__`` exists but
    raises ``TypeError`` as soon as that dict is non-empty. Frozen is not the
    same promise as hashable, and this scorecard makes no claim to the latter.
    """
    results = [make_result(tp=2, fp=1, fn=1, tn=3)]
    latencies = [5.0, 6.0, 7.0]

    first = compute_metrics(results, latencies)
    second = compute_metrics(results, latencies)

    assert first == second
    assert first.per_category == second.per_category
