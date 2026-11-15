# Build state — the only file a later run needs

Read this first. It names the next stage and its first concrete action.

## Last commit

Stage 1 done. Stage 2 done: Wave 6b audited by all nine lanes, every
CRITICAL and HIGH fixed, and the range checker's tautology removed.

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

## Re-audit of the 6b fixes — done

Three auditors over the fixes found 18 findings, four of them regressions the fixes
themselves introduced, all now fixed:
- the sidebar fix left index.html with all 84 links hidden (no lesson is current
  there, so no part opened); the rule is now: explicitly-closed stays closed, the
  current part opens, and with no lesson selected every part with lessons opens
- dark had no `--muted-on-surface`, so the terminal note was 2.73:1 in dark
- dark sets `--accent-strong` to the brand green, so the header hover was back to
  3.01:1; the hover is now a literal that clears 4.5:1 on both bars
- the theme toggle's fixed aria-label did not contain a visible label of "Light
  mode"; the name now follows the visible label

## Next stage

**Stage 2's re-audit — three auditors over the fixes — then Stage 3, Wave 7a
(Part 10, ten lessons, site to 94).**

All nine lanes have now run: 61 findings across two batches. Every CRITICAL and
HIGH is fixed and each motivating check re-run.

Still owed, recorded rather than dropped:
- the three-auditor re-audit of these fixes
- MEDIUMs deferred: five Part 9 concepts are 175-190 words (floor is 200); 9.6's
  exercise repeats its own try_it; 9.4's and 9.2's exercises are answerable from
  their concept; 9.3 cites a README sentence that does not exist; 9.5's why_not
  was copied from 9.1 and names the wrong blocker
- the validator's LINES_PATTERN still accepts a spaced range like "30 - 32"
- the code panel scrolls rather than wraps on long lines; the auditor's fix is
  `white-space: pre-wrap` on pre.code, deferred because it changes every example

First concrete action: package the tree, run three auditors over the Part 9 fixes
and the CSS changes, then start Wave 7a from `build-waves-6a-to-7b_1.md` §5.

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
