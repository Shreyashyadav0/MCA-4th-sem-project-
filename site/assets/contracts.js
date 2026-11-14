/* contracts.js — the shared constants every other module reads.
 *
 * Written once, in Wave 1, before any other site file. Nothing here may be
 * edited by a lesson author, and no other module may add a key to this object.
 * If a later wave needs a new constant, the wave that needs it edits this file
 * deliberately and records the change in site/STATE.md.
 *
 * Globals defined by the site (exactly eight, no others):
 *   window.CONTRACTS  this file
 *   window.App        assets/app.js      router, renderer, helpers
 *   window.Search     assets/search.js   client-side index
 *   window.Progress   assets/progress.js localStorage progress
 *   window.Sidebar    assets/sidebar.js  the lesson tree
 *   window.PyRun      assets/pyodide-loader.js  in-browser Python
 *   window.LESSONS    the content files, an array built by push()
 *   window.REPO_SOURCES  content/repo-sources.js (generated) — the embedded
 *                     repository files the runner writes into Pyodide
 */
(function () {
  "use strict";

  /* Frozen for all seven waves. Never reorder, never renumber, never retitle.
   * `lessons` is the planned count for the part, not the count shipped so far:
   * a part is complete when Progress.partCounts(n).total equals it. */
  var PARTS = [
    { n: 0, title: "Orientation", lessons: 2 },
    { n: 1, title: "Python fundamentals", lessons: 10 },
    { n: 2, title: "Typing and data modelling", lessons: 8 },
    { n: 3, title: "Testing with pytest", lessons: 8 },
    { n: 4, title: "HTTP and FastAPI", lessons: 8 },
    { n: 5, title: "Unified diffs", lessons: 8 },
    { n: 6, title: "The five-field contract", lessons: 8 },
    { n: 7, title: "The parser", lessons: 8 },
    { n: 8, title: "The rule engine", lessons: 10 },
    { n: 9, title: "Configuration and offline-first", lessons: 8 },
    { n: 10, title: "Providers and LLM APIs", lessons: 10 },
    { n: 11, title: "The engine and the fallback", lessons: 6 },
    { n: 12, title: "Surfaces: CLI, API, webhook, GitHub", lessons: 10 }
  ];

  /* The lesson object, as of schema version 2. This comment is the reference a
   * lesson author reads; tools/validate_lessons.py enforces it.
   *
   *   id            "1.3"            part and number, order = part*100 + n
   *   part, part_title, title, order, duration_min
   *   concept_md    markdown, subset in MARKDOWN_SUBSET below
   *   code_examples [ { id: "1.3-ex-0", lang, caption, code, runnable, run_tier,
   *                     expected_output?, why_not?, packages?, files? } ]
   *                 `id` must be "<lesson id>-ex-<index>", unique across the
   *                 site. It is positional: inserting an example renumbers the
   *                 ones after it, so append rather than insert. tryit.html is
   *                 addressed as tryit.html?id=1.3&ex=0 (the index), and the
   *                 lesson page emits that link for you.
   *   try_it        { prompt, starter, solution, explanation }
   *   exercise      { prompt, hint, solution, explanation }
   *   quiz          [ { q, options: [..], answer: <int index>, why } ]
   *                 Optional in Wave 1.6, required from Wave 2 onward.
   *                 The gate enforces: 3 to 5 questions; at least two non-empty
   *                 options each; `answer` an integer inside options; `why` a
   *                 non-empty string, shown whether the answer was right or
   *                 wrong.
   *
   * No raw HTML anywhere an author writes prose: concept_md, quiz q/options/why,
   * code_examples[].caption and code_examples[].why_not. The gate checks all of
   * them; markup fails the wave rather than rendering as text.
   *   common_mistakes, project_links, learn_more, glossary_terms
   */
  window.CONTRACTS = {
    PARTS: PARTS,

    /* The version of the lesson object shape. Version 2 (Wave 1.6) added
     * `code_examples[].id` and `quiz`; version 1 lessons have neither. Nothing
     * enforces the stamp — the validator checks the fields themselves — but it
     * tells a later wave what it is looking at. */
    SCHEMA_VERSION: 2,

    /* localStorage keys. Both are namespaced and versioned so a future format
     * change can ignore old data instead of crashing on it. */
    PROGRESS_KEY: "ai-reviewer-learning-progress-v1",
    THEME_KEY: "ai-reviewer-learning-theme-v1",
    STORAGE_VERSION: 1,

    /* The exact markdown the renderer supports, listed for authors. Anything
     * outside it is escaped and shown as text; no raw HTML, ever. This list is
     * descriptive — app.js implements it and the validator does not derive from
     * it — so a change here and a change in renderMarkdown must be made together. */
    MARKDOWN_SUBSET: [
      "heading-3",
      "heading-4",
      "paragraph",
      "bold",
      "italic",
      "inline-code",
      "fenced-code-with-language",
      "unordered-list",
      "ordered-list",
      "blockquote",
      "link",
      "table"
    ]
  };
})();
