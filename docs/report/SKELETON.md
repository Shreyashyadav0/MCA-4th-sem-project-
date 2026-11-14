# MCA report — skeleton

Purpose: the structure of the project report, with a word target and writing
guidance for each section. This is a skeleton, not a draft. It contains no
results, because no evaluation has been run yet: the dataset at
`benchmarks/golden/` holds two format examples and no labelled samples, and the
local-model benchmark has never run against a real model.

**Two rules that override everything else in this document.**

1. **The report must not claim any result that the benchmark did not produce.**
   Every sentence in sections 5 and 6 that carries a number must trace to a file
   in `benchmarks/out/` (`metrics.csv`, `summary.json`, `summary.md`,
   `chart.png`). If a figure is not in those artifacts, it does not go in the
   report — not as an approximation, not as a "typical" value, not as a number
   remembered from an earlier run.
2. **The two samples in `benchmarks/golden/example_01` and `example_02` are format
   examples, not evaluation data.** `benchmarks/golden/manifest.json` lists them
   under `format_examples` and keeps `evaluation_samples` empty. Any metric
   computed over them is a harness smoke test. Quoting such a number as a result
   is a misrepresentation, even if it looks plausible.

A third rule, less urgent: do not write prose in a section before the facts it
depends on exist. Sections 1–4 and 7–9 can be written now. Sections 5 and 6
cannot, and placeholders are the correct state for them.

---

## Word budget

| Part | Target words |
|---|---|
| Title page | 0 (fixed fields) |
| Abstract | 250–300 |
| Table of contents | 0 (generated) |
| 1 Introduction | 900 |
| 2 Literature / related work | 1,200 |
| 3 System design | 1,500 |
| 4 Implementation | 2,000 |
| 5 Testing and evaluation | 1,200 |
| 6 Results and discussion | 1,000 |
| 7 Limitations | 600 |
| 8 Conclusion and future work | 600 |
| 9 References | 0 (list of 20–30 entries) |
| Appendices | n/a |
| **Body total (1–8)** | **~9,000** |

Numbers in this table are writing targets, not measurements. They are the only
numbers in this file that are allowed to be invented, and they must not appear in
the report as results.

---

## Title page

Fixed fields, no prose:

- Project title: *Autonomous AI Code Reviewer & PR Assistant*.
- Degree, programme, department, institution.
- Candidate name and roll number; supervisor name.
- Submission date — set at submission time, not now.

No word target. Keep the institution's own cover format if one is mandated; it
outranks this skeleton.

---

## Abstract — 250–300 words

Guidance: state the problem, the approach, the artefact, and the evidence, in that
order, in one paragraph. The approach sentence is the honest one: a deterministic
rule engine that always runs, with an optional LLM layer over it. The evidence
sentence must be written only after the benchmark exists; until then, end the
abstract at the artefact and insert
`[FILL AFTER BENCHMARK: abstract result sentence]`. Do not describe the system as
"AI-powered" without also saying what happens when the model is unavailable — that
fallback is the contribution, not a footnote.

---

## Table of contents

Generated from headings. Regenerate after every structural edit; a stale table of
contents is the first thing an examiner notices.

---

## 1 Introduction — 900 words

### 1.1 Problem — 350 words

Guidance: what a code review is for, and where it fails at scale — reviewer time,
review latency on small pull requests, and the well-documented inconsistency of
human review. Frame the gap concretely: the tooling that exists either lints
syntax and style with no security model, or comments freely with no guarantee of
being available, reproducible or correct. Avoid unsourced prevalence statistics;
if you want one, cite it or drop it.

### 1.2 Motivation — 250 words

Guidance: why this problem, and why this approach. The two motivating constraints
are (a) a reviewer that cannot run is worthless, so availability must not depend
on a third-party API, and (b) a reviewer whose output changes between identical
runs cannot be evaluated, so the base layer must be deterministic. Those two
constraints explain nearly every design decision later in the report; say so here.

### 1.3 Objectives — 300 words

Guidance: four or five numbered objectives, each phrased so it can be marked
achieved or not achieved, and each mapped to the section that demonstrates it.
Suggested set: parse a unified diff and anchor findings to changed lines; detect a
defined set of security and quality defects deterministically; add an optional LLM
review layer that degrades without failing; post reviews to a pull request
idempotently; measure the whole thing on a labelled dataset. The last objective is
the one that is not yet met — say that in the report, or the report is overclaiming.

---

## 2 Literature and related work — 1,200 words

