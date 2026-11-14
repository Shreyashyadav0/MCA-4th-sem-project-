/* pyodide-loader.js — optional in-browser Python.
 *
 * Pyodide is a convenience, not a dependency. Nothing is fetched until the
 * reader presses Run, so opening a lesson offline makes no request at all and
 * logs no error. When the CDN cannot be reached the example falls back to what
 * a static site can always offer: the exact command to run in a terminal, and
 * the expected output when the lesson states one.
 *
 * PyRun.attach(container, example) builds the whole figure, so app.js never
 * writes example markup itself.
 */
(function () {
  "use strict";

  var PYODIDE_VERSION = "0.26.4";
  var PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v" + PYODIDE_VERSION + "/full/pyodide.js";
  var runtime = null; /* the loaded Pyodide instance, once there is one */
  var loading = null; /* in-flight load, so two clicks share one download */
  var failed = false; /* set once the CDN has refused; no second attempt per page */

  function loaded() {
    return runtime !== null;
  }

  /* Honest and cheap: true only if the runtime is already in memory, or if the
   * browser claims to be online and we have not already failed once. It never
   * probes the network — a probe would defeat the point of an offline site. */
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
      script.src = src;
      script.async = true;
      script.onload = function () {
        resolve();
      };
      script.onerror = function () {
        reject(new Error("pyodide script failed to load"));
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
        return window.loadPyodide({ stdout: function () {}, stderr: function () {} });
      })
      .then(function (instance) {
        runtime = instance;
        return instance;
      })
      .catch(function (error) {
        failed = true;
        throw error;
      });
    return loading;
  }

  function terminalCommand(example) {
    if (example.lang === "python") {
      return "python example.py";
    }
    return String(example.code || "").trim();
  }

  function buildTerminal(example) {
    var panel = document.createElement("div");
    panel.className = "terminal-panel";
    panel.hidden = true;

    var heading = document.createElement("p");
    heading.className = "terminal-title";
    heading.textContent = "Run it in a terminal, from the repository root";
    panel.appendChild(heading);

    var command = document.createElement("pre");
    command.className = "code terminal-command";
    var commandCode = document.createElement("code");
    commandCode.textContent = terminalCommand(example);
    command.appendChild(commandCode);
    panel.appendChild(command);

    if (example.lang === "python") {
      var note = document.createElement("p");
      note.className = "terminal-note";
      note.textContent = "Save the code above as example.py first.";
      panel.appendChild(note);
    }

    if (example.expected_output) {
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

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).catch(function () {
        return legacyCopy(text);
      });
    }
    return Promise.resolve(legacyCopy(text));
  }

  function legacyCopy(text) {
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "readonly");
    area.className = "visually-hidden";
    document.body.appendChild(area);
    area.select();
    try {
      document.execCommand("copy");
    } catch (err) {
      /* nothing else to try; the code is on screen and selectable */
    }
    document.body.removeChild(area);
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

    var terminal = buildTerminal(example);
    var canRunInBrowser = example.runnable === true && example.lang === "python";

    if (canRunInBrowser) {
      var runButton = document.createElement("button");
      runButton.type = "button";
      runButton.className = "btn btn-run";
      runButton.textContent = "Run";
      runButton.setAttribute("aria-label", "Run this example in the browser");
      runButton.addEventListener("click", function () {
        run(example.code, output, terminal, runButton);
      });
      actions.appendChild(runButton);
    }

    var copyButton = document.createElement("button");
    copyButton.type = "button";
    copyButton.className = "btn btn-copy";
    copyButton.textContent = "Copy code";
    copyButton.addEventListener("click", function () {
      var label = copyButton.textContent;
      copyText(example.code).then(function () {
        copyButton.textContent = "Copied";
        window.setTimeout(function () {
          copyButton.textContent = label;
        }, 1400);
      });
    });
    actions.appendChild(copyButton);

    figure.appendChild(actions);
    figure.appendChild(output);
    figure.appendChild(terminal);

    /* No network, no button: show the terminal path immediately so the reader
     * is never offered an action that cannot work. */
    if (canRunInBrowser && navigator.onLine === false) {
      var run = actions.querySelector(".btn-run");
      if (run) {
        run.hidden = true;
      }
      terminal.hidden = false;
    }
    if (!canRunInBrowser) {
      terminal.hidden = false;
    }

    container.appendChild(figure);
    return figure;
  }

  function run(codeText, outputEl, terminalEl, button) {
    if (!outputEl) {
      return Promise.resolve("");
    }
    var previous = button ? button.textContent : "";
    if (button) {
      button.disabled = true;
      button.textContent = "Loading Python…";
    }
    outputEl.hidden = false;
    outputEl.textContent = "Starting Python in the browser (first run downloads it)…";

    return loadRuntime()
      .then(function (instance) {
        var lines = [];
        instance.setStdout({ batched: function (line) { lines.push(line); } });
        instance.setStderr({ batched: function (line) { lines.push(line); } });
        return instance.runPythonAsync(codeText).then(function (result) {
          var text = lines.join("\n");
          if (result !== undefined && result !== null && String(result) !== "undefined") {
            text = text ? text + "\n" + String(result) : String(result);
          }
          outputEl.textContent = text || "(no output)";
          return text;
        });
      })
      .catch(function () {
        outputEl.hidden = true;
        if (terminalEl) {
          terminalEl.hidden = false;
        }
        if (button) {
          button.hidden = true;
        }
        return "";
      })
      .then(function (text) {
        if (button) {
          button.disabled = false;
          button.textContent = previous;
        }
        return text;
      });
  }

  window.PyRun = {
    attach: attach,
    run: run,
    isAvailable: isAvailable
  };
})();
