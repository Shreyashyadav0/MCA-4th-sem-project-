/* pyodide-loader.js — optional in-browser Python.
 *
 * Pyodide is a convenience, not a dependency. Nothing is fetched until the
 * reader presses Run, so opening a lesson offline makes no request at all and
 * logs no error. When the CDN cannot be reached — offline, blackholed, or slow
 * past the timeout — the example falls back to what a static site can always
 * offer: a command that really runs, and the expected output when the lesson
 * states one.
 *
 * Two failure modes are kept apart on purpose:
 *   - the runtime did not load  -> terminal fallback, Run removed
 *   - the snippet raised        -> the traceback is shown, Run stays available
 * Reporting a Python error as "you must be offline" would be a lie.
 *
 * PyRun.attach(container, example) builds the whole figure, so app.js never
 * writes example markup itself.
 */
(function () {
  "use strict";

  var PYODIDE_VERSION = "0.26.4";
  var PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v" + PYODIDE_VERSION + "/full/pyodide.js";
  var LOAD_TIMEOUT_MS = 20000;

  var runtime = null; /* the loaded Pyodide instance, once there is one */
  var loading = null; /* in-flight load, so two clicks share one download */
  var failed = false; /* set once a load has failed; no second attempt per page */

  function loaded() {
    return runtime !== null;
  }

  /* Honest and cheap: true only if the runtime is already in memory, or if the
   * browser claims to be online and no load has failed yet. It never probes the
   * network — a probe would defeat the point of an offline site. */
  function isAvailable() {
    if (loaded()) {
      return true;
    }
    if (failed) {
      return false;
    }
    return navigator.onLine !== false;
  }

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var script = document.createElement("script");
      var settled = false;
      var timer = window.setTimeout(function () {
        if (!settled) {
          settled = true;
          cleanup();
          reject(new Error("pyodide load timed out"));
        }
      }, LOAD_TIMEOUT_MS);

      function cleanup() {
        window.clearTimeout(timer);
        script.onload = null;
        script.onerror = null;
        if (script.parentNode) {
          script.parentNode.removeChild(script);
        }
      }

      script.src = src;
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
          cleanup();
          reject(new Error("pyodide script failed to load"));
        }
      };
      document.head.appendChild(script);
    });
  }

  function loadRuntime() {
    if (runtime) {
      return Promise.resolve(runtime);
    }
    if (loading) {
      return loading;
    }
    loading = loadScript(PYODIDE_URL)
      .then(function () {
        if (typeof window.loadPyodide !== "function") {
          throw new Error("loadPyodide is not a function");
        }
        return window.loadPyodide();
      })
      .then(function (instance) {
        runtime = instance;
        return instance;
      })
      .catch(function (error) {
        failed = true;
        loading = null;
        throw error;
      });
    return loading;
  }

  /* A command the reader can paste and run. For a Python example that is a
   * heredoc rather than "python example.py", because no example.py exists in
   * the repository and a command that cannot run is worse than none. */
  function terminalCommand(example) {
    if (example.lang === "python") {
      return "python - <<'PY'\n" + String(example.code || "").replace(/\s+$/, "") + "\nPY";
    }
    return String(example.code || "").trim();
  }

  function buildTerminal(example) {
    var panel = document.createElement("div");
    panel.className = "terminal-panel";
    panel.hidden = true;

    var heading = document.createElement("p");
    heading.className = "terminal-title";
    heading.tabIndex = -1;
    heading.textContent = "Run it in a terminal, from the repository root";
    panel.appendChild(heading);

    var command = document.createElement("pre");
    command.className = "code terminal-command";
    var commandCode = document.createElement("code");
    commandCode.textContent = terminalCommand(example);
    command.appendChild(commandCode);
    panel.appendChild(command);

    if (example.expected_output !== undefined && example.expected_output !== null) {
      var label = document.createElement("p");
      label.className = "terminal-title";
      label.textContent = "Expected output";
      panel.appendChild(label);

      var output = document.createElement("pre");
      output.className = "code terminal-output";
      var outputCode = document.createElement("code");
      outputCode.textContent = example.expected_output;
      output.appendChild(outputCode);
      panel.appendChild(output);
    }

    return panel;
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
    } catch (err) {
      ok = false;
    } finally {
      document.body.removeChild(area);
    }
    return ok;
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(
        function () {
          return true;
        },
        function () {
          return legacyCopy(text);
        }
      );
    }
    return Promise.resolve(legacyCopy(text));
  }

  function attach(container, example) {
    var figure = document.createElement("figure");
    figure.className = "code-figure example";

    if (example.caption) {
      var caption = document.createElement("figcaption");
      caption.className = "code-caption";
      caption.textContent = example.caption;
      figure.appendChild(caption);
    }

    var pre = document.createElement("pre");
    pre.className = "code";
    if (example.lang) {
      pre.setAttribute("data-lang", example.lang);
    }
    var code = document.createElement("code");
    code.textContent = example.code;
    pre.appendChild(code);
    figure.appendChild(pre);

    var actions = document.createElement("div");
    actions.className = "example-actions";

    var output = document.createElement("pre");
    output.className = "code example-output";
    output.hidden = true;
    output.setAttribute("role", "status");
    output.setAttribute("aria-live", "polite");

    var terminal = buildTerminal(example);
    var canRunInBrowser = example.runnable === true && example.lang === "python";
    var runBtn = null;

    if (canRunInBrowser) {
      runBtn = document.createElement("button");
      runBtn.type = "button";
      runBtn.className = "btn btn-run";
      runBtn.textContent = "Run";
      runBtn.setAttribute("aria-label", "Run this example in the browser");
      runBtn.addEventListener("click", function () {
        run(example.code, output, terminal, runBtn);
      });
      actions.appendChild(runBtn);
    }

    var copyButton = document.createElement("button");
    copyButton.type = "button";
    copyButton.className = "btn btn-copy";
    copyButton.textContent = "Copy code";
    copyButton.addEventListener("click", function () {
      copyText(example.code).then(function (ok) {
        copyButton.textContent = ok ? "Copied" : "Press Ctrl+C";
        window.setTimeout(function () {
          copyButton.textContent = "Copy code";
        }, 1400);
      });
    });
    actions.appendChild(copyButton);

    figure.appendChild(actions);
    figure.appendChild(output);
    figure.appendChild(terminal);

    /* No runtime, no button: show the terminal path immediately so the reader
     * is never offered an action that cannot work. */
    if (canRunInBrowser && !isAvailable() && runBtn) {
      runBtn.hidden = true;
      terminal.hidden = false;
    }
    if (!canRunInBrowser) {
      terminal.hidden = false;
    }

    container.appendChild(figure);
    return figure;
  }

  function showTerminal(outputEl, terminalEl, button) {
    if (outputEl) {
      outputEl.hidden = true;
    }
    if (terminalEl) {
      terminalEl.hidden = false;
      var heading = terminalEl.querySelector(".terminal-title");
      if (heading && heading.focus) {
        heading.focus();
      }
    }
    if (button) {
      button.hidden = true;
    }
  }

  function run(codeText, outputEl, terminalEl, button) {
    if (!outputEl) {
      return Promise.resolve("");
    }
    if (button) {
      button.disabled = true;
      button.textContent = "Loading Python…";
    }
    outputEl.hidden = false;
    outputEl.textContent = "Starting Python in the browser (the first run downloads it)…";

    return loadRuntime().then(
      function (instance) {
        var chunks = [];
        var capture = function (text) {
          chunks.push(text);
        };
        instance.setStdout({ batched: capture });
        instance.setStderr({ batched: capture });
        return instance.runPythonAsync(codeText).then(
          function (result) {
            var text = chunks.join("");
            if (result !== undefined && result !== null && String(result) !== "undefined" && String(result) !== "None") {
              text += String(result) + "\n";
            }
            outputEl.textContent = text.trim() ? text.replace(/\s+$/, "") : "(no output)";
            if (button) {
              button.disabled = false;
              button.textContent = "Run";
            }
            return text;
          },
          function (error) {
            /* The snippet raised. That is a real answer, not an outage: show the
             * traceback and leave Run available for the next attempt. */
            var printed = chunks.join("");
            outputEl.textContent = (printed ? printed.replace(/\s+$/, "") + "\n" : "") + String(error && error.message ? error.message : error);
            if (button) {
              button.disabled = false;
              button.textContent = "Run";
            }
            return printed;
          }
        );
      },
      function () {
        /* The runtime itself did not arrive: this is the offline case. */
        if (button) {
          button.disabled = false;
          button.textContent = "Run";
        }
        showTerminal(outputEl, terminalEl, button);
        return "";
      }
    );
  }

  window.PyRun = {
    attach: attach,
    run: run,
    isAvailable: isAvailable
  };
})();
