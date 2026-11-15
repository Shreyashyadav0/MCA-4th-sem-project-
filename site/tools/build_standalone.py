#!/usr/bin/env python3
"""Build one self-contained HTML file from the site.

Why this exists: the site is a folder of relative links, and every free proxy
that renders HTML (raw.githack) serves .css as text/plain with nosniff, so the
browser refuses the stylesheets and the page renders unstyled. A single file with
everything inlined has no relative links to break, so it opens correctly from
file://, from an email attachment, or from any host.

    python site/tools/build_standalone.py            # writes site/standalone.html
    python site/tools/build_standalone.py --check    # exits 1 if it is stale
"""

from __future__ import annotations

import pathlib
import re
import sys

SITE = pathlib.Path(__file__).resolve().parent.parent
OUT = SITE / "standalone.html"

CSS = ["tokens.css", "layout.css", "components.css", "code.css", "print.css"]


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def inline_css(html: str) -> str:
    for name in CSS:
        tag = '<link rel="stylesheet" href="assets/css/%s">' % name
        if tag not in html:
            raise SystemExit("missing stylesheet tag: %s" % tag)
        css = read(SITE / "assets" / "css" / name)
        html = html.replace(tag, "<style>\n%s\n</style>" % css, 1)
    return html


def inline_js(html: str) -> str:
    """Replace every <script src> with an inline <script>, in document order."""
    pattern = re.compile(r'<script src="([^"]+)"></script>')

    def replace(match: re.Match[str]) -> str:
        rel = match.group(1)
        path = SITE / rel
        if not path.exists():
            raise SystemExit("missing script: %s" % rel)
        body = read(path)
        # A literal </script> inside a string would end the block early.
        body = body.replace("</script>", "<\\/script>")
        return "<script>\n/* %s */\n%s\n</script>" % (rel, body)

    return pattern.sub(replace, html)


def main(argv: list[str]) -> int:
    check = "--check" in argv
    html = read(SITE / "index.html")
    html = inline_css(html)
    html = inline_js(html)

    if re.search(r'(src|href)="(?!data:|#)[^"]+\.(css|js)"', html):
        print("FAIL: a stylesheet or script link survived inlining", file=sys.stderr)
        return 1

    if check:
        if not OUT.exists():
            print("FAIL: %s does not exist; run without --check" % OUT.name, file=sys.stderr)
            return 1
        if OUT.read_text(encoding="utf-8") != html:
            print("FAIL: %s is stale; rebuild it before publishing" % OUT.name, file=sys.stderr)
            return 1
        print("OK %s is current" % OUT.name)
        return 0

    OUT.write_text(html, encoding="utf-8")
    print("wrote %s (%d KB)" % (OUT.name, len(html.encode("utf-8")) // 1024))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
