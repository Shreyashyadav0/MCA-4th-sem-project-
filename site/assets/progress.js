/* progress.js — "Mark done" state in localStorage.
 *
 * Shape stored under CONTRACTS.PROGRESS_KEY:
 *   { "version": 1, "done": { "0.1": true, "1.1": false } }
 *
 * Every read is defensive: a hand-edited or truncated value must degrade to
 * "nothing done yet", never throw. On file:// some browsers refuse storage
 * entirely, so a failed write falls back to an in-memory copy for the session
 * and the page keeps working; it just will not remember across reloads.
 */
(function () {
  "use strict";

  var C = window.CONTRACTS;
  var memory = null; /* session fallback when localStorage is unavailable */

  function emptyState() {
    return { version: C.STORAGE_VERSION, done: {} };
  }

  function isPlainObject(value) {
    return !!value && typeof value === "object" && !Array.isArray(value);
  }

  function readStorage() {
    try {
      var raw = window.localStorage.getItem(C.PROGRESS_KEY);
      return raw === null ? null : raw;
    } catch (err) {
      return null;
    }
  }

  function writeStorage(serialised) {
    try {
      window.localStorage.setItem(C.PROGRESS_KEY, serialised);
      return true;
    } catch (err) {
      return false;
    }
  }

  function get() {
    if (memory) {
      return memory;
    }
    var raw = readStorage();
    if (raw === null) {
      memory = emptyState();
      return memory;
    }
    var parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (err) {
      parsed = null;
    }
    if (!isPlainObject(parsed) || parsed.version !== C.STORAGE_VERSION || !isPlainObject(parsed.done)) {
      memory = emptyState();
      return memory;
    }
    memory = { version: C.STORAGE_VERSION, done: {} };
    Object.keys(parsed.done).forEach(function (id) {
      if (parsed.done[id] === true) {
        memory.done[id] = true;
      }
    });
    return memory;
  }

  function save(state) {
    memory = state;
    writeStorage(JSON.stringify(state));
  }

  function isDone(id) {
    return get().done[String(id)] === true;
  }

  function toggle(id) {
    var key = String(id);
    var state = get();
    if (state.done[key] === true) {
      delete state.done[key];
    } else {
      state.done[key] = true;
    }
    save(state);
    return state.done[key] === true;
  }

  /* Counts use window.LESSONS, so a part that has not been written yet reports
   * 0 of 0 rather than inventing lessons that do not exist. */
  function partCounts(partN) {
    var list = Array.isArray(window.LESSONS) ? window.LESSONS : [];
    var total = 0;
    var done = 0;
    for (var i = 0; i < list.length; i += 1) {
      if (Number(list[i].part) === Number(partN)) {
        total += 1;
        if (isDone(list[i].id)) {
          done += 1;
        }
      }
    }
    return { done: done, total: total };
  }

  function reset() {
    memory = emptyState();
    save(memory);
    return memory;
  }

  window.Progress = {
    get: get,
    isDone: isDone,
    toggle: toggle,
    partCounts: partCounts,
    reset: reset
  };
})();
