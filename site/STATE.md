# Site state — the wave log

Append-only. Each wave adds one row and one section; no wave rewrites an earlier
entry. If a row disagrees with the repository, the repository is right and the row
is the bug.

| Wave | Date | Base commit | Files added | Lessons added | Validator |
|---|---|---|---|---|---|
| 1 | 2026-11-14 | `ca96890` (frozen reference) | 14 | 2 (`0.1`, `1.1`) | `OK lessons=2 parts_covered=2 manifest_entries=2 ids=0.1,1.1` |

A file cannot record the hash of the commit that contains it, so the column above
names the commit the wave was built on. The wave commit itself is whatever
`git log -1 --format=%h` reports for the commit titled
`Wave 1 — site scaffold + 2 seed lessons`.

## Wave 1 — scaffold, contracts, validator, two seed lessons

**Scope.** `site/` only, plus one row in `README.md`. `app/`, `tests/`,
`benchmarks/` and `docs/learning/` were not touched; `git status` is the evidence.

**Added.**

```
site/index.html
site/lesson.html
site/README.md
site/STATE.md
site/assets/contracts.js
site/assets/style.css
site/assets/app.js
site/assets/search.js
site/assets/progress.js
site/assets/pyodide-loader.js
site/assets/manifest.js
site/content/part-0/lesson-0.1.js
site/content/part-1/lesson-1.1.js
site/tools/validate_lessons.py
```

**Lessons.** `0.1` — What this project is and what you'll know by the end
(Orientation, 10 min). `1.1` — Variables, types, and f-strings (Python
fundamentals, 15 min).

**Decisions taken in this wave, recorded because later waves must not re-litigate
them silently.**

1. Lesson files are JSON-compatible object literals. The validator parses the
   pushed object with `json.loads`, so a lesson containing a template literal or a
   trailing comma fails the gate rather than the browser.
2. The manifest is a data file that declares nothing (`window.LESSONS` and the five
   namespaces stay the only globals). Both pages therefore carry explicit
   `<script src>` tags for the lessons, and the validator checks the three lists —
   manifest, `index.html`, `lesson.html` — agree in content and order.
3. `lesson-0.1`'s quick-start example is `"runnable": false` with an
   `expected_output`, because it is two shell commands and Pyodide cannot run a
   shell. It therefore always shows the terminal panel. `lesson-1.1` carries the
   runnable Python example, so both paths through the example UI are exercised.
4. `README.md` has no table titled "Where things are"; the closest equivalent is
   the Documentation table, so the `site/` row was added there.
5. Lesson 1.1's `project_links` cites `app/models.py` lines `1-11`, not `1-20`:
   the file is 194 lines and the docstring that explains the five-field contract
   ends at line 11, while line 20 sits inside the import block.

**Validator output at the end of the wave.**

```
$ python site/tools/validate_lessons.py
OK lessons=2 parts_covered=2 manifest_entries=2 ids=0.1,1.1
```

**Open questions for Wave 2.**

- Parts 0–2 complete means 20 lessons, but `CONTRACTS.PARTS` gives part 0 two
  lessons and part 1 ten, part 2 eight — 20 in total, of which 2 exist. Wave 2
  writes 18 more, not 20.
- The two HTML pages now need one `<script src>` line per lesson. At 104 lessons
  that is 104 lines in each page. It is mechanical and the validator checks it,
  but if a later wave prefers a loader that injects `<script>` tags from the
  manifest, that is a change to `app.js` plus both pages, and it must keep working
  on `file://`.
- Search covers title and concept only. If a later wave wants code search, the
  index in `assets/search.js` is the single place to change.
- No lesson has been checked in a second browser yet. The Wave 1 checks were run
  ad hoc with a headless Chromium over `file://` and a Node shim for the modules
  that need a DOM; neither harness is committed, so re-running them is a Wave 2
  task worth doing properly.

## Wave 1a — corrections after a nine-agent audit

Nine independent auditors (contracts, renderer, search/progress, Pyodide, CSS,
HTML, lesson 0.1, lesson 1.1, validator + docs) read the Wave 1 tree and returned
95 findings: 3 blockers, 24 major, the rest minor and nit. Every finding was
triaged; the ones that were real defects were fixed in place. This section records
what changed and why, so a later wave does not reintroduce any of it.

