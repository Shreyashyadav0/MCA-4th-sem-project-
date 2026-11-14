/* sidebar.js — the permanent lesson tree.
 *
 * One function, called from both pages, so the markup exists once. It reads
 * window.LESSONS and window.Progress and writes nothing else: no lesson content,
 * no storage of its own, no second source of truth for the curriculum.
 *
 * Desktop: a fixed 260px column with its own scroll. Under 900px it becomes a
 * drawer opened by the header button, closed by Escape, the close button, or a
 * click on the scrim, with focus trapped inside while it is open.
 *
 * Parts with no lessons yet are dimmed but readable — this is a reference site,
 * and hiding a planned part teaches the reader nothing.
 */
(function () {
  "use strict";

  var C = window.CONTRACTS;
  var bound = false;      /* drawer listeners are bound once, never per render */
  var collapsed = {};     /* part numbers the reader has closed, remembered */
  var root = null;        /* the nav this module rendered into */

  function lessonsOf(part) {
    var list = Array.isArray(window.LESSONS) ? window.LESSONS : [];
    return list
      .filter(function (lesson) {
        return Number(lesson.part) === Number(part.n);
      })
      .sort(function (a, b) {
        return (Number(a.order) || 0) - (Number(b.order) || 0);
      });
  }

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

  function counts(part) {
    var lessons = lessonsOf(part);
    var done = 0;
    lessons.forEach(function (lesson) {
      if (window.Progress.isDone(lesson.id)) {
        done += 1;
      }
    });
    return { done: done, total: lessons.length, planned: part.lessons };
  }

  /* ---------------------------------------------------------------- drawer */

  function isNarrow() {
    return window.matchMedia && window.matchMedia("(max-width: 900px)").matches;
  }

  function setDrawer(rootNode, open) {
    var toggle = document.getElementById("sidebar-toggle");
    if (!rootNode) {
      return;
    }
    document.body.classList.toggle("sidebar-open", open);
    if (toggle) {
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    }
    var narrow = isNarrow();
    /* A drawer that is off-screen must not be reachable by Tab or by a screen
     * reader, and `inert` is what actually enforces that. */
    rootNode.setAttribute("aria-hidden", narrow && !open ? "true" : "false");
    if ("inert" in rootNode) {
      rootNode.inert = narrow && !open;
    }
    var page = document.querySelector(".page");
    if (page && "inert" in page) {
      page.inert = narrow && open;
    }
    if (open) {
      var first = rootNode.querySelector("a, button");
      if (first) {
        first.focus();
      }
    } else if (toggle) {
      toggle.focus();
    }
  }

  function bindDrawer(rootNode) {
    var toggle = document.getElementById("sidebar-toggle");
    var scrim = document.querySelector(".sidebar-scrim");
    if (!toggle || bound) {
      return;
    }
    bound = true;

    toggle.addEventListener("click", function () {
      setDrawer(root, !document.body.classList.contains("sidebar-open"));
    });

    /* The close button is re-created on every render, so it is delegated from the
     * container instead of bound per instance. */
    rootNode.addEventListener("click", function (event) {
      if (event.target && event.target.className === "sidebar-close") {
        setDrawer(root, false);
      }
    });
    if (scrim) {
      scrim.addEventListener("click", function () {
        setDrawer(root, false);
      });
    }

    document.addEventListener("keydown", function (event) {
      var open = document.body.classList.contains("sidebar-open");
      if (event.key === "Escape" && open) {
        event.preventDefault();
        setDrawer(root, false);
        return;
      }
      /* Focus trap: while the drawer is open, Tab stays inside it. */
      if (event.key === "Tab" && open && isNarrow()) {
        var focusable = root.querySelectorAll("a[href], button:not([disabled])");
        if (!focusable.length) {
          return;
        }
        var first = focusable[0];
        var last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    });

    setDrawer(root, false);
    /* Recompute on every resize: the wide->narrow direction used to leave the
     * off-screen drawer exposed to the accessibility tree. */
    window.addEventListener("resize", function () {
      setDrawer(root, isNarrow() && document.body.classList.contains("sidebar-open"));
    });
  }

  /* ---------------------------------------------------------------- render */

  function render(container, currentId) {
    if (!container) {
      return;
    }
    container.innerHTML = "";
    container.className = "sidebar";
    container.setAttribute("aria-label", "All lessons");

    var head = el("div", "sidebar-head");
    head.appendChild(el("p", "sidebar-title", "All lessons"));
    var close = el("button", "sidebar-close", "✕");
    close.type = "button";
    close.setAttribute("aria-label", "Close the lesson list");
    head.appendChild(close);
    container.appendChild(head);

    var scroller = el("div", "sidebar-scroll");
    var current = String(currentId || "");
    var currentPart = null;

    C.PARTS.forEach(function (part) {
      var lessons = lessonsOf(part);
      var tally = counts(part);
      var isCurrent = lessons.some(function (lesson) {
        return String(lesson.id) === current;
      });
      if (isCurrent) {
        currentPart = part.n;
      }

      var group = el("section", "side-part" + (lessons.length ? "" : " is-pending"));
      group.setAttribute("data-part", String(part.n));

      var toggle = el("button", "side-toggle");
      toggle.type = "button";
      var openByDefault = lessons.length > 0 && collapsed[part.n] !== true;
      toggle.setAttribute("aria-expanded", openByDefault ? "true" : "false");
      toggle.appendChild(el("span", "side-part-label", "Part " + part.n + " · " + part.title));
      /* Both numbers are real: done/written, with the planned total named
       * separately so a part that is half written cannot look half done. */
      var countLabel = lessons.length
        ? tally.done + "/" + tally.total
        : "0/" + part.lessons + " planned";
      toggle.appendChild(el("span", "side-part-count", countLabel));
      group.appendChild(toggle);

      var body = el("div", "side-body");
      body.hidden = !openByDefault;

      if (lessons.length) {
        var list = el("ul", "side-lessons");
        lessons.forEach(function (lesson) {
          var item = el("li");
          var link = el("a", "side-lesson", lesson.title);
          link.href = "lesson.html?id=" + encodeURIComponent(lesson.id);
          if (String(lesson.id) === current) {
            link.className += " is-current";
            link.setAttribute("aria-current", "page");
          }
          if (window.Progress.isDone(lesson.id)) {
            link.appendChild(el("span", "side-tick", "✓"));
            link.setAttribute("title", lesson.title + " — done");
          }
          item.appendChild(link);
          list.appendChild(item);
        });
        body.appendChild(list);
      } else {
        body.appendChild(el("p", "side-empty", "Not written yet — " + part.lessons + " lessons planned."));
      }
      group.appendChild(body);

      toggle.setAttribute("aria-controls", "side-body-" + part.n);
      body.id = "side-body-" + part.n;

      toggle.addEventListener("click", function () {
        var open = toggle.getAttribute("aria-expanded") === "true";
        toggle.setAttribute("aria-expanded", open ? "false" : "true");
        body.hidden = open;
        collapsed[part.n] = open;
      });

      scroller.appendChild(group);
    });

    container.appendChild(scroller);

    /* The current part opens itself once; after that the reader's collapse wins. */
    if (currentPart !== null && collapsed[currentPart] !== true) {
      var active = container.querySelector('.side-part[data-part="' + currentPart + '"]');
      if (active) {
        var activeToggle = active.querySelector(".side-toggle");
        var activeBody = active.querySelector(".side-body");
        if (activeToggle) {
          activeToggle.setAttribute("aria-expanded", "true");
        }
        if (activeBody) {
          activeBody.hidden = false;
        }
      }
    }

    root = container;
    bindDrawer(container);
    if (bound) {
      setDrawer(container, document.body.classList.contains("sidebar-open"));
    }
  }

  window.Sidebar = {
    render: render
  };
})();
