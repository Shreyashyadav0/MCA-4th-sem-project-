# Site state — the wave log

Append-only. Each wave adds one row and one section; no wave rewrites an earlier
entry. If a row disagrees with the repository, the repository is right and the row
is the bug.

| Wave | Date | Base commit | Files added | Lessons added | Validator |
|---|---|---|---|---|---|
| 1 | 2026-11-14 | `ca96890` (frozen reference) | 14 | 2 (`0.1`, `1.1`) | `OK lessons=2 parts_covered=2 manifest_entries=2 ids=0.1,1.1` |
| 1a | 2026-11-14 | `dd561fe` | 0 added, 14 changed | 0 | `OK lessons=2 parts_covered=2 manifest_entries=2 ids=0.1,1.1` |
| 1.5 | 2026-11-14 | `4c70195` | 2 added, 10 changed | 0 new; `0.1` and `1.1` rewritten with live examples | `OK lessons=2 parts_covered=2 manifest_entries=2 ids=0.1,1.1` |
| 1.6 | 2026-11-14 | `f24c9de` | 2 added, 9 changed | 0 new; `0.1` and `1.1` gained example ids and quizzes | `OK lessons=2 parts_covered=2 manifest_entries=2 ids=0.1,1.1` |
| 1.6a | 2026-11-14 | `346619e` | 0 added, 8 changed | 0 | `OK lessons=2 parts_covered=2 manifest_entries=2 ids=0.1,1.1` |
| 1.6b | 2026-11-14 | `8e36944` | 0 added, 6 changed | 0 | `OK lessons=2 parts_covered=2 manifest_entries=2 ids=0.1,1.1` |
| 2 | 2026-11-14 | `ade2c8d` | 14 added, 5 changed | 14 (`0.2`–`0.4`, `1.2`–`1.12`) | `OK lessons=16 parts_covered=2 manifest_entries=16 ids=0.1,…,1.12` |
| 2a | 2026-11-15 | `3e2eee1` | 0 added, 18 changed | 0 | `OK lessons=16 parts_covered=2 manifest_entries=16 ids=0.1,…,1.12` |
| 2b | 2026-11-15 | `b3924dc` | 0 added, 15 changed | 0 | `OK lessons=16 parts_covered=2 manifest_entries=16 ids=0.1,…,1.12` |
| 3 | 2026-11-15 | `f0c83f7` | 24 added, 12 changed | 18 (`2.1`–`2.10`, `3.1`–`3.8`) | `OK lessons=34 parts_covered=4 manifest_entries=34 ids=0.1,…,3.8` |

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

## Wave 1.5 — the in-browser runner

Wave 1 shipped a runner that could only execute snippets with no project
imports, which made almost every example a "copy this into a terminal" block.
This wave replaces it: a lesson can now run the repository's own modules in the
browser, because the source files are embedded and written into Pyodide's virtual
filesystem before the code executes.

**Added.** `site/tools/embed_sources.py` (generates `site/content/repo-sources.js`
from seven real files: `app/__init__.py`, `app/models.py`, `app/parser.py`,
`app/rules.py`, `app/db.py`, `app/engine.py`, `samples/sample.diff`).
`site/content/repo-sources.js` is generated, 138 KB, and `--check` fails when it
is stale.

**Rewritten.** `assets/pyodide-loader.js` (Pyodide 0.28.0; API is now
`init / isAvailable / run / attachAll`), `assets/style.css` (output pane, spinner,
loading state, terminal panel, `why_not` line), both seed lessons (each now has a
live example and a declared `run_tier`), `tools/validate_lessons.py` (tier checks),
`assets/app.js` (renders example figures from the tier data; the runner wires
them).

**Verified package lists, checked 2026-11-14** against
`https://cdn.jsdelivr.net/pyodide/v0.28.0/full/pyodide-lock.json`
(340 packages, lock version `0.28.0.dev0`):

```
PRESENT  pydantic 2.10.6   pydantic-core 2.27.2   sqlalchemy 2.0.39
         pytest 8.3.5      httpx 0.28.1           openai 1.68.2
         numpy 2.2.5       pyyaml 6.0.2            micropip 0.10.0
ABSENT   fastapi   starlette   uvicorn   pydantic-settings   sarvamai
```

