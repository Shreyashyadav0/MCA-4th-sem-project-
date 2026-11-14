"""One-to-one matching between human labels and the reviewer's findings.

The harness scores a review by deciding, for each sample, which labels the tool
reproduced and which it missed or invented. That decision is this module's whole
job, and it is locked by ``benchmarks/CONTRACT.md``:

    same file AND overlapping line ranges AND (category equal OR in
    CATEGORY_EQUIVALENCE)

One-to-one, greedy, largest overlap first.

Why the rule is forgiving about categories
------------------------------------------
A label carries a rule category, but :class:`app.models.Finding` carries only
prose — the five contract fields have no category slot. The category of an actual
finding is therefore *inferred from its ``issue`` text* by
:func:`infer_category`, a deterministic keyword classifier whose fallback bucket
is ``"llm"`` ("a finding only a model would catch"). Because that inference is
lossy, :data:`CATEGORY_EQUIVALENCE` records which buckets a reviewer could
legitimately have used for the same defect; each entry carries a one-line
justification. Exact equality always counts as a match, so a category missing
from the map still matches itself.

Two documented limitations
--------------------------
* **Greedy, not optimal.** Candidate pairs are taken largest-overlap-first and the
  first pair that leaves both sides unused is accepted. Greedy can be beaten: a
  label overlapping two findings by 3 and 2 lines takes the 3-line finding and may
  then strand a second label that only the 3-line finding could have matched,
  where an optimal assignment would have scored 2 true positives. A Hungarian
  (Jonker-Volgenant) assignment over the overlap matrix would be optimal, but the
  contract locks greedy and an exact solver is out of scope; the harness instead
  removes the ambiguity by making every tie deterministic, so the same inputs
  always produce the same numbers.
* **Category inference is a heuristic.** ``infer_category`` reads prose, so an
  unusually worded issue can land in the fallback ``"llm"`` bucket. That bucket is
  equivalent to every category by design, so the failure mode is a missed
  category distinction, never a spurious false positive.

Determinism
-----------
Candidates are sorted by ``(-overlap, file, expected line_start, actual line
start)`` — the tie-break the contract fixes — with the two element indices
appended as a final discriminator so that even duplicate labels cannot make the
outcome depend on input order. Nothing here iterates a ``set`` or a ``dict`` to
decide an outcome.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import NamedTuple

from app.models import Finding
from benchmarks.loader import ExpectedFinding, Sample

__all__ = [
    "CATEGORY_EQUIVALENCE",
    "Match",
    "CategoryScore",
    "MatchResult",
    "match_sample",
    "infer_category",
    "line_range",
    "overlap_length",
]

#: Categories a reviewer may legitimately have used for the same defect.
#:
#: Maps the *expected* (labelled) category to the set of *actual* (reported)
#: categories that still count as the same finding. Every key is a
#: ``app.rules.RuleCategory`` value plus ``"llm"``; a key's own value is always in
#: its set, and equality matches even when a category is absent from the map.
CATEGORY_EQUIVALENCE: dict[str, frozenset[str]] = {
    # A committed credential and a weak cipher are the same "crypto material in
    # source" smell, and models routinely file a leaked key under crypto.
    "secrets": frozenset({"secrets", "crypto"}),
    # SQL/command/template injection is unambiguous; only injection counts, so a
    # vague "quality" finding can never claim an injection label.
    "injection": frozenset({"injection"}),
    # An unsafe pickle/yaml load IS code execution, so it is reported as either.
    "deserialisation": frozenset({"deserialisation", "injection"}),
    # Weak hash, disabled TLS verification and hardcoded keys are all crypto
    # hygiene to a reviewer; symmetric with the "secrets" entry above.
    "crypto": frozenset({"crypto", "secrets"}),
    # A hardcoded password is simultaneously an auth failure and a secret.
    "auth": frozenset({"auth", "secrets"}),
    # Debug flags, CORS and bind addresses are config-only; nothing else
    # legitimately lands in this bucket, so the entry stays narrow.
    "config": frozenset({"config"}),
    # A missing timeout is both a reliability defect and, to a model, "quality".
    "reliability": frozenset({"reliability", "quality"}),
    # "quality" is the catch-all bucket: hygiene issues get filed under any of the
    # sibling code-health categories, and all four describe the same defect class.
    "quality": frozenset({"quality", "reliability", "complexity", "style"}),
    # A long or deeply nested function is reported as complexity, quality or style
    # depending on the reviewer's taste.
    "complexity": frozenset({"complexity", "quality", "style"}),
    # Style is the lowest-stakes category and is rarely separated from quality by
    # a model, which tends to say "quality" for a naming or formatting nit.
    "style": frozenset({"style", "quality", "complexity"}),
    # An "llm" label means only a model could catch it, so the bucket the model
    # chose is arbitrary; any reported category satisfies it.
    "llm": frozenset(
        {
            "secrets",
            "injection",
            "deserialisation",
            "crypto",
            "auth",
            "config",
            "reliability",
            "quality",
            "complexity",
            "style",
            "llm",
        }
    ),
}

#: Ordered keyword table for :func:`infer_category`; first hit wins.
#:
#: Order is load-bearing: "unsafe deserialisation enables code injection" must be
#: deserialisation, and "hardcoded password" must be secrets rather than crypto.
_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "deserialisation",
        ("deserialis", "deserializ", "pickle", "yaml.load", "marshal", "unsafe load"),
    ),
    (
        "injection",
        (
            "inject",
            "sql",
            "os.system",
            "shell=true",
            "eval(",
            "exec(",
            "subprocess",
            "xss",
            "template",
            "unsanitised",
            "unsanitized",
        ),
    ),
    (
        "secrets",
        (
            "secret",
            "credential",
            "api key",
            "api_key",
            "apikey",
            "token",
            "password",
            "passwd",
            "private key",
            "hardcoded",
            "committed",
        ),
    ),
    (
        "crypto",
        (
            "crypto",
            "md5",
            "sha1",
            "sha-1",
            "hash",
            "tls",
            "ssl",
            "verify=false",
            "cipher",
            "weak random",
        ),
    ),
    (
        "auth",
        (
            "auth",
            "access control",
            "permission",
            "privilege",
            "login",
            "session",
            "jwt",
            "authoriz",
        ),
    ),
    (
        "config",
        ("debug", "cors", "config", "settings", "0.0.0.0", "environment variable"),
    ),
    (
        "reliability",
        (
            "timeout",
            "retry",
            "leak",
            "not closed",
            "resource",
            "bare except",
            "swallow",
            "race",
            "deadlock",
            "unhandled exception",
        ),
    ),
    ("complexity", ("complex", "nest", "cyclomatic", "deeply")),
    (
        "style",
        (
            "style",
            "naming",
            "line length",
            "line too long",
            "formatting",
            "whitespace",
            "trailing",
            "unused import",
            "pep 8",
            "pep8",
            "docstring",
        ),
    ),
    (
        "quality",
        (
            "quality",
            "type hint",
            "mutable default",
            "duplicate",
            "dead code",
            "maintainab",
            "readab",
            "magic number",
            "unused variable",
        ),
    ),
)

#: Bucket used when the issue text names no category at all.
_FALLBACK_CATEGORY = "llm"


class _Candidate(NamedTuple):
    """One admissible label/finding pair, ordered so ``sort()`` is the tie-break.

    Field order is the contract's deterministic order — largest overlap first,
    then file, then the label's start line, then the finding's start line — with
    the two element indices appended so that even duplicate labels cannot let
    input order decide the outcome.

    Attributes:
        overlap: Shared new-side lines, at least 1; sorted descending.
        file: Normalised path shared by the label and the finding.
        label_start: First line of the label.
        finding_start: First line of the finding.
        label_index: Position of the label in the sample's ``expected`` tuple.
        finding_index: Position of the finding in the caller's sequence.
    """

    overlap: int
    file: str
    label_start: int
    finding_start: int
    label_index: int
    finding_index: int

    def __lt__(self, other: "_Candidate") -> bool:
        """Order by overlap descending, then the documented deterministic key."""
        return (
            -self.overlap,
            self.file,
            self.label_start,
            self.finding_start,
            self.label_index,
            self.finding_index,
        ) < (
            -other.overlap,
            other.file,
            other.label_start,
            other.finding_start,
            other.label_index,
            other.finding_index,
        )


@dataclass(frozen=True)
class Match:
    """One label paired with the finding that reproduced it.

    Attributes:
        expected: The human label.
        actual: The finding that satisfied it.
        overlap: Number of shared new-side lines, at least 1.
    """

    expected: ExpectedFinding
    actual: Finding
    overlap: int


@dataclass(frozen=True)
class CategoryScore:
    """Per-category confusion counts.

    Attributes:
        tp: Labels matched by a finding.
        fp: Findings that matched no label.
        fn: Labels no finding matched.
    """

    tp: int = 0
    fp: int = 0
    fn: int = 0


@dataclass(frozen=True)
class MatchResult:
    """Outcome of matching one sample.

    Attributes:
        matched: Accepted label/finding pairs, ordered by label position.
        false_positives: Unmatched findings, projected into label shape so the
            report has one row type (their ``category`` is the inferred one).
        false_negatives: Labels no finding reproduced.
        true_negatives: ``1`` when the label is empty and no finding was produced,
            else ``0``.
        per_category: Confusion counts keyed by category — labels contribute
            ``tp``/``fn`` under their own category, unmatched findings contribute
            ``fp`` under their inferred category.
    """

    matched: tuple[Match, ...]
    false_positives: tuple[ExpectedFinding, ...]
    false_negatives: tuple[ExpectedFinding, ...]
    true_negatives: int
    per_category: dict[str, CategoryScore] = field(default_factory=dict)

    @property
    def tp(self) -> int:
        """Number of matched labels."""
        return len(self.matched)

    @property
    def fp(self) -> int:
        """Number of unmatched findings."""
        return len(self.false_positives)

    @property
    def fn(self) -> int:
        """Number of unmatched labels."""
        return len(self.false_negatives)


def line_range(line: str) -> tuple[int, int]:
    """Parse a finding's ``line`` field into an inclusive range.

    Args:
        line: ``"42"`` for one line or ``"42-45"`` for a range, as validated by
            :class:`app.models.Finding`.

    Returns:
        ``(start, end)``, inclusive.

    Raises:
        ValueError: The text is not a line number or an ascending range.
    """
    start_text, separator, end_text = line.partition("-")
    if not start_text.strip().isdigit():
        raise ValueError(f'line must look like "42" or "42-45", got {line!r}')
    start = int(start_text)
    if not separator:
        return start, start
    if not end_text.strip().isdigit():
        raise ValueError(f'line range must look like "42-45", got {line!r}')
    end = int(end_text)
    if end < start:
        raise ValueError(f"line range must ascend, got {line!r}")
    return start, end


def overlap_length(first: tuple[int, int], second: tuple[int, int]) -> int:
    """Count the shared lines of two inclusive ranges.

    Args:
        first: ``(start, end)`` of the first range.
        second: ``(start, end)`` of the second range.

    Returns:
        The number of common lines, ``0`` when the ranges are disjoint.
    """
    return max(0, min(first[1], second[1]) - max(first[0], second[0]) + 1)


def _normalise_path(path: str) -> str:
    """Strip a leading ``./`` and surrounding whitespace from a file path.

    Args:
        path: Path as written in a label or a finding.

    Returns:
        The comparable form of the path.
    """
    cleaned = path.strip()
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned


def infer_category(finding: Finding) -> str:
    """Infer a rule category from a finding's issue prose.

    :class:`app.models.Finding` has no category field, so the harness reads the
    one signal it does carry. The scan is case-insensitive and first-hit-wins over
    :data:`_CATEGORY_KEYWORDS`.

    Args:
        finding: The finding to classify.

    Returns:
        A category name from :data:`CATEGORY_EQUIVALENCE`, or ``"llm"`` when the
        prose names no category — the bucket that is equivalent to every category.
    """
    haystack = finding.issue.casefold()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            return category
    return _FALLBACK_CATEGORY


def _categories_compatible(expected_category: str, actual_category: str) -> bool:
    """Decide whether two categories describe the same defect.

    Args:
        expected_category: Category from the human label.
        actual_category: Category inferred from the finding.

    Returns:
        ``True`` on equality, or when the actual category is one the labelled
        category may legitimately be reported as.
    """
    if expected_category == actual_category:
        return True
    return actual_category in CATEGORY_EQUIVALENCE.get(
        expected_category, frozenset({expected_category})
    )


def _as_expected(finding: Finding, category: str) -> ExpectedFinding:
    """Project an actual finding into label shape, for the false-positive tuple.

    Args:
        finding: The unmatched finding.
        category: Category inferred for it.

    Returns:
        An :class:`ExpectedFinding` carrying the finding's file, range, inferred
        category and severity.
    """
    start, end = line_range(finding.line)
    return ExpectedFinding(
        file=finding.file,
        line_start=start,
        line_end=end,
        category=category,
        severity=finding.severity.value,
    )


def match_sample(expected: Sample, findings: Sequence[Finding]) -> MatchResult:
    """Match one sample's labels against the findings produced for its diff.

    Candidates need the same file, an overlap of at least one line, and a
    compatible category. Pairs are consumed greedily in
    ``(-overlap, file, expected line_start, actual line_start, expected index,
    actual index)`` order, one-to-one, so no label and no finding is counted
    twice.

    Args:
        expected: The sample whose ``expected`` labels are the ground truth.
        findings: What the reviewer reported for that sample's diff; order is
            irrelevant to the outcome.

    Returns:
        The :class:`MatchResult` for the sample: matched pairs, false positives,
        false negatives, the true-negative flag and per-category counts.

    Raises:
        ValueError: A finding carries a ``line`` string that is not a line number
            or an ascending range. :class:`app.models.Finding` validates this at
            construction, so this signals a hand-built or corrupted finding.
    """
    labels = expected.expected
    actual_categories = [infer_category(finding) for finding in findings]

    candidates: list[_Candidate] = []
    for label_index, label in enumerate(labels):
        label_path = _normalise_path(label.file)
        label_range = (label.line_start, label.line_end)
        for finding_index, finding in enumerate(findings):
            if _normalise_path(finding.file) != label_path:
                continue
            actual_category = actual_categories[finding_index]
            if not _categories_compatible(label.category, actual_category):
                continue
            finding_range = line_range(finding.line)
            overlap = overlap_length(label_range, finding_range)
            if overlap <= 0:
                continue
            candidates.append(
                _Candidate(
                    overlap=overlap,
                    file=label_path,
                    label_start=label.line_start,
                    finding_start=finding_range[0],
                    label_index=label_index,
                    finding_index=finding_index,
                )
            )

    candidates.sort()

    used_labels: set[int] = set()
    used_findings: set[int] = set()
    matched: list[Match] = []
    for candidate in candidates:
        if candidate.label_index in used_labels or candidate.finding_index in used_findings:
            continue
        used_labels.add(candidate.label_index)
        used_findings.add(candidate.finding_index)
        matched.append(
            Match(
                expected=labels[candidate.label_index],
                actual=findings[candidate.finding_index],
                overlap=candidate.overlap,
            )
        )

    matched.sort(
        key=lambda pair: (
            _normalise_path(pair.expected.file),
            pair.expected.line_start,
            pair.expected.line_end,
            line_range(pair.actual.line)[0],
            line_range(pair.actual.line)[1],
        )
    )

    false_negatives = tuple(
        label for index, label in enumerate(labels) if index not in used_labels
    )
    false_positives = tuple(
        _as_expected(findings[index], actual_categories[index])
        for index in range(len(findings))
        if index not in used_findings
    )
    true_negatives = 1 if not labels and not findings else 0

    per_category: dict[str, CategoryScore] = {}
    for label in labels:
        per_category.setdefault(label.category, CategoryScore())
    for label_index, label in enumerate(labels):
        current = per_category[label.category]
        if label_index in used_labels:
            per_category[label.category] = CategoryScore(
                tp=current.tp + 1, fp=current.fp, fn=current.fn
            )
        else:
            per_category[label.category] = CategoryScore(
                tp=current.tp, fp=current.fp, fn=current.fn + 1
            )
    for false_positive in false_positives:
        current = per_category.get(false_positive.category, CategoryScore())
        per_category[false_positive.category] = CategoryScore(
            tp=current.tp, fp=current.fp + 1, fn=current.fn
        )

    return MatchResult(
        matched=tuple(matched),
        false_positives=false_positives,
        false_negatives=false_negatives,
        true_negatives=true_negatives,
        per_category=dict(sorted(per_category.items())),
    )
