/* 8.10 — Guided read and rebuild against the rule tests
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "8.10",
  "part": 8,
  "part_title": "The rule engine",
  "title": "Guided read and rebuild against the rule tests",
  "order": 810,
  "duration_min": 30,
  "concept_md": "### Reading the file in order\n\n`app/rules.py` is 1615 lines and reads in five parts. **The types** — `RuleCategory`, `RuleHit`, `LineContext`, `Rule` — at the top, because everything below uses them. **The registry machinery** — `RULES`, `_register`, `_rule`, `_pattern_rule` — next, so a rule can be declared before it is written. **The helpers** — entropy, comment stripping, the marker regex — which the checks call. **The checks**, one function each, in registration order. **The entry points** — `review_lines` and `review_diff` — which walk the lines and call every rule.\n\n### Why that order\n\nReading top to bottom, no name is used before it is defined, and the file can be imported without side effects beyond building the registry. The same property makes it testable: importing the module gives you the whole rule set with nothing running.\n\n### The rebuild exercise\n\n`rebuild/tests/test_rebuild_rules.py` is a small suite you can run against your own implementation. Start with `Rule`, `RuleHit` and `LineContext`; add two rules; then run the tests and read the failures — they are written to name the missing behaviour rather than a line number.\n\n### What to look for as you read\n\nEvery check returns either `None` or a hit, never a list. Every regex goes through `scan_text`. Every rule has a citation. When those three hold across 63 functions, the file is consistent; when one does not, that is the bug.",
  "code_examples": [
    {
      "id": "8.10-ex-0",
      "lang": "console",
      "caption": "The types come first, then the registry machinery",
      "code": "grep -n '^class \\|^def ' app/rules.py | head -6",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "the browser runner has Python but no shell, so this command cannot run there; it needs a checkout on disk.",
      "expected_output": "59:class RuleCategory(str, Enum):\n75:class RuleHit:\n83:class LineContext:\n113:class Rule:\n128:def _register(rule: Rule) -> None:\n133:def _rule("
    },
    {
      "id": "8.10-ex-1",
      "lang": "console",
      "caption": "The rebuild suite skips until you write the module, then runs",
      "code": "python -m pytest -q rebuild/tests/test_rebuild_rules.py 2>&1 | tail -3",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "the browser runner has Python but no shell, so this command cannot run there; it needs a checkout on disk.",
      "expected_output": "sssss                                                                    [100%]\n5 skipped in 0.35s"
    }
  ],
  "quiz": [
    {
      "q": "Which part of the file must come first?",
      "options": [
        "The entry points, which are the public surface",
        "The checks, which are the content",
        "The types, which everything uses",
        "The registry, which is a plain list"
      ],
      "answer": 2,
      "why": "Reading top to bottom, no name is used before it is defined, which is also what makes the module importable without side effects."
    },
    {
      "q": "What does importing the module give you?",
      "options": [
        "A review of the current directory, walking every file it finds",
        "A live model-provider connection",
        "A database handle",
        "The whole registry, nothing running"
      ],
      "answer": 3,
      "why": "The only import-time work is building the registry, which is why the rule layer is provable offline."
    },
    {
      "q": "What shape does every check function return?",
      "options": [
        "`None` or a single `RuleHit`",
        "A list of hits, possibly empty",
        "A boolean",
        "A tuple of hit and line number"
      ],
      "answer": 0,
      "why": "One line, one hit: the engine accumulates across lines, so a check that returned a list would duplicate that job."
    }
  ],
  "try_it": {
    "prompt": "Count the check functions and compare with the registry size.",
    "starter": "",
    "solution": "```console\n$ grep -c \"^def _check_\" app/rules.py\n$ python -c \"from app.rules import RULES; print(len(RULES))\"\n```",
    "explanation": "There are fewer hand-written checks than rules, because most rules are declared with `_pattern_rule`."
  },
  "exercise": {
    "prompt": "Read `_check_sql_injection` and name the one thing it checks that a pure regex could not.",
    "hint": "It looks at the sibling lines, not only its own.",
    "solution": "```console\n$ sed -n '625,650p' app/rules.py\n```\n\nIt inspects surrounding added lines for the concatenation that makes the string a query, which is why it is hand-written rather than a pattern rule.",
    "explanation": "The sibling lines are in the context for exactly this: a check that needs a little more than its own line, but not the whole file."
  },
  "common_mistakes": [
    "Writing a check that returns a list; the engine accumulates.",
    "Calling `re.search` on `ctx.text` instead of `ctx.scan_text`.",
    "Adding a rule without registering it, so the registry and the file disagree."
  ],
  "project_links": [
    {
      "label": "The entry point that walks the lines",
      "path": "app/rules.py",
      "lines": "1515-1568"
    },
    {
      "label": "The rebuild suite",
      "path": "rebuild/tests/test_rebuild_rules.py",
      "lines": "1-86"
    }
  ],
  "learn_more": [
    {
      "label": "app/rules.py — the rule engine",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/rules.py"
    },
    {
      "label": "rebuild/README.md — the rebuild exercises",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/rebuild/README.md"
    }
  ],
  "glossary_terms": [
    "guided read — a walk through a file in dependency order",
    "rebuild exercise — reimplementing a module against its tests",
    "entry point — the function a caller uses to run the rules"
  ]
});
