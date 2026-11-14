"""Interactive helper for labelling golden-dataset samples by hand.

Human-labelling rule
--------------------
Every label in ``benchmarks/golden`` must be written by a **human reading the
diff**. This tool is a keyboard, not an author: it shows the patch, asks for the
file, the line range, the category and the severity, and records exactly what
was typed. It never parses the patch to suggest a finding, never runs the rule
engine, never calls a model, and never pre-fills a field with a guess. If a
sample is left untouched, its ``expected.json`` keeps whatever it had — an
empty ``findings`` list included, which is itself a legitimate "this change is
clean" label.

Validation is delegated to the loader's own Pydantic wire models
(:class:`benchmarks.loader._ExpectedFindingIn` and
:class:`benchmarks.loader._ExpectedFileIn`), so a label this helper accepts can
never be a label :func:`benchmarks.loader.load_dataset` rejects. The private
names are imported deliberately: a second copy of the schema would drift, and a
drifted schema would corrupt the dataset quietly.

Usage
-----
::

    python -m benchmarks.label_helper --status
    python -m benchmarks.label_helper --dataset benchmarks/golden
    python -m benchmarks.label_helper --dataset benchmarks/golden --force

Commands accepted at the file prompt
------------------------------------
``done``
    Write the findings collected so far (possibly none) and move to the next
    sample.
``skip``
    Leave this sample exactly as it is and move to the next one.
``quit``
    Stop immediately without writing anything for the current sample.
``help``
    Reprint the category and severity vocabularies.

Exit codes
----------
``0``
    The session ended normally, whether or not anything was written.
``1``
    A file could not be read or written.
``2``
    A usage or environment problem: the dataset root is missing, or stdin is not
    a TTY and ``--allow-non-tty`` was not passed — refusing beats hanging on a
    pipe that will never answer.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from pydantic import ValidationError

from app.parser import DiffBundle, DiffParseError, parse_diff
from app.rules import RuleCategory
from benchmarks.loader import (
    DIFF_NAME,
    EXPECTED_NAME,
    FORMAT_EXAMPLE_PREFIX,
    MANIFEST_NAME,
    DatasetError,
    _ExpectedFileIn,
    _ExpectedFindingIn,
    load_sample,
)

__all__ = [
    "SampleStatus",
    "build_parser",
    "main",
    "render_diff",
    "scan_dataset",
]

PROG: str = "python -m benchmarks.label_helper"
"""Program name shown in ``--help`` and in error messages."""

DEFAULT_DATASET: str = "benchmarks/golden"
"""Dataset root used when ``--dataset`` is omitted."""

CATEGORIES: tuple[str, ...] = tuple(
    category.value for category in RuleCategory
) + ("llm",)
"""Legal ``category`` values: every rule category, plus ``llm``.