**The six acceptance tests, run in headless Chromium over `file://`,** with the
runner byte-identical to the shipped file except for one constant: the pod reaches
the internet only through a proxy Chromium does not use, so the CDN was mirrored
locally and `CDN_BASE` pointed at `127.0.0.1`. Verbatim stdout:

```
1 hello | ok=true
hello

2 pydantic extra=forbid | ok=true
ValidationError:
1 validation error for Note
stray
  Extra inputs are not permitted [type=extra_forbidden, input_value='not allowed', input_type=str]

3 app.models.Finding | ok=true
CRITICAL app/db.py:3
verdict: block

4 app.parser on sample.diff | ok=true
files changed: 2
first hunk: @@ -1,5 +1,8 @@

5 app.rules on sample.diff | ok=true
findings: 4
  CRITICAL app/db.py:3
  CRITICAL app/db.py:3
  CRITICAL app/db.py:7
  MEDIUM   app/report.py:1
verdict: block

6 sqlalchemy | ok=true
[(1, 'CRITICAL')]

fatal: none        page console: clean        elapsed: 45 s for all six
```

Test 5 is the claim that matters: the same `app/rules.py`, over the same diff,
gives the same four findings and the same `block` verdict as the CLI.

**Offline degradation, verified.** With `CDN_BASE` pointed at a dead port and
lesson 0.1 loaded on `file://`: the page renders normally, one Run press turns the
browser-tier example into a visible terminal panel with the expected output and a
line saying the runtime could not be loaded, the terminal-tier example keeps its
own `why_not`, no uncaught error, console clean.

**What cannot be imported, and why.** `app/db.py` and `app/engine.py` both do
`from app.config import Settings`, and `app/config.py` needs `pydantic-settings`,
which Pyodide does not ship. So those two files are embedded for reading and
quoting, not for import; a lesson must not promise otherwise. Test 6 therefore
exercises the sqlalchemy stack directly rather than `app.db`. `sqlite3` is
unvendored from the Pyodide stdlib and must be loaded as a package — an example
that wants sqlalchemy must list `"packages": ["sqlalchemy", "sqlite3"]`.

**Deviations from the brief.**

- The brief's module table says `app/engine.py` and `app/db.py` import in the
  browser. They do not, for the `pydantic-settings` reason above. The lessons do
  not rely on either.
- `expected_output` is now required on `terminal` examples and *optional* on the
  other two tiers, where it is used only by the offline fallback. The brief asks
  for the fallback to show "the expected_output", which a browser example can only
  do if it is allowed to carry one.
- `assets/app.js`, `index.html`, `lesson.html` and `validate_lessons.py` all
  changed although the brief assigned five files to five agents: the new API
  renders examples and wires them in one pass, so the page markup and both pages
  had to move with it, and the gate had to learn the tiers.

## Wave 1.5a — second audit round

Nine independent auditors read the Wave 1.5 tree: the runner (which ran its own
acceptance suite in a browser), the source-embedding generator, the renderer and
pages, the stylesheet, the gate, both lessons, the documentation, and a
cross-cutting security review. 79 findings came back: 6 blockers, 21 major, the
rest minor and nit. Every one was triaged; the real defects were fixed here.

**Blockers fixed.**

1. `run()` reported *every* failure as a load failure, so a lesson asking for a
   file that was not embedded told the reader "the page is offline" while the
   runtime was healthy. Failures now carry `error_kind`: `load` (terminal
   fallback, Run hidden), `setup` (the message is shown, Run stays) or `python`
   (traceback shown).
2. `embed_sources.py` read in text mode, so a CRLF source file was silently
   rewritten to LF — the bundle was not byte-identical, which is the one thing it
   promises. It now reads bytes and decodes; proven with a CRLF copy of
   `app/parser.py`.
3. `run_tier: null` skipped the entire tier block, so `runnable`, `why_not`,
   `expected_output` and `packages` went unchecked.
4. An empty lesson file was skipped instead of failed.
5. An empty page was skipped instead of failed.
6. The gate never checked whether `repo-sources.js` matched its sources, so a
   stale bundle could ship. It now regenerates and compares, through the same
   module `--check` uses.

**Major fixes.**

