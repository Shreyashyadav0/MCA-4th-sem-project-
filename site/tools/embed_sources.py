#!/usr/bin/env python3
"""Embed the repository's own source into site/content/repo-sources.js.

file:// forbids fetch(), so a browser cannot read app/models.py from disk. The
runner writes this bundle into Pyodide's virtual filesystem before it executes a
lesson's code, which is what lets a lesson say `from app.models import Finding`
and have it work exactly as it does on a real machine.

Rules this script keeps:
  * Every file is embedded VERBATIM. A paraphrased source file would teach a
    codebase that does not exist.
  * Each file is serialised with json.dumps, so quotes, backslashes, newlines
    and non-ASCII text survive the round trip into a JS string literal.
  * It is re-runnable and deterministic: same inputs, same bytes out.

Usage, from the repository root:

    python site/tools/embed_sources.py          # write the bundle
    python site/tools/embed_sources.py --check  # exit 1 if it is stale

`--check` is what a later wave runs in CI: the bundle is generated, so a source
file that changed without regenerating it is a defect, not a surprise.
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

# What the browser can actually import. app/config.py needs pydantic-settings,
# which Pyodide does not ship, and both db.py and engine.py import it — so those
# two are embedded for reading and quoting, not for import. The lessons must not
# promise otherwise; site/STATE.md records the check that proves it.
IMPORTABLE = ["app/__init__.py", "app/models.py", "app/parser.py", "app/rules.py"]

HEADER = """/* repo-sources.js — GENERATED. Do not edit by hand.
 *
 * Written by site/tools/embed_sources.py from the repository at the frozen
 * commit. Each value is the real file, verbatim, so a lesson can write it into
 * Pyodide's virtual filesystem and then import it.
 *
 * Regenerate with:  python site/tools/embed_sources.py
 * Check it is current:  python site/tools/embed_sources.py --check
 *
 * Importable in the browser: {importable}
 * Embedded for reading only: {reading}
 */
"""


class MissingSource(Exception):
    """A file the bundle promises is not on disk."""


def build() -> str:
    entries = []
    for relative in SOURCES:
        path = REPO / relative
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            raise MissingSource(f"{relative} ({error.strerror})") from error
        entries.append("  %s: %s" % (json.dumps(relative), json.dumps(text)))
    reading = [name for name in SOURCES if name not in IMPORTABLE]
    header = HEADER.format(
        importable=", ".join(IMPORTABLE),
        reading=", ".join(reading) if reading else "none",
    )
    body = "window.REPO_SOURCES = {\n" + ",\n".join(entries) + "\n};\n"
    return header + body


def main(argv: list[str]) -> int:
    try:
        rendered = build()
    except MissingSource as error:
        print("FAIL cannot build the bundle — missing source: %s" % error)
        return 2
    if "--check" in argv:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.is_file() else ""
        if current != rendered:
            print("STALE %s — run python site/tools/embed_sources.py" % OUTPUT.relative_to(REPO))
            return 1
        print("OK repo-sources.js matches %d embedded files" % len(SOURCES))
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(
        "wrote %s (%d files, %d bytes)"
        % (OUTPUT.relative_to(REPO), len(SOURCES), len(rendered.encode("utf-8")))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
