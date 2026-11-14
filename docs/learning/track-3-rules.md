# Track 3 — rules

## Prerequisite check

Pass all five before starting:

- [ ] Track 1 and Track 2 done: you can construct a `Finding`, and you know that
      `Hunk.lines` carries `kind` and `new_lineno` per body line.
- [ ] `python -c "from app.rules import RULE_COUNT; print(RULE_COUNT)"` prints `63`.
- [ ] `python -m pytest -q tests/test_rules.py` runs to completion (187 collected tests
      from 34 test functions) and you
      have looked at what `tests/test_rules.py:166` (`test_every_rule_has_a_sample`)
      demands of a new rule.
- [ ] You can read a regex without running it, and you know what catastrophic
      backtracking is.
- [ ] You accept the project severity rubric at `app/rules.py:19-22` as given; this
      track explains the mechanism, not whether the rubric is right.

## What it does

`app/rules.py` is a deterministic, offline, OWASP-mapped rule engine: 63 rules in one
registry, each with an id, a title, a category, an OWASP reference, a fixed severity and
a `check(ctx) -> RuleHit | None` callable. Two registration paths fill that registry -
`@_rule` for hand-written checks and `_pattern_rule(...)` for pattern-plus-exemption
rules - and `review_lines` runs every rule over the added lines of one file while
`review_diff` feeds it those lines out of a parsed `DiffBundle`. Suppression is parsed
per line from `# noqa` / `# nosec`, and the whole path imports no network client.

## Why it exists

The rejected alternative is the LLM for the offline path. `docs/decisions/0004` records
the shape of the degraded path, and both offline entry points call this module:
`app/mock_provider.py:47` and `app/mock_provider.py:75` both return
`review_diff(bundle, min_severity=...)`. A demo, a CI gate and a
`--provider mock` run cannot depend on a model that may answer differently twice, so the
fallback had to be real logic, not a canned payload: the module docstring is explicit
that "nothing in this module imports `httpx`, `openai` or `sarvam`"
(`app/rules.py:24-25`).

Two smaller designs were rejected inside the module. Scanning whole files instead of
added lines was rejected because a finding must be attachable to a line the pull request
changed (`app/rules.py:7-8`). Letting each check return its own severity was rejected
because it makes the severity of an identical line depend on which branch of the check
fired, and because the severity filter then has to run after every check instead of
before it (`app/rules.py:1548`).

## Key references

- `app/rules.py:56` — `_MAX_REGEX_LINE = 4000`, the regex budget for one line.
- `app/rules.py:97` — `return self.text[:_MAX_REGEX_LINE]`, `LineContext.scan_text` doing the truncation.
- `app/rules.py:120` — `severity: Severity`, the per-rule severity field on the `Rule` dataclass.
- `app/rules.py:139` — `_register(Rule(rule_id, title, category, owasp, severity, check))`, the `@_rule` decorator closing over its metadata.
- `app/rules.py:164` — `if pattern.search(text) is None:`, the whole body of a pattern rule's decision.
- `app/rules.py:337` — `_NOQA_RE = re.compile(r"#\s*(?:noqa|nosec)(?P<ids>[:=][A-Za-z0-9_,\s/\-]+)?", re.IGNORECASE)`, the suppression grammar.
- `app/rules.py:1511` — `if not raw:`, the branch that turns a bare marker into "suppress everything".
- `app/rules.py:1596` — `if line.kind == "added" and line.new_lineno is not None`, the filter that defines what the engine is allowed to see.

## The three hardest ideas

### 1. Rules see added lines only

`review_diff` builds its input by filtering parsed hunks
(`app/rules.py:1591-1597`): only `kind == "added"` lines with a `new_lineno` reach
`review_lines`. Removed lines and untouched context are not scanned at all. Two
consequences follow, one good and one that costs you code.

The good one: every finding the engine emits is anchorable, so `anchor_findings` will
call all of them `anchored` and the poster never has to demote a rule finding to the
summary. `tests/test_rules.py:398` (`test_every_finding_on_the_fixture_is_anchorable`)
locks that property.

The costly one: a rule cannot see the surrounding code unless it asks. Worked example -
this diff, run through the real engine:

```
@@ -1,3 +1,3 @@
-API_KEY = "AKIAIOSFODNN7EXAMPLE"
+API_KEY = os.environ["API_KEY"]
 keep = 1
-query = f"SELECT * FROM t WHERE id = {uid}"
+query = "SELECT * FROM t WHERE id = ?"
```

```
(no findings)
```

