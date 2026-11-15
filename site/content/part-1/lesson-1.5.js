/* 1.5 — Exceptions and custom exception classes
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "1.5",
  "part": 1,
  "part_title": "Python fundamentals",
  "title": "Exceptions and custom exception classes",
  "order": 105,
  "duration_min": 20,
  "concept_md": "### The four clauses\n\n```python\ntry:\n    risky()\nexcept SpecificError as error:\n    handle(error)\nelse:\n    print(\"no exception\")\nfinally:\n    cleanup()\n```\n\n`else` runs only when the `try` block finished without raising; `finally` always runs. Most code needs `try`/`except` and nothing else — but `finally` is how a resource gets closed, and `else` is how you keep the `try` block to the one line that can fail.\n\n### Why custom exception classes\n\nA bare `except Exception` catches everything, including the typo in your own code. A custom class lets a caller say what it can handle:\n\n```python\nclass ReviewError(Exception): ...\nclass AuthError(ReviewError): ...\n```\n\n`app/github_client.py` does exactly this: `GitHubError` is the base, and `GitHubAuthError`, `GitHubNotFoundError`, `GitHubRateLimitError` and `GitHubUnavailableError` subclass it. A caller that only cares about \"posting failed\" catches `GitHubError`; a caller that wants to retry after a rate limit catches `GitHubRateLimitError` and reads `retry_after`.\n\n### Catching the parent buys you one handler\n\nOne `except GitHubError` covers every posting failure, and the subclass is still there for the caller who needs the distinction. Inheritance is not for code reuse here — it is for the granularity of `except`.\n\n### Raising inside an except block\n\n`raise NewError(...) from exc` keeps the original traceback attached as `__cause__`. Without `from`, the context is implicit and the reviewer has to guess what really failed. `app/cli.py` uses `from exc` when it converts a decode failure into a `ReviewInputError`.",
  "code_examples": [
    {
      "id": "1.5-ex-0",
      "lang": "python",
      "caption": "A small hierarchy, caught at the parent",
      "code": "class ReviewError(Exception):\n    \"\"\"Base class for every review failure.\"\"\"\n\n\nclass AuthError(ReviewError):\n    \"\"\"The credential was refused.\"\"\"\n\n\ndef check(token: str | None) -> None:\n    if not token:\n        raise AuthError(\"no credential configured\")\n\n\ntry:\n    check(None)\nexcept ReviewError as error:\n    print(\"caught as the parent:\", type(error).__name__, \"-\", error)\nfinally:\n    print(\"finally runs whether or not it raised\")\n",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "caught as the parent: AuthError - no credential configured\nfinally runs whether or not it raised"
    }
  ],
  "quiz": [
    {
      "q": "Why does `GitHubAuthError` subclass `GitHubError`?",
      "options": [
        "So the subclass can reuse the parent's methods without rewriting them",
        "Because Python requires every custom error to have a parent class",
        "So raising it is faster than raising a plain Exception instance",
        "So one `except GitHubError` covers every posting failure"
      ],
      "answer": 3,
      "why": "The hierarchy exists for the granularity of `except`: catch the base for a single handler, catch the subclass when the caller needs to distinguish."
    },
    {
      "q": "What is wrong with `except Exception: pass`?",
      "options": [
        "Nothing, as long as the block it guards is short enough",
        "It swallows every failure, including bugs in your own code",
        "It is measurably slower than naming a specific exception class",
        "It only catches the first exception raised inside the block"
      ],
      "answer": 1,
      "why": "The degraded path must degrade for known reasons and log exactly one WARNING; a bare pass turns an unknown failure into a silent wrong answer."
    },
    {
      "q": "What does `raise NewError(...) from exc` add?",
      "options": [
        "The original exception as `__cause__`",
        "Nothing that a reader of the traceback can actually see",
        "An automatic retry of the operation that raised the first error",
        "A warning line written to the log at WARNING level"
      ],
      "answer": 0,
      "why": "`from` chains the cause, which is the difference between a readable traceback and a mystery when a decode error becomes a ReviewInputError."
    }
  ],
  "try_it": {
    "prompt": "Add a `RateLimitError(AuthError)` with a `retry_after` attribute, raise it, and catch it twice: once as `AuthError`, once as `RateLimitError`.",
    "starter": "class ReviewError(Exception):\n    pass\n\n\nclass AuthError(ReviewError):\n    pass\n\n\nclass RateLimitError(AuthError):\n    def __init__(self, message: str, retry_after: float) -> None:\n        super().__init__(message)\n        self.retry_after = retry_after\n",
    "solution": "```text\nclass ReviewError(Exception):\n    pass\n\n\nclass AuthError(ReviewError):\n    pass\n\n\nclass RateLimitError(AuthError):\n    def __init__(self, message: str, retry_after: float) -> None:\n        super().__init__(message)\n        self.retry_after = retry_after\n\n\nfor handler in (AuthError, RateLimitError):\n    try:\n        raise RateLimitError(\"slow down\", 30.0)\n    except handler as error:\n        print(handler.__name__, \"caught\", type(error).__name__, getattr(error, \"retry_after\", None))\n```",
    "explanation": "Both handlers catch it, and the second can read `retry_after`. That is the same shape as `GitHubRateLimitError` in `app/github_client.py`, which carries the header value."
  },
  "exercise": {
    "prompt": "Build the two-level hierarchy from the example, then show the difference: catch a `RateLimitError` with `except AuthError`, and try to catch it with a sibling `except NotFoundError`. Print what each handler sees.",
    "hint": "A subclass is caught by a handler for its parent, never by a handler for a sibling.",
    "solution": "class ReviewError(Exception):\n    pass\n\n\nclass AuthError(ReviewError):\n    pass\n\n\nclass RateLimitError(AuthError):\n    pass\n\n\nclass NotFoundError(ReviewError):\n    pass\n\n\ntry:\n    raise RateLimitError(\"slow down\")\nexcept AuthError as error:\n    print(\"parent caught:\", type(error).__name__)\n\ntry:\n    raise RateLimitError(\"slow down\")\nexcept NotFoundError:\n    print(\"sibling caught it\")\nexcept ReviewError as error:\n    print(\"grandparent caught:\", type(error).__name__)\n",
    "explanation": "It prints `parent caught: RateLimitError` then `grandparent caught: RateLimitError`. The sibling handler never fires — that is the shape `app/github_client.py` relies on: one `except GitHubError` covers everything, and a narrower handler only catches its own branch."
  },
  "common_mistakes": [
    "A bare `except:` or `except Exception: pass`. It swallows the typo in your own code and turns a failure into a silent wrong answer.",
    "Raising inside an `except` block without `from`, losing the original cause from the traceback.",
    "Catching a subclass where the parent was meant — `except GitHubError` is usually what a caller wants; narrowing it re-introduces the enumeration problem."
  ],
  "project_links": [
    {
      "label": "The GitHubError family: one base, four subclasses",
      "path": "app/github_client.py",
      "lines": "124-160"
    },
    {
      "label": "read_source — raising ReviewInputError with `from exc`",
      "path": "app/cli.py",
      "lines": "142-166"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-7-surfaces.md — the posting surface",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-7-surfaces.md"
    },
    {
      "label": "ADR 0005 — a 422 demotes one finding, it does not fail the post",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0005-422-demotes-single-finding-not-whole-post.md"
    }
  ],
  "glossary_terms": [
    "exception hierarchy — a base error with subclasses, so callers choose their granularity",
    "bare except — `except:` with no type; catches everything including KeyboardInterrupt",
    "__cause__ — the original exception attached by `raise ... from`",
    "finally — the block that always runs, raise or return"
  ]
});
