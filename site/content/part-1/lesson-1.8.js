/* 1.8 — Decorators, enough to read FastAPI
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "1.8",
  "part": 1,
  "part_title": "Python fundamentals",
  "title": "Decorators, enough to read FastAPI",
  "order": 108,
  "duration_min": 20,
  "concept_md": "### Functions are values\n\nYou can pass a function to a function and return one. A decorator is that, with syntax:\n\n```python\n@logged\ndef severity_rank(name): ...\n```\n\nis exactly `severity_rank = logged(severity_rank)`. The decorator receives the function and returns a replacement. Whatever the replacement is becomes the name.\n\n### The shape you will see everywhere\n\n```python\ndef logged(function):\n    @functools.wraps(function)\n    def wrapper(*args, **kwargs):\n        ...\n        return function(*args, **kwargs)\n    return wrapper\n```\n\n`*args, **kwargs` forwards whatever the caller passed; `return` forwards the result. `@functools.wraps` copies `__name__`, `__doc__` and the annotations onto the wrapper — without it, `severity_rank.__name__` becomes `\"wrapper\"` and every traceback lies about where it came from.\n\n### Why `@app.get` works\n\n```python\n@app.get(\"/rules\")\ndef list_rules() -> list[RuleInfo]:\n    ...\n```\n\n`app.get(\"/rules\")` is called first and returns a decorator; that decorator receives `list_rules`, registers it against the path, and returns it — usually unchanged. The function is not wrapped at all; it is *recorded*. That is why the handler body looks ordinary: the decoration happened at import time, and the framework calls it later.\n\n### Reading one in this repository\n\n`app/main.py` defines the handler at `/rules`. The decorator is `app.get(...)` with a path, tags, a summary and a response model; the wrapped function is `list_rules`; what the decorator returns is the same function, registered in FastAPI's route table. Nothing in the body knows about HTTP.",
  "code_examples": [
    {
      "id": "1.8-ex-0",
      "lang": "python",
      "caption": "A decorator that prints around the call, and keeps the name",
      "code": "import functools\n\n\ndef logged(function):\n    @functools.wraps(function)\n    def wrapper(*args, **kwargs):\n        print(\"before\", function.__name__)\n        result = function(*args, **kwargs)\n        print(\"after\", function.__name__)\n        return result\n    return wrapper\n\n\n@logged\ndef severity_rank(name: str) -> int:\n    return {\"LOW\": 0, \"MEDIUM\": 1, \"HIGH\": 2, \"CRITICAL\": 3}[name]\n\n\nprint(\"rank:\", severity_rank(\"HIGH\"))\nprint(\"name kept:\", severity_rank.__name__)\n",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "before severity_rank\nafter severity_rank\nrank: 2\nname kept: severity_rank"
    }
  ],
  "quiz": [
    {
      "q": "`@logged` above a function is shorthand for what?",
      "options": [
        "A comment that the interpreter skips at import time",
        "A subclass of the decorated function, built at runtime",
        "`severity_rank = logged(severity_rank)`",
        "A type annotation checked by the interpreter at call time"
      ],
      "answer": 2,
      "why": "The decorator is called with the function and its return value takes the name, which is why the wrapper becomes the function callers see."
    },
    {
      "q": "What does `@functools.wraps(function)` change?",
      "options": [
        "It speeds up the wrapped call by caching its arguments",
        "It removes the wrapper and returns the original function",
        "It makes the decorated function run asynchronously",
        "It copies __name__, __doc__ and annotations onto the wrapper"
      ],
      "answer": 3,
      "why": "Without it every decorated function is named `wrapper`, so tracebacks and help() mislead — the one line that keeps a decorator honest."
    },
    {
      "q": "In `@app.get(\"/rules\")` over a handler, what does the decorator return?",
      "options": [
        "A new function that calls the handler on each request",
        "Usually the same function, after registering it against the path",
        "A JSON string built from the handler's annotations",
        "A route object the handler must return to be registered"
      ],
      "answer": 1,
      "why": "FastAPI records the function at import time and calls it later; that is why the body looks like ordinary Python with no HTTP in it."
    }
  ],
  "try_it": {
    "prompt": "Write a `@timed` decorator that prints how many milliseconds the function took, and stack it with `@logged` on the same function. Read the order the lines come out in.",
    "starter": "import functools\nimport time\n\n\ndef timed(function):\n    @functools.wraps(function)\n    def wrapper(*args, **kwargs):\n        start = time.perf_counter()\n        result = function(*args, **kwargs)\n        print(function.__name__, \"took\", round((time.perf_counter() - start) * 1000, 3), \"ms\")\n        return result\n    return wrapper\n",
    "solution": "```text\nimport functools\nimport time\n\n\ndef timed(function):\n    @functools.wraps(function)\n    def wrapper(*args, **kwargs):\n        start = time.perf_counter()\n        result = function(*args, **kwargs)\n        print(function.__name__, \"took\", round((time.perf_counter() - start) * 1000, 3), \"ms\")\n        return result\n    return wrapper\n\n\ndef logged(function):\n    @functools.wraps(function)\n    def wrapper(*args, **kwargs):\n        print(\"before\", function.__name__)\n        result = function(*args, **kwargs)\n        print(\"after\", function.__name__)\n        return result\n    return wrapper\n\n\n@logged\n@timed\ndef work() -> None:\n    sum(range(1000))\n\n\nwork()\n```",
    "explanation": "`@logged` is applied last, so it is the outermost wrapper: `before work`, then the timing line, then `after work`. The number varies by machine; the order does not."
  },
  "exercise": {
    "prompt": "Read the `/rules` handler in `app/main.py` and name three things: the decorator, the function it wraps, and what the decorator returns.",
    "hint": "The decorator takes arguments, so it is called before it decorates anything.",
    "solution": "```text\nThe decorator is `@app.get(\"/rules\", tags=[\"rules\"], summary=\"...\", response_model=list[RuleInfo])` — called with a path first, returning a decorator. The function it wraps is `list_rules`. What it returns is that same function, registered against the path in FastAPI's route table; the framework calls it later and serialises the `list[RuleInfo]` it produces.\n```",
    "explanation": "Three layers: `app.get(path)` builds a decorator, the decorator registers the function, and the framework calls it per request. The handler body never sees HTTP."
  },
  "common_mistakes": [
    "Forgetting `@functools.wraps`, so every decorated function reports itself as `wrapper` in tracebacks and `help()`.",
    "Writing a decorator without `*args, **kwargs`, so it only works on functions that take no arguments.",
    "Assuming a FastAPI decorator wraps the handler. It usually registers it and returns it unchanged."
  ],
  "project_links": [
    {
      "label": "The /rules handler: a decorator with arguments over an ordinary function",
      "path": "app/main.py",
      "lines": "909-922"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-7-surfaces.md — the API surface",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-7-surfaces.md"
    }
  ],
  "glossary_terms": [
    "decorator — a function that takes a function and returns a replacement",
    "functools.wraps — copies the wrapped function's identity onto the wrapper",
    "wrapper — the function a decorator returns; it usually calls the original",
    "route registration — recording a function against a path, which is what @app.get does"
  ]
});