The removed AWS key is invisible, by design: the engine reports on what the change
introduces, not on what it removes. The added `os.environ` lookup is correctly not a
secret, and the added parameterised query is correctly not injection. `tests/test_rules.py:385`
asserts the same thing with a removed `ghp_...` token.

When a rule genuinely needs siblings, it walks `LineContext.added` and `LineContext.index`
itself. `_check_branch_density` (`app/rules.py:1338-1363`) is the only rule that does:
it counts decision points in the lines after the `def` until indentation drops back
(`app/rules.py:1345`, `for _lineno, text in ctx.added[ctx.index + 1 :]:`), which is why
`tests/test_rules.py:222` requires the `def` line itself to be part of the change for
that rule to fire. In a partial diff the body may be missing entirely, and the rule then
under-counts silently. That is a known, accepted limit of the added-lines-only design.

### 2. Every pattern is linear and every line is truncated (ReDoS)

`_MAX_REGEX_LINE` is 4000 (`app/rules.py:56`) and `LineContext.scan_text`
(`app/rules.py:93-97`) returns at most that many characters. The docstring states the
two-part contract at `app/rules.py:9-11`: no nested quantifiers, and a hard cap on input
length. Both parts are needed - a linear pattern is only linear in its input, and a
bounded input still explodes under `(a+)+$`.

Measured, on this checkout, with the module imported directly:

```
re.compile(r"(a+)+$").search("a"*24 + "!")      ~4.1 s   (25 characters)
review_lines("m.py", [(1, "a"*4000 + "!")])     ~0.04 s  (4001 characters, 63 rules)
review_lines("m.py", [(1, "a"*2_000_000)])      ~0.05 s  (2 MB, 63 rules)
```

The 2 MB line is scanned in the same time as the 4 KB one because only the first 4000
characters are ever handed to a regex:

```python
ctx = LineContext(path="m.py", lineno=1, text="x = '" + "A"*200_000 + "'",
                  added=((1, "x = '" + "A"*200_000 + "'"),), index=0)
len(ctx.scan_text)   # 4000
```

`tests/test_rules.py:417` bounds the wall clock at 2 s for a 100 kB line and
`tests/test_rules.py:425` at 5 s for a 10-line regex flood.

The truncation has a visible cost that the tests record. `style/long-line`
(`app/rules.py:1428-1438`) must measure the *real* line, so it reads `ctx.text`, not
`ctx.scan_text` (`app/rules.py:1430`), and reports the true length:

```
review_lines("m.py", [(1, "x = '" + "A"*200_000 + "'")])
# line 1  LOW  "The line is 200006 characters, past the 120-character budget, ..."
```

Everything else sees 4000 characters. A secret sitting at column 5000 of a minified line
is not found by any pattern rule; only the length rule notices the line at all. That is
the trade the module chose, in that order.

### 3. Severity is fixed per rule, never computed per hit

`Rule.severity` is a field on the registered rule (`app/rules.py:120`), and `RuleHit`
carries only two fields (`app/rules.py:74-79`):

```
RuleHit: ['issue', 'suggested_fix']
Rule:    ['id', 'title', 'category', 'owasp', 'severity', 'check']
```

A check therefore cannot return a different severity for a worse instance of the same
problem - the type has nowhere to put it. `_check_high_entropy` states the reasoning in
its own docstring (`app/rules.py:591-592`): entropy is a heuristic, so the rule is
MEDIUM even when the string looks like a live key, because "a false CRITICAL on a hash
constant would train the team to ignore the tool". If a heuristic needs two severities,
it becomes two rules with two patterns, and the pattern does the deciding.

The second reason is mechanical. `min_severity` is applied to the *rule list* before any
check runs (`app/rules.py:1548`, `if rule.severity.rank < floor: continue`), so
`min_severity=Severity.CRITICAL` runs 17 of the 63 rules instead of 63. If severity were
computed inside a check, every check would have to run and the filter would move after
the expensive part. `review_lines` also uses the fixed value for the finding it builds
(`app/rules.py:1565`, `severity=rule.severity`), so a finding's severity is traceable to
exactly one registry entry.

Registry shape, from the live module:

```
RULE_COUNT 63   (18 @_rule + 45 _pattern_rule; 63 unique ids)
severity   HIGH 23, CRITICAL 17, MEDIUM 16, LOW 7
category   secrets 15, injection 14, config 7, crypto 6, quality 5,
           deserialisation 4, style 4, auth 3, complexity 3, reliability 2
```

Two further mechanisms belong with this idea, because both are per-line decisions taken
around the fixed severity. Suppression: `_suppressed_ids` (`app/rules.py:1497-1515`)
returns `(suppress_all, ids)` - a bare `# noqa` or `# nosec` gives `(True, set())` and
skips the line entirely (`app/rules.py:1511`), while a targeted marker gives
`(False, {"unsafe/sql-injection"})` and skips only that rule
(`app/rules.py:1552`). Verified:

