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
5. `app/models.py` is 194 lines; the module docstring that explains the five-field
   contract is lines 1–11, so `project_links` cites `1-11` rather than `1-20`
   (line 20 is inside the import block).

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
- No lesson has been checked in a second browser yet; the Wave 1 verification used
  one headless Chromium over `file://`.
