#!/usr/bin/env python3
"""Embed the repository's own source into site/content/repo-sources.js.

file:// forbids fetch(), so a browser cannot read app/models.py from disk. The
runner writes this bundle into Pyodide's virtual filesystem before it executes a
lesson's code, which is what lets a lesson say `from app.models import Finding`
and have it work exactly as it does on a real machine.

Rules this script keeps:
  * Every file is embedded VERBATIM — byte for byte, including CRLF line endings
    and a missing final newline. A paraphrased or re-encoded source file would
    teach a codebase that does not exist, so the file is read as bytes and only
    then decoded.
  * Each file is serialised with json.dumps, so quotes, backslashes, newlines and
    non-ASCII text survive the round trip into a JS string literal.
  * It is re-runnable and deterministic: same inputs, same bytes out.

Usage, from the repository root:

    python site/tools/embed_sources.py          # write the bundle
    python site/tools/embed_sources.py --check  # exit 1 if it is stale, naming
                                                # every file that drifted

`validate_lessons.py` runs the same check as part of the site gate, so a wave
cannot ship a stale bundle and still pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
REPO = SITE.parent
OUTPUT = SITE / "content" / "repo-sources.js"

# Embedded because the site runs them, quotes them, or both. Ordered so the file
# reads top-down: the package marker, then the dependency order of the modules.
SOURCES = [
    "app/__init__.py",
    "app/models.py",
    "app/parser.py",
    "app/rules.py",
    "app/db.py",
    "app/engine.py",
    "samples/sample.diff",
]

# What the browser can actually import. Two separate reasons keep a file out:
#   app/config.py needs pydantic-settings, which Pyodide does not ship;
#   app/db.py and app/engine.py both import app.config, so they inherit that;
#   app/engine.py also imports app.openai_compat_provider, which is not embedded
#   at all, so fixing config alone would not make it importable.
# Those files are embedded for reading and quoting, not for import, and no
# lesson may promise otherwise. site/STATE.md records the check that proves it.
IMPORTABLE = ["app/__init__.py", "app/models.py", "app/parser.py", "app/rules.py"]

HEADER = """/* repo-sources.js — GENERATED. Do not edit by hand.
 *
 * Written by site/tools/embed_sources.py from the repository at the frozen
 * commit. Each value is the real file, verbatim, so a lesson can write it into
 * Pyodide's virtual filesystem and then import it.
 *
 * Regenerate with:  python site/tools/embed_sources.py
 * Check it is current:  python site/tools/embed_sources.py --check
 * (site/tools/validate_lessons.py runs that check too.)
 *
 * Importable in the browser: {importable}
 * Embedded for reading only: {reading}
 *   db.py and engine.py import app.config, which needs pydantic-settings — not
 *   shipped by Pyodide; engine.py also imports app.openai_compat_provider, which
 *   is not embedded.
 */
"""


class SourceProblem(Exception):
    """A file the bundle promises cannot be read."""

    def __init__(self, relative: str, reason: str) -> None:
        super().__init__(f"{relative} ({reason})")
        self.relative = relative


def read_source(relative: str) -> str:
    """Bytes, then decode — never text mode, which rewrites CRLF to LF."""
    path = REPO / relative
    try:
        raw = path.read_bytes()
    except FileNotFoundError as error:
        raise SourceProblem(relative, "missing") from error
    except OSError as error:
        raise SourceProblem(relative, error.strerror or "unreadable") from error
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SourceProblem(relative, f"not UTF-8 at byte {error.start}") from error


def render() -> str:
    entries = []
    for relative in SOURCES:
        entries.append("  %s: %s" % (json.dumps(relative), json.dumps(read_source(relative))))
    reading = [name for name in SOURCES if name not in IMPORTABLE]
    header = HEADER.format(
        importable=", ".join(IMPORTABLE),
        reading=", ".join(reading) if reading else "none",
    )
    return header + "window.REPO_SOURCES = {\n" + ",\n".join(entries) + "\n};\n"


def existing_bundle() -> dict:
    """The keys currently in the committed bundle, for a per-file diagnosis."""
    if not OUTPUT.is_file():
        return {}
    try:
        text = OUTPUT.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    start = text.find("{")
    if start == -1:
        return {}
    try:
        parsed = json.loads(text[start:].rstrip().rstrip(";"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def drifted() -> list[str]:
    """Source files whose embedded copy differs from what is on disk."""
    current = existing_bundle()
    out = []
    for relative in SOURCES:
        try:
            on_disk = read_source(relative)
        except SourceProblem:
            out.append(relative)
            continue
        if current.get(relative) != on_disk:
            out.append(relative)
    for key in current:
        if key not in SOURCES:
            out.append(key + " (no longer embedded)")
    return out


def main(argv: list[str]) -> int:
    unknown = [arg for arg in argv if arg not in ("--check",)]
    if unknown:
        print("FAIL unknown argument(s): %s — usage: embed_sources.py [--check]" % " ".join(unknown))
        return 2

    try:
        rendered = render()
    except SourceProblem as error:
        print("FAIL cannot build the bundle — %s" % error)
        return 2

    if "--check" in argv:
        stale = drifted()
        if stale:
            print(
                "STALE site/content/repo-sources.js — drifted: %s. "
                "Run python site/tools/embed_sources.py" % ", ".join(stale)
            )
            return 1
        print("OK repo-sources.js matches %d embedded files" % len(SOURCES))
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8", newline="")
    print(
        "wrote %s (%d files, %d bytes)"
        % (OUTPUT.relative_to(REPO), len(SOURCES), len(rendered.encode("utf-8")))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
