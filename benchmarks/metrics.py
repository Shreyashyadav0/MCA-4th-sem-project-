"""Aggregate a run's per-sample match results into one mode's scorecard.

:mod:`benchmarks.matching` answers "which labels did the reviewer reproduce in this
one sample?". This module answers the question a benchmark actually reports: over
the whole run, how precise and how fast is a review mode?

The whole module is pure. It reads no files, writes no logs, mutates no global, and
depends on nothing but the counts already present in the
:class:`~benchmarks.matching.MatchResult` values it is handed — so the same inputs
always produce an equal :class:`ModeMetrics`, and the numbers are reproducible
without a filesystem, a clock or a network.

Confusion counts
----------------
Every count is a plain sum over the supplied results:

    tp = sum(result.tp)              matched labels
    fp = sum(result.fp)              findings no label asked for
    fn = sum(result.fn)              labels no finding reproduced
    tn = sum(result.true_negatives)  samples with no labels and no findings

``true_negatives`` is per sample, not per label: a sample is a true negative when
it is labelled clean and the reviewer reported nothing. That is why ``tn`` moves in
steps of one sample while ``tp``/``fp``/``fn`` move in steps of one finding.

Zero-denominator conventions
----------------------------
Ratios with an empty denominator are **0.0, not an error and not ``nan``** — one
degenerate sample must never crash a benchmark run, and a ``nan`` would poison
every average downstream. There is exactly one documented exception, precision,
because "reported nothing" and "reported only wrong things" are different failures
and collapsing them would let a silent reviewer look perfect.

===================  ==================  ==========================================
Metric               Denominator         Value when the denominator is 0
===================  ==================  ==========================================
``precision``        ``tp + fp``         **1.0** — the single exception (see below)
``recall``           ``tp + fn``         ``0.0``
``f1``               ``precision + recall``  ``0.0``
``fpr``              ``fp + tn``         ``0.0``
``latency_p50``      ``n`` (sample count)  ``0.0``
``latency_p95``      ``n`` (sample count)  ``0.0``
===================  ==================  ==========================================

The precision exception, spelled out
    ``precision = 1.0`` whenever ``tp + fp == 0``, i.e. whenever the mode reported
    *nothing at all*, irrespective of how many labels it missed. That is the
    conventional reading of "of the findings you made, none were wrong", and it
    keeps precision well defined for a clean dataset where no finding could ever
    be a false positive.

    It is **not** a statement that the mode did well. Read it next to ``recall``:
    a mode that reports nothing scores ``precision = 1.0`` and ``recall = 0.0``,
    and its ``f1`` is ``0.0`` — the harmonic mean of 1.0 and 0.0 is zero, so the
    exception cannot leak into a headline score. A report must therefore never
    quote precision on its own; the pair (precision, recall) is the honest unit.
    The precise rule, for ``tp + fp == 0``:

    * nothing reported, labels exist (``fn > 0``): ``1.0`` — deliberate, and
      flagged by ``recall == 0.0`` and ``f1 == 0.0``.
    * nothing reported, no labels (``fn == 0``): ``1.0`` — genuinely vacuous.

Rounding
--------
The four ratios are rounded to 4 decimal places. ``f1`` is computed from the
*unrounded* precision and recall and only then rounded, so it is the harmonic mean
of the true ratios rather than of their rounded shadows. Python's :func:`round`
rounds half to even; at 4 decimal places that is far below any decision the
benchmark makes, and it is deterministic, which is what matters here.

Latency percentiles
-------------------
Latencies are caller-supplied floats in whatever unit the caller used — the
harness passes **milliseconds** — and are returned in that same unit, rounded to 3
decimal places and no further, so a 12.5 ms measurement stays 12.5.

Percentiles use the **nearest-rank** method, the standard for latency reporting
because it always returns an observed measurement instead of an interpolated
value that no request actually took::

    rank = ceil(p / 100 * n) - 1        # 0-based, clamped to [0, n - 1]

Two consequences are worth stating because they surprise people:

* **p95 of 3 samples is the largest sample.** ``ceil(0.95 * 3) - 1 = 2``, the last
  element. With fewer than 20 samples p95 carries no information beyond the
  maximum, and with a handful of samples it is simply the worst case.
* **p50 of an even count is the lower middle sample**, not the mean of the two
  middle ones — ``ceil(0.5 * 4) - 1 = 1`` gives the second of four. With two
  samples p50 is the smaller of them, so a two-sample p50 is not a midpoint.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from benchmarks.matching import CategoryScore, MatchResult

__all__ = ["ModeMetrics", "compute_metrics", "percentile", "RATIO_PRECISION", "LATENCY_PRECISION"]

#: Decimal places kept on ``precision``/``recall``/``f1``/``fpr``.
RATIO_PRECISION = 4

#: Decimal places kept on ``latency_p50``/``latency_p95``.
LATENCY_PRECISION = 3


@dataclass(frozen=True)
class ModeMetrics:
    """One review mode's scorecard over a whole run.

    Frozen so a computed scorecard can be shared, cached or put in a dict without
    any risk of a later stage quietly editing a number that has already been
    reported. Field order follows ``benchmarks/CONTRACT.md``.

    Attributes:
        precision: ``tp / (tp + fp)``, rounded to 4 places; ``1.0`` when nothing
            was reported at all — see the module docstring's conventions table,
            which explains why that exception cannot be read as a good score.
        recall: ``tp / (tp + fn)``, rounded to 4 places; ``0.0`` when there were
            no labels.
        f1: Harmonic mean of the unrounded ``precision`` and ``recall``, rounded
            to 4 places; ``0.0`` when both are zero.
        fpr: ``fp / (fp + tn)``, rounded to 4 places; ``0.0`` when there were
            neither false positives nor true negatives. Because ``tn`` counts
            clean *samples* rather than findings, a run over labelled-only data
            has ``tn == 0`` and therefore ``fpr == 1.0`` as soon as one finding
            is unmatched — the ratio needs clean samples to mean anything, and
            ``tn == 0`` is the flag that it does not.
        tp: True positives — labels a finding reproduced, summed over samples.
        fp: False positives — findings no label asked for, summed over samples.
        fn: False negatives — labels no finding reproduced, summed over samples.
        tn: True negatives — samples that were labelled clean and drew no finding.
        per_category: Confusion counts merged across every result and keyed by
            category, sorted by key. A category present in any result appears
            here even if its counts are all zero.
        latency_p50: Nearest-rank 50th percentile of the supplied latencies, in
            the caller's unit (milliseconds), rounded to 3 places; ``0.0`` for an
            empty sample.
        latency_p95: Nearest-rank 95th percentile, same unit and rounding; with
            fewer than 20 samples this is effectively the maximum.
    """

    precision: float
    recall: float
    f1: float
    fpr: float
    tp: int
    fp: int
    fn: int
    tn: int
    per_category: dict[str, CategoryScore] = field(default_factory=dict)
    latency_p50: float = 0.0
    latency_p95: float = 0.0


def percentile(values: Sequence[float], percent: float) -> float:
    """Nearest-rank percentile of ``values``.

    The rank is ``ceil(percent / 100 * n) - 1``, clamped into ``[0, n - 1]``, so
    the result is always one of the observed values and never an interpolation
    between two of them. ``percent = 0`` therefore yields the minimum and
    ``percent = 100`` the maximum.

    Args:
        values: The measurements, in any order; the input is not modified.
        percent: The percentile to take, in ``[0, 100]``. Values outside that
            range are clamped by the rank clamp rather than raising, so a caller
            computing a rank from a fraction cannot crash a run.

    Returns:
        The selected measurement, unrounded. ``0.0`` when ``values`` is empty —
        there is no observation to report, and ``0.0`` is the documented stand-in
        that keeps averages downstream finite.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = math.ceil(percent / 100 * len(ordered)) - 1
    index = min(max(rank, 0), len(ordered) - 1)
    return float(ordered[index])


