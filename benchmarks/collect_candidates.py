"""Download candidate patches for the golden dataset — templates only, never labels.

Human-labelling rule
--------------------
Labels in ``benchmarks/golden`` must be **authored by a human**. This tool
therefore writes, for every patch it downloads, an ``expected.json`` whose
``findings`` list is **empty** and whose ``note`` says the file is unlabelled.
It never parses a patch to guess what a reviewer ought to report, never calls
the rule engine, and never calls a model: an automatically produced label would
score the tool against itself and measure nothing
(see ``benchmarks/golden/README.md``).

It also never writes ``manifest.json``. Adding a sample id to
``evaluation_samples`` is a human decision — a downloaded patch is a *candidate*
until somebody has read it and labelled it.

Pinned sources
--------------
The source table is :data:`SOURCES`: a short, pinned list of public URLs, each
of which was confirmed to answer ``200`` with ``text/plain`` diff content before
being committed here. Nothing is discovered, scraped or followed: the same
command run twice fetches the same five patches. Sources that could not be
confirmed are left out rather than guessed at, because a wrong URL in this table
would surface as a mysterious 404 months later.

Usage
-----
::

    python -m benchmarks.collect_candidates --out benchmarks/golden --dry-run
    python -m benchmarks.collect_candidates --out benchmarks/golden --limit 2
    python -m benchmarks.collect_candidates --out benchmarks/golden

Exit codes
----------
``0``
    At least one patch was written (or, with ``--dry-run``, the plan was printed).
``1``
    Every source failed — offline, DNS refused, 404, empty body, or a write
    error. Per-source failures are printed as they happen and never abort the
    run, so a flaky network costs one candidate rather than the whole batch.
``2``
    A usage problem: the pinned table contains a non-HTTPS URL, or ``--out``
    points at an existing non-directory.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import httpx

__all__ = [
    "CandidateSource",
    "SOURCES",
    "DEFAULT_OUT",
    "UNLABELLED_NOTE",
    "build_parser",
    "main",
]

PROG: str = "python -m benchmarks.collect_candidates"
"""Program name shown in ``--help`` and in error messages."""

DEFAULT_OUT: str = "benchmarks/golden"
"""Dataset root the templates are written into when ``--out`` is omitted."""

UNLABELLED_NOTE: str = "UNLABELLED — a human must fill this in"
"""The ``note`` written into every template; the em dash is deliberate."""

REQUEST_TIMEOUT: float = 20.0
"""Seconds allowed for one fetch; a hung source must not hang the batch."""

USER_AGENT: str = "ai-code-reviewer-candidate-collector/1.0"
"""Identifies this tool to GitHub, which rejects requests without one."""

EXIT_OK: int = 0
"""At least one candidate was written, or the dry-run plan was printed."""

EXIT_ALL_FAILED: int = 1
"""Every source failed; there is nothing new to label."""

EXIT_USAGE: int = 2
"""A problem with the pinned table or the arguments, not with the network."""


@dataclass(frozen=True, slots=True)
class CandidateSource:
    """One pinned public patch, and why it is worth a human's attention.

    Attributes:
        id: Directory name under the dataset root; short, lowercase, stable.
        title: One line naming the project and the change.
        url: Pinned HTTPS URL returning a unified diff.
        origin: Where the patch comes from, for the ``expected.json`` note trail
            and for the failure lines printed when a fetch does not work.
    """

    id: str
    title: str
    url: str
    origin: str


SOURCES: tuple[CandidateSource, ...] = (
    CandidateSource(
        id="webgoat-2023-5",
        title="OWASP WebGoat — v2023.4 to v2023.5 release delta",
        url="https://github.com/WebGoat/WebGoat/compare/v2023.4...v2023.5.diff",
        origin="OWASP/WebGoat",
    ),
    CandidateSource(
        id="dvwa-2-1",
        title="DVWA — 2.0.1 to 2.1 release delta",
        url="https://github.com/digininja/DVWA/compare/2.0.1...2.1.diff",
        origin="digininja/DVWA",
    ),
    CandidateSource(
        id="cve-2016-10033-phpmailer",
        title="PHPMailer — fix for CVE-2016-10033 / CVE-2016-10045 (mail RCE)",
        url=(
            "https://github.com/PHPMailer/PHPMailer/commit/"
            "9743ff5c7ee16e8d49187bd2e11149afb9485eae.diff"
        ),
        origin="PHPMailer/PHPMailer",
    ),
    CandidateSource(
        id="cve-2021-3129-laravel-ignition",
        title="Laravel Ignition — fix for CVE-2021-3129 (unauthenticated RCE)",
        url=(
            "https://github.com/facade/ignition/commit/"
            "e9738da2c3ef715e0ac6daa998b0e48b9c97ede5.diff"
        ),
        origin="facade/ignition",
    ),
    CandidateSource(
        id="cve-2014-0012-jinja",
        title="Jinja2 — fix for CVE-2014-0012 (bytecode cache sandbox escape)",
        url=(
            "https://github.com/pallets/jinja/commit/"
            "964c61ce79f6748ff8c583e2eb12ec54082bf188.diff"
        ),
        origin="pallets/jinja",
    ),
)
"""The whole pinned source list; five entries, no discovery, no pagination.

