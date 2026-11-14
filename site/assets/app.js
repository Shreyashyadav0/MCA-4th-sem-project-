/* app.js — routing, rendering, markdown.
 *
 * This module owns the page chrome: the parts list, the lesson skeleton and the
 * markdown renderer. pyodide-loader.js builds the example figures it is handed
 * and search.js binds the "/" shortcut, so "only app.js touches the DOM" would
 * be false; what is true is that app.js is the only module that renders lesson
 * *content*.
 *
 * Two entry points, both called from the inline bootstrap at the end of the
 * page, never at parse time:
 *   App.initIndex()   the index page
 *   App.initLesson()  the lesson page
 *
 * The markdown renderer implements exactly CONTRACTS.MARKDOWN_SUBSET and
 * nothing more. Every text node is escaped before any transformation, the only
 * tags emitted are ones this file writes itself, and every URL that reaches an
 * attribute goes through safeHref — so a lesson file cannot inject markup or a
 * script URL, by accident or on purpose.
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

  /* The text handed to this function is already escaped, so the value returned
   * is escaped exactly once. Anything that is not plainly a URL of an allowed
   * shape returns "" and the caller drops the attribute. */
  function safeHref(href) {
    var raw = String(href || "").trim();
    if (!raw) {
      return "";
    }
    if (/^https?:\/\/[^/\s]/i.test(raw) || /^mailto:[^\s]+$/i.test(raw)) {
      return raw;
    }
    if (raw.charAt(0) === "#") {
      return raw;
    }
    if (raw.slice(0, 2) === "//") {
      /* protocol-relative: resolves off-site, so never a lesson link */
      return "";
    }
    /* A relative path: ./x, ../x, x/y.html, x.js — no scheme, no "//" prefix,
     * which would be protocol-relative and therefore off-site. */
    if (/^\.{0,2}\/[A-Za-z0-9._~%\-/]+$/.test(raw) || /^[A-Za-z0-9._~%\-]+\/[A-Za-z0-9._~%\-/]*$/.test(raw) || /^[A-Za-z0-9._~%\-]+\.html?$/.test(raw)) {
      return raw;
    }
    return "";
  }

  /* -------------------------------------------------------------- inline md */

  /* Find the closing marker for an emphasis span, skipping markers that belong
   * to a longer run. Returns -1 when the span is never closed, in which case the
   * marker is shown as the literal character it is. */
  function findClose(text, from, marker) {
    var j = from;
    while (j < text.length) {
      if (text.charAt(j) === "*") {
        if (marker === "**") {
          if (text.charAt(j + 1) === "*") {
            return j;
          }
          j += 1;
        } else if (text.charAt(j + 1) === "*") {
          j += 2;
        } else {
          return j;
        }
      } else {
        j += 1;
      }
    }
    return -1;
  }

  /* One scanner for inline syntax, recursive so emphasis can nest. The order of
   * the branches is the order of precedence: code, then ***x***, then bold, then
   * italic, then links. Deeper or crossed nesting (**a *b*** written that way
   * round) is outside the subset and stays literal. */
  function renderInline(escapedText) {
    var text = String(escapedText);
    var out = "";
    var i = 0;

    while (i < text.length) {
      var ch = text.charAt(i);

      if (ch === "`") {
        var codeEnd = text.indexOf("`", i + 1);
        if (codeEnd !== -1) {
          out += "<code>" + text.slice(i + 1, codeEnd) + "</code>";
          i = codeEnd + 1;
          continue;
        }
      } else if (ch === "*" && text.charAt(i + 1) === "*" && text.charAt(i + 2) === "*") {
        var tripleEnd = text.indexOf("***", i + 3);
        if (tripleEnd !== -1) {
          out += "<strong><em>" + renderInline(text.slice(i + 3, tripleEnd)) + "</em></strong>";
          i = tripleEnd + 3;
          continue;
        }
      } else if (ch === "*" && text.charAt(i + 1) === "*") {
        var boldEnd = findClose(text, i + 2, "**");
        if (boldEnd !== -1) {
          /* "**bold *it***": a run of three stars closes the italic first and the
           * bold last, so the pair to use is the final two and the inner text
           * keeps the star that closes the italic. */
          var run = 0;
          while (text.charAt(boldEnd + run) === "*") {
            run += 1;
          }
          var close = run > 2 ? boldEnd + 1 : boldEnd;
          out += "<strong>" + renderInline(text.slice(i + 2, close)) + "</strong>";
          i = close + 2;
          continue;
        }
      } else if (ch === "*") {
        var emEnd = findClose(text, i + 1, "*");
        if (emEnd > i + 1) {
          out += "<em>" + renderInline(text.slice(i + 1, emEnd)) + "</em>";
          i = emEnd + 1;
          continue;
        }
      } else if (ch === "[") {
        var link = /^\[([^\]]+)\]\(([^()\s]+)\)/.exec(text.slice(i));
        if (link) {
          var url = safeHref(link[2]);
          out += url ? '<a href="' + url + '">' + link[1] + "</a>" : link[1];
          i += link[0].length;
          continue;
        }
      }

      out += ch;
      i += 1;
    }

    return out;
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

  /* Split a table row on unescaped pipes, so a cell can contain "\|". */
  function splitRow(line) {
    var trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
    var cells = [];
    var current = "";
    for (var i = 0; i < trimmed.length; i += 1) {
      var char = trimmed.charAt(i);
      if (char === "\\" && trimmed.charAt(i + 1) === "|") {
        current += "|";
        i += 1;
      } else if (char === "|") {
        cells.push(current.trim());
        current = "";
      } else {
        current += char;
      }
    }
    cells.push(current.trim());
    return cells;
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
      /* Rows are normalised to the header width: extra cells are dropped rather
       * than silently shifting the columns. */
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
        var first = parseInt(line, 10) || 1;
        while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
          ordered.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
          i += 1;
        }
        out.push(
          "<ol" +
            (first !== 1 ? ' start="' + first + '"' : "") +
            ">" +
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
    return (Number(a.order) || 0) - (Number(b.order) || 0);
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
      /* No id: the frozen DOM contract names the ids a page may carry, and a
       * per-part anchor is not one of them. The attribute is enough. */
      section.setAttribute("data-part", String(part.n));

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
          if (lesson.duration_min) {
            meta.appendChild(el("span", "lesson-duration", lesson.duration_min + " min"));
          }
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
      meta.appendChild(
        el("span", "meta-part", "Part " + lesson.part + " · " + (lesson.part_title || "Untitled part"))
      );
      if (lesson.duration_min) {
        meta.appendChild(el("span", "meta-duration", lesson.duration_min + " min"));
      }
    }

    var nav = document.getElementById("lesson-nav");
    if (nav) {
      nav.innerHTML = "";
      var home = el("a", null, "All lessons");
      home.href = "index.html";
      nav.appendChild(home);
      nav.appendChild(el("span", "crumb-sep", " / "));
      var part = partByNumber(lesson.part);
      var partLabel = el(
        "span",
        "crumb-part",
        "Part " + lesson.part + " — " + (part ? part.title : lesson.part_title || "")
      );
      nav.appendChild(partLabel);
      nav.appendChild(el("span", "crumb-sep", " / "));
      var current = el("span", "crumb-current", lesson.id);
      current.setAttribute("aria-current", "page");
      nav.appendChild(current);
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
      return el("li", null, text);
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
        item.appendChild(el("code", "link-path", link.path));
        if (link.lines) {
          item.appendChild(el("span", "link-lines", " lines " + link.lines));
        }
        item.appendChild(el("span", "link-label", " — " + link.label));
        links.appendChild(item);
      });
      (lesson.learn_more || []).forEach(function (link) {
        var href = safeHref(link.href);
        var item = el("li", "link-item");
        if (href) {
          var anchor = el("a", null, link.label);
          anchor.href = href;
          anchor.rel = "noopener noreferrer";
          item.appendChild(anchor);
        } else {
          /* A URL outside the allowed shapes is shown as text, never as a link. */
          item.appendChild(el("span", null, link.label));
        }
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
    button.hidden = false;
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

  function disablePager(link, text) {
    link.removeAttribute("href");
    link.textContent = text;
    link.setAttribute("aria-disabled", "true");
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
        disablePager(prevLink, "← Start of the path");
      }
    }

    var nextLink = document.getElementById("next-link");
    if (nextLink) {
      if (next) {
        nextLink.href = lessonHref(next.id);
        nextLink.textContent = next.id + " " + next.title + " →";
        nextLink.removeAttribute("aria-disabled");
      } else {
        disablePager(nextLink, "End of the written path →");
      }
    }
  }

  function decode(value) {
    try {
      return decodeURIComponent(String(value || "").replace(/\+/g, " "));
    } catch (err) {
      /* A malformed escape is not a lesson id; treat it as no id at all. */
      return "";
    }
  }

  function requestedLessonId() {
    var search = String(window.location.search || "").replace(/^\?/, "");
    var params = search ? search.split("&") : [];
    for (var i = 0; i < params.length; i += 1) {
      var pair = params[i].split("=");
      if (decode(pair[0]) === "id") {
        return decode(pair.slice(1).join("="));
      }
    }
    /* The hash is only read when it looks like an id, so the page's own
     * in-page links (#lesson-concept, #lesson-title) cannot be mistaken for one. */
    var hash = String(window.location.hash || "").replace(/^#/, "");
    return /^\d+\.\d+$/.test(hash) ? decode(hash) : "";
  }

  function renderMissing(id) {
    document.title = "Lesson not found — AI Code Reviewer, learned from the code";

    var title = document.getElementById("lesson-title");
    if (title) {
      title.textContent = id ? "No lesson with id " + id : "No lesson selected";
    }
    var meta = document.getElementById("lesson-meta");
    if (meta) {
      meta.innerHTML = "";
    }
    var concept = document.getElementById("lesson-concept");
    if (concept) {
      concept.innerHTML = renderMarkdown(
        "That lesson is not in this build of the site. Lesson files are added wave by wave; " +
          "the parts list shows what exists so far.\n\n" +
          "[Back to all lessons](index.html)"
      );
    }
    showSection("lesson-concept", true);
    ["lesson-examples", "lesson-tryit", "lesson-exercise", "lesson-mistakes", "lesson-links", "lesson-glossary"].forEach(
      function (key) {
        showSection(key, false);
      }
    );
    var done = document.getElementById("mark-done");
    if (done) {
      done.hidden = true;
    }
    var prevLink = document.getElementById("prev-link");
    if (prevLink) {
      disablePager(prevLink, "← Start of the path");
    }
    var nextLink = document.getElementById("next-link");
    if (nextLink) {
      disablePager(nextLink, "End of the written path →");
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
