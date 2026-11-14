"""Run one review mode over a dataset and score it.

Three modes are benchmarked, and the difference between them is the point of the
harness:

``rules``
    The deterministic rule engine only — :func:`app.rules.review_diff` over
    :func:`app.parser.parse_diff`. It needs no configuration, no model and no
    network, so it is always available and is the baseline every other mode is
    compared against.
``local``
    The model path, routed through :func:`app.engine.select_provider` with
    ``requested="local"`` and reviewed through :func:`app.engine.review`. A local
    model needs a running OpenAI-compatible endpoint; when ``LMSTUDIO_BASE_URL``
    (or ``LMSTUDIO_API_KEY``) is not set the mode **skips cleanly** — see below.
``merged``
    The union of the rule findings and the local findings. The union is computed
    here, in the harness, and never in ``app/engine.py``: the application has no
    "merged" review mode, and inventing one there would change production
    behaviour to satisfy a benchmark. When the local endpoint is unavailable the
    merged mode is rules-only and says so in its note.

Skipping, not pretending
------------------------
A benchmark that silently substitutes the rule engine for a model reports a
number that means nothing: the scorecard would look like a local-model result
while measuring the same code path as ``rules``. So an unavailable ``local`` mode
returns ``samples=0``, ``skipped=len(samples)`` and an all-zero
:class:`~benchmarks.metrics.ModeMetrics`, with a note naming the missing
environment variable. It never raises and never fabricates a scorecard. The same
rule applies to a mid-run degradation: if the endpoint answers but the adapter
falls back to the rule engine, the mode is reported as skipped with the adapter's
own reason, because a "local" scorecard produced by the rule engine would be a
lie.

Timing
------
Every mode times each sample with :func:`time.perf_counter` and passes those
per-sample latencies, in **milliseconds**, to
:func:`benchmarks.metrics.compute_metrics`. The clock wraps the whole per-sample
work of that mode — parse plus review — because that is the cost a user waits
for. For ``merged`` the single span covers both the rule pass and the local pass,
so its latency is the honest cost of producing the merged findings rather than
either half of it.

Determinism
-----------
Samples arrive sorted by id from the loader, findings are de-duplicated and sorted
by ``(file, line start, line end, -severity rank, issue)``, and :func:`run_all`
returns a dict in the order the modes were requested. Two runs over the same
dataset therefore produce the same scorecards in the same order.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.engine import ProviderSelection, review, select_provider
from app.models import Finding
from app.parser import DiffBundle, parse_diff
from app.rules import review_diff
from benchmarks.loader import Sample
from benchmarks.matching import MatchResult, match_sample
from benchmarks.metrics import ModeMetrics, compute_metrics

__all__ = [
    "MODE_NAMES",
    "MODE_LOCAL",
    "MODE_MERGED",
    "MODE_RULES",
    "MERGED_RULES_ONLY_NOTE",
    "ModeResult",
    "run_mode",
    "run_all",
]

logger = logging.getLogger(__name__)

MODE_RULES: str = "rules"
"""Deterministic rule engine only; always available."""

MODE_LOCAL: str = "local"
"""Self-hosted OpenAI-compatible model; skipped when unconfigured."""

MODE_MERGED: str = "merged"
"""Union of rule findings and local findings, de-duplicated here."""

MODE_NAMES: tuple[str, ...] = (MODE_RULES, MODE_LOCAL, MODE_MERGED)
"""Every mode name, in the order the CLI lists them."""

MERGED_RULES_ONLY_NOTE: str = "local unavailable; merged is rules-only"
"""The exact note ``merged`` carries when the local endpoint cannot be reached."""

#: A rule and a model routinely describe one defect in slightly different prose,
#: so the union key is the contract's structural key and nothing more.
FindingKey = tuple[str, str, str, str]


class _LocalDegraded(RuntimeError):
    """The local endpoint answered with a rule-engine fallback instead of a model.

    Raised inside a scoring loop so the loop stops at the first degraded sample
    instead of paying one endpoint timeout per remaining sample.

    Attributes:
        reason: The adapter's own one-line explanation for the degradation.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ModeResult:
    """One mode's outcome for a whole run, scored or skipped.

    Frozen so a result can be cached, shared or put in a dict without a later
    stage quietly editing a number that has already been reported. Field order
    follows ``benchmarks/CONTRACT.md``.

    Attributes:
        mode: One of :data:`MODE_NAMES`.
        metrics: The scorecard, or an all-zero scorecard when the mode was
            skipped. Zero rather than absent: a consumer can then read every
            column without special-casing, and ``skipped`` plus ``note`` say why
            the zeros are there.
        samples: Number of samples actually scored.
        skipped: Number of samples the mode did not score. Equal to the dataset
            size when the mode could not run at all.
        note: One line, user-facing: why the mode was skipped, what limits the
            number, or ``""`` when there is nothing to disclose.
    """

    mode: str
    metrics: ModeMetrics
    samples: int
    skipped: int
    note: str


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def _zero_metrics() -> ModeMetrics:
    """Build the all-zero scorecard used for a skipped mode.

    :func:`benchmarks.metrics.compute_metrics` is deliberately *not* used here:
    an empty result list gives ``precision = 1.0`` by its documented convention,
    and reporting a perfect precision for a mode that never ran is exactly the
    kind of number this harness exists to avoid.

    Returns:
        A frozen :class:`~benchmarks.metrics.ModeMetrics` with every count and
        every ratio at zero and no per-category entries.
    """
    return ModeMetrics(
        precision=0.0,
        recall=0.0,
        f1=0.0,
        fpr=0.0,
        tp=0,
        fp=0,
        fn=0,
        tn=0,
        per_category={},
        latency_p50=0.0,
        latency_p95=0.0,
    )


