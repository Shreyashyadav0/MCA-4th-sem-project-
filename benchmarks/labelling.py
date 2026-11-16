#!/usr/bin/env python3
"""Interactive labelling tool: turn a human's judgement into a label file.

Run from the repo root:

    python benchmarks/labelling.py --root benchmarks/golden

For each sample the tool shows the diff and the rule engine's own findings, then
asks one question per finding. Nothing is pre-accepted: a prediction is a
suggestion and the human types the verdict.

Why it works this way, in one paragraph. A label set built by agreeing with the
tool measures the tool against itself — that is the circular trap
``docs/decisions/0006-labels-must-be-human-authored.md`` exists to prevent. So the
tool shows predictions as prompts rather than answers, and it always offers a way
to add a finding the tool missed. A set with no human-only labels is a warning
sign, not a good result.

The output is ``expected.json`` per sample, in the exact shape
``benchmarks/loader.py`` validates::

    {"findings": [{"file", "line_start", "line_end", "category", "severity"}, ...]}

No network, no keys, no timestamps. Quitting mid-sample loses nothing: a sample is
only written once every finding in it has a verdict, and a re-run continues at the
first sample that has no label file yet.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.loader import MANIFEST_NAME  # noqa: E402
from app.parser import parse_diff_file  # noqa: E402
from app.rules import (  # noqa: E402
    RULES,
    LineContext,
    RuleCategory,
    _suppressed_ids,
)

PROG = "labelling"
LABEL_NAME = "expected.json"
DIFF_NAME = "change.diff"

SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
CATEGORIES = tuple(category.value for category in RuleCategory) + ("llm",)

EXIT_OK = 0
EXIT_INPUT = 1
EXIT_USAGE = 2

BANNER = "=" * 72


# --------------------------------------------------------------------------- #
# Reading the sample
# --------------------------------------------------------------------------- #


def _added_lines(diff_text: str, tmp: Path) -> list[tuple[str, list[tuple[int, str]]]]:
    """Return ``[(path, [(lineno, text), ...]), ...]`` for the diff's added lines.

    The parser wants a path on disk, so the diff is written to a temporary file
    inside the sample directory and read back. Nothing is left behind.

    Args:
        diff_text: Raw unified diff.
        tmp: Scratch path to write the diff to.

    Returns:
        One entry per changed file, in diff order.
    """
    tmp.write_text(diff_text, encoding="utf-8")
    try:
        bundle = parse_diff_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)
    out: list[tuple[str, list[tuple[int, str]]]] = []
    for file in bundle.files:
        out.append((file.path, added_lines_of(file)))
    return out


def added_lines_of(file) -> list[tuple[int, str]]:
    """Return ``[(lineno, text), ...]`` for one file's added lines.

    The rules read the line's *text*, so an empty string would make every rule
    silent. The text comes from the hunk lines, which is what the diff actually
    says.

    Args:
        file: One ``FileDiff`` from the parser.

    Returns:
        Pairs of new-side line number and line text, in diff order.
    """
    pairs: list[tuple[int, str]] = []
    for hunk in file.hunks:
        for line in hunk.lines:
            if line.kind == "added" and line.new_lineno is not None:
                pairs.append((line.new_lineno, line.text))
    return pairs


def _rule_findings(diff_text: str, scratch: Path) -> list[dict]:
    """Run the rule engine over the diff's added lines.

    Args:
        diff_text: Raw unified diff.
        scratch: Scratch path for the temporary diff file.

    Returns:
        One dict per finding, in the label file's field order.
    """
    findings: list[dict] = []
    scratch.write_text(diff_text, encoding="utf-8")
    try:
        bundle = parse_diff_file(scratch)
    finally:
        scratch.unlink(missing_ok=True)
    for file in bundle.files:
        added = tuple(added_lines_of(file))
        for index, (lineno, text) in enumerate(added):
            context = LineContext(
                path=file.path, lineno=lineno, text=text, added=added, index=index
            )
            suppress_all, suppress_ids = _suppressed_ids(text)
            if suppress_all:
                continue
            # The rules are walked directly rather than through review_lines,
            # because a label needs the finding's *category* and a Finding carries
            # only the five-field contract — the category belongs to the rule.
            for rule in RULES:
                if rule.id in suppress_ids:
                    continue
                if rule.check(context) is None:
                    continue
                findings.append(
                    {
                        "file": file.path,
                        "line_start": lineno,
                        "line_end": lineno,
                        "category": rule.category.value,
                        "severity": rule.severity.value,
                    }
                )
    return findings


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #


def _ask(prompt: str, *, allow_empty: bool = False) -> str:
    """Read one line from the human.

    Args:
        prompt: Text shown before the input.
        allow_empty: Whether an empty answer is acceptable.

    Returns:
        The stripped answer, possibly empty.
    """
    while True:
        try:
            answer = input(prompt).strip()
        except EOFError:
            return ""
        if answer or allow_empty:
            return answer
        print("  (an answer is required — press Ctrl-D to stop and keep what is written)")


def _ask_choice(prompt: str, options: Sequence[str]) -> str | None:
    """Ask the human to pick one option by number.

    Args:
        prompt: Text shown before the menu.
        options: The choices, printed 1-based.

    Returns:
        The chosen option, or ``None`` when the human asks to skip the finding.
    """
    for index, option in enumerate(options, 1):
        print("    %2d) %s" % (index, option))
    while True:
        raw = _ask(prompt + " [1-%d, s to skip, q to quit]: " % len(options), allow_empty=True)
        if raw.lower() == "q":
            return None
        if raw.lower() == "s":
            return ""
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("  (enter a number, s, or q)")


def _review_finding(candidate: dict, index: int, total: int) -> dict | None:
    """Put one prediction to the human.

    Args:
        candidate: The finding the rule engine suggested.
        index: 1-based position, for the header.
        total: How many candidates there are.

    Returns:
        The accepted finding with the human's severity and category, ``None`` when
        the human rejects it, or raises ``SystemExit`` when they quit.
    """
    print()
    print("  finding %d of %d — the rule engine says:" % (index, total))
    print("    %s:%d  %s  %s" % (
        candidate["file"], candidate["line_start"],
        candidate["severity"], candidate["category"],
    ))
    print("  Is this a real finding a careful reviewer would raise?")
    while True:
        answer = _ask("  [y]es / [n]o / [q]uit: ", allow_empty=True).lower()
        if answer == "q":
            raise SystemExit(EXIT_OK)
        if answer in ("y", "n"):
            break
        print("  (y, n or q)")

    if answer == "n":
        return None

    print("  Severity — keep the suggestion or change it?")
    severity = _ask_choice("  severity", SEVERITIES)
    if severity is None:
        raise SystemExit(EXIT_OK)
    severity = severity or candidate["severity"]

    print("  Category — keep the suggestion or change it?")
    category = _ask_choice("  category", CATEGORIES)
    if category is None:
        raise SystemExit(EXIT_OK)
    category = category or candidate["category"]

    accepted = dict(candidate)
    accepted["severity"] = severity
    accepted["category"] = category
    return accepted


def _add_missed() -> list[dict]:
    """Ask the human for findings the tool did not report.

    Returns:
        The findings they typed, in the label file's field order.
    """
    added: list[dict] = []
    print()
    print("  Did the tool miss anything? This is the part that stops the benchmark")
    print("  measuring the tool against itself — a set of only-agreed labels is worthless.")
    while True:
        answer = _ask("  add a finding the tool missed? [y/N]: ", allow_empty=True).lower()
        if answer != "y":
            return added
        file = _ask("    file (as in the +++ line): ")
        start_raw = _ask("    first line: ")
        end_raw = _ask("    last line (blank = same as first): ", allow_empty=True)
        try:
            start = int(start_raw)
            end = int(end_raw) if end_raw else start
        except ValueError:
            print("    (line numbers must be integers — that finding was not added)")
            continue
        severity = _ask_choice("    severity", SEVERITIES) or "MEDIUM"
        category = _ask_choice("    category", CATEGORIES) or "llm"
        added.append(
            {
                "file": file,
                "line_start": start,
                "line_end": max(start, end),
                "category": category,
                "severity": severity,
            }
        )
        print("    added: %s:%d-%d %s %s" % (file, start, max(start, end), severity, category))


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #


def write_labels(path: Path, findings: list[dict]) -> None:
    """Write one label file in the shape ``benchmarks/loader.py`` validates.

    Args:
        path: Destination, ``<sample>/expected.json``.
        findings: Human verdicts. An empty list is a real label: it says the
            change is clean, and that is what true negatives are measured from.
    """
    payload = {"findings": findings}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _label_ids(root: Path, manifest: dict) -> list[str]:
    """Sample ids to walk: the manifest's evaluation samples, else every directory.

    Args:
        root: Dataset root.
        manifest: Decoded ``manifest.json``.

    Returns:
        Ids in manifest order when the manifest names them, otherwise every
        directory that has a ``change.diff``, sorted.
    """
    listed = manifest.get("evaluation_samples") or []
    if listed:
        return [str(entry) for entry in listed]
    return sorted(
        child.name
        for child in root.iterdir()
        if child.is_dir() and (child / DIFF_NAME).is_file()
    )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser.

    Returns:
        The configured parser.
    """
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Label samples by hand, one finding at a time.",
    )
    parser.add_argument(
        "--root",
        default="benchmarks/golden",
        help="dataset root holding manifest.json and one directory per sample",
    )
    parser.add_argument(
        "--sample",
        default=None,
        help="label only this sample id, instead of walking the whole set",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing label file (refused by default)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="show which samples are labelled and which are not, then exit",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Walk the samples and collect labels.

    Args:
        argv: Arguments to parse, defaulting to :data:`sys.argv`.

    Returns:
        :data:`EXIT_OK` when the run finished, :data:`EXIT_INPUT` when the dataset
        cannot be read, :data:`EXIT_USAGE` for a bad argument.
    """
    args = build_parser().parse_args(argv)
    root = Path(args.root)
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        print("%s: no %s under %s" % (PROG, MANIFEST_NAME, root), file=sys.stderr)
        return EXIT_INPUT
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("%s: cannot read %s: %s" % (PROG, manifest_path, exc), file=sys.stderr)
        return EXIT_INPUT
    if not isinstance(manifest, dict):
        print("%s: %s must be a JSON object" % (PROG, manifest_path), file=sys.stderr)
        return EXIT_INPUT

    ids = _label_ids(root, manifest)
    if args.sample is not None:
        if args.sample not in ids:
            print("%s: %r is not a sample in %s" % (PROG, args.sample, root), file=sys.stderr)
            return EXIT_INPUT
        ids = [args.sample]

    labelled = [sid for sid in ids if (root / sid / LABEL_NAME).is_file()]
    pending = [sid for sid in ids if sid not in labelled]

    if args.list:
        for sid in ids:
            state = "labelled" if sid in labelled else "pending"
            print("%-28s %s" % (sid, state))
        print("\n%d labelled, %d pending" % (len(labelled), len(pending)))
        return EXIT_OK

    if not ids:
        print(
            "%s: no samples to label. Add directories under %s and list them in "
            "%s's evaluation_samples." % (PROG, root, MANIFEST_NAME),
            file=sys.stderr,
        )
        return EXIT_INPUT

    print(BANNER)
    print("Labelling %d sample(s) under %s" % (len(pending), root))
    print("%d already labelled; this run continues at the first pending one." % len(labelled))
    print("Nothing is pre-accepted. Ctrl-D or q keeps everything written so far.")
    print(BANNER)

    for position, sample_id in enumerate(pending, 1):
        sample_dir = root / sample_id
        label_path = sample_dir / LABEL_NAME
        if label_path.is_file() and not args.force:
            print("\n%s: %s already exists — skipping (use --force to overwrite)"
                  % (sample_id, LABEL_NAME))
            continue
        diff_path = sample_dir / DIFF_NAME
        if not diff_path.is_file():
            print("%s: %s has no %s" % (PROG, sample_id, DIFF_NAME), file=sys.stderr)
            return EXIT_INPUT
        diff_text = diff_path.read_text(encoding="utf-8")

        print()
        print(BANNER)
        print("Sample %s  (%d of %d pending)" % (sample_id, position, len(pending)))
        print(BANNER)
        print()
        for line in diff_text.splitlines():
            print("  " + line)

        scratch = sample_dir / ".labelling.diff"
        candidates = _rule_findings(diff_text, scratch)
        print()
        print("The rule engine reported %d finding(s)." % len(candidates))

        verdicts: list[dict] = []
        for index, candidate in enumerate(candidates, 1):
            accepted = _review_finding(candidate, index, len(candidates))
            if accepted is not None:
                verdicts.append(accepted)

        verdicts.extend(_add_missed())

        if not args.force and label_path.is_file():
            print("\n%s exists — not overwriting." % LABEL_NAME)
            continue
        write_labels(label_path, verdicts)
        human_only = sum(
            1 for verdict in verdicts
            if not any(
                candidate["file"] == verdict["file"]
                and candidate["line_start"] == verdict["line_start"]
                for candidate in candidates
            )
        )
        print()
        print("  wrote %s — %d finding(s), %d of them the tool did not report"
              % (label_path, len(verdicts), human_only))

    remaining = [sid for sid in ids if not (root / sid / LABEL_NAME).is_file()]
    print()
    print("%d of %d samples labelled, %d remaining." % (len(ids) - len(remaining), len(ids), len(remaining)))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
