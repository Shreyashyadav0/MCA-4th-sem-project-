"""Unified-diff parsing and finding anchoring.

Phase 2 turns a raw git diff (or a saved ``.diff`` / ``.patch`` file) into
structured, line-numbered hunks, then maps every :class:`~app.models.Finding`
onto the changed line ranges of that diff.

Two things this module refuses to do:

* invent line numbers — added-line numbers come from the hunk header counters,
  never from counting rows in the file, so a diff that starts at ``@@ -120,7``
  reports 120, not 1;
* widen the five-field finding contract — anchoring is :class:`AnchoredFinding`
  metadata, because "GitHub will drop this comment" is not part of what the
  reviewer believes.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from app.models import (
    AnchorStatus,
    AnchoredFinding,
    Finding,
    severity_counts,
    sort_findings,
    verdict_for,
)

__all__ = [
    "DiffLine",
    "Hunk",
    "FileDiff",
    "DiffBundle",
    "FileSummary",
    "DiffReviewResult",
    "DiffParseError",
    "parse_diff",
    "parse_diff_file",
    "bundle_from_source",
    "anchor_findings",
    "normalize_path",
]

ChangeKind = Literal["added", "modified", "deleted", "renamed"]
LineKind = Literal["added", "removed", "context"]

_DEV_NULL = "/dev/null"
_GIT_RE = re.compile(r"^diff --git (?P<old>\S+) (?P<new>\S+)$")
_HUNK_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))?"
    r" \+(?P<new_start>\d+)(?:,(?P<new_count>\d+))?"
    r" @@[ ]?(?P<section>.*)$"
)


class DiffParseError(ValueError):
    """Raised when a string cannot be read as a unified diff."""


def normalize_path(raw: str) -> str:
    """Strip git's ``a/`` / ``b/`` prefix and quotes from a header path.

    The prefix is removed at most once, so a real path such as
    ``app/config.py`` is never mangled into ``pp/config.py``.
    """
    path = raw.strip()
    if len(path) >= 2 and path.startswith('"') and path.endswith('"'):
        path = path[1:-1]
    if path.startswith("./"):
        path = path[2:]
    if len(path) > 2 and path.startswith(("a/", "b/")):
        path = path[2:]
    return path


def _spans(numbers: Sequence[int]) -> list[str]:
    """Compress ``[1,2,3,7]`` into ``["1-3", "7"]``."""
    ordered = sorted(set(numbers))
    if not ordered:
        return []
    spans: list[str] = []
    start = prev = ordered[0]
    for number in ordered[1:]:
        if number == prev + 1:
            prev = number
            continue
        spans.append(str(start) if start == prev else f"{start}-{prev}")
        start = prev = number
    spans.append(str(start) if start == prev else f"{start}-{prev}")
    return spans


def _parse_range(value: str) -> tuple[int, int]:
    """Turn a finding's line field into ``(start, end)``; ``"42"`` -> ``(42, 42)``."""
    start, _, end = value.partition("-")
    return int(start), int(end or start)


class DiffLine(BaseModel):
    """One body line of a hunk, with the file line number it maps to."""

    model_config = ConfigDict(extra="forbid")

    kind: LineKind
    text: str
    old_lineno: int | None = None
    new_lineno: int | None = None


class Hunk(BaseModel):
    """One ``@@`` block: the header counters plus every body line."""

    model_config = ConfigDict(extra="forbid")

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    section: str = Field(default="", description="Trailing context after the @@ header.")
    lines: list[DiffLine] = Field(default_factory=list)

    @property
    def header(self) -> str:
        """Reconstruct the ``@@`` header line."""
        return (
            f"@@ -{self.old_start},{self.old_count} "
            f"+{self.new_start},{self.new_count} @@ {self.section}"
        ).rstrip()

    @property
    def added_lines(self) -> list[int]:
        return [line.new_lineno for line in self.lines if line.kind == "added" and line.new_lineno]

    @property
    def removed_lines(self) -> list[int]:
        return [line.old_lineno for line in self.lines if line.kind == "removed" and line.old_lineno]