def _elapsed_ms(started: float) -> float:
    """Elapsed wall time since ``started``, in milliseconds.

    Args:
        started: A :func:`time.perf_counter` reading taken before the work.

    Returns:
        Milliseconds elapsed, unrounded; ``compute_metrics`` applies the
        documented rounding.
    """
    return (time.perf_counter() - started) * 1000.0


def _finding_key(finding: Finding) -> FindingKey:
    """Build the de-duplication key for the merged union.

    Args:
        finding: One finding from either source.

    Returns:
        ``(file, line, severity, issue)`` — the contract's structural identity.
        ``suggested_fix`` is deliberately excluded: two reviewers that agree on
        the defect and disagree on the wording of the fix have found one defect.
    """
    return (finding.file, finding.line, finding.severity.value, finding.issue)


def _line_bounds(finding: Finding) -> tuple[int, int]:
    """Read a finding's ``line`` field as an inclusive integer range.

    Args:
        finding: Finding whose ``line`` is ``"42"`` or ``"42-45"``; the field is
            validated by :class:`app.models.Finding`, so it always parses.

    Returns:
        ``(start, end)``, 1-based, with ``end >= start``.
    """
    raw = finding.line
    if "-" in raw:
        start, _, end = raw.partition("-")
        return int(start), int(end)
    number = int(raw)
    return number, number


def _sort_key(finding: Finding) -> tuple[str, int, int, int, str]:
    """Ordering key that makes a finding list independent of input order.

    Args:
        finding: Finding to place.

    Returns:
        ``(file, line start, line end, -severity rank, issue)``: file order, then
        document order, then most severe first, then the issue text as a final
        tie-break so even duplicate labels cannot make the order depend on the
        order the sources were merged in.
    """
    start, end = _line_bounds(finding)
    return (finding.file, start, end, -finding.severity.rank, finding.issue)


def _dedupe(findings: Iterable[Finding]) -> list[Finding]:
    """Collapse the union of two finding lists by structural identity.

    Args:
        findings: Findings from any number of sources, in any order.

    Returns:
        A new, deterministically sorted list holding one finding per
        :func:`_finding_key`, keeping the first occurrence of each key.
    """
    seen: set[FindingKey] = set()
    unique: list[Finding] = []
    for finding in findings:
        key = _finding_key(finding)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    unique.sort(key=_sort_key)
    return unique