``llm`` is the one category that is not a rule: it exists for a finding only a
model would catch, and it is accepted here because ``benchmarks/golden/README.md``
documents it as legal.
"""

SEVERITIES: tuple[str, ...] = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
"""Legal ``severity`` values, mirroring :data:`benchmarks.loader.SeverityLiteral`."""

COMMANDS: tuple[str, ...] = ("done", "skip", "quit", "help")
"""Control words accepted where a file path would otherwise be typed."""

EXIT_OK: int = 0
"""The session ended normally."""

EXIT_IO: int = 1
"""A sample file could not be read or written."""

EXIT_USAGE: int = 2
"""Bad arguments or a non-interactive stdin."""

_STATE_UNLABELLED: str = "unlabelled"
_STATE_LABELLED: str = "labelled"
_STATE_EXAMPLE: str = "format-example"
_STATE_ERROR: str = "error"


class _InputClosed(Exception):
    """Raised when stdin reaches EOF mid-session."""


@dataclass(frozen=True, slots=True)
class SampleStatus:
    """What one sample directory looks like right now.

    Attributes:
        id: Directory name, which is also the sample id.
        path: The sample directory.
        findings: Number of findings in ``expected.json``, or ``None`` when the
            file is missing or unreadable.
        format_example: Whether the directory is a ``example_*`` format example,
            which is never counted as evaluation data.
        in_manifest: Whether the id appears in ``manifest.json`` under
            ``evaluation_samples``.
        error: Why ``expected.json`` could not be counted, if it could not.
    """

    id: str
    path: Path
    findings: int | None
    format_example: bool
    in_manifest: bool
    error: str = ""

    @property
    def kind(self) -> str:
        """``format-example`` or ``evaluation``, for the status table."""
        return _STATE_EXAMPLE if self.format_example else "evaluation"

    @property
    def state(self) -> str:
        """``format-example``, ``error``, ``labelled`` or ``unlabelled``.

        Format examples are reported as such even when they carry illustrative
        findings: they are excluded from every metric, so counting them as
        labelled evaluation data would overstate the dataset.
        """
        if self.error:
            return _STATE_ERROR
        if self.format_example:
            return _STATE_EXAMPLE
        if self.findings:
            return _STATE_LABELLED
        return _STATE_UNLABELLED

    @property
    def needs_label(self) -> bool:
        """True when nothing has been written yet: no findings, or no file.

        A format example with an empty ``findings`` list is labelable like any
        other sample; only the ones already carrying illustrative labels are
        reported as ``format-example`` and skipped unless ``--force`` is given.
        """
        return not self.error and not self.findings


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser.

    Returns:
        A parser accepting ``--dataset``, ``--status``, ``--force`` and
        ``--allow-non-tty``.
    """
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Label golden-dataset samples by hand: shows each diff with new-side "
            "line numbers and records the findings a human types. It never "
            "generates, infers or pre-fills a label."
        ),
        epilog=(
            "At the file prompt type a post-change path, or 'done' to write what "
            "you have, 'skip' to leave the sample untouched, 'quit' to stop. "
            "Adding an id to manifest.json under evaluation_samples remains a "
            "manual step."
        ),
    )
    parser.add_argument(
        "--dataset",
        default=DEFAULT_DATASET,
        metavar="PATH",
        help=f"dataset root holding manifest.json and the sample directories (default: {DEFAULT_DATASET})",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="print how many samples are labelled and unlabelled, then exit",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="allow re-labelling a sample that already has a non-empty findings list",
    )
    parser.add_argument(
        "--allow-non-tty",
        action="store_true",
        help=(
            "permit a piped stdin, for scripted verification only; without this "
            "flag a non-TTY session exits 2 instead of hanging"
        ),
    )
    return parser