class FileDiff(BaseModel):
    """Everything one diff does to one file."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(description="Post-change path; the old path for deletions.")
    old_path: str = Field(default="", description="Pre-change path.")
    change: ChangeKind = "modified"
    hunks: list[Hunk] = Field(default_factory=list)
    binary: bool = False

    @property
    def added_line_numbers(self) -> set[int]:
        """Every added line number in the new file."""
        return {n for hunk in self.hunks for n in hunk.added_lines}

    @property
    def removed_line_numbers(self) -> set[int]:
        return {n for hunk in self.hunks for n in hunk.removed_lines}

    @property
    def added_spans(self) -> list[str]:
        """Added lines compressed into reviewable ranges, e.g. ``["3-8", "12"]``."""
        return _spans(self.added_line_numbers)

    @property
    def added_line_count(self) -> int:
        return len(self.added_line_numbers)

    def hunk_for_line(self, lineno: int) -> Hunk | None:
        """Return the hunk covering ``lineno`` on the new side, if any."""
        for hunk in self.hunks:
            if hunk.new_count == 0:
                if lineno == hunk.new_start:
                    return hunk
                continue
            if hunk.new_start <= lineno < hunk.new_start + hunk.new_count:
                return hunk
        return None


class FileSummary(BaseModel):
    """Compact per-file entry for report output."""

    model_config = ConfigDict(extra="forbid")

    path: str
    change: ChangeKind
    added_spans: list[str] = Field(default_factory=list)
    added_line_count: int = 0
    hunk_count: int = 0
    binary: bool = False


class DiffBundle(BaseModel):
    """A parsed diff: the file list plus lookups used by the anchorer."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(default="<diff>", description="Where the diff came from.")
    files: list[FileDiff] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.files

    @property
    def files_changed(self) -> int:
        return len(self.files)

    @property
    def added_line_count(self) -> int:
        return sum(file.added_line_count for file in self.files)

    def file_for(self, path: str) -> FileDiff | None:
        """Look a file up by path, tolerating ``a/``, ``b/`` and ``./`` prefixes."""
        key = normalize_path(path)
        for file in self.files:
            if file.path == key or file.path == path:
                return file
        return None

    def summaries(self) -> list[FileSummary]:
        return [
            FileSummary(
                path=file.path,
                change=file.change,
                added_spans=file.added_spans,
                added_line_count=file.added_line_count,
                hunk_count=len(file.hunks),
                binary=file.binary,
            )
            for file in self.files
        ]


class DiffReviewResult(BaseModel):
    """A diff-mode review: parsed files, findings, and each finding's anchor."""

    model_config = ConfigDict(extra="forbid")

    mode: str = Field(description='Active review mode: "live" or "mock".')
    target: str = Field(min_length=1, description="Diff file or identifier reviewed.")
    files: list[FileSummary] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    anchors: list[AnchoredFinding] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

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
    def sorted_anchors(self) -> list[AnchoredFinding]:
        """Anchors ordered CRITICAL-first, then by line."""
        order = {
            (finding.file, finding.line, finding.issue): rank
            for rank, finding in enumerate(sort_findings(self.findings))
        }
        return sorted(
            self.anchors,
            key=lambda a: (
                order.get((a.finding.file, a.finding.line, a.finding.issue), len(order)),
                a.finding.file,
                int(a.finding.line.split("-")[0]),
            ),
        )

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def verdict(self) -> str:
        """Gate decision derived from the severity mix; serialised into JSON."""
        return verdict_for(self.findings)

    def to_json(self) -> str:
        """Serialise the full diff review as indented JSON."""
        return self.model_dump_json(indent=2)


class _Builder:
    """Mutable accumulator while a single file's section is being parsed."""

    __slots__ = ("old_path", "new_path", "hunks", "binary", "explicit_change", "has_header")

    def __init__(self, old_path: str = "", new_path: str = "") -> None:
        self.old_path = old_path
        self.new_path = new_path
        self.hunks: list[Hunk] = []
        self.binary = False
        self.explicit_change: ChangeKind | None = None
        self.has_header = False

    def finish(self) -> FileDiff | None:
        """Freeze into a :class:`FileDiff`, inferring the change kind."""
        old, new = self.old_path, self.new_path
        path = new if new and new != _DEV_NULL else old
        if not path:
            return None
        change = self.explicit_change
        if change is None:
            if old == _DEV_NULL:
                change = "added"
            elif new == _DEV_NULL:
                change = "deleted"
            elif old and new and old != new:
                change = "renamed"
            else:
                change = "modified"
        return FileDiff(
            path=path,
            old_path=old or path,
            change=change,
            hunks=self.hunks,
            binary=self.binary,
        )


