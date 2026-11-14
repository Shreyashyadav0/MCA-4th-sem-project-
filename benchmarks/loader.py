"""Strict loader for the golden dataset under ``benchmarks/golden``.

The loader is deliberately unforgiving. A benchmark is only as trustworthy as its
labels, and a label that silently degrades — a string ``"4"`` coerced to ``4``, a
misspelled severity, a reversed line range, an extra key from a future format — is
a wrong label that nobody notices. Every such problem is therefore raised as a
:class:`DatasetError` naming the sample id and the file at fault, so the fix is
mechanical rather than a hunt.

Design contract
---------------
* **Strict Pydantic v2.** The finding shape is ``extra="forbid"`` and every model
  runs in strict mode: no ``str`` -> ``int`` coercion, no ``bool`` standing in for
  an ``int``, no case-insensitive severity. The only tolerated freedom is an
  optional top-level ``"note"`` key, which the README documents as free text.
* **Format examples are loadable.** ``example_*`` directories are picked up even
  when they are absent from ``evaluation_samples``, so the harness can smoke-test
  against them; each such sample is flagged ``meta["format_example"] = True`` and
  must be excluded from any reported metric.
* **Deterministic.** Samples are returned sorted by id, so two runs over the same
  directory produce identical lists in identical order.
* **Offline and inert.** Filesystem and JSON only: no network, no ``app.main``,
  no ``app.cli``.

A missing ``manifest.json`` is an error — without it there is no way to tell the
evaluation set from the format examples. An empty ``evaluation_samples`` list is
not an error: the loader then returns just the format examples.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

__all__ = [
    "DatasetError",
    "ExpectedFinding",
    "Sample",
    "load_dataset",
    "load_sample",
    "MANIFEST_NAME",
    "DIFF_NAME",
    "EXPECTED_NAME",
    "FORMAT_EXAMPLE_PREFIX",
]

MANIFEST_NAME = "manifest.json"
DIFF_NAME = "change.diff"
EXPECTED_NAME = "expected.json"
FORMAT_EXAMPLE_PREFIX = "example_"

#: The only severities a human label may carry, mirroring :class:`app.models.Severity`.
SeverityLiteral = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class DatasetError(Exception):
    """A dataset problem the loader refuses to paper over.

    Attributes:
        sample_id: Id of the offending sample, or ``None`` for a dataset-level
            problem such as a missing or malformed ``manifest.json``.
        path: File or directory at fault, when one is known.
    """

    def __init__(
        self,
        message: str,
        *,
        sample_id: str | None = None,
        path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.sample_id = sample_id
        self.path = path

    def __str__(self) -> str:
        """Message with the sample id and file prefixed, so logs are actionable."""
        parts: list[str] = []
        if self.sample_id is not None:
            parts.append(f"sample {self.sample_id!r}")
        if self.path is not None:
            parts.append(str(self.path))
        prefix = ": ".join(parts)
        return f"{prefix}: {super().__str__()}" if prefix else super().__str__()


@dataclass(frozen=True)
class ExpectedFinding:
    """One human label: what should have been reported, and where.

    Attributes:
        file: Post-change path exactly as it appears in the diff's ``+++`` line.
        line_start: First new-side line, inclusive, 1-based.
        line_end: Last new-side line, inclusive; equal to ``line_start`` for one
            line.
        category: One of the ``app.rules.RuleCategory`` values, or ``"llm"`` for a
            finding only a model would catch.
        severity: ``LOW``, ``MEDIUM``, ``HIGH`` or ``CRITICAL``.
    """

    file: str
    line_start: int
    line_end: int
    category: str
    severity: str


@dataclass(frozen=True)
class Sample:
    """One dataset entry: the diff to review and the labels it must reproduce.

    Attributes:
        id: Directory name under the dataset root, unique within the dataset.
        diff_text: Raw unified diff, verbatim as stored in ``change.diff``.
        expected: Human labels; an empty tuple means "this change is clean" and is
            what true negatives are measured from.
        meta: Provenance flags. Carries ``"format_example": bool`` always, and
            ``"note"`` when ``expected.json`` supplied one.
    """

    id: str
    diff_text: str
    expected: tuple[ExpectedFinding, ...]
    meta: dict = field(default_factory=dict)


class _ExpectedFindingIn(BaseModel):
    """Wire shape of one finding inside ``expected.json``; strict and closed."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    file: str = Field(min_length=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    category: str = Field(min_length=1)
    severity: SeverityLiteral

    @model_validator(mode="after")
    def _check_range(self) -> "_ExpectedFindingIn":
        """Reject a reversed or empty line range before it can skew an overlap."""
        if self.line_end < self.line_start:
            raise ValueError(
                f"line_end ({self.line_end}) is before line_start ({self.line_start})"
            )
        return self


class _ExpectedFileIn(BaseModel):
    """Wire shape of a whole ``expected.json``; only ``note`` is optional extra."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    note: str | None = None
    findings: list[_ExpectedFindingIn] = Field(default_factory=list)


def _read_json(path: Path, *, sample_id: str | None) -> Any:
    """Read and parse one JSON file, converting every failure to DatasetError.

    Args:
        path: File to read.
        sample_id: Id to attach to the error, or ``None`` at dataset level.

    Returns:
        The decoded JSON value.

    Raises:
        DatasetError: The file is missing, unreadable or not valid JSON.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise DatasetError(
            f"missing file {path.name}", sample_id=sample_id, path=path
        ) from exc
    except OSError as exc:
        raise DatasetError(
            f"cannot read file: {exc.strerror or exc}", sample_id=sample_id, path=path
        ) from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DatasetError(
            f"invalid JSON at line {exc.lineno} column {exc.colno}: {exc.msg}",
            sample_id=sample_id,
            path=path,
        ) from exc


