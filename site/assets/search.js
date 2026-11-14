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
  var shortcutBound = false;

  function normalise(value) {
    return String(value === null || value === undefined ? "" : value)
      .toLowerCase()
      .replace(/[`*_#>|[\]]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  /* Markdown to something readable in a one-line snippet: fences, inline code,
   * emphasis markers, links and list markers removed, so the snippet is prose a
   * human can scan. CRLF and ~~~ fences are handled as well as ``` ones. */
  function plainText(markdown) {
    return String(markdown || "")
      .replace(/^(`{3,}|~{3,})[^\n]*\n[\s\S]*?^\1[^\n]*$/gm, " ")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\[([^\]]+)\]\(([^()\s]+)\)/g, "$1")
      .replace(/^#{1,6}\s+/gm, "")
      .replace(/^>\s?/gm, "")
      .replace(/^\s*[-*+]\s+/gm, "")
      .replace(/\*\*|__/g, "")
      .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1$2")
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

  function window_(text, position, needleLength) {
    var start = Math.max(0, position - 60);
    var end = Math.min(text.length, position + needleLength + 80);
    return (start > 0 ? "…" : "") + text.slice(start, end).trim() + (end < text.length ? "…" : "");
  }

  /* The snippet is searched in the same string the match was found in, so the
   * word the reader typed is always visible in it. When the match is only in the
   * title, the title is the snippet rather than an unrelated first sentence. */
  function snippetFor(entry, needle, inTitle, inConcept) {
    if (inConcept) {
      var haystack = entry.concept;
      var position = haystack.toLowerCase().indexOf(needle);
      if (position !== -1) {
        return window_(haystack, position, needle.length);
      }
      var normalisedPosition = entry.conceptText.indexOf(needle);
      if (normalisedPosition !== -1) {
        return window_(entry.conceptText, normalisedPosition, needle.length);
      }
    }
    if (inTitle) {
      return "Title match: " + entry.title;
    }
    return entry.concept.slice(0, 140) + (entry.concept.length > 140 ? "…" : "");
  }

  function query(term) {
    var needle = normalise(term);
    if (!needle) {
      return [];
    }
    /* A term with no letters or digits — ".", "(", "*" — would match almost
     * everything after normalisation, so it is treated as no search at all. */
    if (!/[a-z0-9]/.test(needle)) {
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
        snippet: snippetFor(entry, needle, inTitle, inConcept)
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
   * the search box itself. Bound once; a second call is a no-op. */
  function bindShortcut() {
    if (shortcutBound) {
      return;
    }
    shortcutBound = true;
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