def parse_diff(raw: str, *, source: str = "<diff>") -> DiffBundle:
    """Parse a unified diff (git or plain) into structured hunks.

    Args:
        raw: The diff text.
        source: Label recorded on the bundle, usually the file path.

    Returns:
        A :class:`DiffBundle`; empty hunk lists are legal (mode-only changes).

    Raises:
        DiffParseError: The text is empty or contains no file headers.
    """
    if not raw.strip():
        raise DiffParseError("diff is empty")

    lines = raw.splitlines()
    files: list[FileDiff] = []
    builder: _Builder | None = None
    hunk_lines: list[DiffLine] = []
    hunk_header: tuple[int, int, int, int, str] | None = None
    remaining_old = remaining_new = 0
    old_no = new_no = 0

    def flush_file() -> None:
        nonlocal builder
        if builder is not None:
            finished = builder.finish()
            if finished is not None:
                files.append(finished)
            builder = None

    def close_hunk() -> None:
        nonlocal hunk_lines, hunk_header, remaining_old, remaining_new
        if builder is not None and hunk_header is not None:
            old_start, old_count, new_start, new_count, section = hunk_header
            builder.hunks.append(
                Hunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    section=section,
                    lines=hunk_lines,
                )
            )
        hunk_lines = []
        hunk_header = None
        remaining_old = remaining_new = 0

    index = 0
    while index < len(lines):
        line = lines[index]

        # --- inside a hunk body: counters decide when it ends -----------------
        if remaining_old > 0 or remaining_new > 0:
            if line.startswith("diff --git ") or (
                line.startswith("--- ") and index + 1 < len(lines) and lines[index + 1].startswith("+++ ")
            ):
                # The hunk header promised more lines than the patch contains (a
                # truncated or hand-edited diff). Consuming this line as hunk context
                # would swallow the next file entirely, so close the hunk and let the
                # outer loop re-process it as a header.
                close_hunk()
                continue
            if line.startswith("\\"):  # "\ No newline at end of file"
                index += 1
                continue
            if line.startswith("+"):
                hunk_lines.append(DiffLine(kind="added", text=line[1:], new_lineno=new_no))
                new_no += 1
                remaining_new -= 1
            elif line.startswith("-"):
                hunk_lines.append(DiffLine(kind="removed", text=line[1:], old_lineno=old_no))
                old_no += 1
                remaining_old -= 1
            else:
                text = line[1:] if line.startswith(" ") else line
                hunk_lines.append(
                    DiffLine(kind="context", text=text, old_lineno=old_no, new_lineno=new_no)
                )
                old_no += 1
                new_no += 1
                remaining_old -= 1
                remaining_new -= 1
            index += 1
            continue

        close_hunk()

        git_match = _GIT_RE.match(line)
        if git_match:
            flush_file()
            builder = _Builder(
                normalize_path(git_match.group("old")),
                normalize_path(git_match.group("new")),
            )
            index += 1
            continue

        if line.startswith("--- ") and index + 1 < len(lines) and lines[index + 1].startswith("+++ "):
            close_hunk()
            old_header = normalize_path(line[4:])
            new_header = normalize_path(lines[index + 1][4:])
            # A "diff --git" line already opened this file section; reuse that
            # builder instead of emitting a phantom hunk-less duplicate. A
            # builder that already has a header or hunks belongs to an earlier
            # file and must be flushed.
            if builder is None or builder.has_header or builder.hunks:
                flush_file()
                builder = _Builder()
            builder.old_path = old_header
            builder.new_path = new_header
            builder.has_header = True
            index += 2
            continue

        hunk_match = _HUNK_RE.match(line)
        if hunk_match:
            if builder is None:
                builder = _Builder()
            close_hunk()
            old_start = int(hunk_match.group("old_start"))
            old_count = int(hunk_match.group("old_count") or 1)
            new_start = int(hunk_match.group("new_start"))
            new_count = int(hunk_match.group("new_count") or 1)
            hunk_header = (
                old_start,
                old_count,
                new_start,
                new_count,
                (hunk_match.group("section") or "").strip(),
            )
            old_no, new_no = old_start, new_start
            remaining_old, remaining_new = old_count, new_count
            index += 1
            continue

        if builder is not None:
            if line.startswith("new file mode"):
                builder.explicit_change = "added"
            elif line.startswith("deleted file mode"):
                builder.explicit_change = "deleted"
            elif line.startswith(("rename from", "rename to")):
                if builder.explicit_change is None:
                    builder.explicit_change = "renamed"
            elif line.startswith(("Binary files", "GIT binary patch")):
                builder.binary = True
        index += 1

    close_hunk()
    flush_file()

    if not files:
        raise DiffParseError(
            "no file headers found; expected 'diff --git' or a '--- / +++' pair"
        )
    return DiffBundle(source=source, files=files)


