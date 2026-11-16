/* 8.4 — Regex matchers and line-local evaluation
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "8.4",
  "part": 8,
  "part_title": "The rule engine",
  "title": "Regex matchers and line-local evaluation",
  "order": 804,
  "duration_min": 25,
  "concept_md": "### Two ways to make a rule\n\nHand-written, with `_rule`, when the check needs to look at more than the line. Declarative, with `_pattern_rule`, when it does not:\n\n```python\ndef check(ctx: LineContext) -> RuleHit | None:\n    if skip_tests and ctx.is_test_file:\n        return None\n    text = ctx.scan_text\n    if pattern.search(text) is None:\n        return None\n    if exempt is not None and exempt.search(text) is not None:\n        return None\n    return RuleHit(issue=issue, suggested_fix=suggested_fix)\n```\n\nThat is the whole contract of a pattern rule: skip test files if asked, search, honour an exemption, return a hit. No rule passes the flag today, but two hand-written checks test `ctx.is_test_file` directly, so test paths are already exempt for those two. No state, no history.\n\n### Line-local is a decision, not a limitation\n\nA rule sees one added line and the sibling added lines. It does not see the whole file, and it cannot see a block. That is why `# noqa` is line-local too, and why a secret split across two lines is not caught — a real limitation, stated in the docs rather than hidden.\n\n### `scan_text` exists for one reason\n\nA pathological line — a minified bundle pasted into a `.py` file — would make a backtracking regex run for seconds. `scan_text` truncates to a budget before the pattern ever sees it, so the worst case is bounded.\n\n### What a pattern rule cannot say\n\nIt cannot say \"this file has three of these\". Counting is the engine's job, not a rule's, because a rule that counted would need memory between lines and would stop being a pure function.",
  "code_examples": [
    {
      "id": "8.4-ex-0",
      "lang": "python",
      "caption": "A pattern rule, the exemption, and the test-file skip",
      "code": "from app.rules import LineContext, RULES\n\nrule = next(r for r in RULES if r.id == \"secret/hardcoded-credential\")\n\nfor text in (\"API_KEY = \\\"sk-live-abcdef1234567890\\\"\", \"API_KEY = os.environ[\\\"API_KEY\\\"]\"):\n    ctx = LineContext(path=\"app/demo.py\", lineno=1, text=text, added=(), index=0)\n    hit = rule.check(ctx)\n    print(\"%-46s -> %s\" % (text[:44], \"fires\" if hit else \"silent\"))",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "API_KEY = \"sk-live-abcdef1234567890\"           -> fires\nAPI_KEY = os.environ[\"API_KEY\"]                -> silent",
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
      "q": "What does a pattern rule check before it searches?",
      "options": [
        "Whether the path is a test file",
        "Whether the severity is above LOW",
        "Whether the registry has room",
        "Whether the line ends in a newline"
      ],
      "answer": 0,
      "why": "`skip_tests` exists because a fake key in a fixture is legitimate; the check runs before the search so a test file costs nothing."
    },
    {
      "q": "Why does `scan_text` truncate the line?",
      "options": [
        "So the finding fits inside a comment on one line of the pull request",
        "So a pathological line cannot stall it",
        "So the line number stays correct",
        "So the exemption pattern can match"
      ],
      "answer": 1,
      "why": "A minified bundle pasted into a Python file would otherwise let a regex run for seconds; the budget bounds the worst case."
    },
    {
      "q": "What can a line-local rule not do?",
      "options": [
        "Return the fix beside the issue text",
        "Skip a file that is a test file",
        "Count how often a pattern appeared",
        "Honour an exemption pattern"
      ],
      "answer": 2,
      "why": "Counting needs memory between lines, and a rule is a pure function of one context; the engine does the counting."
    }
  ],
  "try_it": {
    "prompt": "Run the hardcoded-credential rule over three lines and print which fire.",
    "starter": "",
    "solution": "```python\nfrom app.rules import LineContext, RULES\n\nrule = next(r for r in RULES if r.id == \"secret/hardcoded-credential\")\nfor text in (\"TOKEN = 'ghp_exampleTokenValue1234567890'\", \"TOKEN = os.environ['T']\", \"\"):\n    ctx = LineContext(path=\"a.py\", lineno=1, text=text, added=(), index=0)\n    print(bool(rule.check(ctx)), repr(text[:20]))\n```",
    "explanation": "The empty line and the environment read are both silent, which is the false-positive budget working."
  },
  "exercise": {
    "prompt": "Which rules are registered with `skip_tests=True`, and what does that tell you about the test-file skip?",
    "hint": "Count the registrations that pass the flag.",
    "solution": "```console\n$ grep -c 'skip_tests=True' app/rules.py\n0\n```\n\nNone passes the flag. The exemption is not absent, though: `_check_high_entropy` and `_check_print` call `ctx.is_test_file` themselves, so those two are already path-aware without it.",
    "explanation": "A capability with no user is still worth knowing about: the mechanism is there and the decision to use it was not taken."
  },
  "common_mistakes": [
    "Writing a rule that counts across lines; the engine counts, not the rule.",
    "Forgetting that `# noqa` is line-local, so it cannot suppress a block.",
    "Assuming a rule sees the whole file; it sees the line and its siblings."
  ],
  "project_links": [
    {
      "label": "The pattern-rule factory",
      "path": "app/rules.py",
      "lines": "145-170"
    },
    {
      "label": "scan_text and the regex budget",
      "path": "app/rules.py",
      "lines": "92-103"
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
    "pattern rule — a rule declared from a regex and an exemption",
    "exemption — a pattern that cancels a hit",
    "regex budget — the truncation that bounds a regex's worst case"
  ]
});