- Runner: stdout/stderr are flushed before a run resolves (a `print(end="")` used
  to vanish and reappear inside the *next* run); the last expression's value is no
  longer appended to stdout; runs are serialised through a queue, because two
  concurrent runs shared one stdout handler and interleaved; `attachAll()` wires
  figures it has not seen yet instead of being a permanent one-shot; stderr is
  shown on the traceback path too; output is capped at 64 KB; a lesson's `files`
  may no longer contain `..` or an absolute path, and may only name an embedded
  file; `packages` must be distribution names, not URLs; `REPO_SOURCES` is
  snapshotted at first use so a lesson cannot swap the sources under the runner;
  the CDN script now carries a `sha384` integrity hash and `crossorigin`; the
  `micropip` comment that described code that did not exist is gone; coming back
  online re-offers the Run button instead of leaving it hidden for the session.
- Renderer: `PyRun.attachAll()` is called inside a try/catch, so a broken runner
  degrades to "no Run button" instead of a half-rendered lesson; a browser
  example's expected output is now readable in a folded `<details>`; the output
  pane is a focusable region with one live region per figure (it was announcing
  twice); a malformed `?id=` is reported as a broken link instead of silently
  showing the first lesson; the not-found page has a breadcrumb; the lesson page
  hides its sections in markup so a JS-less reader sees the note, not seven empty
  headings.
- CSS: a disabled Run button was 3.82:1 (faded accent) and is now explicit
  colours; the spinner track was 1.42:1 and could shrink to nothing; a print
  preview truncated the output pane and printed a frozen spinner; `pre.code`
  clipped on paper; a dead duplicate `.example-output` block and four redundant
  print tokens are gone.
- Gate: duplicate page ids are rejected; `<script defer src=…>` and single-quoted
  ids are understood; a BOM is reported; an empty embedded value is rejected;
  unknown flags are rejected with exit 2; the docstring now states the rule the
  code enforces.
- Lessons: "six lines" was seven; the terminal block is labelled stdout-only and
  names the stderr WARNING; `project_links` carry real line ranges instead of
  empty strings; the second example's caption no longer implies engine output.
- Docs: the `browser` and `browser-pkg` rows described `micropip` and "nothing
  extra", neither of which was true; the sqlite3 note now records what was
  observed rather than what the lock file claims; the validator description no
  longer says it extracts objects from the manifest; this table gained the missing
  Wave 1a row and the correct file counts.

**Accepted, not fixed.**

- An infinite loop in an example freezes the tab. Interrupting Pyodide needs a
  `SharedArrayBuffer` interrupt buffer or a Worker, and neither is available from
  `file://`. Stated in `site/README.md` under "What this is not".
- Lesson code is not sandboxed: it can `import js` and reach `localStorage` and
  the network. Documented rather than pretended otherwise; a Worker-based sandbox
  is the real fix and it cannot run from `file://`.
- The acceptance suite is run ad hoc and its harness is not committed, so the
  transcript below is reported, not reproducible from the repository alone.
- `HANDOFF.md` in the frozen repo still quotes 638 and 637 tests in two places.
  That file is outside `site/` and frozen; the site must not repeat those numbers,
  and does not.

## Wave 1.6 — the W3Schools layout

The site worked but did not feel like a reference: no permanent topic list, no
full-page editor behind "Try it yourself", no quiz, and prev/next were text
links. This wave changed presentation only — no lesson prose or code was
rewritten, only example ids and quizzes were added.

**Added.** `assets/sidebar.js` (`window.Sidebar = { render }` — the sixth and
only new global), `tryit.html` (the split editor).

**Changed.** `assets/app.js` (sidebar call, quiz, position line, ❮/❯ pager,
arrow keys, "Try it yourself »" links), `assets/style.css` (sidebar, drawer,
quiz, pager, split panes, print overrides), `assets/contracts.js` (schema
version 2, with the lesson object documented), `tools/validate_lessons.py`
(example ids, quiz shape, the new pages), both lessons, `index.html`,
`lesson.html`, `README.md`.

**Two schema fields later waves must now supply.**

1. `code_examples[].id` — stable, `<lesson id>-ex-<n>`, e.g. `1.3-ex-0`. It is
   what `tryit.html?id=1.3&ex=0` addresses, so it must never change once written.
2. `quiz` — an array of 3 to 5 `{q, options, answer, why}`. `answer` is the index
   of the correct option; `why` is one sentence, shown whether the answer was
   right or wrong. Optional in this wave, **required from Wave 2 onward**.

