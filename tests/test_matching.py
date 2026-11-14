"""Offline unit tests for :mod:`benchmarks.matching`.

Everything here is a pure function over in-memory objects, so the whole module
runs in milliseconds with no dataset on disk, no network, no model and no keys.
The two inputs — a :class:`~benchmarks.loader.Sample` and a sequence of
:class:`app.models.Finding` — are built by the small helpers below rather than
loaded from ``benchmarks/golden``, which keeps each test's arithmetic readable
and pins the exact line numbers an assertion talks about.

Category inference is a keyword classifier over the finding's ``issue`` prose
(:func:`~benchmarks.matching.infer_category`), so :data:`CATEGORY_PROBES` maps
every category to one phrase that provably classifies into it. Tests that care
about a *category* therefore state it through that phrase, and
:func:`test_category_probes_classify_as_declared` keeps the table honest — if
the keyword table ever changes, that test fails rather than silently turning
every category test into a no-op.

Shuffling uses a fixed seed so the determinism tests are reproducible, and
``random`` only ever permutes the inputs — the assertions are about the output.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

import pytest

from app.models import Finding, Severity
from benchmarks.loader import ExpectedFinding, Sample
from benchmarks.matching import (
    CATEGORY_EQUIVALENCE,
    MatchResult,
    infer_category,
    line_range,
    match_sample,
)

#: One issue phrase per category that :func:`infer_category` classifies into it.
CATEGORY_PROBES: dict[str, str] = {
    "deserialisation": "unsafe pickle load of untrusted bytes",
    "injection": "sql injection through string concatenation",
    "secrets": "hardcoded password committed to source",
    "crypto": "weak md5 hash used for integrity",
    "auth": "broken access control on the delete route",
    "config": "debug flag enabled in production settings",
    "reliability": "missing timeout on the outbound call",
    "complexity": "deeply nested branching in one function",
    "style": "naming style violation in a local variable",
    "quality": "duplicate dead code left in the module",
    # Deliberately names no keyword from the classifier's table: "retry", the
    # obvious word for an only-a-model observation, would classify as
    # "reliability" and the probe would stop testing the fallback bucket.
    "llm": "the abstraction couples the cache to the storage layer",
}

#: Default file shared by every label and finding built here.
FILE = "app/users.py"

#: Deterministic seed for every permutation used in this module.
SEED = 20240117


def make_finding(
    line: str = "10-12",
    *,
    issue: str = CATEGORY_PROBES["injection"],
    file: str = FILE,
    severity: Severity = Severity.HIGH,
) -> Finding:
    """Build one finding as the reviewer would report it.

    Args:
        line: The finding's ``line`` field, ``"42"`` or ``"42-45"``.
        issue: Prose whose keywords decide the inferred category.
        file: Path the finding is anchored to.
        severity: Reported severity.

    Returns:
        A frozen :class:`app.models.Finding`.
    """
    return Finding(
        file=file,
        line=line,
        severity=severity,
        issue=issue,
        suggested_fix="apply the documented fix",
    )


def make_label(
    line_start: int,
    line_end: int | None = None,
    *,
    category: str = "injection",
    file: str = FILE,
    severity: str = "HIGH",
) -> ExpectedFinding:
    """Build one human label.

    Args:
        line_start: First new-side line, inclusive.
        line_end: Last new-side line, inclusive; defaults to ``line_start``.
        category: Labelled category, used for the compatibility rule.
        file: Path the label refers to.
        severity: Labelled severity.

    Returns:
        A frozen :class:`~benchmarks.loader.ExpectedFinding`.
    """
    return ExpectedFinding(
        file=file,
        line_start=line_start,
        line_end=line_start if line_end is None else line_end,
        category=category,
        severity=severity,
    )


def make_sample(
    labels: Sequence[ExpectedFinding], *, sample_id: str = "sample"
) -> Sample:
    """Wrap labels in a sample; ``diff_text`` is never read by matching.

    Args:
        labels: The sample's ground-truth labels.
        sample_id: Sample id, echoed into no assertion but kept realistic.

    Returns:
        A frozen :class:`~benchmarks.loader.Sample`.
    """
    return Sample(
        id=sample_id,
        diff_text="--- a/app/users.py\n+++ b/app/users.py\n",
        expected=tuple(labels),
        meta={"format_example": False},
    )


def finding_for_category(category: str, line: str = "10-12") -> Finding:
    """Build a finding that :func:`infer_category` classifies as ``category``.

    Args:
        category: Target category, a key of :data:`CATEGORY_PROBES`.
        line: The finding's ``line`` field.

    Returns:
        A finding whose inferred category is ``category``.
    """
    return make_finding(line, issue=CATEGORY_PROBES[category])


def _first_fit_tp(
    labels: Sequence[ExpectedFinding], findings: Sequence[Finding]
) -> int:
    """Count matches the naive label-major, first-compatible-pair greedy yields.

    This is the baseline :func:`match_sample` is compared against: it walks the
    labels in order, takes the first still-unused finding that shares the file
    and at least one line, and ignores overlap size entirely. It exists only to
    show that overlap ordering is what saves a match, so it implements the rule
    loosely — no category check, no path normalisation.

    Args:
        labels: Labels in the order the naive pass sees them.
        findings: Findings in the order the naive pass sees them.

    Returns:
        The number of labels the naive pass matched.
    """
    used_findings: set[int] = set()
    matched = 0
    for label in labels:
        for index, finding in enumerate(findings):
            if index in used_findings:
                continue
            start, end = line_range(finding.line)
            overlap = min(label.line_end, end) - max(label.line_start, start) + 1
            if overlap > 0:
                used_findings.add(index)
                matched += 1
                break
    return matched


# --------------------------------------------------------------------------- #
# Overlap basics
# --------------------------------------------------------------------------- #


def test_perfect_overlap_matches() -> None:
    """A label and a finding on the same lines are one true positive."""
    result = match_sample(make_sample([make_label(10, 12)]), [make_finding("10-12")])

    assert result.tp == 1
    assert result.fp == 0
    assert result.fn == 0
    assert result.true_negatives == 0
    assert result.matched[0].overlap == 3


def test_partial_overlap_matches_with_shared_line_count() -> None:
    """Overlapping ranges match, and ``overlap`` counts the shared lines only."""
    result = match_sample(make_sample([make_label(10, 20)]), [make_finding("15-25")])

    assert result.tp == 1
    assert result.matched[0].overlap == 6
    assert result.false_positives == ()
    assert result.false_negatives == ()


def test_disjoint_ranges_are_a_false_positive_and_a_false_negative() -> None:
    """Touching ranges never match: the shared-line count must be at least one."""
    result = match_sample(make_sample([make_label(10, 12)]), [make_finding("13-15")])

    assert result.tp == 0
    assert result.fp == 1
    assert result.fn == 1
    assert result.false_positives[0].line_start == 13
    assert result.false_negatives[0].line_start == 10


def test_different_file_never_matches_even_with_identical_lines() -> None:
    """The file is part of the match key, not a hint."""
    result = match_sample(
        make_sample([make_label(10, 12, file="app/users.py")]),
        [make_finding("10-12", file="app/orders.py")],
    )

    assert result.tp == 0
    assert result.fp == 1
    assert result.fn == 1


def test_leading_dot_slash_is_normalised_before_comparing_paths() -> None:
    """``./app/users.py`` and ``app/users.py`` name the same file."""
    result = match_sample(
        make_sample([make_label(10, 12, file="./app/users.py")]),
        [make_finding("10-12", file="app/users.py")],
    )

    assert result.tp == 1
    assert result.fp == 0
    assert result.fn == 0


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #


def test_category_probes_classify_as_declared() -> None:
    """Every probe phrase infers the category the table claims for it."""
    for category, phrase in CATEGORY_PROBES.items():
        assert infer_category(make_finding(issue=phrase)) == category


def test_equal_category_matches() -> None:
    """Exact category equality is always a match."""
    result = match_sample(
        make_sample([make_label(10, 12, category="injection")]),
        [finding_for_category("injection")],
    )

    assert infer_category(finding_for_category("injection")) == "injection"
    assert result.tp == 1
    assert result.fp == 0


@pytest.mark.parametrize("expected_category", sorted(CATEGORY_EQUIVALENCE))
def test_equivalence_map_holds_in_both_directions(expected_category: str) -> None:
    """Every ordered pair of categories matches exactly when the map says so.

    The pair is exercised as ``(label, finding)`` and as ``(finding, label)``, so
    a one-sided entry cannot pass: ``auth`` accepts a ``secrets`` finding, but a
    ``secrets`` label does not accept an ``auth`` finding.
    """
    for actual_category in sorted(CATEGORY_EQUIVALENCE):
        forward = match_sample(
            make_sample([make_label(10, 12, category=expected_category)]),
            [finding_for_category(actual_category)],
        )
        backward = match_sample(
            make_sample([make_label(10, 12, category=actual_category)]),
            [finding_for_category(expected_category)],
        )

        forward_ok = (
            actual_category == expected_category
            or actual_category in CATEGORY_EQUIVALENCE[expected_category]
        )
        backward_ok = (
            expected_category == actual_category
            or expected_category in CATEGORY_EQUIVALENCE[actual_category]
        )

        assert forward.tp == (1 if forward_ok else 0), (
            f"label {expected_category!r} vs finding {actual_category!r}"
        )
        assert backward.tp == (1 if backward_ok else 0), (
            f"label {actual_category!r} vs finding {expected_category!r}"
        )
        # Whatever the direction, each side is counted exactly once and never
        # silently dropped: the single label is either a tp or an fn, and the
        # single finding is either the same tp or an fp.
        assert forward.tp + forward.fn == 1
        assert forward.tp + forward.fp == 1
        assert backward.tp + backward.fn == 1
        assert backward.tp + backward.fp == 1


def test_equivalence_map_is_self_consistent() -> None:
    """Every category is equivalent to itself and every member is a real category."""
    known = set(CATEGORY_EQUIVALENCE)

    for category, equivalents in CATEGORY_EQUIVALENCE.items():
        assert category in equivalents, f"{category!r} must accept itself"
        assert equivalents <= known, f"{category!r} names an unknown category"
        assert isinstance(equivalents, frozenset)


def test_category_outside_equivalence_does_not_match() -> None:
    """A vague finding cannot claim a specific label, nor a specific one a vague label."""
    pairs = (
        ("injection", "quality"),
        ("injection", "llm"),
        ("config", "auth"),
        ("config", "style"),
    )

    for label_category, actual_category in pairs:
        result = match_sample(
            make_sample([make_label(10, 12, category=label_category)]),
            [finding_for_category(actual_category)],
        )

        assert result.tp == 0, f"{label_category!r} must not accept {actual_category!r}"
        assert result.fp == 1
        assert result.fn == 1


# --------------------------------------------------------------------------- #
# Line-range parsing
# --------------------------------------------------------------------------- #


def test_line_range_parses_a_single_line() -> None:
    """``"42"`` is the one-line range ``(42, 42)``."""
    assert line_range("42") == (42, 42)


def test_line_range_parses_an_ascending_range() -> None:
    """``"42-45"`` is the inclusive range ``(42, 45)``."""
    assert line_range("42-45") == (42, 45)


def test_line_range_rejects_malformed_text() -> None:
    """Anything but a line number or an ascending range raises."""
    for text in ("", "abc", "42-", "42-41", "-5"):
        with pytest.raises(ValueError):
            line_range(text)


# --------------------------------------------------------------------------- #
# One-to-one enforcement
# --------------------------------------------------------------------------- #


def test_two_labels_cannot_claim_one_finding() -> None:
    """One finding satisfies one label; the other label becomes a false negative."""
    result = match_sample(
        make_sample([make_label(10, 12), make_label(10, 12)]),
        [make_finding("10-12")],
    )

    assert result.tp == 1
    assert result.fp == 0
    assert result.fn == 1
    assert len(result.matched) == 1


def test_one_label_cannot_claim_two_findings() -> None:
    """One label absorbs one finding; the duplicate is a false positive."""
    result = match_sample(
        make_sample([make_label(10, 12)]),
        [make_finding("10-12"), make_finding("10-12")],
    )

    assert result.tp == 1
    assert result.fp == 1
    assert result.fn == 0
    assert len(result.matched) == 1


# --------------------------------------------------------------------------- #
# Greedy ordering
# --------------------------------------------------------------------------- #


def test_greedy_largest_overlap_first_beats_first_fit() -> None:
    """Largest-overlap-first rescues a match that a first-compatible pass strands.

    The single finding ``9-20`` is the only one the second label ``8-20`` can
    reach, and it is also the first finding the first label ``1-10`` could take.
    A naive label-major pass lets ``1-10`` grab it and strands ``8-20``; ordering
    candidates by overlap size serves ``8-20`` first (12 shared lines) and still
    leaves ``1-10`` the ``1-2`` finding (2 shared lines), for two true positives.
    """
    labels = [make_label(1, 10), make_label(8, 20)]
    findings = [make_finding("9-20"), make_finding("1-2")]

    result = match_sample(make_sample(labels), findings)

    assert _first_fit_tp(labels, findings) == 1
    assert result.tp == 2
    assert result.fp == 0
    assert result.fn == 0
    assert {(match.expected.line_start, match.actual.line) for match in result.matched} == {
        (1, "1-2"),
        (8, "9-20"),
    }
    assert [match.overlap for match in result.matched] == [2, 12]


# --------------------------------------------------------------------------- #
# Deterministic tie-break
# --------------------------------------------------------------------------- #


def test_equal_overlap_tie_break_picks_the_same_winner_in_every_order() -> None:
    """Equal overlap is broken by the documented key, not by input order.

    Both findings share exactly six lines with the label, so the tie is decided
    by the finding's start line (``5`` before ``10``). Twenty shuffled input
    orders must all select the ``5-15`` finding.
    """
    labels = [make_label(10, 20)]
    findings = [make_finding("5-15"), make_finding("10-15")]
    reference = match_sample(make_sample(labels), findings)

    assert reference.tp == 1
    assert reference.matched[0].actual.line == "5-15"

    rng = random.Random(SEED)
    for _ in range(20):
        shuffled = list(findings)
        rng.shuffle(shuffled)
        result = match_sample(make_sample(labels), shuffled)
        assert [match.actual.line for match in result.matched] == ["5-15"]
        assert (result.tp, result.fp, result.fn) == (1, 1, 0)


def test_equal_overlap_between_two_labels_picks_the_earlier_label_start() -> None:
    """With one finding and two labels of equal overlap, the earlier label wins.

    Both labels share exactly six lines with the ``20-25`` finding, so overlap
    cannot separate them and the contract's tie-break falls through to the
    label's start line: ``10`` is taken before ``20``. The later label is then a
    false negative — the cost of a one-to-one rule.
    """
    labels = [make_label(20, 30), make_label(10, 25)]
    findings = [make_finding("20-25")]

    result = match_sample(make_sample(labels), findings)

    assert result.tp == 1
    assert result.fn == 1
    assert result.matched[0].expected.line_start == 10
    assert result.matched[0].overlap == 6
    assert [label.line_start for label in result.false_negatives] == [20]


def test_duplicate_findings_keep_the_counts_identical_in_every_order() -> None:
    """Two indistinguishable findings can swap which one is reported, never the counts.

    The contract's tie-break cannot separate findings at the same file and the
    same lines, so *which* duplicate is matched may follow input order — a
    documented limitation. The scorecard must not: the counts are invariant.
    """
    labels = [make_label(10, 12)]
    findings = [make_finding("10-12"), make_finding("10-12")]
    rng = random.Random(SEED)
    outcomes: set[tuple[int, int, int, int]] = set()

    for _ in range(10):
        shuffled = list(findings)
        rng.shuffle(shuffled)
        result = match_sample(make_sample(labels), shuffled)
        outcomes.add((result.tp, result.fp, result.fn, result.true_negatives))

    assert outcomes == {(1, 1, 0, 0)}


# --------------------------------------------------------------------------- #
# True negatives
# --------------------------------------------------------------------------- #


def test_true_negative_when_a_clean_sample_draws_no_finding() -> None:
    """An empty label set and no findings is one true negative."""
    result = match_sample(make_sample([]), [])

    assert result.true_negatives == 1
    assert (result.tp, result.fp, result.fn) == (0, 0, 0)
    assert result.per_category == {}


def test_no_true_negative_when_a_finding_exists_for_a_clean_sample() -> None:
    """A finding on a labelled-clean sample is a false positive, not a negative."""
    result = match_sample(make_sample([]), [make_finding("10-12")])

    assert result.true_negatives == 0
    assert result.tp == 0
    assert result.fp == 1
    assert result.fn == 0


# --------------------------------------------------------------------------- #
# Per-category accumulation
# --------------------------------------------------------------------------- #


def test_per_category_counts_accumulate_and_reconcile_with_the_totals() -> None:
    """Per-category counts carry the same totals, split by category."""
    labels = [
        make_label(10, 12, category="injection"),
        make_label(20, 22, category="quality"),
        make_label(30, 32, category="secrets"),
    ]
    findings = [
        make_finding("10-12", issue=CATEGORY_PROBES["injection"]),
        make_finding("50-51", issue=CATEGORY_PROBES["quality"]),
        make_finding("60-61", issue=CATEGORY_PROBES["secrets"]),
    ]

    result = match_sample(make_sample(labels), findings)

    assert result.tp == 1
    assert result.fp == 2
    assert result.fn == 2
    scores = {name: score for name, score in result.per_category.items()}
    assert (scores["injection"].tp, scores["injection"].fp, scores["injection"].fn) == (
        1,
        0,
        0,
    )
    assert (scores["quality"].tp, scores["quality"].fp, scores["quality"].fn) == (0, 1, 1)
    assert (scores["secrets"].tp, scores["secrets"].fp, scores["secrets"].fn) == (0, 1, 1)

    assert sum(score.tp for score in result.per_category.values()) == result.tp
    assert sum(score.fp for score in result.per_category.values()) == result.fp
    assert sum(score.fn for score in result.per_category.values()) == result.fn


def test_per_category_keys_are_sorted_for_stable_reports() -> None:
    """The mapping is sorted by category so two runs render identically."""
    labels = [
        make_label(10, 12, category="style"),
        make_label(20, 22, category="injection"),
        make_label(30, 32, category="auth"),
    ]

    result = match_sample(make_sample(labels), [])

    assert list(result.per_category) == ["auth", "injection", "style"]


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #


def test_match_result_is_identical_across_repeated_runs() -> None:
    """The same inputs produce an equal ``MatchResult``, field for field."""
    labels = [
        make_label(10, 12, category="injection"),
        make_label(20, 22, category="quality"),
        make_label(40, 44, category="secrets"),
    ]
    findings = [
        make_finding("11-13", issue=CATEGORY_PROBES["injection"]),
        make_finding("21-21", issue=CATEGORY_PROBES["quality"]),
        make_finding("70-71", issue=CATEGORY_PROBES["crypto"]),
    ]

    first = match_sample(make_sample(labels), findings)
    second = match_sample(make_sample(labels), findings)

    assert isinstance(first, MatchResult)
    assert first == second
    assert first.per_category == second.per_category
    assert [(m.expected, m.actual, m.overlap) for m in first.matched] == [
        (m.expected, m.actual, m.overlap) for m in second.matched
    ]


def test_matched_pairs_are_ordered_by_label_position_not_by_overlap() -> None:
    """``matched`` is reported in document order, whatever order greedy consumed."""
    labels = [make_label(30, 40), make_label(10, 12)]
    findings = [make_finding("30-40"), make_finding("10-12")]

    result = match_sample(make_sample(labels), findings)

    assert [match.expected.line_start for match in result.matched] == [10, 30]
    assert [match.overlap for match in result.matched] == [3, 11]
