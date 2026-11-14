/* search.js — client-side search over window.LESSONS.
 *
 * No service, no index file, no fetch: the index is built in memory from the
 * lesson objects that the page already loaded. Search covers the title and the
 * concept text, which is the whole of a lesson that is prose; code examples are
 * deliberately excluded so a hit means "this lesson explains it", not "this
 * word appears in a code block somewhere".
 */
(function () {
  "use strict";

  var index = [];

  function normalise(value) {
    return String(value === null || value === undefined ? "" : value)
      .toLowerCase()
      .replace(/[`*_#>|[\]]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  /* Markdown to something readable in a one-line snippet: fences, inline code,
   * links and list markers removed, so the snippet is prose a human can scan. */
  function plainText(markdown) {
    return String(markdown || "")
      .replace(/```[A-Za-z0-9_+#.-]*\n[\s\S]*?```/g, " ")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, "$1")
      .replace(/^#{1,6}\s+/gm, "")
      .replace(/^>\s?/gm, "")
      .replace(/^\s*[-*+]\s+/gm, "")
      .replace(/\|/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function buildIndex(lessons) {
    var list = Array.isArray(lessons) ? lessons : [];
    index = list
      .map(function (lesson) {
        var concept = plainText(lesson.concept_md);
        return {
          id: String(lesson.id),
          title: String(lesson.title || ""),
          part: Number(lesson.part),
          part_title: String(lesson.part_title || ""),
          order: Number(lesson.order) || 0,
          titleText: normalise(lesson.title),
          conceptText: normalise(concept),
          concept: concept
        };
      })
      .sort(function (a, b) {
        return a.order - b.order;
      });
    return index.length;
  }

  function snippetFor(entry, needle) {
    var haystack = entry.concept;
    var position = haystack.toLowerCase().indexOf(needle);
    if (position === -1) {
      return haystack.slice(0, 140) + (haystack.length > 140 ? "…" : "");
    }
    var start = Math.max(0, position - 60);
    var end = Math.min(haystack.length, position + needle.length + 80);
    return (start > 0 ? "…" : "") + haystack.slice(start, end).trim() + (end < haystack.length ? "…" : "");
  }

  function query(term) {
    var needle = normalise(term);
    if (!needle) {
      return [];
    }
    var hits = [];
    index.forEach(function (entry) {
      var inTitle = entry.titleText.indexOf(needle) !== -1;
      var inConcept = entry.conceptText.indexOf(needle) !== -1;
      if (!inTitle && !inConcept) {
        return;
      }
      hits.push({
        id: entry.id,
        title: entry.title,
        part: entry.part,
        part_title: entry.part_title,
        order: entry.order,
        score: (inTitle ? 3 : 0) + (inConcept ? 1 : 0),
        snippet: snippetFor(entry, needle)
      });
    });
    hits.sort(function (a, b) {
      if (b.score !== a.score) {
        return b.score - a.score;
      }
      return a.order - b.order;
    });
    return hits;
  }

  function isTypingTarget(node) {
    if (!node || !node.tagName) {
      return false;
    }
    var tag = node.tagName.toLowerCase();
    return tag === "input" || tag === "textarea" || tag === "select" || node.isContentEditable === true;
  }

  /* "/" focuses search — but only when the keystroke is not going into a field
   * and no modifier is held, or it would steal the slash from someone typing in
   * the search box itself. */
  function bindShortcut() {
    document.addEventListener("keydown", function (event) {
      if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) {
        return;
      }
      if (isTypingTarget(event.target)) {
        return;
      }
      var input = document.getElementById("search-input");
      if (!input) {
        return;
      }
      event.preventDefault();
      input.focus();
      input.select();
    });
  }

  window.Search = {
    buildIndex: buildIndex,
    query: query,
    bindShortcut: bindShortcut
  };
})();
