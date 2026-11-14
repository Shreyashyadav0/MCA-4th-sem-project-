"""Command-line surface for the reviewer.

Phase 1 scope: read one source file, decide the mode, emit a five-field
structured review. Phase 2 adds diff mode: point the CLI at a ``.diff`` /
``.patch`` (or pass ``--diff``) and each finding is anchored to the changed line
ranges in that patch. Phase 3 puts the local rule engine behind both paths, so
findings are real with zero credentials. Phase 4 put the Sarvam LLM in front of
that engine. Phase 5 added ``--post-to-pr OWNER/REPO#NUM``: a diff review can be
published to the pull request as inline comments plus a summary, through
:func:`app.github_client.post_review`, which degrades to a ``PostResult``
instead of raising. Phase 5.5 routes both paths through
:func:`app.engine.review`, the single provider selector:
``--provider {auto,local,sarvam,mock}`` picks Sarvam, a local LM Studio endpoint
or the rule engine, and the report prints which one actually ran.

Nothing here crashes for want of a credential: mode selection degrades, logs one
WARNING, and still exits 0.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import TextIO

from app import __version__, engine
from app.config import Settings
import httpx

from app.github_client import GitHubError, PostResult, build_payload, post_review
from app.mock_provider import ENGINE_NOTE
from app.models import ReviewResult, Severity
from app.parser import (
    DiffParseError,
    DiffReviewResult,
    anchor_findings,
    bundle_from_source,
    parse_diff,
)
from app.rules import RULES
from app.sarvam_provider import ProviderOutcome

__all__ = ["main", "build_parser", "run"]

logger = logging.getLogger("reviewer")

_EXIT_OK = 0
_EXIT_INPUT_ERROR = 1
_EXIT_USAGE = 2
_MAX_BYTES = 2_000_000  # refuse absurd inputs before reading them
_DIFF_SUFFIXES = {".diff", ".patch"}
_POST_TO_PR_FORMAT = "OWNER/REPO#NUM"

#: Strict ``OWNER/REPO#NUM`` shape: no whitespace, no extra ``/``, a positive
#: integer after the ``#``. Anything else is a usage error, never a guess.
_POST_TO_PR_RE = re.compile(r"^(?P<owner>[^/#\s]+)/(?P<repo>[^/#\s]+)#(?P<number>\d+)$")


class ReviewInputError(Exception):
    """Raised when the target file cannot be read as reviewable text."""


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser (kept separate so tests can introspect it)."""
    parser = argparse.ArgumentParser(
        prog="reviewer",
        description="Review a source file or a diff and print structured findings.",
        epilog=(
            "With no SARVAM_API_KEY and no LMSTUDIO_BASE_URL the reviewer runs in mock "
            "mode and still exits 0. A path ending in .diff/.patch is treated as a patch "
            "automatically."
        ),
    )
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        help="Source file or .diff/.patch to review (omit with --list-rules).",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Force diff mode even if the file name has no .diff/.patch suffix.",
    )
    parser.add_argument(
        "--provider",
        # Ordered as the contract spells the flag; engine.PROVIDERS is the
        # precedence order (sarvam > local > mock) and is documented in the help.
        choices=[engine.REQUEST_AUTO, "local", "sarvam", "mock"],
        default=engine.REQUEST_AUTO,
        help=(
            "Which reviewer to use. auto (default): sarvam when SARVAM_API_KEY is set, "
            "else local when LMSTUDIO_BASE_URL is set, else mock — sarvam wins when "
            "both are set. local: the LM Studio endpoint. sarvam: the hosted model. "
            "mock: the local rule engine. A forced provider with no configuration "
            "degrades to mock and still exits 0."
        ),
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Force mock mode even if credentials are configured.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the full result as JSON instead of a readable report.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show DEBUG logs (mode selection, file size).",
    )
    parser.add_argument(
        "--min-severity",
        choices=[severity.value for severity in Severity],
        default=None,
        help="Drop findings below this severity (LOW, MEDIUM, HIGH, CRITICAL).",
    )
    parser.add_argument(
        "--post-to-pr",
        type=str,
        default=None,
        metavar=_POST_TO_PR_FORMAT,
        help=(
            "Post the review to a GitHub pull request, e.g. shreyash/ai-code-reviewer#12 "
            "(format OWNER/REPO#NUM). Requires diff mode."
        ),
    )
    parser.add_argument(
        "--list-rules",
        action="store_true",
        help="Print every rule in the local engine and exit.",
    )
    parser.add_argument("--version", action="version", version=f"reviewer {__version__}")
    return parser


