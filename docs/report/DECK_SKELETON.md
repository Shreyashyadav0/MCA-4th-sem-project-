# Presentation deck — skeleton

Fourteen slides for the project defence. This file is the outline the deck is built
from; it is not the deck. Every slide below gives a bullet outline and one speaker
note placeholder describing what to say.

Conventions:

- Placeholders use the exact token `[SPEAKER NOTE PLACEHOLDER` so they are
  searchable: `grep -rn "SPEAKER NOTE PLACEHOLDER" docs/report`.
- Numbers already established and safe to show: 582 tests passing with 1 skipped,
  63 rules, 10 categories, 6 build phases. These were produced by the code and can
  be shown without qualification.
- Numbers that do not yet exist: anything from the benchmark. Those are
  `[FILL AFTER BENCHMARK` placeholders and must not be replaced with estimates,
  with numbers from an earlier run on another machine, or with the smoke-test
  figures the harness prints over the two format examples.
- The two samples in `benchmarks/golden/example_01` and `example_02` are format
  examples, not evaluation data. They do not appear on any slide as results.
- One idea per slide. If a slide needs two headlines, it is two slides.

---

## Slide 1 — Title

- Project title: *Autonomous AI Code Reviewer & PR Assistant*.
- Candidate name, roll number, programme.
- Supervisor, department, institution.
- Date.

`[SPEAKER NOTE PLACEHOLDER: 20 seconds. Name the project, name yourself, state in one sentence what it does: reviews a pull-request diff and returns findings in a fixed five-field format, with or without a model. Do not read the title slide.]`

---

## Slide 2 — Problem

- Code review is the last gate before merge, and it is a human gate.
- Small pull requests wait; large ones get skimmed.
- Two kinds of existing tooling, and the gap between them:
  - linters and pattern analysers — fast, reproducible, no semantic judgement;
  - LLM reviewers — broad, but non-deterministic, and unavailable when the API is.
- The gap: a reviewer that is both always available and measurable.

`[SPEAKER NOTE PLACEHOLDER: 90 seconds. Establish the cost of review latency and the inconsistency of human review without quoting statistics you cannot source. Then land the gap in one sentence — the existing options trade reproducibility for coverage, and nobody wants to make that trade on a merge gate.]`

---

## Slide 3 — Objectives

- Parse a unified diff; anchor each finding to a changed line.
- Detect a defined set of security and quality defects deterministically.
- Add an optional model layer that degrades without failing the review.
- Post the review to a pull request, inline and idempotently.
- Measure all of it on a labelled dataset.

`[SPEAKER NOTE PLACEHOLDER: 60 seconds. Read the objectives as a list of things that can be marked done or not done. Say plainly that the first four are implemented and the fifth is the remaining work — that honesty sets up slide 10 and costs nothing.]`

---

## Slide 4 — Architecture

- One diagram, reused from `ARCHITECTURE.md` — do not draw a second version.
- Components: CLI, diff parser, rule engine, provider layer, router, FastAPI server,
  GitHub client, benchmark harness.
- Two boundaries that matter: the finding contract (five fields, `extra="forbid"`)
  and the config boundary (a missing credential is data, not an exception).
- One router decides live versus offline; one adapter serves both providers.

`[SPEAKER NOTE PLACEHOLDER: 120 seconds. Walk the diagram left to right once, then stop. Spend the remaining time on the two boundaries, not on the component list — the list is on the slide, the reasoning is not. Point at the single router and say that everything goes through it, which is why the fallback cannot be bypassed by accident.]`

---

## Slide 5 — Phases and test counts

- Phase 1 — scaffold, config boundary, finding contract, CLI.
- Phase 2 — diff parsing, anchoring to changed line ranges.
- Phase 3 — local rule engine, 63 OWASP-mapped rules, 10 categories; webhook server.
- Phase 4 — model review layer with a guaranteed local fallback.
- Phase 5 — pull-request posting: inline, summary, idempotent.
- Phase 5.5 — one OpenAI-compatible adapter, two providers, one selector.
- Test suite: 637 passed, 1 skipped. The skip is the live local-model test.

