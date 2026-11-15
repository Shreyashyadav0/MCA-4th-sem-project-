/* 8.3 — The 63 rules by category
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "8.3",
  "part": 8,
  "part_title": "The rule engine",
  "title": "The 63 rules by category",
  "order": 803,
  "duration_min": 30,
  "concept_md": "### The shape of the set\n\nSixty-three rules, and they are not spread evenly. Secrets holds 15 and injection 14; reliability holds 2 and auth 3. That distribution is the design: the tool exists to catch the mistakes that leak credentials and execute attacker-controlled strings, not to nag about naming.\n\n### Why the count is a constant\n\n`RULE_COUNT` is exported and asserted against `len(RULES)`, so the number in a report and the number in the registry cannot drift. A test also checks the severity spread, so a wave of new CRITICAL rules fails rather than passing quietly.\n\n### Reading the registry\n\nEach entry is a `Rule`; the ids are stable strings; the categories group them. `RULES` is a plain list, built at import time by `_register`, so its order is registration order — which is a contract, and lesson 8.8's subject.\n\n### What the number is not\n\nIt is not a coverage claim. Sixty-three rules is not \"63 classes of bug found\"; it is 63 regexes and hand-written checks over added lines. A file with no additions gets no findings at all, whatever it contains.\n\n### Where the number comes from\n\n`RULE_COUNT` is assigned once, at import, from `len(RULES)`. Nothing recomputes it later, so a rule added to the list without the constant being re-read would be a bug — which is why the test compares the two rather than trusting either.",
  "code_examples": [
    {
      "id": "8.3-ex-0",
      "lang": "python",
      "caption": "Every category, its rules, and the total",
      "code": "from collections import Counter\nfrom app.rules import RULE_COUNT, RULES\n\nprint(\"RULE_COUNT:\", RULE_COUNT, \"| len(RULES):\", len(RULES))\nfor name, count in sorted(Counter(r.category.value for r in RULES).items(), key=lambda p: -p[1]):\n    print(\"%-16s %2d\" % (name, count))\nprint(\"total           %2d\" % sum(1 for _ in RULES))",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "RULE_COUNT: 63 | len(RULES): 63\nsecrets          15\ninjection        14\nconfig            7\ncrypto            6\nquality           5\ndeserialisation   4\nstyle             4\nauth              3\ncomplexity        3\nreliability       2\ntotal           63",
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
      "q": "Which two categories hold the most rules?",
      "options": [
        "Config and reliability",
        "Style and quality",
        "Auth and crypto",
        "Secrets and injection"
      ],
      "answer": 3,
      "why": "15 and 14 — the tool is aimed at leaked credentials and injected strings, which is why those two dominate the registry."
    },
    {
      "q": "What does `RULE_COUNT` protect?",
      "options": [
        "The report number and the registry",
        "The ids from being renamed",
        "The enum from gaining a member",
        "The severities from being reordered"
      ],
      "answer": 0,
      "why": "It is exported and compared with `len(RULES)`, so a rule added without updating the constant fails a test instead of a report."
    },
    {
      "q": "What does 63 rules NOT mean?",
      "options": [
        "That the registry holds 63 entries",
        "That 63 classes of bug are covered",
        "That every rule has a category",
        "That every rule has an OWASP mapping"
      ],
      "answer": 1,
      "why": "They are checks over added lines; a file with no additions yields no findings regardless of what it contains."
    }
  ],
  "try_it": {
    "prompt": "Print the severity mix across all 63 rules.",
    "starter": "",
    "solution": "```python\nfrom collections import Counter\nfrom app.rules import RULES\n\nprint(Counter(r.severity.value for r in RULES))\n```",
    "explanation": "Most rules are HIGH or CRITICAL, and only seven are LOW — a distribution lesson 8.6 explains."
  },
  "exercise": {
    "prompt": "Which category is third-smallest by rule count, and how many rules does it hold?",
    "hint": "Sort the counter ascending and take the third entry.",
    "solution": "```python\nfrom collections import Counter\nfrom app.rules import RULES\n\nc = Counter(r.category.value for r in RULES)\nprint(sorted(c.items(), key=lambda p: p[1]))\n```\n\nReliability 2, then auth 3 and complexity 3 tied — the third category in count order is complexity with 3.",
    "explanation": "The concept names the two smallest; the third needs the counter."
  },
  "common_mistakes": [
    "Quoting a rule count without reading `RULE_COUNT` at this commit.",
    "Reading 63 as a coverage claim rather than a registry size.",
    "Assuming the categories are evenly populated."
  ],
  "project_links": [
    {
      "label": "The exported count",
      "path": "app/rules.py",
      "lines": "1491"
    },
    {
      "label": "Registration, which builds the list",
      "path": "app/rules.py",
      "lines": "128-130"
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
    "registry — the list every rule is registered into",
    "RULE_COUNT — the exported size, asserted against the list",
    "spread — how rules are distributed across severities"
  ]
});
