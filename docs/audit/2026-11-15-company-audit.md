# Company audit — 15 November 2026

Fifteen auditors, one lane each, over the whole site and the repository. About
160 findings. This file is the backlog: what was fixed in `171c413`, and what is
still open, so nothing is lost.

## Lanes

1 W3Schools parity · 2 accuracy Parts 0–2 · 3 accuracy Parts 3–5 · 4 accuracy
Parts 6–7 · 5 line references · 6 quiz sweep · 7 prose sweep · 8 site
integration · 9 accessibility and responsive · 10 honesty · 11 performance ·
12 print · 13 dark theme · 14 every code example · 15 the repository's documents.

## Fixed in 171c413

| Severity | What |
|---|---|
| CRITICAL | 3.7 quoted two pytest runs that never happened — "51 passed, 590 deselected" and "4 passed, 637 deselected" for a test that does not exist |
| HIGH | sidebar stored the previous expanded state, so a re-render inverted every part the reader had touched |
| HIGH | arrow keys navigated away from a focused control, discarding quiz answers |
| HIGH | README said 42 lessons; the tree has 66 |
| HIGH | "docs/learning is the source of truth" survived in four places, contradicting lesson 0.2 |
| MEDIUM | green pills: 19px at weight 600 is not WCAG large text, so 3.01:1 failed |
| MEDIUM | header progress counter 2.45:1 on the charcoal bar |
| MEDIUM | dark-theme skip link 3.01:1 |
| MEDIUM | print: expected-output label hidden; terminal command printed twice |
| MEDIUM | six quiz questions had two true options |

## Open — in priority order

1. **Page weight (HIGH).** index, lesson and tryit each load all 66 lesson files
   (458,735 B). Measured: a generated summary would take the index from 737 KB to
   235 KB and FCP from 1004 ms to 400 ms. Needs a `lessons-summary.js` and a
   change to the validator, which asserts one script tag per lesson.
2. **Line ranges (HIGH, 45 of 143).** Many `project_links` ranges end on a blank
   line or mid-construct. Full list in the auditor's file; the worst are 0.4, 1.2,
   1.10, 2.2, 2.5, 2.10, 3.1, 3.5, 3.6, 3.8, 7.8.
3. **Openings (HIGH, 26 lessons).** 26 of 66 lessons open on a bare code fence
   with no sentence. Ten worst: 1.4, 2.4, 6.5, 7.1, 2.3, 2.8, 3.3, 2.7, 0.1, 3.6.
4. **Quiz length tell (HIGH).** The correct option is the unique longest in 138
   of 198 questions (70%); gap ≥20 in 41. A validator rule would stop it
   recurring.
5. **Stale numbers outside `site/` (HIGH).** CHANGELOG says 582, HANDOFF says 638
   and 637, TESTING quotes `-k sql` as "14 passed, 569 deselected", and
   `LOCK_PINS` is 36 against 37 pins in the lock.
6. **Duplicated material (MEDIUM).** 5.7 and 7.1 are the same lesson twice; 5.5
   and 7.5 restate `normalize_path`; 8 `common_mistakes` appear in two lessons.
7. **Exercises answered in their own concept (MEDIUM).** 3.2, 2.3, 4.2, 5.5, 6.8,
   7.5; six more only re-run their own try_it.
8. **Glossary (MEDIUM).** 30 of 184 terms are defined two or three times, and
   three contradict each other (`frozen`, `wrapper`, `entry point`).
9. **Print page breaks (MEDIUM).** Blocks break mid-code with no continuation.
10. **Dark theme flash (MEDIUM).** ~300 ms of light paint before dark applies; a
    pre-paint script in `<head>` would fix it.
11. **curl captures (MEDIUM).** Part 4's `curl -s -i` outputs omit the `date`,
    `server` and `content-length` headers curl really prints.
