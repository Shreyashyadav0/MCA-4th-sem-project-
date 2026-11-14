"""Offline review paths — what runs when no LLM is available.

Since Phase 3 these paths are backed by the real local rule engine
(:mod:`app.rules`): no network, no API key, deterministic findings. The module
keeps its Phase 1/2 name and signatures because it is still exactly one thing —
the answer to "the LLM is not available, what do you do instead?" — and Phase 4
swaps the live path in beside it rather than through it.

* :func:`offline_review` — one source file, treated as an all-added hunk.
* :func:`offline_diff_findings` — an already-parsed diff.
"""

from __future__ import annotations

from pathlib import Path

from app.models import Finding, ReviewResult, Severity
from app.parser import DiffBundle, bundle_from_source
from app.rules import RULES, review_diff

__all__ = ["offline_review", "offline_diff_findings", "ENGINE_NOTE"]

ENGINE_NOTE = (
    f"local rule engine: {len(RULES)} deterministic rules, no network, no API key"
)


def offline_review(
    target: Path,
    source: str,
    reason: str,
    *,
    min_severity: Severity | None = None,
) -> ReviewResult:
    """Review one source file with the local rule engine.

    Args:
        target: File under review.
        source: Decoded file content.
        reason: Why the LLM path is not in use.
        min_severity: Drop findings below this severity when set.

    Returns:
        A :class:`ReviewResult` with ``mode="mock"`` and real rule findings.
    """
    bundle = bundle_from_source(target, source)
    findings = review_diff(bundle, min_severity=min_severity)
    notes = [f"mock mode: {reason}", ENGINE_NOTE]
    if not findings:
        notes.append("no findings from the local rule engine on this file")
    return ReviewResult(
        mode="mock",
        target=str(target),
        findings=findings,
        notes=notes,
    )


def offline_diff_findings(
    bundle: DiffBundle,
    reason: str,
    *,
    min_severity: Severity | None = None,
) -> list[Finding]:
    """Review a parsed diff with the local rule engine.

    Args:
        bundle: Parsed diff.
        reason: Why the LLM path is not in use; recorded by the caller.
        min_severity: Drop findings below this severity when set.

    Returns:
        Findings on the diff's added line numbers, CRITICAL first.
    """
    return review_diff(bundle, min_severity=min_severity)
