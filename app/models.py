"""Structured output models for the reviewer (Pydantic v2).

Two layers, deliberately separate:

* :class:`Finding` — what the reviewer believes. Exactly five fields, nothing
  else, ``extra="forbid"``. A stray key from a future LLM response fails at the
  boundary instead of leaking into a PR comment.
* :class:`AnchoredFinding` — where that finding lands in a diff. Anchoring is
  review metadata (can GitHub attach this comment?), not part of the finding
  contract, so it wraps a finding rather than extending it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

__all__ = [
    "Severity",
    "AnchorStatus",
    "Finding",
    "AnchoredFinding",
    "ReviewResult",
    "ReviewMode",
    "severity_counts",
    "verdict_for",
    "sort_findings",
]

ReviewMode = str  # "live" | "mock", narrowed by the validator on each result

_LINE_RE = re.compile(r"^\d+(?:-\d+)?$")
_ORDER: tuple[str, ...] = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


class Severity(str, Enum):
    """Severity ladder. Nothing outside these four values is legal."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        """0 for LOW through 3 for CRITICAL; used to order findings."""
        return _ORDER.index(self.value)


class AnchorStatus(str, Enum):
    """How a finding relates to the diff under review."""

    ANCHORED = "anchored"      # file is in the diff and the line is an added line
    FILE_ONLY = "file_only"    # file is in the diff, but the line was not changed
    UNANCHORED = "unanchored"  # file is not in the diff at all


class Finding(BaseModel):
    """One review finding, carrying the five contract fields and no others."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    file: str = Field(
        min_length=1,
        description="Path relative to the project root, or '<snippet>' for pasted code.",
    )
    line: str = Field(description='Line number as "42", or a range as "42-45".')
    severity: Severity = Field(description="LOW | MEDIUM | HIGH | CRITICAL.")
    issue: str = Field(min_length=1, description="One sentence: what is wrong and why it bites.")
    suggested_fix: str = Field(
        min_length=1,
        description="Concrete replacement code or the exact change to make.",
    )

    @field_validator("line")
    @classmethod
    def _check_line(cls, value: str) -> str:
        """Reject anything that is not a line number or an ascending range."""
        if not _LINE_RE.match(value):
            raise ValueError(f'line must look like "42" or "42-45", got {value!r}')
        if "-" in value:
            start, _, end = value.partition("-")
            if int(end) < int(start):
                raise ValueError(f"line range must ascend, got {value!r}")
        return value

    def as_row(self) -> dict[str, str]:
        """Flatten to the five display fields, in contract order."""
        return {
            "File": self.file,
            "Line": self.line,
            "Severity": self.severity.value,
            "Issue": self.issue,
            "Suggested Fix": self.suggested_fix,
        }


class AnchoredFinding(BaseModel):
    """A finding placed against the changed lines of a parsed diff."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    finding: Finding
    status: AnchorStatus
    hunk_header: str | None = Field(
        default=None, description='Hunk the finding lands in, e.g. "@@ -1,5 +1,9 @@".'
    )
    detail: str = Field(default="", description="Why this status was assigned.")

    def as_row(self) -> dict[str, str]:
        """Five contract fields plus the anchor status, for display."""
        return {**self.finding.as_row(), "Anchor": self.status.value}


def severity_counts(findings: Iterable[Finding]) -> dict[str, int]:
    """Finding count per severity, always all four keys."""
    tally = {name: 0 for name in _ORDER}
    for finding in findings:
        tally[finding.severity.value] += 1
    return tally


def sort_findings(findings: Iterable[Finding]) -> list[Finding]:
    """CRITICAL first, then by line number — the order a reviewer reads in."""
    return sorted(
        findings,
        key=lambda f: (-f.severity.rank, f.file, int(f.line.split("-")[0]), f.issue),
    )


def verdict_for(findings: Iterable[Finding]) -> str:
    """One-line gate decision derived from the severity mix."""
    tally = severity_counts(findings)
    if tally["CRITICAL"] or tally["HIGH"]:
        return "block"
    if tally["MEDIUM"] or tally["LOW"]:
        return "approve with comments"
    return "approve"


class ReviewResult(BaseModel):
    """The whole review for one source file: mode, findings and notes."""

    model_config = ConfigDict(extra="forbid")

    mode: str = Field(description='Active review mode: "live" or "mock".')
    target: str = Field(min_length=1, description="File that was reviewed.")
    findings: list[Finding] = Field(default_factory=list)
    notes: list[str] = Field(
        default_factory=list,
        description="Why this mode was chosen; shown to the user, never dropped.",
    )

    @field_validator("mode")
    @classmethod
    def _check_mode(cls, value: str) -> str:
        if value not in ("live", "mock"):
            raise ValueError(f'mode must be "live" or "mock", got {value!r}')
        return value

    @model_validator(mode="before")
    @classmethod
    def _drop_computed(cls, data: object) -> object:
        """Ignore the serialised ``verdict`` so the model can read its own JSON."""
        if isinstance(data, dict) and "verdict" in data:
            data = {k: v for k, v in data.items() if k != "verdict"}
        return data

    @property
    def sorted_findings(self) -> list[Finding]:
        return sort_findings(self.findings)

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def verdict(self) -> str:
        """Gate decision derived from the severity mix; serialised into JSON."""
        return verdict_for(self.findings)

    def to_json(self) -> str:
        """Serialise the full result (mode included) as indented JSON."""
        return self.model_dump_json(indent=2)