**Blockers fixed.**

1. `pyodide-loader.js` declared `var run` inside `attach`, which hoisted over the
   module's `run()` — clicking Run called the DOM node and threw, so no example
   could ever run. The local is now `runBtn` and the handler uses it directly.
2. Lesson 0.1's `expected_output` claimed it omitted only the findings, while it
   also dropped the two `note :` lines and the `changed lines:` block. The output
   is now verbatim down to `verdict`, with the findings marked as the only
   omission. The `try_it` solution carried the same truncated transcript and was
   corrected the same way.
3. Lesson 1.1 described a finding as a dict with five keys and then showed four,
   with `line` as an int where `app/models.py` types it `str`. The example now has
   all five keys and `"line": "3"`.

**Major fixes.**

- Renderer: `learn_more[].href` was the one unsanitised URL sink — now `safeHref`.
  `safeHref` accepts relative paths (the 404 page's recovery link had rendered as
  text), rejects protocol-relative `//host`, and no longer double-escapes `&`.
  Inline emphasis is now one recursive scanner instead of three regex passes, so
  `**bold *it***` and `*italic with **bold** inside*` both render. Ordered lists
  keep their start number; table cells accept an escaped pipe and are normalised
  to the header width.
- Router: a malformed percent-escape in `?id=` threw `URIError` and left the page
  on its placeholder; the hash fallback also read the page's own `#…` links as
  lesson ids. Both are guarded, and the hash is used only when it looks like an id.
  A missing lesson now disables the pager instead of leaving dead `href="#"`.
- Search: a title-only hit produced a snippet with no match in it (now
  "Title match: …"), the snippet was searched in a differently-normalised string
  than the index, `~~~` and CRLF fences leaked code into the index, and a
  punctuation-only term matched every lesson (now returns nothing).
- Progress: `get()` returned the live internal object, so a caller could corrupt
  the stored state; it returns a copy.
- CSS: the focus ring used `--accent` on controls filled with `--accent` — a
  1.00:1 ring — so it is now two-tone; the print block was missing the four
  `--sev-*` tokens and would print dark pastels on white; `break-inside: avoid` on
  long code and tables clipped them; hiding `details.solution > summary` deleted
  collapsed answers from the printout; hiding `.terminal-panel` deleted the
  expected output of every example that cannot run in a browser; the search field
  border and the placeholder were below 3:1 and 4.5:1.
- HTML: the pages carried eight ids the contract does not name (`#main`, seven
  `*-heading` hooks); they now carry exactly the contract ids and use `aria-label`
  instead. `app.js` no longer writes `id="part-N"`. Added: a `<noscript>`, a real
  static `h1`, `tabindex="-1"` on the skip-link target, a `<nav>` landmark around
  the parts list, a `readyState` guard in the bootstrap, and honest footer text
  (the old footer pinned a commit hash that later waves would make false).
- Validator: an undecodable lesson file crashed with a traceback instead of a
  FAIL line; `project_links` accepted absolute paths and paths outside the repo;
  coverage only globbed `*.js`, so a stray file under `content/` went unreported;
  ids with leading zeros passed; a lesson that quotes the `window.LESSONS.push(`
  pattern in its prose was rejected; the raw-HTML check was greedy and fired on
  `<` inside a table. All six fixed, plus a new check 10: each page must carry
  exactly the ids the DOM contract names.
- Comments that claimed behaviour the code did not have were corrected:
  `SCHEMA_VERSION` is not enforced by anything (it is a stamp), `MARKDOWN_SUBSET`
  is descriptive, `manifest.js` is the validator's source of truth rather than a
  runtime one, and `app.js` is not "the only module that touches the DOM".

**Accepted, not fixed.**

- `Progress.reset()` has no UI. Adding one needs a new id on a page, which the
  frozen DOM contract forbids; it stays available to a future wave that amends
  the contract deliberately.
- The theme is applied on `DOMContentLoaded`, so a dark-mode reader sees one
  light frame. Fixing it means setting `data-theme` before first paint, i.e. a
  second inline script, which the init contract forbids.
- 104 `<script src>` lines per page at full size. Mechanical and gate-checked; a
  manifest-driven loader is the alternative if it becomes painful.
