/* 7.5 — normalize_path and the project root
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "7.5",
  "part": 7,
  "part_title": "The parser",
  "title": "normalize_path and the project root",
  "order": 705,
  "duration_min": 25,
  "concept_md": "### Three jobs, one function\n\n`normalize_path` at **73** strips quotes, drops a leading `./`, and removes one `a/` or `b/` prefix. Each rule exists because a real diff can carry that form.\n\n### The guard\n\n`len(path) > 2` before the prefix strip stops the degenerate path `a/` from becoming empty. It is not protection against a double strip — the strip is a single `if`, so it runs once by construction.\n\n### Keeping a path inside the project root\n\nNormalising is not the same as confining. The parser normalises so a finding names a real file; the API separately refuses a path that escapes the root, at `app/main.py:427`, with a 403. Two functions, two jobs: one cleans, one constrains.\n\n### Why the distinction matters\n\nA path like `../../etc/passwd` survives normalisation — it is already relative and has no prefix. Only the confinement check can reject it, which is why the parser cannot be the only defence.\n\n### The rule to remember\n\nStrip once, and let something else decide whether the result is allowed.\n\n### What it is not for\n\nIt is not a sanitiser and not a security boundary. It assumes the input is a path from a diff header, and it makes that path match the repository. A caller that wants a guarantee about where a file may be read from needs the confinement check, not this function.",
  "code_examples": [
    {
      "id": "7.5-ex-0",
      "lang": "python",
      "caption": "The four forms it handles",
      "code": "from app.parser import normalize_path\n\nfor raw in ('b/app/db.py', '\"a/app/config.py\"', './app/x.py', 'app/db.py', 'a/'):\n    print(repr(raw), \"->\", repr(normalize_path(raw)))",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "'b/app/db.py' -> 'app/db.py'\n'\"a/app/config.py\"' -> 'app/config.py'\n'./app/x.py' -> 'app/x.py'\n'app/db.py' -> 'app/db.py'\n'a/' -> 'a/'",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py",
        "app/parser.py",
        "samples/sample.diff"
      ]
    }
  ],
  "quiz": [
    {
      "q": "What does `normalize_path('a/')` return?",
      "options": [
        "It raises a ValueError",
        "An empty string",
        "`/`",
        "`a/`, because the guard stops the strip"
      ],
      "answer": 3,
      "why": "`len('a/') > 2` is false, so the prefix rule is skipped and the degenerate path survives unchanged rather than collapsing."
    },
    {
      "q": "Does normalisation stop `../../etc/passwd`?",
      "options": [
        "Yes, it strips the parent segments",
        "No — that is the confinement check in the API",
        "Yes, it rejects any path with a dot",
        "No, and nothing else does either"
      ],
      "answer": 1,
      "why": "Cleaning a path and confining it are different jobs; the API's guard at `app/main.py:427` is what refuses an escape."
    },
    {
      "q": "Why is the prefix stripped only once?",
      "options": [
        "Because git never writes two prefixes",
        "Because of the `len(path) > 2` guard",
        "Because the strip is a single `if`, not a loop",
        "Because the regex anchors at the start"
      ],
      "answer": 2,
      "why": "One conditional means one strip; the length guard is about the degenerate `a/` case, not about repetition."
    }
  ],
  "try_it": {
    "prompt": "Normalise a quoted path with the prefix and confirm both rules applied.",
    "starter": "",
    "solution": "```python\nfrom app.parser import normalize_path\n\nprint(normalize_path('\"b/app/config.py\"'))\n```",
    "explanation": "`app/config.py` — the quotes came off, then the prefix, in that order."
  },
  "exercise": {
    "prompt": "Which line strips the prefix, and what would `normalize_path('app/config.py')` return?",
    "hint": "The path does not start with a prefix at all.",
    "solution": "```text\nThe prefix strip is lines 84-85: the `if` and `path = path[2:]`.\n\nnormalize_path('app/config.py') returns 'app/config.py' unchanged — it starts\nwith 'ap', not 'a/', so no rule matches.\n```",
    "explanation": "A path that never had a prefix is the common case; the function is written so that case costs nothing."
  },
  "common_mistakes": [
    "Expecting normalisation to reject a traversal path.",
    "Stripping the prefix twice, which mangles a real path such as `a/a/x`.",
    "Comparing a normalised path against a raw one from the diff."
  ],
  "project_links": [
    {
      "label": "normalize_path, all four rules",
      "path": "app/parser.py",
      "lines": "73-88"
    },
    {
      "label": "The confinement check that rejects an escape",
      "path": "app/main.py",
      "lines": "425-429"
    }
  ],
  "learn_more": [
    {
      "label": "app/parser.py — the parser",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/parser.py"
    },
    {
      "label": "app/main.py — the API boundary",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/main.py"
    }
  ],
  "glossary_terms": [
    "normalise — reduce a diff path to a repository path",
    "confine — refuse a path that leaves the project root",
    "traversal — a path using .. to escape a directory"
  ]
});
