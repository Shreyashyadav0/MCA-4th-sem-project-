# The learning site

A static, offline-first W3Schools-style site for the Autonomous AI Code Reviewer.
Thirteen parts, 104 lessons planned; two are written (0.1 and 1.1).

**This site is a learning aid; `docs/learning/` is the source of truth.**

## Open it

Double-click `site/index.html`. That is the whole installation.

No server, no build step, no npm, no framework. The site is vanilla HTML, CSS and
JavaScript, and every content file is a `.js` file loaded by a `<script>` tag —
which is why it works on `file://`, where `fetch()` of a local JSON file is
blocked. Opening `index.html` from a web server works too, but nothing requires it.

## What is where

```
site/
  README.md                      this file
  index.html                     the parts list, search, progress, theme toggle
  lesson.html                    one lesson, addressed as lesson.html?id=1.1
  assets/contracts.js            PARTS, storage keys, the markdown subset
  assets/app.js                  router, renderer, page chrome
  assets/search.js               client-side search over titles and concepts
  assets/progress.js             "Mark done" state in localStorage
  assets/pyodide-loader.js       optional in-browser Python
  assets/manifest.js             the ordered list of lesson files
  assets/style.css               tokens, dark theme, print CSS, a11y
  content/part-<n>/lesson-<id>.js  one lesson per file
  tools/validate_lessons.py      the machine gate every wave must pass
  STATE.md                       the wave log
```

## What Pyodide does, and what it does not

Examples marked `"runnable": true` can be executed in the browser. The first press
of **Run** downloads Pyodide (~10 MB) from `https://cdn.jsdelivr.net/pyodide/` and
runs the code in a WebAssembly Python. Nothing is downloaded before that press, and
nothing else on the page needs the network.

It is a convenience. It is never a dependency:

- With no network, a runnable example shows **Copy code** and a **Run in terminal**
  panel with the exact command. The page makes no request, so there is no failed
  request and no error in the console.
- Examples that cannot run in a browser (anything that shells out, needs the
  repository, or needs a credential) are authored with `"runnable": false` and an
  `expected_output`, and always show the terminal panel.

## What degrades offline

| Feature | With network | Without network |
|---|---|---|
| Lessons, parts, search, progress | works | works — all local files |
| Runnable Python examples | runs in the browser | Copy + terminal panel |
| Everything else | — | unaffected |

## Progress and theme

Both live in `localStorage`, on the reader's machine, and never leave it:

- `ai-reviewer-learning-progress-v1` — `{"version": 1, "done": {"0.1": true}}`
- `ai-reviewer-learning-theme-v1` — `"light"` or `"dark"`

If a browser refuses storage (some configurations do on `file://`), the site keeps
working for the session and simply will not remember. Nothing throws.

## The validator

```bash
python site/tools/validate_lessons.py     # exit 0 and one summary line when clean
```

Standard library only. It parses `assets/manifest.js`, extracts each pushed lesson
object, and checks the frozen schema, the id/order arithmetic, the `part_title`
against `CONTRACTS.PARTS`, that every `project_links` path exists (and its line
range fits), that no `concept_md` contains raw HTML, that `content/` and the
manifest list the same files, that both pages load the manifest's lessons in
manifest order, and that each page carries exactly the ids the DOM contract
names — no missing id, no extra one. It exits non-zero with one line per problem.

## Adding a lesson

1. Write `content/part-<n>/lesson-<id>.js` as exactly:

   ```js
   window.LESSONS = window.LESSONS || [];
   window.LESSONS.push({ ...one object matching the frozen schema... });
   ```

   The object must be **JSON-compatible** (double-quoted keys and strings, no
   template literals, no trailing commas) because the validator parses it as JSON.
   `concept_md` is markdown only, and only the subset in `CONTRACTS.MARKDOWN_SUBSET`:
   `###`/`####` headings, paragraphs, bold, italic, inline code, fenced code with a
   language tag, unordered and ordered lists, blockquotes, links, simple tables.
   No raw HTML, no images, no footnotes. Emphasis nests one level — `***both***`
   or `*italic with **bold** inside*`; anything deeper, or the two markers
   crossed, stays literal text.

2. Append its path to `assets/manifest.js`, in lesson order.
3. Add the same `<script src>` to `index.html` and `lesson.html`, in the same place.
4. Run the validator. It fails if the three lists disagree, which is the point.
5. Append a row to `STATE.md`. Never rewrite an earlier row.

## Constraints this site keeps

- No real API keys, ever, and no fabricated numbers or paths. Every lesson cites a
  file that exists; the validator checks it.
- No claimed outcomes. Nothing here says the model layer produced a review, or that
  a benchmark number exists, because in this repository neither has happened. See
  `HANDOFF.md`.
- Test counts, rule counts and module counts are quoted from the repository at
  commit `ca96890`, and only there.

## Licence

Same as the repository: MIT.