def _scored_note(samples: Sequence[Sample]) -> str:
    """Describe a run's data provenance, or nothing when it needs no caveat.

    Args:
        samples: The samples that were scored.

    Returns:
        ``""`` when no format example is present, otherwise one line recording
        how many of the scored samples are format examples — which the dataset
        README defines as excluded from every reported metric.
    """
    total = len(samples)
    examples = sum(1 for sample in samples if sample.meta.get("format_example"))
    if examples == 0:
        return ""
    if examples == total:
        return (
            f"all {total} sample(s) are format examples; these numbers are a "
            "smoke test, not evaluation data"
        )
    return f"{examples} of {total} sample(s) are format examples; not evaluation data"


def _parse(sample: Sample) -> DiffBundle:
    """Parse one sample's diff, labelling parse errors with the sample id.

    Args:
        sample: Sample to parse.

    Returns:
        The parsed :class:`app.parser.DiffBundle`.
    """
    return parse_diff(sample.diff_text, source=sample.id)


def _score(
    samples: Sequence[Sample],
    produce: Callable[[Sample], list[Finding]],
) -> tuple[list[MatchResult], list[float]]:
    """Score every sample with one producer, timing each one.

    Args:
        samples: Samples to score, already in a deterministic order.
        produce: Callable returning the findings for one sample. It may raise
            :class:`_LocalDegraded`, which this function does not catch, so the
            caller can abandon the run at the first degraded sample.

    Returns:
        A pair ``(results, latencies)``: one
        :class:`~benchmarks.matching.MatchResult` per sample in input order, and
        one wall-clock duration per sample in milliseconds.
    """
    results: list[MatchResult] = []
    latencies: list[float] = []
    for sample in samples:
        started = time.perf_counter()
        findings = produce(sample)
        latencies.append(_elapsed_ms(started))
        results.append(match_sample(sample, findings))
    return results, latencies


def _rules_findings(sample: Sample) -> list[Finding]:
    """Run the deterministic rule engine over one sample.

    Args:
        sample: Sample whose diff is reviewed.

    Returns:
        The rule findings, CRITICAL first.
    """
    return list(review_diff(_parse(sample)))


# --------------------------------------------------------------------------- #
# Local provider plumbing
# --------------------------------------------------------------------------- #


def _missing_local_variable(settings: Settings) -> str:
    """Name the setting that stops the local provider from being usable.

    Args:
        settings: Application settings read from the environment.

    Returns:
        ``"LMSTUDIO_BASE_URL"`` or ``"LMSTUDIO_API_KEY"`` — the base URL first,
        because that is the one a user has to supply and the one the CLI's own
        selection reason names.
    """
    if not (settings.lmstudio_base_url or "").strip():
        return "LMSTUDIO_BASE_URL"
    return "LMSTUDIO_API_KEY"


def _local_selection(settings: Settings) -> tuple[ProviderSelection | None, str]:
    """Ask the application which provider a ``local`` request resolves to.

    Args:
        settings: Application settings read from the environment.

    Returns:
        ``(selection, "")`` when a live local endpoint is configured, otherwise
        ``(None, note)`` where ``note`` names the missing variable and explains
        how to make the mode runnable.
    """
    selection = select_provider(settings, requested=MODE_LOCAL)
    if selection.provider == MODE_LOCAL and selection.config is not None:
        return selection, ""

    if not (settings.lmstudio_base_url or "").strip() or not (
        settings.lmstudio_api_key or ""
    ).strip():
        missing = _missing_local_variable(settings)
        note = (
            f"skipped: {missing} is not set, so no OpenAI-compatible local "
            "endpoint is configured; set it to a running LM Studio base URL to "
            "benchmark the model path"
        )
    else:
        # Any other fallback is the application's own reason, quoted verbatim
        # rather than paraphrased, so the note cannot drift from the engine.
        note = f"skipped: {selection.reason}"
    return None, note