Guidance: three groups, in this order. (a) Static analysis and rule-based
detection — the OWASP Top Ten as the taxonomy the rule set maps onto, plus the
long line of pattern-matching analysers and what they systematically miss. (b)
LLM-based code review and defect detection — what recent work claims, and the two
recurring weaknesses: hallucinated locations and non-determinism. (c) Review
automation in the development workflow — bots that comment on pull requests, and
the availability and idempotency problems that follow. Close the section with the
gap statement that motivates this project: work that uses an LLM alone does not
address availability or reproducibility, and work that is purely rule-based does
not address semantic defects.

Every claim needs a citation. Do not cite a paper you have not read; a short,
accurate bibliography beats a long, decorative one. Prefer primary sources
(papers, standards, official documentation) over blog posts.

---

## 3 System design — 1,500 words

Guidance: this section is a narrative over `ARCHITECTURE.md`, not a copy of it.
Do not paste the document; reference it and explain the reasoning in report voice.

Cover, in order: the component map (CLI, parser, rule engine, provider layer,
router, API, GitHub client, benchmark harness); the five-field finding contract
and why a sixth field is a validation error rather than an extra; the anchor model
(`anchored` / `file_only` / `unanchored`) and why GitHub's line-comment semantics
force it; the config boundary, where a missing credential is data rather than an
exception; the single router as the one place that decides live versus offline;
and the single OpenAI-compatible adapter that serves both the hosted and the local
model.

Include the architecture diagram — reuse the one in `ARCHITECTURE.md` rather than
drawing a second, diverging version. Caption it and refer to it in the text.

---

## 4 Implementation — 2,000 words

Guidance: one subsection per phase, in build order, each stating what the phase
added, the interface it fixed, and the failure mode it closed. Roughly 300–350
words per phase; the local rule engine and the provider layer deserve the most.

### 4.1 Phase 1 — scaffold, configuration boundary, finding contract, CLI
### 4.2 Phase 2 — diff parsing and anchoring to changed line ranges
### 4.3 Phase 3 — local rule engine (63 OWASP-mapped rules) and the webhook server
### 4.4 Phase 4 — the LLM review layer and the guaranteed local fallback
### 4.5 Phase 5 — posting reviews to a pull request: inline, summary, idempotent
### 4.6 Phase 5.5 — one OpenAI-compatible adapter, two providers, one selector

For each phase, name the module that owns it and the tests that hold it. Keep code
listings short: a signature or a ten-line excerpt, never a whole function. Do not
claim a phase is "complete" without saying what it does not do — every phase in
this project has a stated non-goal, and listing them here makes section 7 honest
instead of defensive.

---

## 5 Testing and evaluation — 1,200 words

**Every result line in this section is a placeholder until the benchmark has run.
No numbers. Not one.**

Guidance: separate the two halves clearly. Testing is what exists now: the suite,
what it covers, and what the skip means. Evaluation is the benchmark harness —
methodology, dataset, matching rule, metrics — and its results are placeholders.

### 5.1 Test strategy — 400 words

Guidance: describe the layers — a firing sample for every rule (so a silently
broken pattern fails the suite), false-positive guards, malicious payloads,
suppression semantics, the API schema, webhook signature verification, provider
degradation, and the guarantee that a credential never reaches a log record. State
the suite's size and the single skip, and say what the skip is.

`[FILL AFTER BENCHMARK: exact suite line — total passed, skipped, interpreter]`

### 5.2 Benchmark methodology — 400 words

Guidance: the harness, not the results. The dataset format (`change.diff` +
hand-written `expected.json`), why labels must be human-written, the matching rule
(same file, overlapping line range, equal or equivalent category, one-to-one,
greedy, largest overlap first), the metrics (precision, recall, F1, false-positive
rate, p50/p95 latency), the three modes (`rules`, `local`, `merged`), and the fact
that an unconfigured mode skips cleanly rather than failing. Name the artifacts.

`[FILL AFTER BENCHMARK: dataset size — number of labelled samples, per category]`
`[FILL AFTER BENCHMARK: label provenance — who labelled them, against which diff revision]`

### 5.3 Results — 400 words

Guidance: the table and nothing else until the table exists. One row per mode,
columns precision, recall, F1, false-positive rate, p50, p95, samples. Reference
the chart artifact. Any prose here interprets; it does not supply.

`[FILL AFTER BENCHMARK: results table — one row per mode, from benchmarks/out/metrics.csv]`
`[FILL AFTER BENCHMARK: latency figures — p50 and p95 per mode, from summary.json]`
`[FILL AFTER BENCHMARK: per-category breakdown — where each mode gains and loses]`

If a mode could not be run in the submission environment, the table says "not run"
in that row. It does not carry a number from a different machine.

