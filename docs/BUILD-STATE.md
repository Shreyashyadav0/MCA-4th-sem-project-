# Build state — the only file a later run needs

Read this first. It names the next stage and its first concrete action.

## Last commit

Stage 1 complete — quiz length tell 0 of 252, all four within 3 chars 0.

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

**Stage 2 — Wave 6b's nine-auditor round.** The wave is written, gated and committed
as unaudited; it needs its auditors before Stage 3.

First concrete action: package the tree and run five auditors (anchors, claims,
schema, quiz, prose) over `site/content/part-9/`, then four more, then fix every
CRITICAL and HIGH and re-audit the fixes with three.

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