`[SPEAKER NOTE PLACEHOLDER: 90 seconds. Do not read all six phases. Say that the project was built in six phases, each with a fixed interface and its own tests, and that the suite is the evidence: 582 tests, all offline, one skip that needs a local model to run. Point out that every rule has a firing sample, so a broken pattern fails the suite rather than silently under-reporting.]`

---

## Slide 6 — The hybrid design: deterministic base, model on top

- The rule engine always runs and always produces the same findings for the same diff.
- The model layer runs only when configured, and sees only the added lines.
- Its output is checked before it becomes a finding: fenced JSON unwrapped,
  hallucinated files dropped, invented line numbers snapped or dropped, duplicates
  collapsed, list capped and severity-sorted.
- Every live finding carries its provenance in the issue text — `(source: sarvam)`,
  `(source: local)`.

`[SPEAKER NOTE PLACEHOLDER: 120 seconds. This is the design contribution, so slow down. The claim is not "an LLM reviews code" — the claim is that the model's output is untrusted and passes through a validator before it reaches the report, and that the deterministic layer below it means a model failure is a degradation rather than an outage. Give one concrete example of a rejected model output: a finding for a file that is not in the diff.]`

---

## Slide 7 — The key decision: the offline fallback

- No key, blank key, `--offline`, SDK absent, 401/403/5xx, timeout, unparseable
  JSON — every one of those routes to the local rule engine.
- The run still exits 0 and still produces a review.
- Exactly one warning line explains what happened; the reason is carried into the
  result's `provider` and `model` fields.
- Consequence: the tool is demonstrable with no credentials and no network, and CI
  stays green on a machine with no model.

`[SPEAKER NOTE PLACEHOLDER: 90 seconds. Frame this as the decision the project would be worse without. The alternative — fail when the model is unavailable — makes a merge gate depend on someone else's uptime. Then give the reporting half: a caller can always tell what actually ran, because the result says so rather than reporting what was configured.]`

---

## Slide 8 — Provider precedence

- `sarvam` > `local` > `mock`. Fixed, tested, and not configurable away.
- `SARVAM_API_KEY` set selects `sarvam`; else `LMSTUDIO_BASE_URL` selects `local`;
  else `mock`.
- Both set: sarvam wins. That ordering is deliberate — the hosted model is the
  path to describe as built but never exercised in the report, and the local one is the demo path.
- `--provider auto|local|sarvam|mock` forces a choice per run; forcing an
  unconfigured provider degrades to mock with a reason naming the missing variable.

`[SPEAKER NOTE PLACEHOLDER: 60 seconds. State the order, then state why it is locked: precedence that can be changed by environment drift makes the report's numbers unattributable. Mention that forcing a provider never crashes — it degrades and says which variable was missing.]`

---

## Slide 9 — Benchmark methodology

- Dataset: `benchmarks/golden/`, each sample a `change.diff` plus a hand-written
  `expected.json`. Labels must be human-written; a label copied from the tool scores
  the tool against itself.
- Matching: same file, overlapping line range, equal or equivalent category;
  one-to-one, greedy, largest overlap first.
- Metrics: precision, recall, F1, false-positive rate, p50 and p95 latency.
- Modes: `rules`, `local`, `merged`.
- Artifacts: `metrics.csv`, `summary.json`, `summary.md`, `chart.png`.
- Dataset size and label provenance: `[FILL AFTER BENCHMARK: labelled sample count and who labelled them]`

`[SPEAKER NOTE PLACEHOLDER: 90 seconds. Explain the methodology before any result, and be explicit that at the time of building, the repository contains two format examples and no labelled evaluation samples — so the harness is demonstrated, not scored. If asked why, the answer is that labels written by the tool measure nothing. Then show the result table.]`

---

## Slide 10 — What is real and what is simulated

One slide, and it is not optional. Read it as a ledger.

| Item | Status |
|---|---|
| 63-rule engine, CLI, API, diff parsing and anchoring | Implemented and covered by the offline test suite (637 passed, 1 skipped). |
| Zero-network, zero-credential operation | Verified: the health check includes a zero-network proof. |
| Benchmark harness end to end | Verified over the two format examples — the harness runs, the numbers are a smoke test and are not results. |
| Labelled evaluation dataset | Does not exist yet. `evaluation_samples` in the manifest is empty. |
| Local-model provider | Verified against a stub OpenAI-compatible server. Never run against a real model, so real-model behaviour is unmeasured. |
| Sarvam provider | Never run against the live hosted service. No real key has been used at any point. |
| Pull-request posting | Behaviour verified by tests against a simulated GitHub API; a live post against a real pull request is not stated in the project record. |

