# Build state — the only file a later run needs

Read this first. It names the next stage and its first concrete action.

## Last commit

Stage 1 done (quiz tell 0 of 252). Stage 2 partially done: Wave 6b audited
by five of nine lanes, every HIGH fixed.

## Validator

`OK lessons=84 parts_covered=10 manifest_entries=84` — parts 0–9 written, 7 of 13
parts complete (0–9 minus the last), 26 lessons to go to 110.

## Stages done

- Waves 1–3: parts 0–3 (34 lessons)
- Wave 4a: part 4 (8) · 4b: part 5 (8) · Wave 5: parts 6–7 (16)
- Wave 5b: content integrity pass, six of eleven items
- Wave 6a: part 8 (10) — **unaudited**
- Wave 6b: part 9 (8) — **unaudited**
- Quiz tell: 134 → 121 → 56, script in `site/tools/check_quiz.py`, now in CI

## Stages done (mission)

- **Stage 1 — quiz length tell: DONE.** 121 → 0 of 252, and the clustered rule 20 → 0.
  `check_quiz.py` exits 0 and runs in CI beside the other two checkers.

## Next stage

**Stage 2, second half — four more auditors on Part 9, then re-audit the fixes with
three.** Five lanes ran (facts, quiz, prose, schema, honesty) and returned 33
findings; every CRITICAL and HIGH is fixed.

Still owed from that round, recorded rather than dropped:
- the four remaining lanes: links, accessibility, layout at 375/1440, consistency
- the three-auditor re-audit of the fixes
- MEDIUMs deferred: five Part 9 concepts are 175-190 words (floor is 200); 9.6's
  exercise repeats its own try_it; 9.4's and 9.2's exercises are answerable from
  their concept; 9.3 cites a README sentence that does not exist; 9.5's why_not
  was copied from 9.1 and names the wrong blocker; 9.8's rebuild-suite link ends
  mid-literal at 1-30
- the validator's LINES_PATTERN still accepts a spaced range like "30 - 32"

First concrete action: run the four remaining lanes over `site/content/part-9/`,
fix what they return, then re-audit with three.

## Blocked

Nothing.

## Standing rules a new run must not break

Parts are never renamed; no part 13 or 14. Fifteen schema keys exactly. `order` =
`part*100 + n`. `part_title` matches `contracts.js`. Every terminal example carries
`expected_output` and `why_not`. Every `project_links` range starts and ends on a
construct. No test count in a lesson; 582/597/598/509/630 appear nowhere under
`site/`. The manifest and all three pages list the same paths in the same order.
Every example is executed at build time. Never touch `app/`, `tests/`,
`benchmarks/`, `docs/learning/`. Never merge or force-push `origin/submission`.
