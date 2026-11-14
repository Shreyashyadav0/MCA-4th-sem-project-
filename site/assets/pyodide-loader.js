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
 *   browser      stdlib or a package Pyodide bundles; runs immediately
 *   browser-pkg  runs after micropip installs a pure-Python wheel (network once)
 *   terminal     cannot run here; the panel says so, with the command to run
 *
 * Failure is not an exception. A Python traceback is shown as a teaching
 * moment; a runtime that cannot load turns every Run into Copy + terminal.
 */
(function () {
  "use strict";

  var PYODIDE_VERSION = "0.28.0";
  var CDN_BASE = "https://cdn.jsdelivr.net/pyodide/v" + PYODIDE_VERSION + "/full/";
  var LOAD_TIMEOUT_MS = 120000;
  var FS_ROOT = "/home/pyodide";

  var runtime = null;
  var loading = null;
  var loadFailed = false;
  var pathReady = false;
  var loadedPackages = {};
  var wired = false;

  function isAvailable() {
    if (runtime) {
      return true;
    }
    if (loadFailed) {
      return false;
    }
    return navigator.onLine !== false;
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
      return Promise.resolve();
    }
    pyodide.runPython(
      "import sys\n" +
        "if " + JSON.stringify(FS_ROOT) + " not in sys.path:\n" +
        "    sys.path.insert(0, " + JSON.stringify(FS_ROOT) + ")\n"
    );
    pathReady = true;
    return Promise.resolve();
  }

  function ensurePackages(pyodide, packages) {
    var wanted = Array.isArray(packages) ? packages.filter(Boolean) : [];
    var missing = wanted.filter(function (name) {
      return !loadedPackages[name];
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
   * at the same relative path they have in the repository. */
  function materialise(pyodide, files) {
    var wanted = Array.isArray(files) ? files : [];
    if (!wanted.length) {
      return [];
    }
    var sources = window.REPO_SOURCES || {};
    var written = [];
    wanted.forEach(function (relative) {
      if (!Object.prototype.hasOwnProperty.call(sources, relative)) {
        throw new Error("no embedded source for " + relative + " — run site/tools/embed_sources.py");
      }
      var absolute = FS_ROOT + "/" + relative;
      var directory = absolute.slice(0, absolute.lastIndexOf("/"));
      pyodide.FS.mkdirTree(directory);
      pyodide.FS.writeFile(absolute, sources[relative], { encoding: "utf8" });
      written.push(relative);
    });
    return written;
  }

  function execute(pyodide, code) {
    var stdout = [];
    var stderr = [];
    var decoder = new TextDecoder("utf-8");
    /* Raw writes, not batched lines: the bytes are what CPython produced, so a
     * newline is never lost or doubled by the transport. */
    var capture = function (sink) {
      return function (buffer) {
        sink.push(decoder.decode(buffer, { stream: true }));
        return buffer.length;
      };
    };
    pyodide.setStdout({ write: capture(stdout) });
    pyodide.setStderr({ write: capture(stderr) });

    return pyodide.runPythonAsync(code).then(
      function (result) {
        var out = stdout.join("");
        if (result !== undefined && result !== null && String(result) !== "undefined" && String(result) !== "None") {
          out += String(result) + "\n";
        }
        return { ok: true, stdout: out, stderr: stderr.join(""), error: "" };
      },
      function (error) {
        /* A Python exception is content, not a crash: hand back the traceback. */
        return {
          ok: false,
          stdout: stdout.join(""),
          stderr: stderr.join(""),
          error: String(error && error.message ? error.message : error)
        };
      }
    );
  }

  /* run(code, {packages, files}) -> Promise<{ok, stdout, stderr, error}> */
  function run(code, opts) {
    var options = opts || {};
    return init()
      .then(function (pyodide) {
        return ensurePath(pyodide)
          .then(function () {
            return ensurePackages(pyodide, options.packages);
          })
          .then(function () {
            materialise(pyodide, options.files);
            return execute(pyodide, code);
          });
      })
      .catch(function (error) {
        return {
          ok: false,
          stdout: "",
          stderr: "",
          error: String(error && error.message ? error.message : error),
          load_failed: true
        };
      });
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
        button.disabled = false;
        button.textContent = "Run again";
        setStatus(figure, "");

        if (result.load_failed) {
          showTerminal(
            figure,
            "The Python runtime could not be loaded — the page is offline, or the download was blocked. " +
              "Run the command below in a terminal instead."
          );
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
        var pane = "This is what the error looks like:\n\n" + result.error;
        if (result.stdout) {
          pane = result.stdout + "\n" + pane;
        }
        showOutput(figure, pane);
      });
    });
  }

  /* Wire every rendered example on the page. Idempotent: a second call is a
   * no-op, so a page that renders in stages cannot double-bind a button. */
  function attachAll() {
    if (wired) {
      return;
    }
    wired = true;
    var figures = document.querySelectorAll(".example");
    for (var i = 0; i < figures.length; i += 1) {
      wireCopy(figures[i]);
      wireRun(figures[i]);
    }
  }

  window.PyRun = {
    init: init,
    isAvailable: isAvailable,
    run: run,
    attachAll: attachAll
  };
})();