**Gate results, verbatim.**

```
$ python site/tools/validate_lessons.py
OK lessons=2 parts_covered=2 manifest_entries=2 ids=0.1,1.1

$ python site/tools/embed_sources.py --check
OK repo-sources.js matches 7 embedded files

$ python -m pytest -q tests
640 passed, 1 skipped

$ git status --porcelain
(only site/ paths)
```

Browser checks, headless Chromium over `file://` at 1400×900 and 600×900:

```
index:  sidebar parts 13 | part 0 expanded (1 lesson) | part 2 collapsed |
        aria-current 0 | toggle display none | sidebar width 260px
lesson: aria-current on 0.1 | part 0 expanded | ticks 0 -> 1 after marking done |
        "Part 0 · Lesson 1 of 2" | prev "❮ Start of the path" |
        next "Next part ❯ · Variables, types, and f-strings" |
        quiz 3 questions, q1 wrong -> why text, q2 right, q3 "Pick an answer first." |
        2 try-it links, first href tryit.html?id=0.1&ex=0 |
        ArrowRight inside a textarea does not navigate
drawer: at 600px toggle display block | closed -> aria-hidden true |
        open -> body.sidebar-open, aria-expanded true, focus inside the sidebar |
        Escape -> closed, aria-expanded false
tryit:  1.1 ex 0 preloaded | edited code ran -> "edited in the browser" |
        Reset restored the original snippet | back link lesson.html?id=1.1
tryit:  0.1 ex 1 (terminal tier) -> no Run button, command
        "python -m pytest -q tests", expected output, and the why line
```

**Deviations from the brief.**

- `index.html`, `lesson.html` and `tryit.html` were not assigned to any agent but
  had to change: the sidebar needs a container and a toggle on both pages, and
  `tryit.html` is new. All three are in the tree above.
- The brief says every part is a collapsible group *and* that one click reaches
  any lesson. Both cannot hold for a collapsed group, so parts that have lessons
  start expanded and parts that do not start collapsed; the current part is
  always forced open.
- "Next part" appears when the next lesson belongs to a different part, which
  for lesson 0.1 (the only written lesson of Part 0) means 0.1 already shows it.
- The quiz is optional in the validator, as the brief specifies, but both shipped
  lessons carry three questions each so the shape has a reference implementation.

## Wave 1.6b — two audit rounds

Two rounds of independent audit, each followed by fixes: six auditors over the
Wave 1.6 tree (67 findings: 4 blockers, 20 major), then six more over the fixed
tree (51 findings: 3 blockers, 8 major). Both rounds were fixed in place; this
section records what the two rounds changed and what was deliberately left.

**Round one — the blockers.**

1. `sidebar.js` re-added the drawer's click listener on every render, so the
   handlers stacked and two clicks cancelled out. Every drawer listener is now
   bound once behind a module flag, and the close button is delegated.
2. The closed drawer carried `aria-hidden="true"` while staying in the tab
   order; it now also gets `inert` and `visibility: hidden`, and the page behind
   an open drawer goes inert.
3. `tryit.html` crashed on a malformed percent-escape before binding anything,
   leaving an empty editor and a dead Run button.
4. The drawer's scrim painted `--bg`, so it was invisible in both themes; it has
   its own `--scrim` token now.

**Round one — the rest.** Sidebar counts no longer mix written and planned
numbers; the tick and the part count refresh after "Mark done"; the resize
handler no longer leaves an off-screen drawer exposed; the quiz skips
unanswerable questions, guards an out-of-range answer index, clears stale marks
and announces verdicts; the position line says "of 10 planned" while a part is
half written; the lesson page gained the theme toggle the other pages had; the
split editor's Tab no longer traps focus, its divider follows the stacked axis,
its offline fallback prints the code the reader actually typed, and Run comes
back after a load failure; print hides the editor; the gate learned per-page
script order, quiz-shaped raw HTML, duplicate JSON keys and the new page ids.

**Round two — the blockers.**

1. The print fix over-reached: hiding `.tryit`, `.split` and `.pane` hid the
   output pane too, so printing the editor produced a blank sheet. Only
   `.tryit-bar`, `.tryit-status`, `.pane-left`, the textarea and the divider are
   hidden now, and the output prints as a plain page — proven by rendering a PDF.
