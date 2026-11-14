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
  var rendered = false;

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

  function bindDrawer(root) {
    var toggle = document.getElementById("sidebar-toggle");
    var scrim = document.querySelector(".sidebar-scrim");
    if (!toggle) {
      return;
    }

    var setOpen = function (open) {
      document.body.classList.toggle("sidebar-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      root.setAttribute("aria-hidden", isNarrow() && !open ? "true" : "false");
      if (open) {
        var first = root.querySelector("a, button");
        if (first) {
          first.focus();
        }
      } else {
        toggle.focus();
      }
    };

    toggle.addEventListener("click", function () {
      setOpen(!document.body.classList.contains("sidebar-open"));
    });

    var close = root.querySelector(".sidebar-close");
    if (close) {
      close.addEventListener("click", function () {
        setOpen(false);
      });
    }
    if (scrim) {
      scrim.addEventListener("click", function () {
        setOpen(false);
      });
    }

    document.addEventListener("keydown", function (event) {
      var open = document.body.classList.contains("sidebar-open");
      if (event.key === "Escape" && open) {
        event.preventDefault();
        setOpen(false);
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

    root.setAttribute("aria-hidden", isNarrow() ? "true" : "false");
    window.addEventListener("resize", function () {
      if (!isNarrow()) {
        document.body.classList.remove("sidebar-open");
        toggle.setAttribute("aria-expanded", "false");
        root.setAttribute("aria-hidden", "false");
      }
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
      var openByDefault = lessons.length > 0;
      toggle.setAttribute("aria-expanded", openByDefault ? "true" : "false");
      toggle.appendChild(el("span", "side-part-label", "Part " + part.n + " · " + part.title));
      toggle.appendChild(
        el("span", "side-part-count", lessons.length ? tally.done + "/" + tally.total : "0/" + part.lessons)
      );
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

      toggle.addEventListener("click", function () {
        var open = toggle.getAttribute("aria-expanded") === "true";
        toggle.setAttribute("aria-expanded", open ? "false" : "true");
        body.hidden = open;
      });

      scroller.appendChild(group);
    });

    container.appendChild(scroller);

    /* The current part is always expanded, whatever its default was. */
    if (currentPart !== null) {
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

    bindDrawer(container);
    rendered = true;
  }

  window.Sidebar = {
    render: render
  };
})();