def _count_findings(expected_path: Path) -> tuple[int | None, str]:
    """Count the findings in one ``expected.json`` without validating them.

    Counting is deliberately lenient: ``--status`` must be able to report a
    broken label file instead of dying on it, and the strict check belongs to
    :func:`benchmarks.loader.load_sample`.

    Args:
        expected_path: Path to the label file.

    Returns:
        ``(count, error)`` where ``count`` is ``None`` when the file is missing
        or unreadable and ``error`` explains why.
    """
    if not expected_path.is_file():
        return None, f"missing {EXPECTED_NAME}"
    try:
        payload = json.loads(expected_path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, f"cannot read {EXPECTED_NAME}: {exc.strerror or exc}"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON at line {exc.lineno}: {exc.msg}"
    if not isinstance(payload, dict):
        return None, f"{EXPECTED_NAME} is not a JSON object"
    findings = payload.get("findings")
    if not isinstance(findings, list):
        return None, f"{EXPECTED_NAME} has no 'findings' list"
    return len(findings), ""


def _manifest_ids(root: Path) -> tuple[set[str], list[str]]:
    """Read ``evaluation_samples`` ids, tolerating a missing manifest.

    Args:
        root: Dataset root.

    Returns:
        ``(ids, warnings)``; the warnings are printed by the caller so a
        malformed manifest is visible rather than silently ignored.
    """
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        return set(), [f"{MANIFEST_NAME} is missing: no sample counts as evaluation data"]
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return set(), [f"{MANIFEST_NAME} cannot be read ({exc}): no sample counts as evaluation data"]
    if not isinstance(payload, dict):
        return set(), [f"{MANIFEST_NAME} is not a JSON object: no sample counts as evaluation data"]
    raw = payload.get("evaluation_samples", [])
    if not isinstance(raw, list):
        return set(), ["'evaluation_samples' is not a list: ignored"]
    return {entry for entry in raw if isinstance(entry, str)}, []


def scan_dataset(root: Path) -> tuple[list[SampleStatus], list[str]]:
    """Inventory every sample directory under a dataset root.

    Args:
        root: Dataset root, e.g. ``benchmarks/golden``.

    Returns:
        ``(statuses, warnings)``, statuses sorted by sample id for determinism.
    """
    manifest_ids, warnings = _manifest_ids(root)
    statuses: list[SampleStatus] = []
    for child in sorted(root.iterdir(), key=lambda path: path.name):
        if not child.is_dir():
            continue
        if not (child / DIFF_NAME).is_file() and not (child / EXPECTED_NAME).is_file():
            continue
        count, error = _count_findings(child / EXPECTED_NAME)
        statuses.append(
            SampleStatus(
                id=child.name,
                path=child,
                findings=count,
                format_example=child.name.startswith(FORMAT_EXAMPLE_PREFIX),
                in_manifest=child.name in manifest_ids,
                error=error,
            )
        )
    return statuses, warnings


def _render_bundle(bundle: DiffBundle) -> tuple[str, tuple[str, ...], frozenset[int]]:
    """Render a parsed diff with new-side line numbers, one line per row.

    Args:
        bundle: The parsed diff.

    Returns:
        ``(text, paths, added_lines)`` — the printable block, the post-change
        paths it touches, and every added new-side line number.
    """
    rows: list[str] = []
    paths: list[str] = []
    added: set[int] = set()

    for file_diff in bundle.files:
        paths.append(file_diff.path)
        header = f"=== {file_diff.path}  ({file_diff.change}"
        if file_diff.added_spans:
            header += f"; added new-side lines: {', '.join(file_diff.added_spans)}"
        rows.append(header + ") ===")
        if file_diff.binary:
            rows.append("  (binary file: no hunks to review)")
            continue
        for hunk in file_diff.hunks:
            rows.append(f"  {hunk.header}")
            for line in hunk.lines:
                if line.kind == "added":
                    marker, number = "+", line.new_lineno
                    if number is not None:
                        added.add(number)
                elif line.kind == "removed":
                    marker, number = "-", line.old_lineno
                else:
                    marker, number = " ", line.new_lineno
                label = f"{number:>5}" if number is not None else "     "
                rows.append(f"  {label} | {marker}{line.text}")
    return "\n".join(rows), tuple(paths), frozenset(added)


def render_diff(diff_text: str) -> tuple[str, tuple[str, ...], frozenset[int]]:
    """Render a raw unified diff with new-side line numbers.

    Args:
        diff_text: Raw diff content.

    Returns:
        ``(text, paths, added_lines)`` as returned by :func:`_render_bundle`.

    Raises:
        DiffParseError: The text is not a unified diff.
    """
    return _render_bundle(parse_diff(diff_text))


def _ask(stdin: TextIO, stdout: TextIO, prompt: str) -> str:
    """Read one stripped line of input.

    Args:
        stdin: Input stream.
        stdout: Stream the prompt is written to.
        prompt: Text to show before reading.

    Returns:
        The line, stripped of surrounding whitespace.

    Raises:
        _InputClosed: EOF was reached, which is treated as ``quit``.
    """
    stdout.write(prompt)
    stdout.flush()
    line = stdin.readline()
    if line == "":
        raise _InputClosed
    return line.strip()


def _ask_choice(
    stdin: TextIO,
    stdout: TextIO,
    prompt: str,
    choices: Sequence[str],
    *,
    upper: bool,
) -> str:
    """Prompt until the human types one of ``choices``.

    Args:
        stdin: Input stream.
        stdout: Stream prompts and errors are written to.
        prompt: Text to show before reading.
        choices: Legal values.
        upper: Whether the input is upper-cased before matching (severities) or
            lower-cased (categories).

    Returns:
        The matching choice, in its canonical spelling.

    Raises:
        _InputClosed: EOF was reached.
    """
    while True:
        answer = _ask(stdin, stdout, prompt)
        normalised = answer.upper() if upper else answer.lower()
        if normalised in choices:
            return normalised
        stdout.write(f"  invalid — choose one of: {', '.join(choices)}\n")


def _ask_line(
    stdin: TextIO,
    stdout: TextIO,
    prompt: str,
    *,
    default: int | None = None,
) -> int:
    """Prompt for a 1-based line number.

    Args:
        stdin: Input stream.
        stdout: Stream prompts and errors are written to.
        prompt: Text to show before reading.
        default: Value used when the human just presses Enter.

    Returns:
        The line number.

    Raises:
        _InputClosed: EOF was reached.
    """
    while True:
        answer = _ask(stdin, stdout, prompt)
        if answer == "" and default is not None:
            return default
        try:
            value = int(answer)
        except ValueError:
            stdout.write(f"  invalid — expected a whole number, got {answer!r}\n")
            continue
        if value < 1:
            stdout.write(f"  invalid — line numbers start at 1, got {value}\n")
            continue
        return value


def _print_help(stdout: TextIO) -> None:
    """Print the vocabularies and control words.

    Args:
        stdout: Stream to write to.
    """
    stdout.write(
        "\n  category: " + ", ".join(CATEGORIES) + "\n"
        "  severity: " + ", ".join(SEVERITIES) + "\n"
        "  commands: " + ", ".join(COMMANDS) + "\n"
        "  line_start / line_end are new-side numbers, inclusive; press Enter "
        "for line_end to reuse line_start.\n\n"
    )


def _prompt_finding(
    stdin: TextIO,
    stdout: TextIO,
    *,
    paths: Sequence[str],
    added: frozenset[int],
    index: int,
) -> dict[str, object] | None:
    """Collect one finding from the human, or handle a control word.

    Args:
        stdin: Input stream.
        stdout: Stream prompts and warnings are written to.
        paths: Post-change paths present in the diff, used to catch a typo.
        added: Added new-side line numbers, used to warn about context lines.
        index: 1-based position of this finding in the sample.

    Returns:
        ``(finding, command)``: ``finding`` is the validated mapping, and is
        ``None`` when the human typed a control word — which is then returned as
        ``command`` (``"done"``, ``"skip"`` or ``"quit"``). ``help`` is handled
        here and never returned.

    Raises:
        _InputClosed: EOF was reached.
    """
    while True:
        answer = _ask(
            stdin,
            stdout,
            f"\nfinding #{index} — file (post-change path), or one of "
            f"{', '.join(COMMANDS)}: ",
        )
        word = answer.lower()
        if word in COMMANDS:
            if word == "help":
                _print_help(stdout)
                continue
            return None, word
        if not answer:
            stdout.write("  invalid — a path is required here\n")
            continue
        if paths and answer not in paths:
            stdout.write(
                "  not a path in this diff — expected one of: "
                + ", ".join(paths)
                + "\n"
            )
            continue

        line_start = _ask_line(stdin, stdout, "line_start (new side): ")
        line_end = _ask_line(
            stdin,
            stdout,
            f"line_end (Enter for {line_start}): ",
            default=line_start,
        )
        if line_end < line_start:
            stdout.write(
                f"  invalid — line_end {line_end} is before line_start {line_start}\n"
            )
            continue
        category = _ask_choice(
            stdin,
            stdout,
            f"category ({'/'.join(CATEGORIES)}): ",
            CATEGORIES,
            upper=False,
        )
        severity = _ask_choice(
            stdin,
            stdout,
            f"severity ({'/'.join(SEVERITIES)}): ",
            SEVERITIES,
            upper=True,
        )

        if added and line_start not in added:
            stdout.write(
                f"  warning — line {line_start} is not an added line in this diff; "
                "recorded as typed\n"
            )

        candidate = {
            "file": answer,
            "line_start": line_start,
            "line_end": line_end,
            "category": category,
            "severity": severity,
        }
        try:
            _ExpectedFindingIn.model_validate(candidate)
        except ValidationError as exc:
            for error in exc.errors():
                location = ".".join(str(part) for part in error["loc"]) or "<root>"
                stdout.write(f"  rejected by the loader schema — {location}: {error['msg']}\n")
            continue
        return candidate, ""


def _write_labels(
    root: Path,
    status: SampleStatus,
    findings: Sequence[dict[str, object]],
    note: str,
    stdout: TextIO,
) -> bool:
    """Validate and write one ``expected.json``, then re-load it through the loader.

    Args:
        root: Dataset root, needed for the loader round-trip.
        status: The sample being labelled.
        findings: Findings exactly as the human typed them.
        note: Optional free-text note; omitted from the file when empty.
        stdout: Stream the confirmation is written to.

    Returns:
        ``True`` when the file was written and re-loaded cleanly.
    """
    payload: dict[str, object] = {"findings": list(findings)}
    if note:
        payload["note"] = note

    try:
        _ExpectedFileIn.model_validate(payload)
    except ValidationError as exc:
        stdout.write(f"  error — the loader rejects this label file:\n{exc}\n")
        return False

    expected_path = status.path / EXPECTED_NAME
    temp_path = status.path / f".{EXPECTED_NAME}.tmp"
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    try:
        temp_path.write_text(text, encoding="utf-8")
        os.replace(temp_path, expected_path)
    except OSError as exc:
        stdout.write(f"  error — cannot write {expected_path}: {exc}\n")
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        return False

    try:
        sample = load_sample(root, status.id, format_example=status.format_example)
    except DatasetError as exc:
        stdout.write(f"  error — the loader rejects the written file: {exc}\n")
        return False

    stdout.write(
        f"  wrote {expected_path} — {len(sample.expected)} finding(s); "
        "re-loaded cleanly through benchmarks.loader.load_sample\n"
    )
    return True


def _label_sample(
    root: Path,
    status: SampleStatus,
    *,
    force: bool,
    stdin: TextIO,
    stdout: TextIO,
) -> str:
    """Run one sample's labelling session.

    Args:
        root: Dataset root.
        status: The sample to label.
        force: Whether an existing non-empty label may be replaced.
        stdin: Input stream.
        stdout: Stream the session is written to.

    Returns:
        ``"written"``, ``"skipped"``, ``"quit"``, ``"refused"`` or ``"failed"``.
    """
    diff_path = status.path / DIFF_NAME
    try:
        diff_text = diff_path.read_text(encoding="utf-8")
    except OSError as exc:
        stdout.write(f"  error — cannot read {diff_path}: {exc.strerror or exc}\n")
        return "failed"

    stdout.write(f"\n{'=' * 72}\n{status.id}  ({status.kind})\n{'=' * 72}\n")
    if status.findings:
        stdout.write(
            f"existing label: {status.findings} finding(s)"
            + (" — replacing because --force was given\n" if force else "\n")
        )
    else:
        stdout.write("existing label: none\n")

    try:
        rendered, paths, added = render_diff(diff_text)
    except DiffParseError as exc:
        stdout.write(
            f"  warning — this diff could not be parsed ({exc}); showing it raw, "
            "so no line numbers are offered\n\n"
        )
        rendered, paths, added = diff_text, (), frozenset()
    stdout.write(rendered + "\n")

    findings: list[dict[str, object]] = []
    while True:
        finding, command = _prompt_finding(
            stdin,
            stdout,
            paths=paths,
            added=added,
            index=len(findings) + 1,
        )
        if finding is not None:
            findings.append(finding)
            stdout.write(f"  recorded: {finding}\n")
            continue

        if command == "skip":
            stdout.write(f"  skipped {status.id} — nothing written\n")
            return "skipped"
        if command == "quit":
            stdout.write(f"  quit — nothing written for {status.id}\n")
            return "quit"

        # Re-read the file rather than trusting the scan: a label written by
        # another session while this one was open must not be overwritten.
        on_disk, _ = _count_findings(status.path / EXPECTED_NAME)
        if on_disk and not force:
            stdout.write(
                f"  refused — {status.id} now has {on_disk} human label(s) on "
                "disk; nothing overwritten (re-run with --force to replace them)\n"
            )
            return "refused"

        note = _ask(stdin, stdout, "note (optional, Enter to leave it out): ")
        if _write_labels(root, status, findings, note, stdout):
            return "written"
        return "failed"


def _print_status(statuses: Sequence[SampleStatus], warnings: Sequence[str], stdout: TextIO) -> None:
    """Print the label-coverage table.

    Args:
        statuses: Every sample found on disk.
        warnings: Dataset-level problems to report above the table.
        stdout: Stream to write to.
    """
    for warning in warnings:
        stdout.write(f"warning: {warning}\n")

    headers = ("sample", "kind", "manifest", "findings", "status")
    widths = (28, 15, 9, 9, 15)
    stdout.write(
        "  ".join(name.ljust(width) for name, width in zip(headers, widths)).rstrip()
        + "\n"
    )
    stdout.write("  ".join("-" * width for width in widths) + "\n")
    for status in statuses:
        cells = (
            status.id,
            status.kind,
            "yes" if status.in_manifest else "no",
            "?" if status.findings is None else str(status.findings),
            status.state,
        )
        stdout.write(
            "  ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip()
            + "\n"
        )
        if status.error:
            stdout.write(f"    ! {status.error}\n")

    evaluation = [status for status in statuses if not status.format_example]
    labelled = [status for status in evaluation if status.state == _STATE_LABELLED]
    unlabelled = [status for status in evaluation if status.state == _STATE_UNLABELLED]
    examples = [status for status in statuses if status.format_example]
    broken = [status for status in statuses if status.error]

    stdout.write(
        f"\n{len(evaluation)} evaluation sample(s): "
        f"{len(labelled)} labelled, {len(unlabelled)} unlabelled\n"
        f"{len(examples)} format example(s), excluded from every metric\n"
    )
    if broken:
        stdout.write(f"{len(broken)} sample(s) have an unreadable {EXPECTED_NAME}\n")
    if unlabelled:
        stdout.write(
            f"label them with: {PROG} --dataset {evaluation[0].path.parent}\n"
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the labelling session.

    Args:
        argv: Command-line arguments, excluding the program name; ``None`` means
            ``sys.argv[1:]``.

    Returns:
        :data:`EXIT_OK`, :data:`EXIT_IO` or :data:`EXIT_USAGE`.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.dataset)
    stdout = sys.stdout
    stderr = sys.stderr

    if not root.is_dir():
        print(f"error: dataset root {root} does not exist", file=stderr)
        return EXIT_USAGE

    statuses, warnings = scan_dataset(root)

    if args.status:
        _print_status(statuses, warnings, stdout)
        return EXIT_OK

    if not sys.stdin.isatty() and not args.allow_non_tty:
        print(
            "error: stdin is not a TTY, so a labelling session would hang. "
            "Run this in a terminal; --status works non-interactively. "
            "(--allow-non-tty exists only for scripted verification.)",
            file=stderr,
        )
        return EXIT_USAGE
    if not sys.stdin.isatty():
        print(
            "warning: stdin is not a TTY; continuing because --allow-non-tty "
            "was given. Every label still comes from the input stream.",
            file=stderr,
        )

    for warning in warnings:
        stdout.write(f"warning: {warning}\n")

    queue = [status for status in statuses if status.needs_label or args.force]
    if not queue:
        stdout.write(
            f"nothing to label — every sample under {root} already has a "
            "human label (use --force to replace one)\n"
        )
        return EXIT_OK

    stdout.write(
        f"{len(queue)} sample(s) to label under {root}. "
        "Type 'help' at a file prompt for the vocabularies.\n"
    )

    written = skipped = failed = 0
    try:
        for status in queue:
            outcome = _label_sample(
                root, status, force=args.force, stdin=sys.stdin, stdout=stdout
            )
            if outcome == "written":
                written += 1
            elif outcome == "skipped":
                skipped += 1
            elif outcome == "failed":
                failed += 1
            elif outcome == "quit":
                stdout.write("session ended by 'quit'; remaining samples untouched\n")
                break
    except _InputClosed:
        stdout.write("\ninput closed — stopping without writing the current sample\n")
        failed += 1

    stdout.write(
        f"\n{written} written, {skipped} skipped, {failed} failed, "
        f"{len(queue) - written - skipped - failed} not visited\n"
    )
    return EXIT_IO if failed else EXIT_OK


if __name__ == "__main__":  # pragma: no cover - exercised through the module CLI
    raise SystemExit(main())