---

## 6 Results and discussion — 1,000 words

Guidance: interpretation, not repetition of section 5. Three questions: does the
deterministic layer alone justify the design (what it catches, what it cannot
catch); does the model layer add anything the rules miss, and at what cost in
latency and in false positives; and where does the hybrid arrangement fail. Be
willing to report a null or negative finding — a model that adds nothing over 63
rules on this dataset is a legitimate, useful result, and it is more defensible
than a tuned number.

`[FILL AFTER BENCHMARK: rules-only versus local versus merged — the central comparison]`
`[FILL AFTER BENCHMARK: false-positive analysis — the dominant false-positive categories and a worked example]`
`[FILL AFTER BENCHMARK: false-negative analysis — the defect classes no mode detected]`
`[FILL AFTER BENCHMARK: cost of the model layer — latency delta and its effect on review turnaround]`

Do not discuss a number that is not in `benchmarks/out/`. Do not compare against a
published system's reported figures unless the datasets are comparable, and if you
do compare, state that they are not.

---

## 7 Limitations — 600 words

Guidance: state them plainly and without apology. At minimum, the limitations that
are already known and true:

- The evaluation dataset is small and, at the time of writing, does not exist as
  labelled data; the two samples in the repository are format examples.
- The local-model path has been verified against a stub server, not a real model,
  so its behaviour on real model output is unmeasured.
- The Sarvam path has never run against the live hosted model; no real key has
  been used at any point.
- Labels are one person's judgement; inter-annotator agreement is not measured.
- Matching is greedy and file-and-line based, so a correct finding on the right
  line with a neighbouring category can score as both a false positive and a
  false negative.
- The rule set is pattern-based and cannot detect defects that require data flow
  across functions.
- The idempotency marker is a public HTML comment, so a third party able to
  comment on the pull request can suppress a review.
- The interpreter is pinned to a release that reaches end-of-life in October 2026.

Add anything the benchmark reveals. Remove nothing because it is inconvenient.

---

## 8 Conclusion and future work — 600 words

### 8.1 Conclusion — 300 words

Guidance: restate the objective set from 1.3 and mark each one achieved, partially
achieved, or not achieved, with a pointer to the evidence. The evaluation objective
is the one that will be partial unless the dataset is labelled; say so.

### 8.2 Future work — 300 words

Guidance: the honest list. Label a larger dataset with more than one annotator and
measure agreement; run the local-model benchmark on real model output; verify the
hosted path with a live key; replace the public marker with an author-filtered
listing or an HMAC-derived marker; extend the rule engine with data-flow analysis;
move off the end-of-life interpreter. Each item should name the constraint that
blocks it, not just the wish.

---

## 9 References

Guidance: 20–30 entries, one consistent style throughout (IEEE is the usual choice
for an MCA report; confirm with the department). Cite: OWASP Top Ten, the Python
and FastAPI documentation you actually relied on, the model's own documentation,
the papers discussed in section 2, and the standards the crypto and auth rules
reference. Cite the dataset labelling procedure if you adopt one. No entry that
does not appear in the text, and no claim in the text without an entry.

---

## Appendices

### Appendix A — Commands

Guidance: the exact commands used to produce every number in sections 5 and 6, in
order, with the working directory and the interpreter. Include the one-command
health check. A reader must be able to reproduce the results from this page alone.

### Appendix B — Screenshots

Guidance: CLI review output, the `/health` response, the `/docs` page, a posted
pull-request review, and the benchmark chart.

`[FILL AFTER BENCHMARK: screenshot — CLI review of samples/sample.diff]`
`[FILL AFTER BENCHMARK: screenshot — GET /health response]`
`[FILL AFTER BENCHMARK: screenshot — benchmark chart from benchmarks/out/chart.png]`
`[FILL AFTER BENCHMARK: screenshot — posted pull-request review with inline and summary comments]`

### Appendix C — Repository map

Guidance: the layout table from `README.md`, plus the benchmark harness and the
documentation tree. One page.

---

## Pre-submission checklist

- [ ] `grep -rn "FILL AFTER BENCHMARK" docs/report` returns nothing.
- [ ] Every number in sections 5 and 6 appears in a file under `benchmarks/out/`.
- [ ] No sentence claims a result from `example_01` or `example_02`.
- [ ] The abstract's result sentence matches section 5's table exactly.
- [ ] The table of contents is regenerated.
- [ ] Every reference is cited in the text and every citation has a reference.
- [ ] Section 7 lists the stub-server and no-live-key limitations.
- [ ] The word count of sections 1–8 is within 10% of 9,000.