def _review_local(sample: Sample, settings: Settings) -> list[Finding]:
    """Review one sample through the local provider.

    Args:
        sample: Sample whose diff is reviewed.
        settings: Application settings read from the environment.

    Returns:
        The findings reported by the model.

    Raises:
        _LocalDegraded: The adapter fell back to the rule engine, so the findings
            are not a model's.
    """
    outcome = review(_parse(sample), settings, provider=MODE_LOCAL)
    if outcome.mode != "live":
        raise _LocalDegraded(
            outcome.reason or "the local endpoint degraded to the rule engine"
        )
    return list(outcome.findings)


# --------------------------------------------------------------------------- #
# Per-mode runners
# --------------------------------------------------------------------------- #


def _skipped(mode: str, samples: Sequence[Sample], note: str) -> ModeResult:
    """Build the clean-skip result for a mode that could not run.

    Args:
        mode: Mode being skipped.
        samples: The samples the mode would have scored.
        note: One line explaining the skip.

    Returns:
        A :class:`ModeResult` with ``samples=0``, ``skipped=len(samples)`` and an
        all-zero scorecard.
    """
    logger.info("benchmark mode %s: %s", mode, note)
    return ModeResult(
        mode=mode,
        metrics=_zero_metrics(),
        samples=0,
        skipped=len(samples),
        note=note,
    )


def _empty(mode: str) -> ModeResult:
    """Build the result for a run over an empty dataset.

    Args:
        mode: Mode that ran.

    Returns:
        A :class:`ModeResult` with no samples and an all-zero scorecard, so a
        vacuous run cannot report the conventional ``precision = 1.0``.
    """
    return ModeResult(
        mode=mode,
        metrics=_zero_metrics(),
        samples=0,
        skipped=0,
        note="no samples loaded from the dataset",
    )


def _run_rules(samples: Sequence[Sample]) -> ModeResult:
    """Score the deterministic rule engine.

    Args:
        samples: Samples to score.

    Returns:
        The rules scorecard, or the empty-dataset result.
    """
    if not samples:
        return _empty(MODE_RULES)
    results, latencies = _score(samples, _rules_findings)
    return ModeResult(
        mode=MODE_RULES,
        metrics=compute_metrics(results, latencies),
        samples=len(samples),
        skipped=0,
        note=_scored_note(samples),
    )


def _run_local(samples: Sequence[Sample]) -> ModeResult:
    """Score the local model path, or skip cleanly when it is not configured.

    Args:
        samples: Samples to score.

    Returns:
        The local scorecard when every sample was reviewed live; otherwise a
        skipped result whose note names the missing variable or the adapter's own
        degradation reason.
    """
    if not samples:
        return _empty(MODE_LOCAL)

    settings = Settings()
    selection, note = _local_selection(settings)
    if selection is None:
        return _skipped(MODE_LOCAL, samples, note)

    try:
        results, latencies = _score(
            samples, lambda sample: _review_local(sample, settings)
        )
    except _LocalDegraded as degraded:
        return _skipped(
            MODE_LOCAL,
            samples,
            f"skipped: the local endpoint degraded to the rule engine "
            f"({degraded.reason}); no model findings were recorded",
        )

    return ModeResult(
        mode=MODE_LOCAL,
        metrics=compute_metrics(results, latencies),
        samples=len(samples),
        skipped=0,
        note=_scored_note(samples),
    )