Every URL above was verified to return HTTP 200 with ``text/plain`` diff content
before being added. A source that could not be verified belongs here commented
out with a note, never as a guess.
"""

DIFF_NAME: str = "change.diff"
"""Filename the patch is saved as, matching ``benchmarks.golden.README``."""

EXPECTED_NAME: str = "expected.json"
"""Filename of the label file this tool only ever creates empty."""


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser.

    Returns:
        A parser accepting ``--out``, ``--limit``, ``--timeout`` and
        ``--dry-run``.
    """
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Download candidate patches from a short pinned list of public "
            "sources and write one EMPTY expected.json template per patch. "
            "Labels are written by a human with benchmarks.label_helper; this "
            "tool never guesses a finding and never edits manifest.json."
        ),
        epilog=(
            "After a run, read each <id>/change.diff yourself and fill in "
            "<id>/expected.json by hand, then add the id to manifest.json "
            "under evaluation_samples if it belongs in the evaluation set."
        ),
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        metavar="PATH",
        help=f"dataset root to write <id>/change.diff into (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=None,
        metavar="N",
        help="fetch at most the first N pinned sources, for a quick smoke run",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=REQUEST_TIMEOUT,
        metavar="SECONDS",
        help=f"per-request timeout in seconds (default: {REQUEST_TIMEOUT:g})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "print what would be fetched and where, then exit without touching "
            "the filesystem or the network"
        ),
    )
    return parser


def _positive_int(raw: str) -> int:
    """Parse a strictly positive integer for ``--limit``.

    Args:
        raw: The command-line value.

    Returns:
        The parsed value.

    Raises:
        argparse.ArgumentTypeError: The value is not an integer of at least 1.
    """
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected an integer, got {raw!r}") from exc
    if value < 1:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {value}")
    return value


def _select_sources(limit: int | None) -> tuple[CandidateSource, ...]:
    """Apply ``--limit`` to the pinned table, preserving its order.

    Args:
        limit: Maximum number of sources to keep, or ``None`` for all of them.

    Returns:
        The selected sources, in pinned order.
    """
    if limit is None:
        return SOURCES
    return SOURCES[:limit]


def _template_payload(source: CandidateSource) -> dict[str, object]:
    """Build the empty ``expected.json`` template for one source.

    The ``findings`` list is always empty: filling it in is a human's job, and
    the ``note`` says so in the file itself so a later reader cannot mistake an
    empty template for a labelled clean change.

    Args:
        source: The patch the template belongs to.

    Returns:
        A JSON-ready mapping with ``note`` and an empty ``findings`` list.
    """
    return {
        "note": f"{UNLABELLED_NOTE} (source: {source.origin} — {source.title})",
        "findings": [],
    }


