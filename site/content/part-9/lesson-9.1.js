/* 9.1 — Settings: one object, one place the environment is read
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "9.1",
  "part": 9,
  "part_title": "Configuration and offline-first",
  "title": "Settings: one object, one place the environment is read",
  "order": 901,
  "duration_min": 20,
  "concept_md": "### One class reads the environment\n\n`app/config.py` defines a single `Settings` class. It subclasses `BaseSettings`, so every annotated field is filled from an environment variable of the same name, case-insensitively, and from a `.env` file when one exists.\n\nNothing else in the codebase calls `os.environ`. That is the design: one place reads the environment, and every other module asks for a `Settings` object.\n\n### Why one place matters\n\nA second reader means a second default. Two modules reading `LMSTUDIO_BASE_URL` independently can disagree about what absence means — one treating it as \"use the default\", the other as \"disabled\". With one class, absence has exactly one meaning per field, written beside the field.\n\n### `extra=\"ignore\"`\n\nThe config sets `extra=\"ignore\"`, so an unknown variable in `.env` does not raise. That is deliberate for a file a reader edits by hand: a stray line should not stop the application.\n\n### Every field has a default\n\nThe class docstring says so, and it is testable: constructing `Settings()` in an empty environment succeeds. A required field would make the tool refuse to start on a fresh checkout, which is the opposite of offline-first.",
  "code_examples": [
    {
      "id": "9.1-ex-0",
      "lang": "console",
      "caption": "Every field, and that a bare Settings() succeeds",
      "code": "python - <<'PY'\nfrom app.config import Settings\n\ns = Settings()\nprint(\"fields:\", len(Settings.model_fields))\nprint(\"mode:\", s.review_mode, \"| timeout:\", s.request_timeout_s)\nprint(\"db:\", s.database_path)\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "fields: 15\nmode: auto | timeout: 20.0\ndb: data/reviewer.db",
      "why_not": "the browser runner does not embed app/config.py, and it needs pydantic-settings; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "How many modules read the environment directly?",
      "options": [
        "Only app/config.py itself",
        "Two: config and the CLI",
        "Three: config, CLI, engine",
        "Every module needing a value"
      ],
      "answer": 0,
      "why": "`Settings` is the only reader; everything else takes a settings object, so absence has one meaning per field."
    },
    {
      "q": "What does `extra=\"ignore\"` do to an unknown key?",
      "options": [
        "Skips it without raising",
        "Raises on start, naming it in the error",
        "Stores it in a catch-all",
        "Warns once, then ignores"
      ],
      "answer": 0,
      "why": "A hand-edited `.env` should not stop the application, so an unknown name is skipped rather than fatal."
    },
    {
      "q": "Why does every field carry a default?",
      "options": [
        "So a fresh checkout starts",
        "So tests skip validation",
        "So the class subclasses well",
        "So Pydantic infers types"
      ],
      "answer": 0,
      "why": "A required field would make the tool refuse to start, contradicting the offline-first promise."
    }
  ],
  "try_it": {
    "prompt": "Print the name and default of every field.",
    "starter": "",
    "solution": "```python\nfrom app.config import Settings\n\nfor name, f in Settings.model_fields.items():\n    print(\"%-24s %r\" % (name, f.default))\n```",
    "explanation": "The defaults are the documented behaviour when nothing is set, which is lesson 9.4's subject."
  },
  "exercise": {
    "prompt": "Which field controls the HTTP timeout, and what is its lower bound?",
    "hint": "Look for a float with a `gt=` constraint.",
    "solution": "```python\nfrom app.config import Settings\n\nf = Settings.model_fields[\"request_timeout_s\"]\nprint(f.default, [str(m) for m in f.metadata])\n```\n\n`20.0`, and the constraint is `gt=0` — zero or negative is refused.",
    "explanation": "The bound sits in the field, so an invalid value fails at construction rather than at request time."
  },
  "common_mistakes": [
    "Reading `os.environ` in a module instead of taking a `Settings` object.",
    "Assuming an unknown `.env` key raises; `extra=\"ignore\"` swallows it.",
    "Adding a required field, which breaks the fresh-checkout start."
  ],
  "project_links": [
    {
      "label": "The Settings class and its config",
      "path": "app/config.py",
      "lines": "20-28"
    },
    {
      "label": "The timeout field and its bound",
      "path": "app/config.py",
      "lines": "61"
    }
  ],
  "learn_more": [
    {
      "label": "app/config.py — the settings",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/config.py"
    },
    {
      "label": ".env.example — every variable",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/.env.example"
    }
  ],
  "glossary_terms": [
    "settings — the one object the environment is read into",
    "base settings — the class that maps variables to fields",
    "default — what a field holds when nothing is set"
  ]
});