def _ratio(numerator: float, denominator: float, *, empty: float) -> float:
    """Divide, returning the documented convention when the denominator is zero.

    Args:
        numerator: Quantity on top of the fraction — a count, or for ``f1`` the
            already-computed ``2 * precision * recall``.
        denominator: Quantity underneath it.
        empty: Value to return when ``denominator`` is zero, per the module's
            conventions table.

    Returns:
        The unrounded ratio, or ``empty``.
    """
    if denominator == 0:
        return empty
    return numerator / denominator


def _merge_categories(results: Sequence[MatchResult]) -> dict[str, CategoryScore]:
    """Sum the per-category counts of every result into one sorted mapping.

    Categories are merged by key, so a label category seen in one sample and a
    finding category inferred in another land in the same bucket. Keys that only
    ever carry zeros are kept: they record that the category was *expected* in the
    run, which the report needs in order to show a category at 0% rather than
    omitting it.

    Args:
        results: The per-sample match results.

    Returns:
        A new dict keyed by category in ascending sort order, with fresh
        :class:`~benchmarks.matching.CategoryScore` values. Empty when no result
        carried any category.
    """
    totals: dict[str, list[int]] = {}
    for result in results:
        for category, score in result.per_category.items():
            running = totals.get(category)
            if running is None:
                totals[category] = [score.tp, score.fp, score.fn]
            else:
                running[0] += score.tp
                running[1] += score.fp
                running[2] += score.fn
    return {
        category: CategoryScore(tp=tp, fp=fp, fn=fn)
        for category, (tp, fp, fn) in sorted(totals.items())
    }