`[SPEAKER NOTE PLACEHOLDER: 120 seconds. Do not soften this slide. Say which parts are built and tested, and which parts are built but unexercised, and why — no key, no local model, no labelled data in the build environment. An examiner who finds an unexercised path you claimed was verified will discount everything else on the deck; an examiner who hears it from you first will trust the rest.]`

---

## Slide 11 — Demo

- `python reviewer.py samples/sample.diff` — mock mode, four findings, verdict block.
- `GET /health` — mode, provider, rule count, credential state.
- `GET /docs` — the API surface.
- A posted pull-request review — inline findings and the summary.
- `benchmarks/out/chart.png`.

`[SPEAKER NOTE PLACEHOLDER: 120 seconds. Screenshots, not a live terminal — a live demo fails in front of an audience for reasons unrelated to the work. Narrate the CLI run in one pass: four findings, three critical, one medium, verdict block. Then the health response, because it answers "what is this actually running" in one line.]`

`[FILL AFTER BENCHMARK: screenshot — CLI review of samples/sample.diff]`
`[FILL AFTER BENCHMARK: screenshot — GET /health response]`
`[FILL AFTER BENCHMARK: screenshot — posted pull-request review]`
`[FILL AFTER BENCHMARK: screenshot — benchmark chart]`

---

## Slide 12 — Limitations

- The evaluation dataset is not labelled; there is no measured result yet.
- The local path is stub-verified, not model-verified.
- The hosted path has never run live.
- Labels are one person's judgement; agreement is not measured.
- Matching is greedy and line-based, so a near-miss scores twice — as a false
  positive and as a false negative.
- Pattern rules cannot follow data across functions.
- The idempotency marker is a public HTML comment and can be suppressed by a third
  party who can comment on the pull request.
- The interpreter is pinned to a release that reaches end-of-life in October 2026.

`[SPEAKER NOTE PLACEHOLDER: 90 seconds. Pick the two limitations that actually bound the claims — no labelled dataset, and an unexercised model path — and say what each one costs the conclusion. Do not read all eight. Ending on the interpreter pin shows you know the project has a maintenance horizon.]`

---

## Slide 13 — Future work

- Label a dataset, with more than one annotator, and report agreement.
- Run the benchmark on real local-model output.
- Verify the hosted path with a live key.
- Replace the public marker with an author-filtered listing or an HMAC-derived one.
- Extend the rule engine with data-flow analysis.
- Move off the end-of-life interpreter.

`[SPEAKER NOTE PLACEHOLDER: 60 seconds. Pair each item with the constraint that blocks it, not just the wish — the dataset needs a human, the local run needs hardware, the marker change needs a format decision. That distinction is what separates future work from a wish list.]`

---

## Slide 14 — References

- OWASP Top Ten.
- FastAPI and Python documentation.
- The local and hosted model documentation used.
- The papers discussed in the report's related-work section.
- The benchmark contract and dataset format in this repository.

`[SPEAKER NOTE PLACEHOLDER: 20 seconds. Do not read the references. Say that the report carries the full bibliography and that this slide lists the sources that shaped the design. Then stop and invite questions.]`

---

## Build notes

- Total speaking time is the sum of the per-slide estimates above. If the slot is
  shorter, trim slide 5 and slide 13 first; do not trim slide 10.
- Reuse the `ARCHITECTURE.md` diagram verbatim on slide 4. Two diagrams of one system
  is a defect, and an examiner will find the difference.
- After the benchmark runs, fill slide 9's dataset line, slide 10's dataset row, and
  slide 11's screenshots — in that order, then re-read slide 10 for anything the
  results contradict.
- `grep -rn "SPEAKER NOTE PLACEHOLDER" docs/report` and
  `grep -rn "FILL AFTER BENCHMARK" docs/report` must both return nothing before the
  defence.