def _read_diff(path: Path, *, sample_id: str) -> str:
    """Read one ``change.diff`` verbatim.

    Args:
        path: File to read.
        sample_id: Id to attach to the error.

    Returns:
        The diff text, newlines preserved.

    Raises:
        DatasetError: The file is missing, unreadable or empty.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise DatasetError(
            f"missing file {path.name}", sample_id=sample_id, path=path
        ) from exc
    except OSError as exc:
        raise DatasetError(
            f"cannot read file: {exc.strerror or exc}", sample_id=sample_id, path=path
        ) from exc
    if not text.strip():
        raise DatasetError("diff is empty", sample_id=sample_id, path=path)
    return text


def load_sample(root: Path, sample_id: str, *, format_example: bool = False) -> Sample:
    """Load and validate one sample directory.

    Args:
        root: Dataset root holding the sample directory.
        sample_id: Directory name of the sample; also the sample id.
        format_example: Whether this sample is a format example rather than
            evaluation data; recorded in ``meta["format_example"]``.

    Returns:
        The validated sample.

    Raises:
        DatasetError: The directory or one of its files is missing or unreadable,
            the JSON does not validate, a line range is reversed, or a severity is
            not one of the four legal values.
    """
    directory = root / sample_id
    if not directory.is_dir():
        raise DatasetError(
            "sample directory does not exist", sample_id=sample_id, path=directory
        )

    diff_text = _read_diff(directory / DIFF_NAME, sample_id=sample_id)
    expected_path = directory / EXPECTED_NAME
    payload = _read_json(expected_path, sample_id=sample_id)

    if not isinstance(payload, dict):
        raise DatasetError(
            "expected.json must be a JSON object with a 'findings' key",
            sample_id=sample_id,
            path=expected_path,
        )

    try:
        parsed = _ExpectedFileIn.model_validate(payload)
    except ValidationError as exc:
        raise DatasetError(
            "expected.json does not match the label schema:\n"
            + _format_validation_error(exc),
            sample_id=sample_id,
            path=expected_path,
        ) from exc

    expected = tuple(
        ExpectedFinding(
            file=item.file,
            line_start=item.line_start,
            line_end=item.line_end,
            category=item.category,
            severity=item.severity,
        )
        for item in parsed.findings
    )

    meta: dict = {"format_example": format_example}
    if parsed.note is not None:
        meta["note"] = parsed.note
    return Sample(id=sample_id, diff_text=diff_text, expected=expected, meta=meta)


def _format_validation_error(exc: ValidationError) -> str:
    """Render a Pydantic error list as one indented, human-readable block.

    Args:
        exc: The validation failure.

    Returns:
        One line per error, each naming the JSON location and the reason.
    """
    lines: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "<root>"
        lines.append(f"  {location}: {error['msg']} (got {error.get('input')!r})")
    return "\n".join(lines)


def _manifest_ids(manifest: dict, manifest_path: Path) -> list[str]:
    """Extract the evaluation sample ids from a parsed manifest.

    Args:
        manifest: Decoded ``manifest.json``.
        manifest_path: Path of the manifest, for error reporting.

    Returns:
        Ids in manifest order, duplicates removed, first occurrence kept.

    Raises:
        DatasetError: ``evaluation_samples`` is present but is not a list of
            strings.
    """
    raw = manifest.get("evaluation_samples", [])
    if not isinstance(raw, list):
        raise DatasetError(
            "'evaluation_samples' must be a list of sample ids", path=manifest_path
        )
    ids: list[str] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, str) or not entry.strip():
            raise DatasetError(
                f"'evaluation_samples' entries must be non-empty strings, got {entry!r}",
                path=manifest_path,
            )
        if entry not in seen:
            seen.add(entry)
            ids.append(entry)
    return ids


def load_dataset(root: Path) -> list[Sample]:
    """Load every sample under a dataset root.

    Loads each id listed in ``manifest.json`` under ``evaluation_samples``, plus
    every ``example_*`` directory that exists on disk (so the format examples can
    drive a smoke run). Format examples are flagged in ``meta`` and must be
    excluded from reported metrics.

    Args:
        root: Dataset root, e.g. ``benchmarks/golden``.

    Returns:
        Samples sorted by id, for determinism.

    Raises:
        DatasetError: ``manifest.json`` is missing, unreadable or not a JSON
            object; ``evaluation_samples`` is malformed; or any sample is missing,
            unreadable or fails label validation.
    """
    root = Path(root)
    if not root.is_dir():
        raise DatasetError("dataset root does not exist", path=root)

    manifest_path = root / MANIFEST_NAME
    manifest = _read_json(manifest_path, sample_id=None)
    if not isinstance(manifest, dict):
        raise DatasetError(
            "manifest.json must be a JSON object", path=manifest_path
        )

    evaluation_ids = _manifest_ids(manifest, manifest_path)
    example_ids = sorted(
        child.name
        for child in root.iterdir()
        if child.is_dir() and child.name.startswith(FORMAT_EXAMPLE_PREFIX)
    )

    samples: list[Sample] = []
    for sample_id in evaluation_ids:
        samples.append(load_sample(root, sample_id, format_example=False))
    for sample_id in example_ids:
        if sample_id in evaluation_ids:
            # An id explicitly listed for evaluation is evaluation data even if it
            # happens to be named example_*; loading it twice would double-count.
            continue
        samples.append(load_sample(root, sample_id, format_example=True))

    samples.sort(key=lambda sample: sample.id)
    return samples