2. `restoreRun()` bailed out whenever the runtime was unavailable, so Reset after
   a blocked CDN never brought Run back; and it also unhid Run for a
   terminal-tier example, deleting its command panel. It now checks the tier and
   restores unconditionally for browser tiers.
3. A `null` entry in `quiz` threw out of `renderLesson`, taking the sidebar, the
   pager and the theme toggle with it. Broken entries are skipped.

**Round two — the rest.** The sidebar no longer steals focus when it re-renders;
its Tab trap skips links inside collapsed groups; the header and footer go inert
with the page. `bindMarkDone` and `bindThemeToggle` bind once and re-sync, so a
third render no longer makes them no-ops. The not-found page binds the theme
button, empties the sections it hides, and says when a link is unreadable. The
divider is a 24px track with an 8px bar, so it never overlays a pane. The dark
scrim is visible. Print re-declares `--scrim` and `--divider`. The gate now
parses every `<script>` tag regardless of attributes or quoting, ignores
`data-id`, reports the actual tag it found, and checks order even when
`manifest.js` is missing.

**Accepted, not fixed.**

- The collapsed state of a sidebar part is remembered for the session, not
  across page loads: every navigation re-expands the parts that have lessons.
  Persisting it would be a new storage key, and the wave did not ask for one.
- `inert` is not supported everywhere. Where it is missing, the drawer still
  works (visibility and focus trapping carry it) but the page behind it stays in
  the accessibility tree.
- Printing the editor before pressing Run prints an empty output pane, because
  the pane is empty. That is the page, not the stylesheet.

## Curriculum changes

**Wave 2 — 104 lessons became 108.** Parts 0 and 1 were enlarged: Part 0 from 2
lessons to 4, Part 1 from 10 to 12. The reason is that setup and typing deserve
their own lessons — every later part assumes a working environment and a reader
who can read a type annotation, and both were previously compressed into a single
orientation lesson. The remaining wave map is now 16 / 32 / 48 / 64 / 92 / 108.

## Wave 2 — Parts 0 and 1

Fourteen new lessons: `0.2`, `0.3`, `0.4` (Orientation, now complete at 4) and
`1.2`–`1.12` (Python fundamentals, now complete at 12). `0.1` and `1.1` were not
touched.

**Changed.** `assets/contracts.js` (PARTS: part 0 → 4, part 1 → 12 — the array
lives there and nowhere else), `assets/manifest.js` (14 paths appended in id
order), `index.html` / `lesson.html` / `tryit.html` (one `<script>` per lesson, in
manifest order), `STATE.md`.

**Tiers, as declared and as verified.** Thirteen examples are `browser` and were
executed twice — once under CPython and once in the browser through the real
runner; five are `terminal` (`0.1` ex1, `0.2`, `0.3`, `0.4`, `1.11`) and carry
both `expected_output` and `why_not`.

**Gate results, verbatim.**

```
$ python site/tools/validate_lessons.py
OK lessons=16 parts_covered=2 manifest_entries=16 ids=0.1,0.2,0.3,0.4,1.1,1.2,1.3,1.4,1.5,1.6,1.7,1.8,1.9,1.10,1.11,1.12

$ python site/tools/embed_sources.py --check
OK repo-sources.js matches 7 embedded files

$ python -m pytest -q tests
640 passed, 1 skipped

$ git status --porcelain
(only site/ paths)
```

**Every browser example executed, with its real output** (CPython 3.12.13, then
re-checked in the page for 1.2):

```
0.1 ex0  files changed: 2 / findings: 4 / verdict: block
1.1 ex0  CRITICAL app/db.py:3 / verdict: block
1.1 ex1  CRITICAL  app/db.py:3 / MEDIUM    app/report.py:1
1.2 ex0  {'CRITICAL': 2, 'MEDIUM': 1} / 2 distinct files: ['app/db.py', 'app/report.py']
1.3 ex0  {'file': 'app/db.py', ...} / {'return': dict[str, str]}
1.4 ex0  Point(x=3.0, y=4.0) / magnitude: 5.0 / FrozenInstanceError -> cannot assign to field 'x'
1.5 ex0  caught as the parent: AuthError - no credential configured / finally runs …
1.6 ex0  imported: hello reader / run directly
1.7 ex0  read back: 'line one\n' / enter block / inside BLOCK / exit block
1.8 ex0  before severity_rank / after severity_rank / rank: 2 / name kept: severity_rank
1.9 ex0  2 added lines: ['added one', 'added two'] / lazy: generator
1.10 ex0 loaded: [...] / old start/count: 1 5 / new start/count: 1 8 / section: 'def check():'
1.12 ex0 running mock / ['rule-engine finding'] / running local / … / Literal aliases: …
```

