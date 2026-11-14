/* 1.6 — Modules, imports, and __name__ == '__main__'
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "1.6",
  "part": 1,
  "part_title": "Python fundamentals",
  "title": "Modules, imports, and __name__ == '__main__'",
  "order": 106,
  "duration_min": 15,
  "concept_md": "### Module, package, entry point\n\nA **module** is a `.py` file. A **package** is a directory with an `__init__.py` — `app/` is one, and its `__init__.py` holds the version string. An **entry point** is a file you run: `reviewer.py` at the repository root.\n\n### Absolute imports, from the root\n\n```python\nfrom app.models import Finding\nfrom app.parser import parse_diff\n```\n\nInside the package, imports are absolute and start at `app`, never `from ..models`. That is why every command is run from the repository root: `python -m pytest`, `python reviewer.py samples/sample.diff`. Change directory and the package is no longer importable.\n\n### What the guard actually does\n\nEvery module has a `__name__`. Run the file directly and it is `\"__main__\"`; import it and it is the module's dotted name. So:\n\n```python\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n```\n\nmeans \"do this only when I am the program\", not \"when I am imported\". `reviewer.py` is four lines of exactly that: import `main` from `app.cli`, call it under the guard, nothing else.\n\n### Why it matters for tests\n\n`python -m pytest` imports test modules; their guards do not fire, so nothing runs at import time. `python tests/test_rules.py` executes the file as `__main__` — and if the file has no guard, its import-time code runs and the test functions are merely defined, never executed. That is the difference between \"the tests ran\" and \"the file loaded\".\n\n### One more thing worth knowing\n\n`python -m pytest` puts the current directory on `sys.path`; `python tests/test_rules.py` puts `tests/` there instead. That is why the same file can import `app` under one command and fail under the other.",
  "code_examples": [
    {
      "id": "1.6-ex-0",
      "lang": "python",
      "caption": "A module with a guard: silent when imported, noisy when run",
      "code": "from pathlib import Path\n\nPath(\"demo_mod.py\").write_text(\n    'def greet(name: str) -> str:\\n'\n    '    return f\"hello {name}\"\\n'\n    '\\n'\n    'if __name__ == \"__main__\":\\n'\n    '    print(\"run directly\")\\n',\n    encoding=\"utf-8\",\n)\n\nimport demo_mod\nprint(\"imported:\", demo_mod.greet(\"reader\"))\n\nimport runpy\nrunpy.run_path(\"demo_mod.py\", run_name=\"__main__\")\n",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "imported: hello reader\nrun directly"
    }
  ],
  "quiz": [
    {
      "q": "What is `__name__` inside a module that has just been imported?",
      "options": [
        "\"__main__\"",
        "The module's dotted name",
        "None",
        "The file path"
      ],
      "answer": 1,
      "why": "Only the file Python was told to run gets `\"__main__\"`; an imported module carries its own name, which is why the guard is silent."
    },
    {
      "q": "Why must the commands be run from the repository root?",
      "options": [
        "Because git requires it",
        "Because the imports are absolute and start at the `app` package",
        "Because pytest is installed there",
        "It does not matter"
      ],
      "answer": 1,
      "why": "`from app.models import Finding` resolves only if the directory containing `app/` is on sys.path, which the root is and a subdirectory is not."
    },
    {
      "q": "You run `python tests/test_rules.py` and see no test output. Why?",
      "options": [
        "The tests are broken",
        "Running the file executes it as __main__; test functions are defined, not run",
        "pytest is missing",
        "The file has no guard"
      ],
      "answer": 1,
      "why": "pytest is the thing that discovers and calls test functions. Running the file directly only defines them — and it puts tests/ on sys.path, not the root."
    }
  ],
  "try_it": {
    "prompt": "Delete the `if __name__ == \"__main__\":` line from the generated module, run the snippet again, and see when `run directly` appears.",
    "starter": "",
    "solution": "Without the guard the print is at module level, so it fires on **import** as well: the output becomes `run directly` (during the import) then `imported: hello reader` then `run directly` again from `runpy`. With the guard it prints once, only when run.",
    "explanation": "The guard is not a formality: without it, importing a module has side effects, and a test that imports your module runs its `main()`."
  },
  "exercise": {
    "prompt": "Predict what `python -m pytest -q tests` prints versus `python tests/test_rules.py`, for the same file. Then check it.",
    "hint": "One command discovers tests and calls them; the other imports the file as __main__ and stops.",
    "solution": "`python -m pytest -q tests` prints the suite result — `640 passed, 1 skipped`. `python tests/test_rules.py` prints nothing: the module body runs, the test functions are defined, and no one calls them. It also puts `tests/` on `sys.path`, so any `import app` inside the file fails unless the root is there too.",
    "explanation": "Test functions are data until a runner calls them. pytest is the runner; the file itself is not."
  },
  "common_mistakes": [
    "Relative imports inside the package (`from ..models import Finding`), which break the moment the module is run as a script.",
    "Running commands from a subdirectory, so `app` is not importable and the failure looks like a missing package.",
    "Putting a `main()` call at module level instead of under the guard, so importing the module runs the program."
  ],
  "project_links": [
    {
      "label": "The package marker and its version",
      "path": "app/__init__.py",
      "lines": "1-3"
    },
    {
      "label": "reviewer.py — the whole file is the __main__ guard",
      "path": "reviewer.py",
      "lines": "1-13"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-2-parser.md — the parser track, which starts with the package layout",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-2-parser.md"
    }
  ],
  "glossary_terms": [
    "__name__ — the module's dotted name, or \"__main__\" for the file being run",
    "entry point — the file you run: reviewer.py",
    "absolute import — `from app.models import ...`, resolved from the root",
    "sys.path — where Python looks for importable modules"
  ]
});
