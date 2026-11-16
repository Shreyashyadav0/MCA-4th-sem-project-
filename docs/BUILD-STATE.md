# Build state — the only file a later run needs

Read this first. It names the next stage and its first concrete action.

## Last commit

`84fb9ae` — the Parts 11-12 audit. **THE SITE IS COMPLETE AND AUDITED: 110 lessons,
13 parts, gate green.**

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

## Defect fixed this run

`sidebar.js` computed `currentPart` inside the same `forEach` that read it, so every
part before the current one saw null and expanded. A Part 10 lesson opened 11 of 13
groups and the reader never saw Part 10. Resolved in a first pass; the active link
is also scrolled into view. Verified: id=10.1 opens Part 10 only, id=9.1 Part 9, id=0.1
Part 0.

## Next stage

**Stage 3 — the final integrity pass (the freeze), then the release, MAINTAINING.md
and the benchmark labelling tool.**

The audit is done: five lanes over Parts 11-12 (37 findings, every CRITICAL and HIGH
fixed), and the three-auditor re-audit is still owed.

First concrete action: run the freeze's mechanical checks — fifteen keys per lesson,
every `learn_more` href resolving, the claim greps ("the LLM works", "improves recall
by", "found N vulnerabilities", "merged achieved", bare percentages), and any rule or
category count against `app/rules.py`.

Then regenerate and verify every derived artifact: `build_standalone.py`,
`embed_sources.py`, `build_deck.py`, `build_guide.py` — the guide's line-count table
and LOCK_PINS are computed at build time, so prove it by grepping the rebuilt PDF
against `wc -l`.

Then reconcile README (site row, 110 lessons, 13 parts), HANDOFF, site/STATE.md and
CHANGELOG, and commit "Freeze — site complete (110 lessons)".

Then the release, as five separate commands: `git tag -a v1.1-site`, `git push`,
`git push --tags`, `git archive --format=zip --prefix=ai-code-reviewer/`, `sha256sum`.
Verify with `unzip -l` that it lists 110 lesson files and no .git, .venv or pycache.

Then MAINTAINING.md (how to add a lesson, the gate, each checker, the nine lanes, the
four standing rules) and the benchmark labelling tool.

Watch for the defect class that has appeared in every round: my own fixes
introducing duplicates. In this round it was three quiz pairs and a second true
option.

Deferred: four word-count paragraphs (10.3, 10.6, 10.8, 10.9) restate a section the
lesson already had. Not false, but redundant; removing them drops those lessons under
the 200-word floor, so it needs a rewrite rather than a deletion.

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