def _run_merged(samples: Sequence[Sample]) -> ModeResult:
    """Score the union of rule findings and local findings.

    The union is built here, per sample, and de-duplicated by
    :func:`_finding_key`. When the local endpoint is unavailable — or degrades
    partway through — the mode is rules-only and carries
    :data:`MERGED_RULES_ONLY_NOTE`, so the scorecard can never be mistaken for a
    model-plus-rules result.

    Args:
        samples: Samples to score.

    Returns:
        The merged scorecard, or the rules-only scorecard with the documented
        note.
    """
    if not samples:
        return _empty(MODE_MERGED)

    settings = Settings()
    selection, _ = _local_selection(settings)

    if selection is None:
        results, latencies = _score(samples, _rules_findings)
        return ModeResult(
            mode=MODE_MERGED,
            metrics=compute_metrics(results, latencies),
            samples=len(samples),
            skipped=0,
            note=MERGED_RULES_ONLY_NOTE,
        )

    def _merged_findings(sample: Sample) -> list[Finding]:
        """Union one sample's rule findings with its live local findings.

        Args:
            sample: Sample to review twice.

        Returns:
            The de-duplicated union, deterministically sorted.

        Raises:
            _LocalDegraded: The local pass degraded to the rule engine.
        """
        return _dedupe([*_rules_findings(sample), *_review_local(sample, settings)])

    try:
        results, latencies = _score(samples, _merged_findings)
    except _LocalDegraded:
        # The endpoint answered, then fell back to the rule engine. The union
        # would collapse to the rules, so report exactly that rather than a
        # merged scorecard that silently measured one source.
        results, latencies = _score(samples, _rules_findings)
        return ModeResult(
            mode=MODE_MERGED,
            metrics=compute_metrics(results, latencies),
            samples=len(samples),
            skipped=0,
            note=MERGED_RULES_ONLY_NOTE,
        )

    return ModeResult(
        mode=MODE_MERGED,
        metrics=compute_metrics(results, latencies),
        samples=len(samples),
        skipped=0,
        note=_scored_note(samples),
    )


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def run_mode(
    mode: str,
    samples: Sequence[Sample],
    *,
    dataset_root: Path,
) -> ModeResult:
    """Run one mode over ``samples`` and score it.

    Args:
        mode: ``"rules"``, ``"local"`` or ``"merged"``; case and surrounding
            whitespace are ignored.
        samples: The samples to score, typically from
            :func:`benchmarks.loader.load_dataset`.
        dataset_root: Root the samples were loaded from. Used as a provenance
            guard: a missing root is logged as a WARNING (the samples are already
            in memory, so the run still proceeds) rather than raised, because the
            loader — not this function — owns dataset errors.

    Returns:
        The :class:`ModeResult` for this mode. A mode that cannot run returns a
        skipped result with an all-zero scorecard; it never raises for a
        configuration reason.

    Raises:
        ValueError: ``mode`` is not one of :data:`MODE_NAMES`. An unknown mode
            name is a programming error, so it is not hidden.
    """
    normalized = (mode or "").strip().lower()
    if normalized not in MODE_NAMES:
        raise ValueError(
            f"unknown benchmark mode {mode!r}; expected one of {', '.join(MODE_NAMES)}"
        )

    root = Path(dataset_root)
    if not root.is_dir():
        logger.warning(
            "dataset root %s does not exist; scoring the %d supplied sample(s) anyway",
            root,
            len(samples),
        )

    if normalized == MODE_RULES:
        return _run_rules(samples)
    if normalized == MODE_LOCAL:
        return _run_local(samples)
    return _run_merged(samples)


def run_all(modes: Sequence[str], *, dataset_root: Path) -> dict[str, ModeResult]:
    """Load the dataset once and run every requested mode over it.

    Args:
        modes: Mode names to run, in the order the caller wants them reported.
            Duplicates collapse onto one entry, keeping the first position.
        dataset_root: Dataset root passed to
            :func:`benchmarks.loader.load_dataset`.

    Returns:
        A dict keyed by mode name, in request order, holding each
        :class:`ModeResult`.

    Raises:
        ValueError: A mode name is not one of :data:`MODE_NAMES`.
        benchmarks.loader.DatasetError: The dataset cannot be loaded. Propagated
            untouched so the CLI can report it and exit with its dataset-error
            code.
    """
    # Imported here so a caller that only needs run_mode does not pay for the
    # loader's Pydantic import graph.
    from benchmarks.loader import load_dataset

    samples = load_dataset(Path(dataset_root))

    results: dict[str, ModeResult] = {}
    for mode in modes:
        normalized = (mode or "").strip().lower()
        if normalized in results:
            continue
        results[normalized] = run_mode(normalized, samples, dataset_root=dataset_root)
    return results