def compute_metrics(
    results: Sequence[MatchResult],
    latencies: Sequence[float],
) -> ModeMetrics:
    """Aggregate per-sample match results and per-sample timings into a scorecard.

    Counts are summed over ``results``; the ratios are derived from those totals,
    never averaged per sample, so a sample with ten labels weighs what its labels
    weigh and not one-tenth of the run.

    Zero-denominator conventions (the full table is in the module docstring):
    ``precision`` is ``1.0`` when ``tp + fp == 0`` — the mode reported nothing —
    and every other ratio is ``0.0`` when its own denominator is zero. The
    precision exception is why the scorecard must be read as a (precision, recall)
    pair: a silent mode shows ``precision = 1.0`` beside ``recall = 0.0`` and
    ``f1 = 0.0``.

    Args:
        results: The match results of one mode, one per scored sample. An empty
            sequence is legal and yields an all-zero scorecard with
            ``precision = 1.0``, which the ``f1 = 0.0`` immediately qualifies.
        latencies: One elapsed time per scored sample, in milliseconds. Length is
            not required to match ``results`` — a caller may time a subset — but
            the two are reported side by side, so a mismatch is worth a look at
            the call site. An empty sequence gives ``0.0`` for both percentiles.

    Returns:
        The frozen :class:`ModeMetrics` for this mode. Ratios are rounded to 4
        decimal places, ``f1`` having been computed from the unrounded pair;
        percentiles keep 3 decimal places and the caller's unit.
    """
    tp = sum(result.tp for result in results)
    fp = sum(result.fp for result in results)
    fn = sum(result.fn for result in results)
    tn = sum(result.true_negatives for result in results)

    precision = _ratio(tp, tp + fp, empty=1.0)
    recall = _ratio(tp, tp + fn, empty=0.0)
    fpr = _ratio(fp, fp + tn, empty=0.0)
    # Harmonic mean of the unrounded pair; 0.0 when both are zero, so a mode that
    # reported nothing scores f1 = 0.0 despite its conventional precision of 1.0.
    f1 = _ratio(2 * precision * recall, precision + recall, empty=0.0)

    return ModeMetrics(
        precision=round(precision, RATIO_PRECISION),
        recall=round(recall, RATIO_PRECISION),
        f1=round(f1, RATIO_PRECISION),
        fpr=round(fpr, RATIO_PRECISION),
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        per_category=_merge_categories(results),
        latency_p50=round(percentile(latencies, 50.0), LATENCY_PRECISION),
        latency_p95=round(percentile(latencies, 95.0), LATENCY_PRECISION),
    )