def parse_diff_file(path: Path) -> DiffBundle:
    """Read and parse a ``.diff`` / ``.patch`` file.

    Raises:
        DiffParseError: The file is unreadable or is not a diff.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DiffParseError(f"cannot read {path}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise DiffParseError(f"{path} is not valid UTF-8 text") from exc
    return parse_diff(raw, source=str(path))


def anchor_findings(bundle: DiffBundle, findings: Iterable[Finding]) -> list[AnchoredFinding]:
    """Place each finding against the diff's changed line ranges.

    Status is ``anchored`` when the file is in the diff *and* the reported line
    range touches an added line, ``file_only`` when the file is in the diff but
    the line was not changed (GitHub would drop that inline comment), and
    ``unanchored`` when the file is not in the diff at all.

    Args:
        bundle: Parsed diff.
        findings: Findings to place; they are returned in severity order.

    Returns:
        One :class:`AnchoredFinding` per input finding, same order.
    """
    anchored: list[AnchoredFinding] = []
    for finding in sort_findings(findings):
        target = bundle.file_for(finding.file)
        if target is None:
            anchored.append(
                AnchoredFinding(
                    finding=finding,
                    status=AnchorStatus.UNANCHORED,
                    detail=f"{finding.file} is not part of this diff",
                )
            )
            continue

        start, end = _parse_range(finding.line)
        hits = sorted(n for n in target.added_line_numbers if start <= n <= end)
        if hits:
            hunk = target.hunk_for_line(hits[0])
            detail = "added line" if len(hits) == 1 else f"{len(hits)} added lines in range"
            anchored.append(
                AnchoredFinding(
                    finding=finding,
                    status=AnchorStatus.ANCHORED,
                    hunk_header=hunk.header if hunk else None,
                    detail=f"{detail}: {', '.join(_spans(hits))}",
                )
            )
        else:
            hunk = target.hunk_for_line(start)
            anchored.append(
                AnchoredFinding(
                    finding=finding,
                    status=AnchorStatus.FILE_ONLY,
                    hunk_header=hunk.header if hunk else None,
                    detail=(
                        f"{target.path} is in the diff but line {finding.line} was not changed; "
                        "GitHub would drop this inline comment"
                    ),
                )
            )
    return anchored


def bundle_from_source(path: Path | str, source: str) -> DiffBundle:
    """Wrap a whole source file as one all-added hunk.

    Phase 3 runs diff-based rules on a single file by pretending the entire file
    is new: every line is an added line, so every finding is anchorable and the
    rule engine needs no second code path.

    Args:
        path: File path recorded on the bundle and its findings.
        source: Decoded file content.

    Returns:
        A :class:`DiffBundle` with exactly one file and one hunk.
    """
    lines = source.splitlines()
    hunks: list[Hunk] = []
    if lines:
        hunks.append(
            Hunk(
                old_start=0,
                old_count=0,
                new_start=1,
                new_count=len(lines),
                lines=[
                    DiffLine(kind="added", text=text, new_lineno=number)
                    for number, text in enumerate(lines, start=1)
                ],
            )
        )
    return DiffBundle(
        source=str(path),
        files=[
            FileDiff(
                path=normalize_path(str(path)),
                old_path=_DEV_NULL,
                change="added",
                hunks=hunks,
            )
        ],
    )
