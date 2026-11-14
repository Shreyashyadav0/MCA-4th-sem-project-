/* manifest.js — the ordered list of lesson files.
 *
 * This is the single source of truth for lesson order, and the file the
 * validator reads. It writes no global and touches no DOM: it is a data file
 * wrapped in a function so that it declares nothing, which is why the array
 * below is a bare expression.
 *
 * Two invariants, both checked by tools/validate_lessons.py:
 *   1. Every file under site/content/ appears here exactly once.
 *   2. index.html and lesson.html list these same paths, in this same order,
 *      as <script src> tags after manifest.js. Later waves append in one place
 *      and update the two pages to match; the validator fails the wave if the
 *      three lists disagree.
 *
 * Paths are relative to site/. Order is lesson order, never alphabetical.
 */
(function () {
  "use strict";

  [
    "content/part-0/lesson-0.1.js",
    "content/part-1/lesson-1.1.js"
  ];
})();
