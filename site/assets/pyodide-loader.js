/* pyodide-loader.js — the in-browser Python runner.
 *
 * Pyodide runs CPython in WebAssembly, so a lesson can execute real code instead
 * of asking the reader to copy it into a terminal. Nothing is downloaded until
 * the first Run press: a 10 MB runtime must never delay the page.
 *
 * The interesting part is the embedded source bundle. file:// forbids fetch(),
 * so a lesson cannot read app/models.py from disk; instead
 * site/content/repo-sources.js carries the repository's own files, and run()
 * writes the ones an example asks for into Pyodide's virtual filesystem before
 * executing. `from app.models import Finding` then works exactly as it does on a
 * real machine — same file, same bytes, no paraphrase.
 *
 * Three tiers, declared by each example as data-tier:
 *   browser      stdlib, or a package from the Pyodide distribution; runs now
 *   browser-pkg  the same, with a wheel the distribution ships separately
 *                (loaded through pyodide.loadPackage — never PyPI)
 *   terminal     cannot run here; the panel says so, with the command to run
 *
 * Failure is not an exception, and the kinds of failure are kept apart:
 *   load    the runtime never arrived (offline, blocked, slow) -> terminal panel
 *   setup   a lesson asked for a file or package that does not exist -> shown
 *   python  the snippet raised -> the traceback, which is a teaching moment
 * Only a load failure hides the Run button; the other two are fixable and keep
 * it available.
 *
 * WHAT THIS IS NOT. Lesson code is arbitrary Python running in the reader's
 * page. It can import `js` and reach the page (localStorage, the network). The
 * site is a folder the reader chose to open, and its lessons are trusted input;
 * the runner is a convenience, not a sandbox. A `while True:` in an example
 * freezes the tab — Pyodide cannot be interrupted from a file:// page, because a
 * Web Worker cannot be created from that origin and SharedArrayBuffer needs
 * headers the site cannot set.
 */
