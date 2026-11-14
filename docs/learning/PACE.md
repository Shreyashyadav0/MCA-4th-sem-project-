# PACE: the 16-week schedule

`README.md` says what to study and in what order. This file says when, what to do when you are not
on time, and which hours are not negotiable.

**Total: 90 hours across 16 weeks — about 5.6 hours a week on average.** The average hides a real
shape: weeks 1–4 run at 8 hours because Tracks 1–4 must be green before Track 5 opens, weeks 5–7
run at 8 hours because Track 5 is the hard one, week 8 is deliberately empty, and weeks 9–12 are
light enough to absorb a slip. A plan that spread 90 hours perfectly evenly at 5.6/week would put
Track 5 in weeks 5–9 and Track 6 in weeks 10–12, which is the same plan with the buffer in a worse
place.

---

## The gate

> **Do not start Track N+1 until Track N's verification test is green:
> `python scripts/learning_progress.py check N`.**

Stated once, here, and assumed everywhere below. The dependency graph in `README.md` is a statement
about what is comprehensible, not a preference about reading order: Track 3 consumes `DiffBundle`,
Track 5 consumes `RuleCategory`, Track 6 consumes `ProviderOutcome`. A red test means the thing the
next track reads does not exist in your head yet. Spending the week anyway converts a two-week slip
into a four-week one, because you end up debugging two modules at once with no way to tell which one
is wrong.

A green test is the only completion criterion this curriculum recognises. Reading a track, answering
its questions and doing its rebuild exercise are all in service of that one command returning zero.

---

## Week by week

| Week | Track | Work | Hours | Cumulative |
| --- | --- | --- | --- | --- |
| 1 | 1 → 2 | `models.py` complete (5 h); begin `parser.py` (3 h) | 8 | 8 |
| 2 | 2 | `parser.py`: diff grammar, hunk bookkeeping, `anchor_findings` | 8 | 16 |
| 3 | 3 | `rules.py`: registry, `LineContext`, the check functions | 8 | 24 |
| 4 | 3 → 4 | `rules.py` finish (4 h); `mock_provider.py` + `config.py` (4 h) | 8 | 32 |
| 5 | 5 | **HARD.** `sarvam_provider.py`: `build_prompt`, payload parsing, line snapping | 8 | 40 |
| 6 | 5 | **HARD.** `sarvam_provider.py` live path and fallback; begin `openai_compat_provider.py` | 8 | 48 |
| 7 | 5 | `openai_compat_provider.py`: repair path, `review_with_fallback` | 8 | 56 |
| 8 | — | Buffer. Track 5 verification green. Checkpoint 2. | 0 | 56 |
| 9 | 6 | `engine.py`: `ProviderSelection`, the two config builders | 3 | 59 |
| 10 | 6 | `engine.py`: `select_provider` precedence and the reason strings | 3 | 62 |
| 11 | 6 | **HARD.** Degraded path, `_mock_outcome` relabelling, `review` never raising | 4 | 66 |
| 12 | 6 | **HARD.** Finish, then Track 6 verification green. Checkpoint 3. | 4 | 70 |
| 13 | 7 | `cli.py`: argument surface, exit codes, rendering | 5 | 75 |
| 14 | 7 | `main.py`: FastAPI surfaces, webhook verification, publishing | 5 | 80 |
| 15 | 7 | `github_client.py`: payload construction, path canonicalisation, idempotency markers | 5 | 85 |
| 16 | 7 | `github_client.py`: retry ladder, 422 per-comment demotion; Track 7 green | 5 | 90 |

**Weeks 5–6 and 11–12 are the hard ones.** They carry Track 5 and Track 6 — 1,729 and 385 lines
respectively. Track 6's line count is small and misleading: 385 lines encode the selection precedence,
the reason strings, the relabelling of the degraded path and the promise that `review` raises for
nothing except an unknown provider name. Expect those four weeks to feel slower than their hours
suggest, and do not read that as a schedule failure.

