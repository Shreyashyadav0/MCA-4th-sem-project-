/* 8.8 — The rule registry and why order is a contract
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "8.8",
  "part": 8,
  "part_title": "The rule engine",
  "title": "The rule registry and why order is a contract",
  "order": 808,
  "duration_min": 20,
  "concept_md": "### A list built at import time\n\n`RULES` starts empty and `_register` appends. Because Python runs the module top to bottom, the list ends up in the order the decorators and factory calls appear in the file. That order is visible in the report, in `RULE_COUNT`, and in any test that indexes `RULES[0]`.\n\n### Why that is a contract\n\nTwo reasons. A report that reordered itself between runs would make a diff of two reports useless. And a test that asserts `RULES[0].id` is asserting registration order, so inserting a rule in the middle is a deliberate act with a visible consequence.\n\n### What registration does not do\n\nIt does not sort, deduplicate or validate. A duplicate id would be registered twice and nothing would complain — which is why the ids are checked in review rather than at runtime. The registry is a list, not a set, because order matters and the cost of a duplicate is small.\n\n### The stable part\n\nIds are stable strings; the position is not. Code that needs a rule looks it up by id — `RULES_BY_ID` exists for exactly that — so a reordering cannot break a caller.\n\n### What the list is not\n\nIt is not a plugin registry. Nothing discovers rules from a directory or an entry point; every rule is declared in this one module, which is why the file is 1615 lines and why its import cost is fixed.",
  "code_examples": [
    {
      "id": "8.8-ex-0",
      "lang": "python",
      "caption": "Registration order is the list's order",
      "code": "from app.rules import RULES, RULES_BY_ID\n\nprint(\"first three:\", [r.id for r in RULES[:3]])\nprint(\"lookup by id :\", RULES_BY_ID[\"unsafe/sql-injection\"].id)\nprint(\"ids are unique:\", len({r.id for r in RULES}) == len(RULES))",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "first three: ['secret/hardcoded-credential', 'secret/aws-access-key', 'secret/aws-secret-key']\nlookup by id : unsafe/sql-injection\nids are unique: True",
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
      "q": "Why is `RULES` a list rather than a set?",
      "options": [
        "Because registration order is visible",
        "Because a list searches much faster",
        "Because sets cannot hold dataclasses",
        "Because duplicate ids are impossible"
      ],
      "answer": 0,
      "why": "The report and the tests both read position, so the order has to be stable and intentional."
    },
    {
      "q": "What does registration NOT check?",
      "options": [
        "That the severity is set",
        "That the id is unique",
        "That the category is an enum",
        "That a check is callable"
      ],
      "answer": 1,
      "why": "A duplicate id would register twice silently; uniqueness is enforced by review, not at runtime."
    },
    {
      "q": "What should a caller use to find one rule?",
      "options": [
        "The index into `RULES`, because it is ordered",
        "The category filter, because it is smaller",
        "`RULES_BY_ID`, because ids are stable",
        "A scan of `RULES` by title"
      ],
      "answer": 2,
      "why": "A reordering changes every index but no id, so lookup by id survives a registry change."
    }
  ],
  "try_it": {
    "prompt": "Print how many rules would be lost if duplicates were dropped.",
    "starter": "",
    "solution": "```python\nfrom app.rules import RULES\n\nids = [r.id for r in RULES]\nprint(len(ids) - len(set(ids)), \"duplicate ids\")\n```",
    "explanation": "It prints 0 — the registry is clean today, which is a fact worth checking rather than assuming."
  },
  "exercise": {
    "prompt": "Which rule sits at index 30, and would a caller that hard-coded that index survive a new rule inserted at index 5?",
    "hint": "Print the id at 30, then consider what insertion does to every index after it.",
    "solution": "```python\nfrom app.rules import RULES\n\nprint(RULES[30].id)\n```\n\nThe id is stable; index 30 is not, so the hard-coded caller would now get a different rule.",
    "explanation": "That is the difference between an id and a position, and why `RULES_BY_ID` exists."
  },
  "common_mistakes": [
    "Indexing `RULES` in application code instead of looking up by id.",
    "Assuming the registry sorts or deduplicates.",
    "Inserting a rule mid-file without checking what indexes it."
  ],
  "project_links": [
    {
      "label": "The registry list",
      "path": "app/rules.py",
      "lines": "113-130"
    },
    {
      "label": "Lookup by id",
      "path": "app/rules.py",
      "lines": "1490-1491"
    }
  ],
  "learn_more": [
    {
      "label": "app/rules.py — the rule engine",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/rules.py"
    },
    {
      "label": "tests/test_rules.py — the registry tests",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/tests/test_rules.py"
    }
  ],
  "glossary_terms": [
    "registry — the ordered list of registered rules",
    "registration — appending a rule at import time",
    "stable id — a name that survives reordering"
  ]
});