(function () {
  "use strict";

  var PYODIDE_VERSION = "0.28.0";
  var CDN_BASE = "https://cdn.jsdelivr.net/pyodide/v" + PYODIDE_VERSION + "/full/";
  /* Integrity of the one file we execute; the rest are data Pyodide loads. */
  var PYODIDE_JS_SRI =
    "sha384-aD6ek5pFVnSSMGK0qubk9ZJdMYGjPs8F6jdJaDJiyZbTcH9jLWR4LJNJ7yY430qI";
  var LOAD_TIMEOUT_MS = 120000;
  var FS_ROOT = "/home/pyodide";
  var MAX_OUTPUT = 64 * 1024;
  var PACKAGE_NAME = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;

  var runtime = null;
  var loading = null;
  var loadFailed = false;
  var pathReady = false;
  var loadedPackages = {};
  var queue = Promise.resolve(); /* one run at a time: stdout is shared */
  var wired = typeof WeakSet === "function" ? new WeakSet() : null;
  var sources = null; /* snapshot of REPO_SOURCES, taken once */

  function isAvailable() {
    if (runtime) {
      return true;
    }
    if (loadFailed) {
      return false;
    }
    return navigator.onLine !== false;
  }

  function embeddedSources() {
    if (!sources) {
      sources = Object.assign({}, window.REPO_SOURCES || {});
    }
    return sources;
  }

  function injectScript() {
    return new Promise(function (resolve, reject) {
      var script = document.createElement("script");
      var settled = false;
      var timer = window.setTimeout(function () {
        if (!settled) {
          settled = true;
          reject(new Error("the Python runtime did not arrive within " + LOAD_TIMEOUT_MS / 1000 + "s"));
        }
      }, LOAD_TIMEOUT_MS);

      script.src = CDN_BASE + "pyodide.js";
      script.async = true;
      script.integrity = PYODIDE_JS_SRI;
      script.crossOrigin = "anonymous";
      script.onload = function () {
        if (!settled) {
          settled = true;
          window.clearTimeout(timer);
          resolve();
        }
      };
      script.onerror = function () {
        if (!settled) {
          settled = true;
          window.clearTimeout(timer);
          reject(new Error("the Python runtime could not be downloaded"));
        }
      };
      document.head.appendChild(script);
    });
  }

  /* Idempotent. Concurrent callers share one download and one init. */
  function init() {
    if (runtime) {
      return Promise.resolve(runtime);
    }
    if (loading) {
      return loading;
    }
    loading = injectScript()
      .then(function () {
        if (typeof window.loadPyodide !== "function") {
          throw new Error("pyodide.js loaded but loadPyodide is missing");
        }
        return window.loadPyodide({ indexURL: CDN_BASE });
      })
      .then(function (pyodide) {
        runtime = pyodide;
        return pyodide;
      })
      .catch(function (error) {
        loadFailed = true;
        loading = null;
        throw error;
      });
    return loading;
  }

  function ensurePath(pyodide) {
    if (pathReady) {
      return;
    }
    pyodide.runPython(
      "import sys\n" +
        "if " + JSON.stringify(FS_ROOT) + " not in sys.path:\n" +
        "    sys.path.insert(0, " + JSON.stringify(FS_ROOT) + ")\n"
    );
    pathReady = true;
  }

  function ensurePackages(pyodide, packages) {
    var wanted = Array.isArray(packages) ? packages.filter(Boolean) : [];
    var missing = [];
    wanted.forEach(function (name) {
      if (!PACKAGE_NAME.test(name)) {
        throw new Error("'" + name + "' is not a package name — only names from the Pyodide distribution can be loaded");
      }
      if (!loadedPackages[name]) {
        missing.push(name);
      }
    });
    if (!missing.length) {
      return Promise.resolve();
    }
    return pyodide.loadPackage(missing).then(function () {
      missing.forEach(function (name) {
        loadedPackages[name] = true;
      });
    });
  }

  /* Write the repository files an example declares into the virtual filesystem,
   * at the same relative path they have in the repository. The path is checked:
   * a lesson may not reach outside FS_ROOT, and may only name a file that was
   * actually embedded. */
  function materialise(pyodide, files) {
    var wanted = Array.isArray(files) ? files : [];
    if (!wanted.length) {
      return;
    }
    var available = embeddedSources();
    wanted.forEach(function (relative) {
      var clean = String(relative).replace(/^\.\//, "");
      if (!clean || clean.charAt(0) === "/" || clean.indexOf("..") !== -1) {
        throw new Error("'" + relative + "' is not a path inside the repository");
      }
      if (!Object.prototype.hasOwnProperty.call(available, clean)) {
        throw new Error("no embedded source for " + clean + " — run site/tools/embed_sources.py");
      }
      var absolute = FS_ROOT + "/" + clean;
      var directory = absolute.slice(0, absolute.lastIndexOf("/"));
      pyodide.FS.mkdirTree(directory);
      pyodide.FS.writeFile(absolute, available[clean], { encoding: "utf8" });
    });
  }

  function capped(text) {
    if (text.length <= MAX_OUTPUT) {
      return text;
    }
    return text.slice(0, MAX_OUTPUT) + "\n… output truncated at " + MAX_OUTPUT / 1024 + " KB";
  }

  function execute(pyodide, code) {
    var stdout = [];
    var stderr = [];
    var decoder = new TextDecoder("utf-8");
    var size = 0;

    /* Raw writes, not batched lines: the bytes are what CPython produced, so a
     * newline is never lost or doubled by the transport. Output is capped so a
     * runaway loop cannot eat the tab's memory. */
    var capture = function (sink) {
      return function (buffer) {
        if (size < MAX_OUTPUT) {
          var text = decoder.decode(buffer, { stream: true });
          sink.push(text);
          size += text.length;
        }
        return buffer.length;
      };
    };

    pyodide.setStdout({ write: capture(stdout) });
    pyodide.setStderr({ write: capture(stderr) });

    var flush = function () {
      /* Anything written without a trailing newline is still buffered in Python
       * at this point; without the flush it surfaces inside the NEXT run. */
      try {
        pyodide.runPython("import sys\nsys.stdout.flush()\nsys.stderr.flush()\n");
      } catch (error) {
        /* a half-dead runtime must not mask the original result */
      }
      var tailOut = decoder.decode();
      if (tailOut) {
        stdout.push(tailOut);
      }
    };

    return pyodide.runPythonAsync(code).then(
      function () {
        flush();
        return {
          ok: true,
          stdout: capped(stdout.join("")),
          stderr: capped(stderr.join("")),
          error: "",
          error_kind: ""
        };
      },
      function (error) {
        flush();
        return {
          ok: false,
          stdout: capped(stdout.join("")),
          stderr: capped(stderr.join("")),
          error: String(error && error.message ? error.message : error),
          error_kind: "python"
        };
      }
    );
  }

  function failure(error, kind) {
    return {
      ok: false,
      stdout: "",
      stderr: "",
      error: String(error && error.message ? error.message : error),
      error_kind: kind
    };
  }

  /* run(code, {packages, files}) -> Promise<{ok, stdout, stderr, error, error_kind}>
   *
   * Runs are serialised: Pyodide has one interpreter and one stdout handler, so
   * two concurrent runs would interleave into whichever buffer was registered
   * last. Queueing is the only honest option without a worker. */
  function run(code, opts) {
    var options = opts || {};
    var job = queue
      .then(function () {
        return init().then(
          function (pyodide) {
            ensurePath(pyodide);
            materialise(pyodide, options.files);
            return ensurePackages(pyodide, options.packages).then(function () {
              return execute(pyodide, code);
            });
          },
          function (error) {
            return failure(error, "load");
          }
        );
      })
      /* run() must never reject: a bad package name, a bad path or a bug in this
       * file is a result the caller can render, not an exception it must catch. */
      .catch(function (error) {
        return failure(error, "setup");
      });
    /* Keep the chain alive whatever happened to this job. */
    queue = job.then(
      function () {},
      function () {}
    );
    return job;
  }

  /* ------------------------------------------------------------------ DOM */

  function parseList(figure, name) {
    var raw = figure.getAttribute(name);
    if (!raw) {
      return [];
    }
    try {
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      return [];
    }
  }

  function find(figure, selector) {
    return figure.querySelector(selector);
  }

  function codeOf(figure) {
    var node = find(figure, "pre.code > code");
    return node ? node.textContent : "";
  }

  function setStatus(figure, text) {
    var status = find(figure, ".example-status");
    if (!status) {
      return;
    }
    status.textContent = text || "";
    status.hidden = !text;
  }

  function showOutput(figure, text) {
    var output = find(figure, ".example-output");
    if (!output) {
      return;
    }
    output.textContent = text;
    output.hidden = false;
  }

  function showTerminal(figure, reason) {
    var terminal = find(figure, ".terminal-panel");
    var output = find(figure, ".example-output");
    var button = find(figure, ".btn-run");
    if (output) {
      output.hidden = true;
    }
    if (terminal) {
      terminal.hidden = false;
      /* Say why the Run button went away: a vanished button with no explanation
       * is worse than no button. A lesson's own why_not wins if it has one. */
      if (!terminal.querySelector(".terminal-why") && reason) {
        var why = document.createElement("p");
        why.className = "terminal-why";
        why.textContent = reason;
        terminal.appendChild(why);
      }
    }
    if (button) {
      button.hidden = true;
    }
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(
        function () { return true; },
        function () { return legacyCopy(text); }
      );
    }
    return Promise.resolve(legacyCopy(text));
  }

  function legacyCopy(text) {
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "readonly");
    area.className = "visually-hidden";
    document.body.appendChild(area);
    var ok = false;
    try {
      area.select();
      ok = document.execCommand("copy") === true;
    } catch (error) {
      ok = false;
    } finally {
      document.body.removeChild(area);
    }
    return ok;
  }

  function wireCopy(figure) {
    var button = find(figure, ".btn-copy");
    if (!button) {
      return;
    }
    button.addEventListener("click", function () {
      copyText(codeOf(figure)).then(function (ok) {
        button.textContent = ok ? "Copied" : "Press Ctrl+C";
        window.setTimeout(function () {
          button.textContent = "Copy code";
        }, 1400);
      });
    });
  }

  function wireRun(figure) {
    var button = find(figure, ".btn-run");
    if (!button) {
      return;
    }
    var tier = figure.getAttribute("data-tier") || "terminal";
    if (tier === "terminal") {
      showTerminal(figure);
      return;
    }
    if (!isAvailable()) {
      /* No runtime, no button: the terminal panel is the honest fallback. */
      showTerminal(figure, "Python cannot run in this browser right now — it needs a one-time download.");
      return;
    }

    button.addEventListener("click", function () {
      var packages = parseList(figure, "data-packages");
      var files = parseList(figure, "data-files");
      var first = !runtime;

      button.disabled = true;
      button.textContent = first ? "Loading Python…" : "Running…";
      setStatus(figure, first ? "Loading Python (about 10 MB, once)…" : "Running…");

      if (tier === "browser-pkg") {
        setStatus(figure, "Loading the package, then running…");
      }

      run(codeOf(figure), { packages: packages, files: files }).then(function (result) {
        setStatus(figure, "");

        if (result.error_kind === "load") {
          button.disabled = false;
          showTerminal(
            figure,
            "The Python runtime could not be loaded — the page is offline, or the download was blocked. " +
              "Run the command below in a terminal instead."
          );
          return;
        }

        button.disabled = false;
        button.textContent = "Run again";

        if (result.error_kind === "setup") {
          /* A lesson bug, not the reader's network: say what it is, keep Run. */
          showOutput(figure, "This example asks for something that does not exist:\n\n" + result.error);
          return;
        }

        if (result.ok) {
          var text = result.stdout;
          if (result.stderr) {
            text += (text ? "\n" : "") + result.stderr;
          }
          showOutput(figure, text || "(no output)");
          return;
        }

        /* A traceback is a teaching moment, so it is shown, not hidden. */
        var pane = "";
        if (result.stdout) {
          pane += result.stdout;
        }
        if (result.stderr) {
          pane += (pane ? "\n" : "") + result.stderr;
        }
        pane += (pane ? "\n" : "") + "This is what the error looks like:\n\n" + result.error;
        showOutput(figure, pane);
      });
    });
  }

  /* Wire every rendered example on the page. Each figure is wired once, so a
   * page that renders in stages (or re-renders a section) still ends up with
   * live buttons and never with a double-bound one. */
  function attachAll() {
    var figures = document.querySelectorAll(".example");
    for (var i = 0; i < figures.length; i += 1) {
      var figure = figures[i];
      if (wired) {
        if (wired.has(figure)) {
          continue;
        }
        wired.add(figure);
      } else if (figure.getAttribute("data-wired") === "1") {
        continue;
      } else {
        figure.setAttribute("data-wired", "1");
      }
      wireCopy(figure);
      wireRun(figure);
    }
  }

  /* A transient outage should not cost the reader the Run button for the rest of
   * the session: when the browser comes back online, offer it again. */
  if (window.addEventListener) {
    window.addEventListener("online", function () {
      if (!loadFailed || runtime) {
        return;
      }
      loadFailed = false;
      var figures = document.querySelectorAll('.example[data-tier="browser"], .example[data-tier="browser-pkg"]');
      for (var i = 0; i < figures.length; i += 1) {
        var button = find(figures[i], ".btn-run");
        var terminal = find(figures[i], ".terminal-panel");
        if (button) {
          button.hidden = false;
          button.disabled = false;
          button.textContent = "Run";
        }
        if (terminal && terminal.getAttribute("data-own") !== "1") {
          terminal.hidden = true;
        }
      }
    });
  }

  window.PyRun = {
    init: init,
    isAvailable: isAvailable,
    run: run,
    attachAll: attachAll
  };
})();
