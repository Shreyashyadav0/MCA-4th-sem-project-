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
