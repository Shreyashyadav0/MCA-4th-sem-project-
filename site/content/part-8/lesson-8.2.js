/* 8.2 — RuleCategory and its ten members
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "8.2",
  "part": 8,
  "part_title": "The rule engine",
  "title": "RuleCategory and its ten members",
  "order": 802,
  "duration_min": 20,
  "concept_md": "### Ten names, one enum\n\n```python\nclass RuleCategory(str, Enum):\n    SECRETS = \"secrets\"\n    INJECTION = \"injection\"\n    DESERIALISATION = \"deserialisation\"\n    CRYPTO = \"crypto\"\n    AUTH = \"auth\"\n    CONFIG = \"config\"\n    RELIABILITY = \"reliability\"\n    QUALITY = \"quality\"\n    COMPLEXITY = \"complexity\"\n    STYLE = \"style\"\n```\n\nIt subclasses `str`, so a category serialises as `\"secrets\"` and a client filters on that text.\n\n### What the categories are for\n\nThree jobs, none of them cosmetic. They group the report so a reviewer can skip style and read secrets first. They are a filter on `review_lines(categories=…)`, so a caller can ask for injection only. And they are the first segment of every rule id, which is why `secret/hardcoded-credential` sits under `SECRETS`.\n\n### Why ten and not fewer\n\nThe four that look mergeable — `quality`, `complexity`, `style`, `reliability` — answer different questions. `complexity` is about the shape of the control flow, `style` about naming and layout, `quality` about the code's own hygiene, `reliability` about what breaks under load or at a boundary. Merging them would make the report's first column meaningless.\n\n### The count is checked\n\n`test_registry_covers_every_category` fails if a category has no rules, so the enum cannot grow a member that nothing uses.\n\n### Reading the enum in a report\n\nThe member name and the value differ in case — `DESERIALISATION` against `deserialisation` — so a report that prints the member rather than the value will not match a client that filters on the text. Print `.value`.",
  "code_examples": [
    {
      "id": "8.2-ex-0",
      "lang": "python",
      "caption": "The ten members, and how many rules each holds",
      "code": "from collections import Counter\nfrom app.rules import RULES, RuleCategory\n\nprint(\"members:\", len(RuleCategory))\nfor name, count in Counter(r.category.value for r in RULES).most_common():\n    print(\"%-16s %d\" % (name, count))",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "members: 10\nsecrets          15\ninjection        14\nconfig           7\ncrypto           6\nquality          5\ndeserialisation  4\nstyle            4\nauth             3\ncomplexity       3\nreliability      2",
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
      "q": "What does `RuleCategory` being a `str` enum give you?",
      "options": [
        "The enum can hold duplicate values",
        "Categories can be compared as integers",
        "A category serialises as its own text",
        "Rules can be sorted by category name"
      ],
      "answer": 2,
      "why": "The JSON and the display text are the same string, so a client filters on `secrets` without an enum encoder."
    },
    {
      "q": "Which job do categories NOT do?",
      "options": [
        "Prefix each rule id",
        "Group the report for a reader",
        "Filter which rules run",
        "Decide a finding's severity"
      ],
      "answer": 3,
      "why": "Severity is a field on the rule; the category groups, filters and namespaces, but it never grades."
    },
    {
      "q": "Why are `quality`, `complexity`, `style` and `reliability` kept apart?",
      "options": [
        "Each answers a different question",
        "Because merging would break ids",
        "Because the enum needs ten members",
        "Because the API exposes them"
      ],
      "answer": 0,
      "why": "Control-flow shape, naming, hygiene and failure-at-a-boundary are different diagnoses; merging them makes the first column of the report say nothing."
    }
  ],
  "try_it": {
    "prompt": "Print the category that holds the most rules and the one that holds the fewest.",
    "starter": "",
    "solution": "```python\nfrom collections import Counter\nfrom app.rules import RULES\n\nc = Counter(r.category.value for r in RULES)\nprint(c.most_common(1), c.most_common()[-1])\n```",
    "explanation": "Secrets leads and reliability trails, which matches what the tool is for: leaked credentials are the failure that matters most."
  },
  "exercise": {
    "prompt": "Which categories contain no rule at all, and what would the test suite do about it?",
    "hint": "Run a counter over the categories and compare with the enum's members.",
    "solution": "```python\nfrom collections import Counter\nfrom app.rules import RULES, RuleCategory\n\nused = {r.category for r in RULES}\nprint([c.value for c in RuleCategory if c not in used])\n```\n\nIt prints `[]`. If it did not, `test_registry_covers_every_category` would fail.",
    "explanation": "The empty list is the assertion: an enum member with no rule behind it is a promise the report cannot keep."
  },
  "common_mistakes": [
    "Adding a category without a rule, which the registry test catches.",
    "Filtering on the enum member instead of its `.value` in JSON.",
    "Assuming the category decides severity; it does not."
  ],
  "project_links": [
    {
      "label": "The ten-member enum",
      "path": "app/rules.py",
      "lines": "59-71"
    },
    {
      "label": "The registry the categories describe",
      "path": "app/rules.py",
      "lines": "113-130"
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
    "category — the coarse group a rule belongs to",
    "filter — restricting a run to some categories",
    "namespace — the first segment of a rule id"
  ]
});
