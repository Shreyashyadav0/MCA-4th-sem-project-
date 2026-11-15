/* manifest.js — the ordered list of lesson files.
 *
 * This is the validator's source of truth for lesson order. At runtime the
 * pages load lessons from their own <script src> tags, because file:// forbids
 * fetch and the order must be fixed before the bootstrap runs; this file is the
 * list those tags are checked against, so the two cannot drift.
 *
 * It writes no global and touches no DOM: the array is a bare expression inside
 * a function, so the file declares nothing and no sixth global exists.
 *
 * Two invariants, both enforced by tools/validate_lessons.py:
 *   1. Every file under site/content/ appears here exactly once.
 *   2. index.html and lesson.html list these same paths, in this same order,
 *      as <script src> tags after manifest.js. A later wave appends here and
 *      updates both pages; the validator fails the wave if they disagree.
 *
 * Paths are relative to site/. Order is lesson order, never alphabetical.
 */
(function () {
  "use strict";

  [
    "content/part-0/lesson-0.1.js",
    "content/part-0/lesson-0.2.js",
    "content/part-0/lesson-0.3.js",
    "content/part-0/lesson-0.4.js",
    "content/part-1/lesson-1.1.js",
    "content/part-1/lesson-1.2.js",
    "content/part-1/lesson-1.3.js",
    "content/part-1/lesson-1.4.js",
    "content/part-1/lesson-1.5.js",
    "content/part-1/lesson-1.6.js",
    "content/part-1/lesson-1.7.js",
    "content/part-1/lesson-1.8.js",
    "content/part-1/lesson-1.9.js",
    "content/part-1/lesson-1.10.js",
    "content/part-1/lesson-1.11.js",
    "content/part-1/lesson-1.12.js",
    "content/part-2/lesson-2.1.js",
    "content/part-2/lesson-2.2.js",
    "content/part-2/lesson-2.3.js",
    "content/part-2/lesson-2.4.js",
    "content/part-2/lesson-2.5.js",
    "content/part-2/lesson-2.6.js",
    "content/part-2/lesson-2.7.js",
    "content/part-2/lesson-2.8.js",
    "content/part-2/lesson-2.9.js",
    "content/part-2/lesson-2.10.js",
    "content/part-3/lesson-3.1.js",
    "content/part-3/lesson-3.2.js",
    "content/part-3/lesson-3.3.js",
    "content/part-3/lesson-3.4.js",
    "content/part-3/lesson-3.5.js",
    "content/part-3/lesson-3.6.js",
    "content/part-3/lesson-3.7.js",
    "content/part-3/lesson-3.8.js",
    "content/part-4/lesson-4.1.js",
    "content/part-4/lesson-4.2.js",
    "content/part-4/lesson-4.3.js",
    "content/part-4/lesson-4.4.js",
    "content/part-4/lesson-4.5.js",
    "content/part-4/lesson-4.6.js",
    "content/part-4/lesson-4.7.js",
    "content/part-4/lesson-4.8.js",
    "content/part-5/lesson-5.1.js",
    "content/part-5/lesson-5.2.js",
    "content/part-5/lesson-5.3.js",
    "content/part-5/lesson-5.4.js",
    "content/part-5/lesson-5.5.js",
    "content/part-5/lesson-5.6.js",
    "content/part-5/lesson-5.7.js",
    "content/part-5/lesson-5.8.js",
    "content/part-6/lesson-6.1.js",
    "content/part-6/lesson-6.2.js",
    "content/part-6/lesson-6.3.js",
    "content/part-6/lesson-6.4.js",
    "content/part-6/lesson-6.5.js",
    "content/part-6/lesson-6.6.js",
    "content/part-6/lesson-6.7.js",
    "content/part-6/lesson-6.8.js",
    "content/part-7/lesson-7.1.js",
    "content/part-7/lesson-7.2.js",
    "content/part-7/lesson-7.3.js",
    "content/part-7/lesson-7.4.js",
    "content/part-7/lesson-7.5.js",
    "content/part-7/lesson-7.6.js",
    "content/part-7/lesson-7.7.js",
    "content/part-7/lesson-7.8.js"
  ];
})();