Track 7 is 2,856 lines in 20 hours — faster per line than any other track, and that is correct. It
is three surfaces over machinery you already own, and almost every line is plumbing whose shape is
forced by what Track 6 returns.

---

## Checkpoints

Three of them, at the end of weeks 4, 8 and 12. Each one is a single command per completed track,
not a review meeting. Be honest with the rows below; the schedule only works if the checkpoints do.

### Checkpoint 1 — end of week 4

Expected: Tracks 1, 2, 3, 4 green. 32 hours spent.

| State | Signal | What to do |
| --- | --- | --- |
| On schedule | `check 1` through `check 4` all exit 0 | Proceed to Track 5 in week 5. Re-read the ADR `0002-offline-first-fallback` the weekend before; Track 5 is where it stops being abstract. |
| Behind | Track 4 red, or Track 3 red with fewer than 8 hours left in week 4 | Compress Track 4 into two evenings — it is 167 lines of glue — and protect Track 5's start date by at most one week. If Track 3 is the red one, apply the recovery rule below rather than stealing from Track 5. |
| Ahead | All four green before the end of week 3 | Do not start Track 5 early. Spend the surplus re-deriving Track 2 from memory with the track document closed, then take a full week off before week 5. Track 5 is the track you want to arrive at rested. |

### Checkpoint 2 — end of week 8

Expected: Track 5 green. 56 hours spent. Week 8 is empty on purpose.

| State | Signal | What to do |
| --- | --- | --- |
| On schedule | `check 5` exits 0 | Use the empty week 8 as a genuine buffer: no new material, or re-run `check 1` through `check 4` cold. Then start Track 6 in week 9. |
| Behind | Track 5 red at the end of week 7 | Week 8 exists for exactly this. Take it, finish Track 5, and lose nothing — weeks 9–12 have enough slack to absorb the shift. If Track 5 is still red at the end of week 8, shift Track 6 by one week and Track 7 by one week; the 16-week frame becomes 17 and the checkpoints move with it. |
| Ahead | Track 5 green by the end of week 7 | Start Track 6 in week 8, since its gate is satisfied. Do not compress Track 6 to buy time for Track 7 — Track 6's four weeks are already the minimum for its conceptual load, not its line count. |

### Checkpoint 3 — end of week 12

Expected: Track 6 green. 70 hours spent.

| State | Signal | What to do |
| --- | --- | --- |
| On schedule | `check 6` exits 0 | Start Track 7 in week 13 with 20 hours and four weeks. Do not read `github_client.py` before `cli.py`: the payload construction only makes sense once you have seen what the CLI hands it. |
| Behind | Track 6 red at the end of week 12 | Track 7 is breadth and compresses better than anything else in the plan. Take one week from it (20 h → 15 h) and accept a thinner `main.py` rebuild: keep the webhook signature check and the publishing path, skim the operational endpoints. Do not take the week from Track 6. |
| Ahead | Track 6 green before week 11 | Extend Track 7 rather than shortening the plan: use the surplus on the retry ladder and the 422 per-comment demotion in `github_client.py`, which are the two places in this repository where a rebuild from memory is most likely to be subtly wrong and least likely to be caught by a happy-path test. |

---

### If your weekly hours differ

The checkpoint dates above assume ~5 h/week. They scale linearly, so do not reuse the
week numbers at another rate: at 3 h/week the 32 h checkpoint lands around week 11 and the
90 h plan takes ~30 weeks; at 10 h/week the 32 h checkpoint lands around week 4 and the plan
takes ~9 weeks. Divide the cumulative hours in the table by your weekly rate to get your own
dates; keep the order and the gates unchanged.

## Recovery: if you are two or more weeks behind

Compress **Tracks 3 and 4**. Never compress **Tracks 1, 5 or 6**.