def read_source(path: Path) -> str:
    """Read ``path`` as UTF-8 text, or raise :class:`ReviewInputError`.

    Args:
        path: File to read.

    Returns:
        Decoded file content.

    Raises:
        ReviewInputError: Path is missing, not a file, too large, or not UTF-8.
    """
    if not path.exists():
        raise ReviewInputError(f"no such file: {path}")
    if not path.is_file():
        raise ReviewInputError(f"not a regular file: {path}")
    size = path.stat().st_size
    if size > _MAX_BYTES:
        raise ReviewInputError(f"file is {size} bytes; limit is {_MAX_BYTES}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ReviewInputError(f"file is not valid UTF-8 text: {path}") from exc
    except OSError as exc:
        raise ReviewInputError(f"cannot read {path}: {exc}") from exc


def looks_like_diff(path: Path, raw: str) -> bool:
    """Decide whether the input should be parsed as a patch.

    Suffix wins; otherwise sniff the first bytes for git or plain unified-diff
    headers so a patch saved as ``pr_42.txt`` still works.
    """
    if path.suffix.lower() in _DIFF_SUFFIXES:
        return True
    head = raw.lstrip()[:4000]
    if head.startswith("diff --git"):
        return True
    return "\n--- " in f"\n{head}" and "\n+++ " in f"\n{head}"


def _notes_for(outcome: ProviderOutcome) -> list[str]:
    """Build the note lines for one outcome.

    A live run names the provider, model and wall time so the reader can tell a
    real model answer from a rule-engine one at a glance. A degraded run keeps
    the ``mock mode:`` prefix and the engine note exactly as before.

    Args:
        outcome: The result of :func:`app.engine.review`.

    Returns:
        Note strings, in display order.
    """
    if outcome.mode == "live":
        return [
            f"live review: {outcome.provider}/{outcome.model} in {outcome.latency_ms} ms"
        ]
    return [f"mock mode: {outcome.reason}", ENGINE_NOTE]


def _log_mode(outcome: ProviderOutcome) -> None:
    """Record the routing decision; the provider owns the single WARNING.

    Args:
        outcome: The result of :func:`app.engine.review`.
    """
    if outcome.mode == "mock":
        logger.debug("LLM unavailable (%s) — using the offline path", outcome.reason)
    else:
        logger.debug("live review via %s/%s", outcome.provider, outcome.model)


def _render(
    result: ReviewResult,
    *,
    provider: str = "",
    model: str = "",
) -> str:
    """Render a single-file :class:`ReviewResult` as a readable report.

    ``provider`` and ``model`` are the honest labels of what actually ran
    (``mock``/``local``/``sarvam`` and the model id behind them). They are
    printed but never added to the :class:`ReviewResult` document, so ``--json``
    keeps its shape; the same facts travel there in the notes.
    """
    counts = result.counts()
    lines: list[str] = [
        f"target   : {result.target}",
        f"mode     : {result.mode}",
    ]
    if provider:
        lines.append(f"provider : {provider}")
    if model:
        lines.append(f"model    : {model}")
    lines += [
        f"findings : {len(result.findings)} "
        f"(CRITICAL {counts['CRITICAL']}, HIGH {counts['HIGH']}, "
        f"MEDIUM {counts['MEDIUM']}, LOW {counts['LOW']})",
    ]
    lines.extend(f"note     : {note}" for note in result.notes)
    lines.append("")

    for index, finding in enumerate(result.sorted_findings, start=1):
        lines.append(f"{index}. File          : {finding.file}")
        lines.append(f"   Line          : {finding.line}")
        lines.append(f"   Severity      : {finding.severity.value}")
        lines.append(f"   Issue         : {finding.issue}")
        lines.append(f"   Suggested Fix : {finding.suggested_fix}")
        lines.append("")

    lines.append(f"verdict  : {result.verdict}")
    return "\n".join(lines) + "\n"


def _render_diff(
    result: DiffReviewResult,
    *,
    provider: str = "",
    model: str = "",
) -> str:
    """Render a :class:`DiffReviewResult`: changed ranges first, then findings.

    ``provider`` and ``model`` are the honest labels of what actually ran; they
    are printed, not stored, so the ``--json`` document keeps its shape.
    """
    counts = result.counts()
    lines: list[str] = [
        f"target   : {result.target}",
        f"mode     : {result.mode}",
    ]
    if provider:
        lines.append(f"provider : {provider}")
    if model:
        lines.append(f"model    : {model}")
    lines += [
        f"files    : {len(result.files)} changed",
        f"findings : {len(result.findings)} "
        f"(CRITICAL {counts['CRITICAL']}, HIGH {counts['HIGH']}, "
        f"MEDIUM {counts['MEDIUM']}, LOW {counts['LOW']})",
    ]
    lines.extend(f"note     : {note}" for note in result.notes)
    lines.append("")
    lines.append("changed lines:")
    for summary in result.files:
        spans = ", ".join(summary.added_spans) if summary.added_spans else "no added lines"
        kind = "binary" if summary.binary else summary.change
        lines.append(f"  {kind:<9} {summary.path}  (+{summary.added_line_count}: {spans})")
    lines.append("")

    for index, anchored in enumerate(result.sorted_anchors, start=1):
        finding = anchored.finding
        lines.append(f"{index}. File          : {finding.file}")
        lines.append(f"   Line          : {finding.line}")
        lines.append(f"   Severity      : {finding.severity.value}")
        lines.append(f"   Issue         : {finding.issue}")
        lines.append(f"   Suggested Fix : {finding.suggested_fix}")
        anchor = anchored.status.value
        if anchored.hunk_header:
            anchor += f" @ {anchored.hunk_header}"
        lines.append(f"   Anchor        : {anchor}")
        lines.append("")

    lines.append(f"verdict  : {result.verdict}")
    return "\n".join(lines) + "\n"


def parse_post_target(value: str) -> tuple[str, str, int] | None:
    """Parse a ``--post-to-pr`` value strictly as ``OWNER/REPO#NUM``.

    Args:
        value: The raw flag value, e.g. ``shreyash/ai-code-reviewer#12``.

    Returns:
        ``(owner, repo, number)`` when the value matches exactly, else ``None``.
        Nothing is guessed: a malformed value is a usage error at the call site.
    """
    match = _POST_TO_PR_RE.match(value)
    if match is None:
        return None
    number = int(match.group("number"))
    if number <= 0:
        return None
    return match.group("owner"), match.group("repo"), number


def _posting_stream(use_json: bool) -> TextIO:
    """Pick where posting lines go.

    With ``--json`` stdout must stay a single valid JSON document, so the posting
    report goes to stderr; in the readable mode it follows the report on stdout.
    """
    return sys.stderr if use_json else sys.stdout


def _post_to_pr(
    owner: str,
    repo: str,
    number: int,
    review: DiffReviewResult,
    diff_files: list[object],
    settings: Settings,
) -> PostResult:
    """Build the payload from the review's anchors and post it to the pull request.

    Args:
        owner: Repository owner.
        repo: Repository name.
        number: Pull request number.
        review: The completed diff review; its ``anchors`` drive the comments.
        diff_files: The parsed diff's files, used to canonicalise paths.
        settings: Loaded configuration (token and inline cap).

    Returns:
        The :class:`PostResult` from :func:`app.github_client.post_review`. A
        failure raised by the patchable client seam (a GitHub error, an httpx
        error, an OS error or a runtime error) becomes a failed ``PostResult``;
        any other exception is a bug and is allowed to surface.
    """
    payload = build_payload(
        review.anchors,
        diff_files,  # type: ignore[arg-type]
        max_inline=settings.github_max_inline,
    )
    try:
        # No head SHA is known on the CLI path (there is no webhook payload to
        # read it from), so the review is not pinned to a commit.
        return post_review(
            owner,
            repo,
            number,
            payload,
            token=settings.github_token,
            commit_id=None,
        )
    except (GitHubError, httpx.HTTPError, OSError, RuntimeError) as exc:
        # post_review is documented never to raise; this guard exists only because
        # _build_github_client is a patchable seam. Anything outside this tuple is a
        # genuine bug, and a CLI should show the traceback rather than hide it.
        logger.warning("posting the review to GitHub failed: %s", exc)
        return PostResult(False, 0, 0, False, False, f"{type(exc).__name__}: {exc}")


def _report_posting(result: PostResult, stream: TextIO) -> int:
    """Print one readable line per posting outcome and return the exit code.

    Args:
        result: Outcome of :func:`app.github_client.post_review`.
        stream: Where to write (stdout, or stderr under ``--json``).

    Returns:
        ``0`` when the post succeeded or was skipped as a duplicate, ``1`` when
        ``result.ok`` is False.
    """
    print(f"posted   : {result.inline_posted} inline comment(s)", file=stream)
    print(f"demoted  : {result.inline_demoted} moved to the summary", file=stream)
    print(f"summary  : {'yes' if result.summary_posted else 'no'}", file=stream)
    if result.skipped_dup:
        print("skipped  : duplicate review already present", file=stream)
    elif not result.ok:
        print(f"error    : {result.error}", file=stream)
    return _EXIT_OK if (result.ok or result.skipped_dup) else _EXIT_INPUT_ERROR


def _print_rules() -> int:
    """Print the rule registry, CRITICAL first, and exit 0."""
    for rule in sorted(RULES, key=lambda item: (-item.severity.rank, item.id)):
        print(f"{rule.severity.value:<8} {rule.category.value:<16} {rule.id:<40} {rule.title}")
    print(f"\n{len(RULES)} rules")
    return _EXIT_OK


def _run_diff(
    args: argparse.Namespace,
    raw: str,
    settings: Settings,
    min_severity: Severity | None,
    post_target: tuple[str, str, int] | None = None,
) -> int:
    """Parse a patch, produce findings, anchor them, and print the result.

    When ``post_target`` is given the review is also published to that pull
    request after it is printed; the review output itself is unchanged.
    """
    try:
        bundle = parse_diff(raw, source=str(args.path))
    except DiffParseError as exc:
        print(f"error: cannot parse diff {args.path}: {exc}", file=sys.stderr)
        return _EXIT_INPUT_ERROR

    outcome = engine.review(
        bundle,
        settings,
        provider=args.provider,
        force_offline=args.offline,
        min_severity=min_severity,
    )
    _log_mode(outcome)

    result = DiffReviewResult(
        mode=outcome.mode,
        target=str(args.path),
        files=bundle.summaries(),
        findings=outcome.findings,
        anchors=anchor_findings(bundle, outcome.findings),
        notes=_notes_for(outcome),
    )
    rendered = (
        result.to_json()
        if args.json
        else _render_diff(result, provider=outcome.provider, model=outcome.model)
    )
    print(rendered.rstrip("\n"))

    if post_target is not None:
        owner, repo, number = post_target
        posted = _post_to_pr(owner, repo, number, result, bundle.files, settings)
        return _report_posting(posted, _posting_stream(args.json))
    return _EXIT_OK


def run(argv: list[str] | None = None) -> int:
    """Execute one review and return a process exit code.

    Args:
        argv: Arguments without the program name; ``None`` reads ``sys.argv``.

    Returns:
        ``0`` when a review was produced (in either mode), ``1`` on bad input or a
        failed pull-request post, ``2`` on a usage error.
    """
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if args.list_rules:
        return _print_rules()

    # Strict, up front: a malformed target is a usage error, before any work.
    post_target: tuple[str, str, int] | None = None
    if args.post_to_pr is not None:
        post_target = parse_post_target(args.post_to_pr)
        if post_target is None:
            print(f"error: --post-to-pr expects {_POST_TO_PR_FORMAT}", file=sys.stderr)
            return _EXIT_USAGE

    if args.path is None:
        print("error: a path is required unless --list-rules is used", file=sys.stderr)
        return _EXIT_USAGE

    try:
        raw = read_source(args.path)
    except ReviewInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return _EXIT_INPUT_ERROR

    min_severity = Severity(args.min_severity) if args.min_severity else None
    settings = Settings()

    if args.diff or looks_like_diff(args.path, raw):
        return _run_diff(args, raw, settings, min_severity, post_target)

    if post_target is not None:
        print(
            "error: --post-to-pr needs a diff review; "
            f"{args.path} is a single source file, so there are no diff anchors to post against",
            file=sys.stderr,
        )
        return _EXIT_INPUT_ERROR

    bundle = bundle_from_source(args.path, raw)
    outcome = engine.review(
        bundle,
        settings,
        provider=args.provider,
        force_offline=args.offline,
        min_severity=min_severity,
    )
    _log_mode(outcome)

    notes = _notes_for(outcome)
    if outcome.mode == "mock" and not outcome.findings:
        notes.append("no findings from the local rule engine on this file")
    result = ReviewResult(
        mode=outcome.mode,
        target=str(args.path),
        findings=outcome.findings,
        notes=notes,
    )
    rendered = (
        result.to_json()
        if args.json
        else _render(result, provider=outcome.provider, model=outcome.model)
    )
    print(rendered.rstrip("\n"))
    return _EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Console entry point."""
    return run(argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
