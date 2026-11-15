/* 8.6 — Severity assignment discipline
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "8.6",
  "part": 8,
  "part_title": "The rule engine",
  "title": "Severity assignment discipline",
  "order": 806,
  "duration_min": 20,
  "concept_md": "### The ladder, and who climbs it\n\nFour values — LOW, MEDIUM, HIGH, CRITICAL — with `rank` giving 0 to 3. The verdict blocks on CRITICAL or HIGH. So severity is not a label; it is the input to the gate decision.\n\n### Fixed per rule\n\nA rule is registered with its severity. `secret/hardcoded-credential` is CRITICAL wherever it fires. That is the discipline: the grade belongs to the mistake, not to the file it happened in. If the same mistake were CRITICAL in `app/main.py` and LOW in a script, the verdict would depend on where code lived, which is indefensible.\n\n### The distribution is a design statement\n\nSeventeen CRITICAL, twenty-three HIGH, sixteen MEDIUM, seven LOW. Most rules sit in the top half because the registry is aimed at security defects. A tool where most rules were LOW would be a linter; this one is meant to block.\n\n### What a test protects\n\n`test_severity_spread_is_sane` asserts the shape of the distribution, so a wave of new CRITICAL rules fails the suite rather than silently making everything block. That is a rule about the rules, and it is the kind of check that only exists when someone has been burned by severity inflation.",
  "code_examples": [
    {
      "id": "8.6-ex-0",
      "lang": "python",
      "caption": "The distribution, and what it decides",
      "code": "from collections import Counter\nfrom app.models import verdict_for\nfrom app.rules import RULES\nfrom app.models import Finding\n\nprint(Counter(r.severity.value for r in RULES))\n\nfor sev in (\"CRITICAL\", \"HIGH\", \"MEDIUM\", \"LOW\"):\n    f = Finding(file=\"a.py\", line=\"1\", severity=sev, issue=\"x\", suggested_fix=\"y\")\n    print(\"%-9s -> %s\" % (sev, verdict_for([f])))",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "Counter({'HIGH': 23, 'CRITICAL': 17, 'MEDIUM': 16, 'LOW': 7})\nCRITICAL  -> block\nHIGH      -> block\nMEDIUM    -> approve with comments\nLOW       -> approve with comments",
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
      "q": "Where is a rule's severity decided?",
      "options": [
        "By the file the line sits inside, not the rule",
        "By the run's own finding count",
        "At registration, never per hit",
        "By the category's default value"
      ],
      "answer": 2,
      "why": "The grade belongs to the mistake; deciding it per hit would make the verdict depend on where the code lived."
    },
    {
      "q": "Which severities block the verdict?",
      "options": [
        "Every severity above LOW",
        "CRITICAL only",
        "CRITICAL, HIGH and MEDIUM",
        "CRITICAL and HIGH"
      ],
      "answer": 3,
      "why": "`verdict_for` blocks on those two and approves with comments for MEDIUM and LOW."
    },
    {
      "q": "What does `test_severity_spread_is_sane` guard against?",
      "options": [
        "Inflation making every run block",
        "A category losing its last rule",
        "A rule registered twice by mistake",
        "An id being renamed by a wave"
      ],
      "answer": 0,
      "why": "It asserts the shape of the distribution, so adding a wave of CRITICAL rules fails the suite instead of silently changing every verdict."
    }
  ],
  "try_it": {
    "prompt": "Print the rank of each severity, lowest first.",
    "starter": "",
    "solution": "```python\nfrom app.models import Severity\n\nfor s in Severity:\n    print(s.value, s.rank)\n```",
    "explanation": "LOW is 0 and CRITICAL is 3, which is what `sort_findings` orders by."
  },
  "exercise": {
    "prompt": "Which single severity change would flip a review from approve-with-comments to block? Name it and show the two verdicts.",
    "hint": "Look at the threshold in `verdict_for`.",
    "solution": "```python\nfrom app.models import Finding, verdict_for\n\nfor sev in (\"MEDIUM\", \"HIGH\"):\n    f = Finding(file=\"a.py\", line=\"1\", severity=sev, issue=\"x\", suggested_fix=\"y\")\n    print(sev, verdict_for([f]))\n```\n\nMEDIUM approves with comments; HIGH blocks.",
    "explanation": "One step on the ladder is the difference between a comment and a block, which is why the grade is fixed per rule."
  },
  "common_mistakes": [
    "Raising a rule's severity to make a demo look decisive.",
    "Grading a finding by the file it sits in rather than by the mistake.",
    "Assuming MEDIUM blocks; it approves with comments."
  ],
  "project_links": [
    {
      "label": "The ladder and its rank",
      "path": "app/models.py",
      "lines": "46-57"
    },
    {
      "label": "The verdict the ladder decides",
      "path": "app/models.py",
      "lines": "141-148"
    }
  ],
  "learn_more": [
    {
      "label": "app/models.py — the models",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/models.py"
    },
    {
      "label": "tests/test_rules.py — the severity-spread test",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/tests/test_rules.py"
    }
  ],
  "glossary_terms": [
    "severity — the fixed grade a rule carries",
    "rank — the integer a severity sorts by",
    "verdict — the gate decision the severities produce"
  ]
});