def _existing_findings(expected_path: Path) -> int | None:
    """Count the findings already in an ``expected.json``.

    Args:
        expected_path: Path to the label file.

    Returns:
        The number of findings, or ``None`` when the file is absent or cannot be
        read as JSON. Both mean "no human label here that must be preserved".
    """
    if not expected_path.is_file():
        return None
    try:
        payload = json.loads(expected_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    findings = payload.get("findings")
    if not isinstance(findings, list):
        return None
    return len(findings)


def _write_template(sample_dir: Path, source: CandidateSource) -> None:
    """Write the empty ``expected.json`` for one sample directory.

    Args:
        sample_dir: The ``<out>/<id>`` directory.
        source: The patch the template belongs to.

    Raises:
        OSError: The file could not be written.
    """
    payload = _template_payload(source)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    sample_dir.joinpath(EXPECTED_NAME).write_text(text, encoding="utf-8")


def _fetch(client: httpx.Client, source: CandidateSource) -> str:
    """Download one patch body.

    Args:
        client: Reusable HTTP client carrying the timeout and user agent.
        source: The pinned source to fetch.

    Returns:
        The response body as text.

    Raises:
        httpx.HTTPError: The request failed or returned a non-2xx status.
        ValueError: The body is empty, which means the URL no longer serves a
            patch even though it answered successfully.
    """
    response = client.get(source.url)
    response.raise_for_status()
    text = response.text
    if not text.strip():
        raise ValueError("response body is empty")
    return text


def _collect_one(
    client: httpx.Client,
    source: CandidateSource,
    out_root: Path,
    *,
    stdout: TextIO,
) -> bool:
    """Fetch one source and write its patch plus an empty label template.

    A sample directory that already holds human labels is left completely
    untouched: re-downloading the patch would invalidate the line numbers those
    labels point at, which would corrupt the benchmark silently.

    Args:
        client: Reusable HTTP client.
        source: The pinned source to fetch.
        out_root: Dataset root the sample directory is created under.
        stdout: Stream progress and failure lines are written to.

    Returns:
        ``"written"`` when a patch and an empty template were written,
        ``"kept"`` when the directory already held human labels and was left
        alone, or ``"failed"`` when the fetch or the write did not work.
    """
    sample_dir = out_root / source.id
    expected_path = sample_dir / EXPECTED_NAME

    existing = _existing_findings(expected_path)
    if existing:
        print(
            f"  keep  {source.id}: {existing} human label(s) already present, "
            "nothing overwritten",
            file=stdout,
        )
        return "kept"

    try:
        diff_text = _fetch(client, source)
    except (httpx.HTTPError, ValueError) as exc:
        reason = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
        print(f"  FAIL  {source.id}: {source.url} — {reason}", file=stdout)
        return "failed"

    try:
        sample_dir.mkdir(parents=True, exist_ok=True)
        sample_dir.joinpath(DIFF_NAME).write_text(diff_text, encoding="utf-8")
        _write_template(sample_dir, source)
    except OSError as exc:
        print(f"  FAIL  {source.id}: cannot write to {sample_dir} — {exc}", file=stdout)
        return "failed"

    print(
        f"  ok    {source.id}: {len(diff_text.splitlines())} diff line(s) -> "
        f"{sample_dir / DIFF_NAME} (expected.json left EMPTY)",
        file=stdout,
    )
    return "written"


def _print_plan(sources: Sequence[CandidateSource], out_root: Path) -> None:
    """Print what a real run would fetch, without fetching anything.

    Args:
        sources: The selected pinned sources.
        out_root: Dataset root the samples would be written under.
    """
    print(f"dry run — would fetch {len(sources)} source(s) into {out_root}")
    for index, source in enumerate(sources, start=1):
        print(f"  {index}. {source.id}  [{source.origin}]")
        print(f"     url:  {source.url}")
        print(f"     diff: {out_root / source.id / DIFF_NAME}")
        print(f"     label: {out_root / source.id / EXPECTED_NAME} (empty template)")
    print("no files written, no requests made, manifest.json not touched")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the collector.

    Args:
        argv: Command-line arguments, excluding the program name; ``None`` means
            ``sys.argv[1:]``.

    Returns:
        :data:`EXIT_OK` when at least one candidate exists, :data:`EXIT_ALL_FAILED`
        when every source failed, :data:`EXIT_USAGE` for a usage problem.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    sources = _select_sources(args.limit)
    out_root = Path(args.out)

    if args.dry_run:
        _print_plan(sources, out_root)
        return EXIT_OK

    insecure = [source.id for source in sources if not source.url.startswith("https://")]
    if insecure:
        print(
            "error: the pinned table must use HTTPS only; offending ids: "
            + ", ".join(insecure),
            file=sys.stderr,
        )
        return EXIT_USAGE

    if out_root.exists() and not out_root.is_dir():
        print(f"error: --out {out_root} exists and is not a directory", file=sys.stderr)
        return EXIT_USAGE

    try:
        out_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"error: cannot create {out_root}: {exc}", file=sys.stderr)
        return EXIT_USAGE

    print(f"fetching {len(sources)} pinned source(s) into {out_root}")
    outcomes: list[str] = []
    with httpx.Client(
        timeout=args.timeout,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for source in sources:
            outcomes.append(_collect_one(client, source, out_root, stdout=sys.stdout))

    written = outcomes.count("written")
    kept = outcomes.count("kept")
    failed = outcomes.count("failed")
    print(f"{written} written, {kept} kept (already labelled), {failed} failed")
    if written or kept:
        if written:
            print(
                "expected.json files are EMPTY on purpose: label them by hand "
                "with `python -m benchmarks.label_helper --dataset "
                f"{out_root}`."
            )
        print(
            "manifest.json was not touched — adding an id to evaluation_samples "
            "is a human decision."
        )
        return EXIT_OK

    print(
        "error: every source failed; nothing was written and there is nothing "
        "to label",
        file=sys.stderr,
    )
    return EXIT_ALL_FAILED


if __name__ == "__main__":  # pragma: no cover - exercised through the module CLI
    raise SystemExit(main())
