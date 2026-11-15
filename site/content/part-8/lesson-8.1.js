/* 8.1 — Anatomy of a rule
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "8.1",
  "part": 8,
  "part_title": "The rule engine",
  "title": "Anatomy of a rule",
  "order": 801,
  "duration_min": 25,
  "concept_md": "### Six fields and a function\n\nA rule is a small frozen record plus one callable:\n\n```python\n@dataclass(frozen=True, slots=True)\nclass Rule:\n    id: str\n    title: str\n    category: RuleCategory\n    owasp: str\n    severity: Severity\n    check: Callable[[LineContext], RuleHit | None]\n```\n\n`id` is the stable name — `secret/hardcoded-credential` — and it is what a `# noqa` names. `severity` is fixed per rule, not decided per hit, so the same mistake is never CRITICAL in one file and LOW in another.\n\n### What a rule is given and what it returns\n\nIt receives a `LineContext`: the path, the line number, the text, and the sibling added lines. It returns either `None` or a `RuleHit` carrying two strings:\n\n```python\n@dataclass(frozen=True, slots=True)\nclass RuleHit:\n    issue: str\n    suggested_fix: str\n```\n\nNotice what is *not* in the hit: the file, the line and the severity. Those belong to the rule and the context, so a rule cannot disagree with itself about where it fired.\n\n### Why the split matters\n\nBecause the check is a plain function of one line, it can be tested with a string literal — no file, no diff, no engine. Every rule on this site is exercised that way, which is why the rule layer can be proven offline while the model layer cannot.",
  "code_examples": [
    {
      "id": "8.1-ex-0",
      "lang": "python",
      "caption": "One rule, its fields, and what it returns",
      "code": "from app.rules import RULES, LineContext\n\nrule = RULES[0]\nprint(rule.id, \"|\", rule.category.value, \"|\", rule.severity.value)\nprint(rule.title)\n\nctx = LineContext(path=\"app/demo.py\", lineno=1, text=\"\", added=(), index=0)\nhit = rule.check(ctx)\nprint(\"fires on a blank line:\", hit)",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "secret/hardcoded-credential | secrets | CRITICAL\nHardcoded credential\nfires on a blank line: None",
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
      "q": "What does a `RuleHit` deliberately not carry?",
      "options": [
        "The issue and the suggested fix",
        "The file, the line and the grade",
        "The rule id and its short title",
        "The category and the citation"
      ],
      "answer": 1,
      "why": "Those three come from the context and the rule, so a hit cannot contradict the rule about where it fired or how serious it is."
    },
    {
      "q": "Why is `severity` fixed on the rule rather than chosen per hit?",
      "options": [
        "So the enum can be sorted",
        "Because the context has no grade",
        "So one mistake is never graded two ways",
        "Because Pydantic forbids a per-hit grade"
      ],
      "answer": 2,
      "why": "A rule that graded itself per hit would make the verdict depend on where the code sat, which is the opposite of a rule."
    },
    {
      "q": "What makes a single rule testable without a diff?",
      "options": [
        "The rule is registered at import time",
        "The registry is a module-level list",
        "`LineContext` is a frozen dataclass",
        "`check` takes one context and returns"
      ],
      "answer": 3,
      "why": "A pure function of one context can be called with a literal, which is why the rule layer is proven offline and the model layer is not."
    }
  ],
  "try_it": {
    "prompt": "Print the id and severity of the first five rules.",
    "starter": "",
    "solution": "```python\nfrom app.rules import RULES\n\nfor rule in RULES[:5]:\n    print(rule.id, rule.severity.value)\n```",
    "explanation": "The ids read like paths — `secret/…`, `injection/…` — because the category is the first segment."
  },
  "exercise": {
    "prompt": "How many fields does a `Rule` have, and which one makes the rule findable by a `# noqa` comment?",
    "hint": "Count the dataclass fields; the comment names one of them.",
    "solution": "```text\nSix fields: id, title, category, owasp, severity, check.\n\nThe id — that is the string a targeted # noqa names, e.g. noqa: secret/hardcoded-credential.\n```",
    "explanation": "The id is both the stable name and the suppression handle, which is why it is a path-like string rather than a number."
  },
  "common_mistakes": [
    "Returning a severity from `check`, which the rule already owns.",
    "Treating `id` as a display label; it is the stable name a suppression names.",
    "Testing a rule through the engine when calling `check` with a literal would do."
  ],
  "project_links": [
    {
      "label": "The Rule record",
      "path": "app/rules.py",
      "lines": "113-125"
    },
    {
      "label": "RuleHit, the two strings a rule returns",
      "path": "app/rules.py",
      "lines": "75-79"
    },
    {
      "label": "LineContext, what a rule is given",
      "path": "app/rules.py",
      "lines": "83-109"
    }
  ],
  "learn_more": [
    {
      "label": "app/rules.py — the rule engine",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/rules.py"
    },
    {
      "label": "rebuild/tests/test_rebuild_rules.py",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/rebuild/tests/test_rebuild_rules.py"
    }
  ],
  "glossary_terms": [
    "rule — a named check with one fixed severity and category",
    "rule hit — the issue and the fix a firing rule returns",
    "line context — the line a rule sees, plus its path and number"
  ]
});
