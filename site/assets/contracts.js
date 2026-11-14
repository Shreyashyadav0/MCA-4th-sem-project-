/* contracts.js — the shared constants every other module reads.
 *
 * Written once, in Wave 1, before any other site file. Nothing here may be
 * edited by a lesson author, and no other module may add a key to this object.
 * If a later wave needs a new constant, the wave that needs it edits this file
 * deliberately and records the change in site/STATE.md.
 *
 * Globals defined by the site (exactly six, no others):
 *   window.CONTRACTS  this file
 *   window.App        assets/app.js      router, renderer, helpers
 *   window.Search     assets/search.js   client-side index
 *   window.Progress   assets/progress.js localStorage progress
 *   window.PyRun      assets/pyodide-loader.js  optional in-browser Python
 *   window.LESSONS    the content files, an array built by push()
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

  window.CONTRACTS = {
    PARTS: PARTS,

    /* Bumped only when the lesson object shape changes. The validator refuses
     * a lesson written against a different version than this one. */
    SCHEMA_VERSION: 1,

    /* localStorage keys. Both are namespaced and versioned so a future format
     * change can ignore old data instead of crashing on it. */
    PROGRESS_KEY: "ai-reviewer-learning-progress-v1",
    THEME_KEY: "ai-reviewer-learning-theme-v1",
    STORAGE_VERSION: 1,

    /* The exact markdown the renderer supports. Anything outside this list is
     * not rendered: it is escaped and shown as text. No raw HTML, ever. */
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