**Browser checks.** Index: 16 lessons loaded, Part 0 `0/4`, Part 1 `0/12`,
Part 2 `0/8 planned`, 16 sidebar links. Search: `Protocol` → 1.12 and 1.7,
`f-string` → 1.1, `comprehension` → 1.2 and 1.9, `zzzz` → 0. Lesson 1.2 pressed Run and
printed its stated output from the real `app.models` import; position line
"Part 1 · Lesson 2 of 12"; three quiz questions; try-it link
`tryit.html?id=1.2&ex=0`. Lesson 1.11 shows no Run button, a visible terminal
panel with its command and why line, and all eight sections. `tryit.html?id=1.12&ex=0`
preloads that lesson's snippet.

**Decisions and deviations.**

- `app/db.py` and `app/engine.py` are embedded but NOT importable in the browser:
  both import `app.config`, which needs `pydantic-settings`. Lessons that cite
  them quote them; `0.4`'s example is `terminal` for exactly this reason, and no
  lesson points a Run button at them.
- Lesson 1.7 says plainly that `app/` reads files with `pathlib.read_text`
  rather than `with open(...)`; there is no real `with open(` in `app/` to cite,
  so it cites `cli.py:read_source` and the rule in `rules.py` that recommends the
  pattern to other people's code.
- `tryit.html` had to change too: it loads every lesson so it can address an
  example, and the brief named only `manifest.js` and the PARTS array.
- Lesson 1.9's wording about the parser's derived values was wrong twice over
  before the audit rounds: `Hunk.added_lines` is a property (`app/parser.py:143-144`)
  and `FileDiff.added_line_count` / `added_line_numbers` are properties too. The
  lesson now says exactly that.
- Word counts of the new lessons run 221–306; `1.1` is 537 words and was left
  alone because Wave 2 must not re-author it.

## Waves 2a and 2b — two audit rounds on the lessons

Two rounds of independent audit over the fourteen new lessons, each followed by
fixes. Round one: six auditors, 69 findings (3 blockers). Round two: six
auditors, 63 findings (3 blockers). Both rounds are fixed in place.

**Round one — the blockers.**

1. Lesson 0.2's terminal example grepped `site/content/`, and by Wave 2 the
   lesson file itself contained the string, so the command printed two paths
   where the lesson claimed one. It now greps `site/content/part-1/`.
2. Lesson 1.2's dedupe exercise claimed two distinct positions from findings at
   `db.py:3`, `db.py:7` and `report.py:1` — three. The example's second finding
   now shares line 3, and the solution is self-contained.
3. Every Part 1 quiz put the correct answer at index 1 (38 of 42). The answers
   were rotated across all four indices, and the fifteen questions where the key
   was also the longest option by a wide margin were rewritten so length is no
   longer a tell.

**Round one — the rest.** Practice answers written as prose were rendering as
Python code blocks and would `SyntaxError` if pasted; they are fenced as text.
The 1.3 signature now matches `app/engine.py`, the 1.4 exercise builds and runs
instead of asking for an explanation, 1.7's try-it stopped duplicating 1.8's,
1.9 stopped claiming the parser walks hunks lazily (it has no `yield`), 1.10
parses the real `{"findings": [...]}` shape, 1.11 names the script that actually
shells out, and 1.12 marks Protocol as a general technique rather than repository
practice. The sidebar gained a real scroll container, the gate learned to reject
a consistently mis-ordered site, and the gate is now run by CI and by
`make site`.

**Round two — the blockers.**

1. Lesson 0.2 called `docs/learning/` "the source of truth", but `HANDOFF.md`
   says it is the ledger that wins, and `docs/learning/README.md:161` still
   quotes a stale `597 passed`. The lesson and the site README now name
   `HANDOFF.md` as the ledger and describe `docs/learning/` as the curriculum.