Tracks 3 and 4 together are 1,785 lines and 16 hours, and they compress honestly because their cost
is repetition rather than insight. `rules.py` registers 63 rules through 18 decorated check functions:
once you have read `_check_hardcoded_secret`, `_check_eval` and one complexity rule, you have read the
shape of all of them, and the remainder is a catalogue you can look up while rebuilding. `config.py`
and `mock_provider.py` are 167 lines of settings and two thin wrappers over `review_diff`. Skimming
them costs you rule-id recall, which `reviewer --list-rules` restores in one command. It costs you no
structural understanding, and nothing downstream depends on you having memorised the catalogue.

**Track 1 is not compressible because it defines every type the rest of the codebase speaks.** `Severity`
and its `rank`, `AnchorStatus` with its three states, the five-field frozen `Finding`, `AnchoredFinding`,
`ReviewResult`, and the three helpers `sort_findings`, `severity_counts` and `verdict_for`. Every later
module's signature is written in these words, and every later module's tests assert against them. Skipping
or skimming Track 1 does not save five hours; it makes every subsequent track's test failure ambiguous,
because you will be unable to tell whether the module is wrong or your mental model of `Finding` is. Five
hours is the cheapest insurance in the plan.

**Track 5 is not compressible because it is where the two ideas the project is actually about live.**
The provider-agnostic design — one `OpenAICompatConfig`, one `review_diff_live`, one `review_with_fallback`
serving both the hosted Sarvam endpoint and a local LM Studio server — and the fallback chain that
degrades on a missing key, a missing SDK, `REVIEW_MODE=mock`, a transport error, a timeout, malformed JSON
and a schema violation, all without raising. It also holds the least guessable code in the repository:
`_json_candidates`, `_strip_fences`, `_snap_to_added` and `_nearest`, which exist because models do not
respect line numbers. You cannot reconstruct those from a docstring, and you cannot skim your way to
remembering why they are shaped that way. Twenty-four hours is the largest single block in the plan and
it is the correct one.

**Track 6 is not compressible because it is the single selector every surface calls.** `engine.review` is
the one entry point for the CLI, the FastAPI endpoints and the webhook: it chooses the provider, produces
the honest `mode`/`provider`/`model` labels, relabels the degraded run's reason with the caller's more
useful fact, logs exactly one WARNING, and promises never to raise for a configuration or transport
failure. Fourteen hours over four weeks is already thin for 385 lines that carry that much contract. If
you compress it, you will be able to recite the precedence order and still not be able to say what
`ProviderOutcome.reason` contains in the case you are debugging.

If compressing Tracks 3 and 4 is not enough — that is, you are more than about four weeks behind —
the plan is not the problem. Cut scope instead: drop Track 7's `main.py` rebuild and keep the CLI and
`github_client.py`, finish the other six tracks properly, and accept a 90-hour curriculum delivered in
18 weeks. A finished six-track rebuild is worth more than a seven-track rebuild where Track 5 was read
instead of rebuilt.

---

## If your available time is not ~5 hours a week

The order, the gates and the checkpoints do not change. Only the dates do.

- **About 3 hours a week (≈30 weeks).** Double the buffer: put two empty weeks after Track 3 and after
  Track 5. Tracks 5 and 6 will each take six weeks rather than three and four, and the extra weeks are
  not waste — they are where a slower reader actually consolidates. Move the checkpoints to weeks 6, 14
  and 22.
- **About 5 hours a week.** The schedule as written. 16 weeks, 90 hours.
- **About 10 hours a week (≈9 weeks).** Keep every gate; compress the calendar, not the material. Weeks
  become half-weeks and the empty week 8 disappears, but Track 5 still gets 24 hours and Track 6 still
  gets 14. Checkpoints fall at weeks 2, 4 and 6 of the compressed calendar. Do not use the extra hours
  to run two tracks in parallel — the whole point of the dependency graph is that parallel tracks give
  you two half-understood modules instead of one finished one.

Whatever the rate, the honest progress measure is the count of tracks whose verification test is green,
not the number of weeks elapsed.
