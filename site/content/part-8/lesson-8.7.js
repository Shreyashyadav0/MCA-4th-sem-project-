/* 8.7 — The OWASP mapping and the gaps
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "8.7",
  "part": 8,
  "part_title": "The rule engine",
  "title": "The OWASP mapping and the gaps",
  "order": 807,
  "duration_min": 30,
  "concept_md": "### Every rule carries a citation\n\nEach `Rule` has an `owasp` string — `A02:2021-Cryptographic Failures`, `A03:2021-Injection` — and the registry holds nine distinct values across 63 rules. That is a claim a reader can check: this check is an instance of that published category.\n\n### Why it is a string and not an enum\n\nBecause the citation must be quotable in a report and readable in a JSON response without a lookup table. A string also lets a future rule cite something the enum does not yet name.\n\n### The gaps are real\n\nNine of the ten 2021 entries are cited. The one nothing cites is `A06:2021-Vulnerable and Outdated Components` — a dependency pin is not visible on an added line, so no rule can claim it. `A04:2021-Insecure Design` *is* cited, by eleven rules, which is the tool saying a design smell can sometimes be seen in a single line. That is the honest reading: the mapping says what each rule is an instance of, not that the tool covers the OWASP Top Ten.\n\n### What to do with it\n\nIn a report, group by citation to show which class of defect a change introduces. In a review, a rule with a citation is arguable; a rule without one is opinion. If you add a rule, add its citation — and if there is none, say so rather than inventing one.",
  "code_examples": [
    {
      "id": "8.7-ex-0",
      "lang": "python",
      "caption": "The nine citations, and which category uses each",
      "code": "from collections import Counter, defaultdict\nfrom app.rules import RULES\n\nby_cat = defaultdict(set)\nfor r in RULES:\n    by_cat[r.category.value].add(r.owasp.split(\":\")[0])\n\nprint(\"distinct citations:\", len({r.owasp for r in RULES}))\nfor cat, refs in sorted(by_cat.items()):\n    print(\"%-16s %s\" % (cat, sorted(refs)))",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "distinct citations: 9\nauth             ['A01', 'A07']\ncomplexity       ['A04']\nconfig           ['A05']\ncrypto           ['A02']\ndeserialisation  ['A08']\ninjection        ['A01', 'A03', 'A10']\nquality          ['A04', 'A09']\nreliability      ['A04']\nsecrets          ['A02', 'A07']\nstyle            ['A04', 'A09']",
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
      "q": "What does a rule's `owasp` field assert?",
      "options": [
        "The tool covers the whole Top Ten",
        "OWASP audited this rule",
        "The rule is therefore CRITICAL",
        "This check is an instance of"
      ],
      "answer": 3,
      "why": "It is a citation for one check, not a coverage claim about the ten categories."
    },
    {
      "q": "Why is the citation a string rather than an enum?",
      "options": [
        "So it can be quoted and read in JSON",
        "So it can be translated later",
        "So it can be sorted alphabetically in the report's citation column",
        "Because enums cannot hold a colon"
      ],
      "answer": 0,
      "why": "The report and the API both show the text; a string also lets a new rule cite something the enum has not named."
    },
    {
      "q": "Which 2021 entry does no rule cite?",
      "options": [
        "A06, vulnerable and outdated components",
        "A04, insecure design",
        "A02, cryptographic failures",
        "A10, server-side request forgery, which one rule does cite"
      ],
      "answer": 0,
      "why": "A dependency version is not visible on an added line, so no line-local rule can claim that entry; A04 is cited by eleven rules."
    }
  ],
  "try_it": {
    "prompt": "Print every rule that cites injection.",
    "starter": "",
    "solution": "```python\nfrom app.rules import RULES\n\nfor r in RULES:\n    if \"Injection\" in r.owasp:\n        print(r.id, \"|\", r.owasp)\n```",
    "explanation": "A02 (cryptographic failures) is the largest group with 20 rules; A03 covers 11 of the 14 injection rules, because three of them cite a neighbouring weakness."
  },
  "exercise": {
    "prompt": "Which category maps to the most distinct OWASP citations, and which to the fewest? Check it.",
    "hint": "Group by category and count distinct citations.",
    "solution": "```python\nfrom collections import defaultdict\nfrom app.rules import RULES\n\nm = defaultdict(set)\nfor r in RULES:\n    m[r.category.value].add(r.owasp)\nfor cat, refs in sorted(m.items(), key=lambda p: -len(p[1])):\n    print(cat, len(refs))\n```",
    "explanation": "The spread shows where a category draws on more than one published weakness."
  },
  "common_mistakes": [
    "Reading the citation as proof of OWASP coverage.",
    "Adding a rule without a citation, or inventing one.",
    "Assuming every category maps to a distinct citation."
  ],
  "project_links": [
    {
      "label": "The owasp field on a rule",
      "path": "app/rules.py",
      "lines": "119"
    },
    {
      "label": "Where the citation is registered",
      "path": "app/rules.py",
      "lines": "133-142"
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
    "citation — the OWASP category a rule is an instance of",
    "coverage — what a citation does not claim",
    "Top Ten — the published list the citations point into"
  ]
});