```
'x = 1  # noqa'                                  -> (True, set())
'q = 1 # nosec'                                  -> (True, set())
'q = 1  # noqa: unsafe/sql-injection'            -> (False, {'unsafe/sql-injection'})
'q = 1 # noqa: unsafe/sql-injection, style/long-line' -> (False, {'unsafe/sql-injection', 'style/long-line'})
'x = 1  # noqa:E501'                             -> (False, {'E501'})
```

That last line is a gap worth knowing about: any token parses as an id, so a
flake8-style `# noqa: E501` suppresses nothing and says nothing. And deduplication is
per `(path, lineno, rule.id)` (`app/rules.py:1557`), so two rules firing on one line
produce two findings while one rule firing twice on one line produces one; the rule id is
also appended to the issue text (`app/rules.py:1566`) so a reader can see which of the
63 fired.

## Rebuild exercise

Time: 1-3 hours. Fresh file: `track3_rules.py`, outside `app/` (for example
`/tmp/track3/track3_rules.py`). Do not modify `app/rules.py`; import it read-only to
compare.

Build a five-rule engine with the same external contract:

1. `RuleCategory` (at least `secrets`, `injection`, `style`), `RuleHit(issue,
   suggested_fix)` as a frozen dataclass, and `Rule(id, title, category, owasp,
   severity, check)` as a frozen dataclass with slots.
2. `LineContext(path, lineno, text, added, index)` with `scan_text` (4000-char cap),
   `indent` (tabs expanded to 4), `is_test_file`.
3. `_rule(...)` decorator and `_pattern_rule(...)` registration, both appending to one
   `RULES` list, plus `RULES_BY_ID` and `RULE_COUNT` derived from it.
4. Five rules: one hand-written (a hardcoded-credential check: assignment, secret-shaped
   name, string literal, not an env lookup, not a placeholder, at least 8 characters) and
   four pattern rules (one secrets pattern with an `exempt` pattern, `style/long-line`
   reading the untruncated text, and two others of your choice).
5. `_suppressed_ids`, `review_lines(path, lines, *, min_severity, categories)` with
   pre-check severity and category filtering plus per-line dedup, and `review_diff(bundle)`
   that feeds only added lines.

Test it against the real module:

- `python -c "from app.rules import RULE_COUNT; print(RULE_COUNT)"` must print `63`, and
  your own registry must have no duplicate ids (the check `tests/test_rules.py:134`
  makes on the real one).
- For a fixed list of `(lineno, text)` pairs, your `review_lines` findings must have the
  same `(line, severity, rule id)` triples as the real `review_lines` for the rules you
  implemented. Use at least: `query = f'SELECT * FROM users WHERE id = {uid}'`
  (CRITICAL, `unsafe/sql-injection`), `os.system("ls")` (HIGH, `unsafe/os-system`),
  `x = 1  # noqa` (no findings), and a 200 kB line (LOW, `style/long-line`).
- `review_lines("a.py", [(7, q)])` must produce one CRITICAL finding whose issue ends
  with `(rule: unsafe/sql-injection)`-style attribution; the same line with
  `# noqa: unsafe/sql-injection` must produce none; with `# noqa: style/long-line` it
  must still produce the injection finding.
- `review_lines` on a 2 MB line must finish in well under a second and report the true
  length from the long-line rule.
- `review_diff` on the diff in idea 1 must return no findings, and on the added
  `query = f"SELECT ... {uid}"` line must return exactly one.

## Self-test questions

1. `review_lines` filters on `min_severity` and `categories` per rule inside the line
   loop, not once before it. What is the cost of that placement, and what would break if
   the filters were hoisted into a precomputed rule list?
2. `_check_branch_density` walks `ctx.added[ctx.index + 1:]` and stops at the first line
   whose indentation is `<= base`. Name two real diffs where that heuristic gives a
   wrong count, and say in which direction it errs.
3. A rule cannot see removed lines. Which of the 63 rule ids would be genuinely stronger
   if it could, and what anchoring problem would that create downstream?
4. `# noqa: E501` parses as `(False, {'E501'})` and suppresses nothing. Is that a bug in
   `_suppressed_ids`, in the caller, or in the design? Argue one position and state what
   you would change.
5. `_pattern_rule` applies `exempt` to the same `scan_text` the pattern matched. Give a
   case where truncation makes an exemption fail to apply, and a case where it makes a
   pattern match text that was never on the line.
