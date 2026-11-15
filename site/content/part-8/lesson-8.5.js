/* 8.5 — # noqa and # nosec: line-local, never block-level
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "8.5",
  "part": 8,
  "part_title": "The rule engine",
  "title": "# noqa and # nosec: line-local, never block-level",
  "order": 805,
  "duration_min": 25,
  "concept_md": "### One regex, three answers\n\n```python\n_NOQA_RE = re.compile(r\"#\\s*(?:noqa|nosec)(?P<ids>[:=][A-Za-z0-9_,\\s/\\-]+)?\", re.IGNORECASE)\n```\n\nThe helper returns a pair: `(suppress_all, rule_ids)`. A bare `# noqa` gives `(True, set())`. A targeted `# noqa: secret/hardcoded-credential` gives `(False, {\"secret/hardcoded-credential\"})`. No marker gives `(False, set())`.\n\n### Why two spellings\n\n`noqa` is the flake8 convention and `nosec` is bandit's. Accepting both means a reader arriving from either tool finds the marker they already know, rather than learning a third.\n\n### Why the ids are a set, not a count\n\nBecause the marker may name several: `# noqa: secret/aws-access-key, secret/aws-secret-key`. Splitting on commas and whitespace and keeping a set means the check is a membership test, and a duplicate id costs nothing.\n\n### The line-local decision\n\nA marker suppresses the line it sits on, not the block below it. That is deliberate: a block-level suppression would silence rules the author never considered, and the whole point of naming an id is to say which rule you have thought about. If you need three lines suppressed, you write three markers — and a reviewer sees three.\n\n### What a marker cannot do\n\nIt cannot suppress a finding a rule made about a different line, and it cannot suppress a parse error. It is a comment in the source under review, so a file that is not parsed as Python has no markers at all — which is why a suppression in a YAML file does nothing.",
  "code_examples": [
    {
      "id": "8.5-ex-0",
      "lang": "python",
      "caption": "Bare, targeted and absent",
      "code": "from app.rules import _suppressed_ids\n\nfor text in (\"x = 1  # noqa\", \"x = 1  # noqa: secret/aws-access-key\", \"x = 1  # nosec: injection/eval\", \"x = 1\"):\n    print(\"%-40s -> %s\" % (text, _suppressed_ids(text)))",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "x = 1  # noqa                            -> (True, set())\nx = 1  # noqa: secret/aws-access-key     -> (False, {'secret/aws-access-key'})\nx = 1  # nosec: injection/eval           -> (False, {'injection/eval'})\nx = 1                                    -> (False, set())",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py",
        "app/rules.py"
      ]
    }
  ],
  "quiz": [
    {
      "q": "What does a bare `# noqa` suppress?",
      "options": [
        "Every rule in the file",
        "Every rule on that one line",
        "Only CRITICAL rules",
        "Nothing until an id is named"
      ],
      "answer": 1,
      "why": "It returns `(True, set())` — suppress all, on that line. The scope is the line, never the block."
    },
    {
      "q": "Why accept both `noqa` and `nosec`?",
      "options": [
        "One is for Python, one for YAML files",
        "The regex needs two branches",
        "They are the flake8 and bandit names",
        "Bandit rules are stricter than flake8"
      ],
      "answer": 2,
      "why": "Two established conventions, one marker: a reader arriving from either tool does not have to learn a third spelling."
    },
    {
      "q": "What does the targeted form return?",
      "options": [
        "An error if the id is unknown",
        "Suppress all, plus the named ids, which is what a bare marker does",
        "Suppress all, with an empty set",
        "Suppress nothing, plus the named ids"
      ],
      "answer": 3,
      "why": "`(False, ids)` — the first element is the bare-marker flag, and the ids are what the caller tests membership against."
    }
  ],
  "try_it": {
    "prompt": "Print what a marker naming two rules returns.",
    "starter": "",
    "solution": "```python\nfrom app.rules import _suppressed_ids\n\nprint(_suppressed_ids(\"x = 1  # noqa: secret/a, secret/b\"))\n```",
    "explanation": "Two ids in one set, and the bare flag false — the marker names what it silences."
  },
  "exercise": {
    "prompt": "Does `# noqa` on one line silence the same rule three lines below? Prove it.",
    "hint": "The marker is matched per line; look at how the caller uses the pair.",
    "solution": "```python\nfrom app.rules import LineContext, RULES, _suppressed_ids\n\nprint(_suppressed_ids(\"x = 1  # noqa\"))\nprint(_suppressed_ids(\"x = 1\"))\n```\n\n`(True, set())` then `(False, set())` — the second line has no marker, so nothing is suppressed there.",
    "explanation": "Suppression is a property of a line, so a marker cannot reach another line even one below it."
  },
  "common_mistakes": [
    "Expecting a bare `# noqa` to cover the block beneath it.",
    "Naming an id that does not exist, which suppresses nothing and hides the typo.",
    "Adding a marker in a test file where `skip_tests` already handles it."
  ],
  "project_links": [
    {
      "label": "The marker regex",
      "path": "app/rules.py",
      "lines": "334"
    },
    {
      "label": "The helper that reads it",
      "path": "app/rules.py",
      "lines": "1494-1512"
    }
  ],
  "learn_more": [
    {
      "label": "app/rules.py — the rule engine",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/rules.py"
    },
    {
      "label": "tests/test_rules.py — the rule tests",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/tests/test_rules.py"
    }
  ],
  "glossary_terms": [
    "suppression — a marker that silences a rule on its own line",
    "bare marker — a suppression with no ids, silencing every rule",
    "targeted marker — a suppression naming the ids it silences"
  ]
});
