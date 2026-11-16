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


LESSON_MAIN = re.compile(r"<main class=\"page\">.*?</main>", re.S)
INDEX_MAIN = re.compile(r"<main class=\"page\">", re.S)

# The single file holds both views and switches between them on the hash. Without
# this, every lesson link pointed at a lesson.html that does not exist beside the
# standalone, and clicking one gave the browser's "access denied".
HOST_STYLE = """<style>
  /* The single file holds two views in one grid cell: the layout grid has a
   * sidebar column and one content column, so a second <main> as a sibling would
   * be placed in a new row and never seen. */
  .view-host { min-width: 0; }
</style>
"""

ROUTER = """<script>
  (function () {
    var home = document.getElementById("index-view");
    var lessonView = document.getElementById("lesson-view");

    function idFromHash() {
      var h = String(window.location.hash || "").replace(/^#/, "");
      return /^\\d+\\.\\d+$/.test(h) ? h : "";
    }

    function show(id) {
      var isLesson = !!id;
      if (home) home.hidden = isLesson;
      if (lessonView) lessonView.hidden = !isLesson;
      try {
        if (isLesson) { window.App.initLesson(); } else { window.App.initIndex(); }
      } catch (error) {
        if (window.console && window.console.warn) {
          window.console.warn("view failed to render:", error);
        }
      }
      window.scrollTo(0, 0);
    }

    /* A lesson link becomes a hash change, so nothing is ever navigated to. */
    document.addEventListener("click", function (event) {
      var node = event.target;
      while (node && node !== document) {
        if (node.tagName === "A" && node.getAttribute("href") &&
            node.getAttribute("href").indexOf("lesson.html") === 0) {
          var m = /[?&]id=([^&]+)/.exec(node.getAttribute("href"));
          if (m) {
            event.preventDefault();
            window.location.hash = decodeURIComponent(m[1]);
            return;
          }
        }
        node = node.parentNode;
      }
    });

    window.addEventListener("hashchange", function () { show(idFromHash()); });

    function boot() { show(idFromHash()); }
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", boot, { once: true });
    } else {
      boot();
    }
  })();
</script>"""


def add_lesson_view(html: str) -> str:
    """Add the lesson page's markup and the router that switches to it.

    The lesson view has to sit inside ``.layout``, as the sibling of the index
    view within one grid cell. Inserting it anywhere else (next to the boot
    script, say) puts it outside the grid and it renders below the fold with the
    content column empty.

    Args:
        html: The index page, already inlined.

    Returns:
        The same page with both views in one cell and the index boot replaced by
        a router.
    """
    lesson_html = read(SITE / "lesson.html")
    match = LESSON_MAIN.search(lesson_html)
    if match is None:
        raise SystemExit("FAIL: could not find the lesson page's <main>")
    lesson_main = match.group(0).replace(
        '<main class="page">', '<main class="page" id="lesson-view" hidden>', 1
    )

    # Capture the index page's whole <main> so the lesson view can be placed
    # inside the same grid cell, immediately after it.
    index_main = re.compile(r"<main class=\"page\">(.*?)</main>", re.S)
    if len(index_main.findall(html)) != 1:
        raise SystemExit("FAIL: expected exactly one <main class=\"page\"> in index.html")
    html = index_main.sub(
        lambda m: (
            '<div class="view-host"><main class="page" id="index-view">'
            + m.group(1)
            + "</main>\n"
            + lesson_main
            + "\n</div>"
        ),
        html,
        count=1,
    )

    boot = re.compile(
        r"<script>\s*\(function \(\) \{.*?window\.App\.initIndex\(\);.*?</script>", re.S
    )
    if boot.search(html) is None:
        raise SystemExit("FAIL: could not find the index boot script")
    html = boot.sub(lambda _m: ROUTER, html, count=1)
    return html


def main(argv: list[str]) -> int:
    check = "--check" in argv
    html = read(SITE / "index.html")
    html = inline_css(html)
    html = inline_js(html)
    html = add_lesson_view(html)
    html = html.replace("</head>", HOST_STYLE + "</head>", 1)

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
