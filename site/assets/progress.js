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

  /* A copy, never the internal object: a caller that mutates what it gets back
   * cannot corrupt the stored state behind the module's back. */
  function clone(state) {
    return { version: state.version, done: Object.assign({}, state.done) };
  }

  function loadState() {
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
    /* Only ids this build actually has: a hand-edited or foreign value must not
     * be able to make every isDone() call walk a hundred thousand keys. */
    var known = {};
    var lessons = Array.isArray(window.LESSONS) ? window.LESSONS : [];
    lessons.forEach(function (lesson) {
      known[String(lesson.id)] = true;
    });
    memory = { version: C.STORAGE_VERSION, done: {} };
    var kept = 0;
    Object.keys(parsed.done).forEach(function (id) {
      if (kept < 500 && parsed.done[id] === true && (known[id] === true || !lessons.length)) {
        memory.done[id] = true;
        kept += 1;
      }
    });
    return memory;
  }

  function save(state) {
    memory = state;
    writeStorage(JSON.stringify(state));
  }

  function get() {
    return clone(loadState());
  }

  function isDone(id) {
    return loadState().done[String(id)] === true;
  }

  function toggle(id) {
    var key = String(id);
    var state = loadState();
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
    var state = loadState();
    var total = 0;
    var done = 0;
    for (var i = 0; i < list.length; i += 1) {
      if (Number(list[i].part) === Number(partN)) {
        total += 1;
        if (state.done[String(list[i].id)] === true) {
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