2. Lesson 1.7 used `@contextlib.contextmanager` and `yield` four lessons before
   either is taught, with no pointer forward. It now says so explicitly.
3. Lesson 1.3's exercise solution imported `app.models` while its example
   declared no `files`, so the practice failed in the browser. The example now
   declares the file.

**Round two — the rest.** 1.11 said `learning_progress.py` runs `git`; it runs
pytest per track through `subprocess.run`. 1.4's quiz stopped claiming the
benchmark's `MatchResult` is hashable (it holds a dict). 0.3's "which file"
question had two right answers (`requirements-dev.txt` also installs pytest) and
now asks which file pins all 37. 1.6's "the file has no guard" distractor was
also true. 1.12 now uses the repository's real four-value Literal from
`app/main.py`. The sidebar's duplicate `overflow-y` went, and the focus-ring
padding moved onto the scroller that actually clips. `scripts/verify.sh` runs the
gate, so `make verify` can no longer go green while CI fails.

**Measured, not fixed.** After the rewrites, "pick the longest option" still
names the right answer more often than chance (the correct option remains the
longest in 35 of 48 questions, but the median gap to the next-longest is now
under 10 characters, against a maximum of 71 before). Removing the last of that
signal means rewriting every distractor by hand; it is recorded here rather than
claimed as done.

## Curriculum changes

**Wave 3 — 108 lessons became 110.** Part 2 (Typing and data modelling) grew from
8 planned lessons to 10, because Pydantic deserves two lessons the outline did not
have: serialisation (`model_dump` and JSON mode) and tolerant parsing (returning
`None` instead of raising). Part 3 (Testing with pytest) stays at 8. Parts 0 and 1
are untouched. The remaining wave map is now 34 written of 110.

## Wave 3 — Parts 2 and 3, and the visual design pass

Eighteen new lessons: `2.1`–`2.10` (Pydantic v2 at the boundary) and `3.1`–`3.8`
(pytest, from discovery to the zero-network proof). Parts 0 and 1 were not touched:
`git diff HEAD~1 -- site/content/part-0 site/content/part-1` prints nothing.

**The design pass.** The single 1,467-line `style.css` became five files under
`assets/css/`, linked in order from all three pages:

```
tokens.css      162 lines   every colour, type and space value; both themes; print tokens
layout.css      506 lines   reset, shell, header, sidebar, lesson column, pager, drawer
components.css  456 lines   parts list, search, prose, practice, quiz, badges, tables
code.css        336 lines   code blocks, output pane, terminal panel, split editor
print.css       192 lines   print rules + the a11y utilities (focus, skip link, sr-only, motion)
```

`style.css` is now an eight-line shim that `@import`s the five, so an old link still
works. All 148 selectors from the old file survive — the split moved rules, it did
not rewrite them — and the restyle is a new token palette plus targeted component
rules:

- Accent `#0F766E` (deep blue-teal) with its own hover and soft tints, kept clear
  of the severity ramp, which stays red/orange/amber/blue.
- Type: 17px body, 1.65 line height, a 13/15/17/20/26/34/44 scale, 72ch measure.
- Space: a 4px scale from `--space-1` to `--space-10`; every margin and padding
  in the five files reads from it.
- Shape: 12px cards, 1px borders, two soft shadows, no heavy drop shadows.
- Code blocks are dark cards in both themes with a header strip that names the
  language, so a block reads as a component rather than as a paragraph that
  happens to be monospaced. The output pane keeps its own darker surface.
- Buttons are 40px tall (a real touch target), Run is the accent fill, the rest
  are outlined. Focus is a 3px accent ring with a halo, visible on accent-filled
  controls too.
- Motion is 120–160ms on hover and expand only, and `prefers-reduced-motion`
  zeroes it.

**Gate, verbatim.**

```
$ python site/tools/validate_lessons.py
OK lessons=34 parts_covered=4 manifest_entries=34 ids=0.1,0.2,0.3,0.4,1.1,…,3.8

$ python site/tools/embed_sources.py --check
OK repo-sources.js matches 7 embedded files

$ python -m pytest -q tests
640 passed, 1 skipped

$ grep -n "#[0-9a-fA-F]\{3,6\}" site/assets/css/*.css | grep -v tokens.css
(no output — every colour literal lives in tokens.css)
```

