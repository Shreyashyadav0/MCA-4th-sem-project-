/* app.js — routing, rendering, markdown.
 *
 * The only module allowed to touch the DOM. Two entry points, both called from
 * the inline bootstrap at the end of the page, never at parse time:
 *   App.initIndex()   the index page
 *   App.initLesson()  the lesson page
 *
 * The markdown renderer implements exactly CONTRACTS.MARKDOWN_SUBSET and
 * nothing more. Every text node is escaped before any transformation, and the
 * only tags emitted are ones this file writes itself, so a lesson file cannot
 * inject markup by accident or on purpose.
 */
(function () {
  "use strict";

  var C = window.CONTRACTS;
  var SLOT = "\u0000";

  /* ------------------------------------------------------------------ text */

  function escapeHtml(value) {
    return String(value === null || value === undefined ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function safeHref(href) {
    var raw = String(href || "").trim();
    if (/^(https?:\/\/|mailto:|#|\.{0,2}\/)/i.test(raw)) {
      return escapeHtml(raw);
    }
    return "";
  }

  /* -------------------------------------------------------------- inline md */

  function renderInline(escapedText) {
    var slots = [];
    var text = String(escapedText);

    text = text.replace(/`([^`]+)`/g, function (match, code) {
      slots.push("<code>" + code + "</code>");
      return SLOT + (slots.length - 1) + SLOT;
    });

    text = text.replace(/\[([^\]]+)\]\(([^()\s]+)\)/g, function (match, label, href) {
      var url = safeHref(href);
      if (!url) {
        return label;
      }
      return '<a href="' + url + '">' + label + "</a>";
    });

    text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    text = text.replace(/(^|[^*])\*([^*\s][^*]*?)\*(?!\*)/g, "$1<em>$2</em>");

    text = text.replace(new RegExp(SLOT + "(\\d+)" + SLOT, "g"), function (match, index) {
      return slots[Number(index)];
    });
    return text;
  }

  function isBlank(line) {
    return /^\s*$/.test(line);
  }

  function isBlockStart(line) {
    return (
      /^```/.test(line) ||
      /^#{3,4}\s+/.test(line) ||
      /^>\s?/.test(line) ||
      /^\s*[-*+]\s+/.test(line) ||
      /^\s*\d+\.\s+/.test(line)
    );
  }

  function splitRow(line) {
    var trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
    return trimmed.split("|").map(function (cell) {
      return cell.trim();
    });
  }

  function renderTable(headerLine, alignLine, bodyLines) {
    var headers = splitRow(headerLine);
    var aligns = splitRow(alignLine).map(function (cell) {
      if (/^:-+:$/.test(cell)) {
        return "center";
      }
      if (/^:-+$/.test(cell)) {
        return "left";
      }
      if (/^-+:$/.test(cell)) {
        return "right";
      }
      return "";
    });
    var html = ['<div class="table-wrap"><table>', "<thead><tr>"];
    headers.forEach(function (cell, index) {
      var align = aligns[index] ? ' class="align-' + aligns[index] + '"' : "";
      html.push("<th" + align + ">" + renderInline(escapeHtml(cell)) + "</th>");
    });
    html.push("</tr></thead><tbody>");
    bodyLines.forEach(function (row) {
      var cells = splitRow(row);
      html.push("<tr>");
      headers.forEach(function (ignored, index) {
        var align = aligns[index] ? ' class="align-' + aligns[index] + '"' : "";
        html.push("<td" + align + ">" + renderInline(escapeHtml(cells[index] || "")) + "</td>");
      });
      html.push("</tr>");
    });
    html.push("</tbody></table></div>");
    return html.join("");
  }

  function renderMarkdown(markdown) {
    var lines = String(markdown === null || markdown === undefined ? "" : markdown)
      .replace(/\r\n?/g, "\n")
      .split("\n");
    var out = [];
    var i = 0;

    while (i < lines.length) {
      var line = lines[i];

      if (isBlank(line)) {
        i += 1;
        continue;
      }

      var fence = line.match(/^```([A-Za-z0-9_+#.-]*)\s*$/);
      if (fence) {
        var lang = fence[1];
        var buffer = [];
        i += 1;
        while (i < lines.length && !/^```\s*$/.test(lines[i])) {
          buffer.push(lines[i]);
          i += 1;
        }
        i += 1;
        out.push(
          '<pre class="code"' +
            (lang ? ' data-lang="' + escapeHtml(lang) + '"' : "") +
            "><code>" +
            escapeHtml(buffer.join("\n")) +
            "</code></pre>"
        );
        continue;
      }

      var heading = line.match(/^(#{3,4})\s+(.*)$/);
      if (heading) {
        var level = heading[1].length;
        out.push(
          "<h" + level + ">" + renderInline(escapeHtml(heading[2].trim())) + "</h" + level + ">"
        );
        i += 1;
        continue;
      }

      if (
        line.indexOf("|") !== -1 &&
        i + 1 < lines.length &&
        /^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$/.test(lines[i + 1])
      ) {
        var body = [];
        var headerLine = line;
        var alignLine = lines[i + 1];
        i += 2;
        while (i < lines.length && lines[i].indexOf("|") !== -1 && !isBlank(lines[i])) {
          body.push(lines[i]);
          i += 1;
        }
        out.push(renderTable(headerLine, alignLine, body));
        continue;
      }

      if (/^>\s?/.test(line)) {
        var quoted = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) {
          quoted.push(lines[i].replace(/^>\s?/, ""));
          i += 1;
        }
        out.push("<blockquote>" + renderInline(escapeHtml(quoted.join(" "))) + "</blockquote>");
        continue;
      }

      if (/^\s*[-*+]\s+/.test(line)) {
        var items = [];
        while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) {
          items.push(lines[i].replace(/^\s*[-*+]\s+/, ""));
          i += 1;
        }
        out.push(
          "<ul>" +
            items
              .map(function (item) {
                return "<li>" + renderInline(escapeHtml(item)) + "</li>";
              })
              .join("") +
            "</ul>"
        );
        continue;
      }

      if (/^\s*\d+\.\s+/.test(line)) {
        var ordered = [];
        while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
          ordered.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
          i += 1;
        }
        out.push(
          "<ol>" +
            ordered
              .map(function (item) {
                return "<li>" + renderInline(escapeHtml(item)) + "</li>";
              })
              .join("") +
            "</ol>"
        );
        continue;
      }

      var paragraph = [];
      while (i < lines.length && !isBlank(lines[i]) && (paragraph.length === 0 || !isBlockStart(lines[i]))) {
        paragraph.push(lines[i].trim());
        i += 1;
      }
      out.push("<p>" + renderInline(escapeHtml(paragraph.join(" "))) + "</p>");
    }

    return out.join("\n");
  }

  /* --------------------------------------------------------------- lessons */

  function allLessons() {
    return Array.isArray(window.LESSONS) ? window.LESSONS.slice() : [];
  }

  function byOrder(a, b) {
    return a.order - b.order;
  }

  function getLessonById(id) {
    var key = String(id);
    var list = allLessons();
    for (var i = 0; i < list.length; i += 1) {
      if (String(list[i].id) === key) {
        return list[i];
      }
    }
    return null;
  }

  function getLessonsByPart(partN) {
    return allLessons()
      .filter(function (lesson) {
        return Number(lesson.part) === Number(partN);
      })
      .sort(byOrder);
  }

  function partByNumber(partN) {
    for (var i = 0; i < C.PARTS.length; i += 1) {
      if (Number(C.PARTS[i].n) === Number(partN)) {
        return C.PARTS[i];
      }
    }
    return null;
  }

  function lessonHref(id) {
    return "lesson.html?id=" + encodeURIComponent(id);
  }

  /* ----------------------------------------------------------------- theme */

  function storedTheme() {
    try {
      var value = window.localStorage.getItem(C.THEME_KEY);
      return value === "dark" || value === "light" ? value : "light";
    } catch (err) {
      return "light";
    }
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      window.localStorage.setItem(C.THEME_KEY, theme);
    } catch (err) {
      /* storage refused: the page still renders, it just will not remember */
    }
  }

  function applyStoredTheme() {
    document.documentElement.setAttribute("data-theme", storedTheme());
  }

  /* ------------------------------------------------------------ index page */

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined && text !== null) {
      node.textContent = String(text);
    }
    return node;
  }

  function renderParts(container) {
    container.innerHTML = "";
    var written = 0;

    C.PARTS.forEach(function (part) {
      var lessons = getLessonsByPart(part.n);
      var counts = window.Progress.partCounts(part.n);

      var section = el("section", lessons.length ? "part" : "part part-pending");
      section.id = "part-" + part.n;

      var head = el("div", "part-head");
      var title = el("h2", "part-title");
      var number = el("span", "part-number", "Part " + part.n);
      title.appendChild(number);
      title.appendChild(document.createTextNode(" " + part.title));
      head.appendChild(title);

      var badge = el(
        "span",
        "part-badge",
        lessons.length ? counts.done + "/" + counts.total + " done" : "0/" + part.lessons + " planned"
      );
      head.appendChild(badge);
      section.appendChild(head);

      if (lessons.length) {
        written += 1;
        var list = el("ul", "lesson-list");
        lessons.forEach(function (lesson) {
          var item = el("li", "lesson-item");
          var link = el("a", "lesson-link", lesson.title);
          link.href = lessonHref(lesson.id);
          item.appendChild(link);

          var meta = el("span", "lesson-meta");
          meta.appendChild(el("span", "lesson-id", lesson.id));
          meta.appendChild(el("span", "lesson-duration", lesson.duration_min + " min"));
          if (window.Progress.isDone(lesson.id)) {
            var flag = el("span", "lesson-done", "done");
            flag.setAttribute("title", "You marked this lesson done");
            meta.appendChild(flag);
          }
          item.appendChild(meta);
          list.appendChild(item);
        });
        section.appendChild(list);
      } else {
        section.appendChild(
          el("p", "part-note", "Not written yet — " + part.lessons + " lessons planned for a later wave.")
        );
      }

      container.appendChild(section);
    });

    var note = el("p", "parts-note", written + " of " + C.PARTS.length + " parts have lessons so far.");
    container.appendChild(note);
  }

  function updateTotal() {
    var target = document.getElementById("progress-total");
    if (!target) {
      return;
    }
    var list = allLessons();
    var done = 0;
    list.forEach(function (lesson) {
      if (window.Progress.isDone(lesson.id)) {
        done += 1;
      }
    });
    target.textContent = done + " of " + list.length + " lessons done";
  }

  function renderSearchResults(container, term) {
    container.innerHTML = "";
    var query = String(term || "").trim();

    if (!query) {
      container.appendChild(el("p", "search-hint", "Type to search lesson titles and concepts. Press / from anywhere to jump here."));
      return;
    }

    var hits = window.Search.query(query);
    if (!hits.length) {
      var empty = el("div", "search-empty");
      empty.appendChild(el("p", "search-empty-title", 'No lessons match "' + query + '".'));
      empty.appendChild(
        el(
          "p",
          "search-empty-hint",
          "Try a shorter word, or browse the parts below. Search covers lesson titles and concept text only."
        )
      );
      container.appendChild(empty);
      return;
    }

    container.appendChild(el("p", "search-count", hits.length + (hits.length === 1 ? " lesson matches" : " lessons match")));
    var list = el("ul", "search-list");
    hits.forEach(function (hit) {
      var item = el("li", "search-item");
      var link = el("a", "search-link", hit.title);
      link.href = lessonHref(hit.id);
      item.appendChild(link);
      item.appendChild(el("span", "search-part", "Part " + hit.part + " · " + hit.part_title));
      if (hit.snippet) {
        item.appendChild(el("p", "search-snippet", hit.snippet));
      }
      list.appendChild(item);
    });
    container.appendChild(list);
  }

  function bindThemeToggle() {
    var button = document.getElementById("theme-toggle");
    if (!button) {
      return;
    }
    var sync = function () {
      var current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
      button.textContent = current === "dark" ? "Light mode" : "Dark mode";
      button.setAttribute("aria-pressed", current === "dark" ? "true" : "false");
      button.setAttribute(
        "aria-label",
        current === "dark" ? "Switch to light theme" : "Switch to dark theme"
      );
    };
    button.addEventListener("click", function () {
      var current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
      applyTheme(current === "dark" ? "light" : "dark");
      sync();
    });
    sync();
  }

  function initIndex() {
    applyStoredTheme();

    var partsList = document.getElementById("parts-list");
    if (partsList) {
      renderParts(partsList);
    }
    updateTotal();
    bindThemeToggle();

    var input = document.getElementById("search-input");
    var results = document.getElementById("search-results");
    if (input && results) {
      window.Search.buildIndex(allLessons());
      window.Search.bindShortcut();
      renderSearchResults(results, "");
      input.addEventListener("input", function () {
        renderSearchResults(results, input.value);
      });
      input.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
          input.value = "";
          renderSearchResults(results, "");
        }
      });
    }
  }

  /* ----------------------------------------------------------- lesson page */

  function sectionFor(id) {
    var node = document.getElementById(id);
    if (!node) {
      return null;
    }
    var section = node;
    while (section && section.tagName !== "SECTION") {
      section = section.parentElement;
    }
    return section;
  }

  function showSection(id, visible) {
    var section = sectionFor(id);
    if (section) {
      section.hidden = !visible;
    }
  }

  function fillList(id, items, renderItem) {
    var node = document.getElementById(id);
    if (!node) {
      return false;
    }
    node.innerHTML = "";
    var list = Array.isArray(items) ? items : [];
    if (!list.length) {
      return false;
    }
    list.forEach(function (item) {
      node.appendChild(renderItem(item));
    });
    return true;
  }

  function codeFigure(caption, code, lang) {
    var figure = el("figure", "code-figure");
    if (caption) {
      figure.appendChild(el("figcaption", "code-caption", caption));
    }
    var pre = el("pre", "code");
    if (lang) {
      pre.setAttribute("data-lang", lang);
    }
    var codeEl = el("code", null, code);
    pre.appendChild(codeEl);
    figure.appendChild(pre);
    return figure;
  }

  function detailsBlock(summary, body) {
    var wrap = el("details", "solution");
    var head = el("summary", null, summary);
    wrap.appendChild(head);
    if (body && body.kind === "markdown") {
      var div = el("div", "solution-body");
      div.innerHTML = renderMarkdown(body.text);
      wrap.appendChild(div);
    } else if (body && body.kind === "code") {
      wrap.appendChild(codeFigure(null, body.text, body.lang || "python"));
    }
    return wrap;
  }

  function renderPractice(id, data, labels) {
    var node = document.getElementById(id);
    if (!node || !data) {
      return false;
    }
    node.innerHTML = "";
    var hasAny = false;

    if (data.prompt) {
      var prompt = el("div", "practice-prompt");
      prompt.innerHTML = renderMarkdown(data.prompt);
      node.appendChild(prompt);
      hasAny = true;
    }
    if (data.starter) {
      node.appendChild(codeFigure("Starter", data.starter, "python"));
      hasAny = true;
    }
    if (data.hint) {
      node.appendChild(detailsBlock(labels.hint, { kind: "markdown", text: data.hint }));
      hasAny = true;
    }
    if (data.solution) {
      /* A solution that carries its own fenced block is markdown — that is how a
       * lesson says "this answer is a console transcript, not Python". Anything
       * else is Python source, which is the common case. */
      var isMarkdown = String(data.solution).indexOf("```") !== -1;
      node.appendChild(
        detailsBlock(
          labels.solution,
          isMarkdown
            ? { kind: "markdown", text: data.solution }
            : { kind: "code", text: data.solution, lang: "python" }
        )
      );
      hasAny = true;
    }
    if (data.explanation) {
      var note = el("div", "practice-explanation");
      note.innerHTML = renderMarkdown(data.explanation);
      node.appendChild(note);
      hasAny = true;
    }
    return hasAny;
  }

  function renderLesson(lesson) {
    document.title = lesson.id + " " + lesson.title + " — AI Code Reviewer, learned from the code";

    var title = document.getElementById("lesson-title");
    if (title) {
      title.textContent = lesson.title;
    }

    var meta = document.getElementById("lesson-meta");
    if (meta) {
      meta.innerHTML = "";
      meta.appendChild(el("span", "meta-id", "Lesson " + lesson.id));
      meta.appendChild(el("span", "meta-part", "Part " + lesson.part + " · " + lesson.part_title));
      meta.appendChild(el("span", "meta-duration", lesson.duration_min + " min"));
    }

    var nav = document.getElementById("lesson-nav");
    if (nav) {
      nav.innerHTML = "";
      var home = el("a", null, "All lessons");
      home.href = "index.html";
      nav.appendChild(home);
      nav.appendChild(el("span", "crumb-sep", " / "));
      var part = partByNumber(lesson.part);
      var partLabel = el("span", "crumb-part", "Part " + lesson.part + " — " + (part ? part.title : lesson.part_title));
      nav.appendChild(partLabel);
      nav.appendChild(el("span", "crumb-sep", " / "));
      nav.appendChild(el("span", "crumb-current", lesson.id));
    }

    var concept = document.getElementById("lesson-concept");
    if (concept) {
      concept.innerHTML = renderMarkdown(lesson.concept_md || "");
    }
    showSection("lesson-concept", !!(lesson.concept_md && lesson.concept_md.trim()));

    var examples = document.getElementById("lesson-examples");
    var hasExamples = Array.isArray(lesson.code_examples) && lesson.code_examples.length > 0;
    if (examples && hasExamples) {
      examples.innerHTML = "";
      lesson.code_examples.forEach(function (example) {
        window.PyRun.attach(examples, example);
      });
    }
    showSection("lesson-examples", hasExamples);

    var hasTryIt = renderPractice("lesson-tryit", lesson.try_it, {
      hint: "Hint",
      solution: "Show solution"
    });
    showSection("lesson-tryit", hasTryIt);

    var hasExercise = renderPractice("lesson-exercise", lesson.exercise, {
      hint: "Hint",
      solution: "Show solution"
    });
    showSection("lesson-exercise", hasExercise);

    var hasMistakes = fillList("lesson-mistakes", lesson.common_mistakes, function (text) {
      var item = el("li", null, text);
      return item;
    });
    showSection("lesson-mistakes", hasMistakes);

    var hasLinks =
      (Array.isArray(lesson.project_links) && lesson.project_links.length > 0) ||
      (Array.isArray(lesson.learn_more) && lesson.learn_more.length > 0);
    var links = document.getElementById("lesson-links");
    if (links) {
      links.innerHTML = "";
      (lesson.project_links || []).forEach(function (link) {
        var item = el("li", "link-item");
        var code = el("code", "link-path", link.path);
        item.appendChild(code);
        if (link.lines) {
          item.appendChild(el("span", "link-lines", " lines " + link.lines));
        }
        item.appendChild(el("span", "link-label", " — " + link.label));
        links.appendChild(item);
      });
      (lesson.learn_more || []).forEach(function (link) {
        var item = el("li", "link-item");
        var anchor = el("a", null, link.label);
        anchor.href = link.href;
        anchor.rel = "noopener noreferrer";
        item.appendChild(anchor);
        links.appendChild(item);
      });
    }
    showSection("lesson-links", hasLinks);

    var hasGlossary = fillList("lesson-glossary", lesson.glossary_terms, function (term) {
      return el("li", null, term);
    });
    showSection("lesson-glossary", hasGlossary);

    bindMarkDone(lesson);
    bindPrevNext(lesson);
  }

  function bindMarkDone(lesson) {
    var button = document.getElementById("mark-done");
    if (!button) {
      return;
    }
    var sync = function () {
      var done = window.Progress.isDone(lesson.id);
      button.textContent = done ? "Done — click to undo" : "Mark done";
      button.setAttribute("aria-pressed", done ? "true" : "false");
      button.className = done ? "btn btn-done is-done" : "btn btn-done";
    };
    button.addEventListener("click", function () {
      window.Progress.toggle(lesson.id);
      sync();
    });
    sync();
  }

  function bindPrevNext(lesson) {
    var ordered = allLessons().sort(byOrder);
    var index = -1;
    for (var i = 0; i < ordered.length; i += 1) {
      if (String(ordered[i].id) === String(lesson.id)) {
        index = i;
      }
    }
    var prev = index > 0 ? ordered[index - 1] : null;
    var next = index >= 0 && index < ordered.length - 1 ? ordered[index + 1] : null;

    var prevLink = document.getElementById("prev-link");
    if (prevLink) {
      if (prev) {
        prevLink.href = lessonHref(prev.id);
        prevLink.textContent = "← " + prev.id + " " + prev.title;
        prevLink.removeAttribute("aria-disabled");
      } else {
        prevLink.removeAttribute("href");
        prevLink.textContent = "← Start of the path";
        prevLink.setAttribute("aria-disabled", "true");
      }
    }

    var nextLink = document.getElementById("next-link");
    if (nextLink) {
      if (next) {
        nextLink.href = lessonHref(next.id);
        nextLink.textContent = next.id + " " + next.title + " →";
        nextLink.removeAttribute("aria-disabled");
      } else {
        nextLink.removeAttribute("href");
        nextLink.textContent = "End of the written path →";
        nextLink.setAttribute("aria-disabled", "true");
      }
    }
  }

  function requestedLessonId() {
    var search = String(window.location.search || "").replace(/^\?/, "");
    var params = search ? search.split("&") : [];
    for (var i = 0; i < params.length; i += 1) {
      var pair = params[i].split("=");
      if (decodeURIComponent(pair[0]) === "id") {
        return decodeURIComponent((pair[1] || "").replace(/\+/g, " "));
      }
    }
    var hash = String(window.location.hash || "").replace(/^#/, "");
    return hash ? decodeURIComponent(hash) : "";
  }

  function renderMissing(id) {
    var title = document.getElementById("lesson-title");
    if (title) {
      title.textContent = id ? "No lesson with id " + id : "No lesson selected";
    }
    var concept = document.getElementById("lesson-concept");
    if (concept) {
      concept.innerHTML = renderMarkdown(
        "That lesson is not in this build of the site. Lesson files are added wave by wave; " +
          "the parts list shows what exists so far.\n\n" +
          "[Back to all lessons](index.html)"
      );
    }
    ["lesson-examples", "lesson-tryit", "lesson-exercise", "lesson-mistakes", "lesson-links", "lesson-glossary"].forEach(
      function (key) {
        showSection(key, false);
      }
    );
    var done = document.getElementById("mark-done");
    if (done) {
      done.hidden = true;
    }
  }

  function initLesson() {
    applyStoredTheme();
    var id = requestedLessonId();
    var lesson = id ? getLessonById(id) : allLessons().sort(byOrder)[0] || null;
    if (!lesson) {
      renderMissing(id);
      return;
    }
    renderLesson(lesson);
  }

  window.App = {
    initIndex: initIndex,
    initLesson: initLesson,
    renderMarkdown: renderMarkdown,
    escapeHtml: escapeHtml,
    getLessonById: getLessonById,
    getLessonsByPart: getLessonsByPart
  };
})();