**Executed, not trusted.** Every `browser` example in Parts 2 and 3 was run under
CPython and matched its `expected_output` byte for byte; `2.5` was then re-run in
the page through the real runner (`accepted: 42-45 / rejected: Value error`).
The `terminal` examples in Part 3 quote outputs captured from this repository at
this commit — `640 passed, 1 skipped`, `641 tests collected`, `7 passed` for the
parametrised test, `63 passed, 578 deselected` for `-k github`, and the `-rs`
skip line naming `tests/test_openai_compat_provider.py:1062`.

**Two facts the writing corrected.** `model_copy(update=...)` does **not** validate
its update, so a string where a `Severity` belongs survives until something reads
it — lesson 2.4 now teaches the re-validating pattern instead. And `Finding.line`
is typed `str` (not `int`) because the contract allows a range, which 2.2 and 2.7
both use as the example of why the type has to match the contract.

**Left for Wave 4.** Parts 4 and 5. The sidebar's collapsed state is still
per-session, `tryit.html` still prints only its output pane, and the CSS has no
syntax highlighting yet — code is one colour, which is honest but plain.

## Waves 3a and 3b — two audit rounds on Wave 3

Six auditors over the Wave 3 tree (87 findings, 4 blockers), then three more over
the fixed tree (28 findings, 1 blocker). Both rounds are fixed in place.

**Round one — the blockers.**

1. Lesson 2.9 taught that `model_validate_json` raises `json.JSONDecodeError` for
   prose. It raises `ValidationError` with type `json_invalid` — one exception
   type for bad syntax and bad shape alike. The concept, the hint, the
   common_mistakes and the quiz key all said the wrong thing; all four are fixed.
2. Every Wave 3 quiz put the correct answer at index 1 (49 of 54). Answers now
   spread evenly across all four indices, and the twelve questions where the key
   was the longest option by 30 characters or more were rebalanced.
3. `site/README.md` still said 108 lessons planned and sixteen written.
4. The ≤900px editor rules lived in `layout.css`, but `code.css` loads later and
   re-declares `.split` at the same specificity — so the stacked layout never
   applied and the divider was a vertical bar on a horizontal split. The rules
   moved into `code.css`, after the base rule.

**Round one — the rest.** `model_copy` does not validate (2.4 already said so;
2.2 and 2.6 claimed the opposite of Pydantic's default-copying), `MatchResult` is
not hashable, the enum repr is `<Severity.LOW: 'LOW'>`, a constrained default is
never validated, `pattern` is a search, 2.9's parse path is the real one
(raise → catch → one repair retry → empty list with a WARNING), `-x` is for a
cascade rather than a broken import, `tests_cli.py` fails on its prefix, 3.3's
try-it no longer needs `tmp_path`, 3.4's try-it tests what its name says, and
three TESTING.md links stopped pointing at ranges that quote a stale count.

**Round two — the blocker.** The skip-link fix hid the link permanently: the
off-screen `transform` was never cleared on focus, so the one control meant to
help keyboard users was unreachable. `.skip-link:focus` now resets it.

**Round two — the rest.** The duplicate language label survived the first fix
(a second rule painted it at 2.87:1) and is gone; `.btn-tryit` and the narrow
`.lesson-meta` lost their cascade fights to later sheets and were moved; pager and
drawer-close borders moved to `--border-control` (3.29:1); quiz marks stopped
borrowing the severity ramp for `--ok`/`--bad`; print now wraps long code lines,
opens every `<details>` before printing (a closed one renders nothing on paper),
and re-declares the soft surface tokens so a lesson printed from the dark theme
does not keep dark quiz cards. `common_mistakes`, `glossary_terms`, quiz verdicts
and fence-less solutions render inline markdown instead of printing literal
backticks, and the quiz's own question and option text render `<code>`.

**Measured, not fixed.** "Pick the longest option" still names the right answer
more often than chance (the key remains the longest in 85 of 102 questions, but
the median gap to the next-longest is 12 characters, against a maximum of 78
before). Two lessons still open on an abstract paragraph rather than a snippet
(3.1, 3.5), and six lessons never address the reader in the second person. All
three are recorded rather than claimed as done.
