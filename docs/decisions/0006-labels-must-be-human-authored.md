# 0006 — Benchmark labels are human-authored only

## Status

Accepted — 2026-11-14

## Context

The benchmark scores the reviewer against labelled diffs: for each sample, which
labels did the tool reproduce, which did it miss, which did it invent. Everything the
harness reports — precision, recall, F1, per-category breakdown — is a function of
those labels. If the labels are generated, the numbers describe the generator.

The failure is easy to reach. The rule engine is deterministic, so running it over a
diff and writing its output as `expected.json` produces a benchmark where the rule
engine scores 100% and tells you nothing. A model doing the same is worse, because the
labels then look plausible and nobody can tell they were copied.

## Decision

Labels are written by a human, and the harness never generates or infers them.
`benchmarks/golden/README.md:3` states it: "**Labels in this directory must be written
by a human.** A label produced by the rule engine, by an LLM, or by copying the tool's
own output makes the benchmark measure nothing: it would score the tool against
itself."

- The loader treats labels as ground truth and refuses to repair them:
  `ExpectedFinding` is documented as "One human label: what should have been reported,
  and where" (`benchmarks/loader.py:93`), and a schema mismatch raises `DatasetError`
  rather than being coerced (`benchmarks/loader.py:260`).
- The shipped dataset contains no evaluation data at all:
  `benchmarks/golden/manifest.json` has `"evaluation_samples": []` and marks
  `example_01` / `example_02` as `format_examples`, excluded from every metric.
- An empty `"findings": []` is a legitimate human label meaning "this change is
  clean", which is how true negatives are measured.

## Consequences

Positive: the numbers mean what they claim. A false positive is a finding no human
wanted, not a finding the generator did not produce. The empty evaluation set is an
honest statement of state rather than a fabricated one — no precision figure in this
repository is backed by machine-written labels.

Negative, and it is a real cost: the evaluation set cannot be produced automatically.
Label authoring is the bottleneck — every sample is a diff read by hand and a JSON
file written by hand — so the benchmark is deferred to a human and the shipped
manifest is empty until someone does that work. A repository with `"evaluation_samples":
[]` reports no benchmark numbers, which is less impressive than a populated table and
more truthful. The discipline also cannot be enforced by code: nothing stops a future
contributor from running the rule engine and committing its output as labels. Only
this record and the README warn against it.

Note on drift: `benchmarks/golden/README.md:55` refers to `collect_candidates.py` and
`label_helper.py` as the tooling that writes an empty template and prompts a human.
Neither script exists in this tree; the stated policy is real, the helper tooling is
not.

## Alternatives considered

**Bootstrap labels from the rule engine, then have a human edit them.** Fast, and it
anchors the human on the tool's output — the reviewer will confirm what the tool
already found and miss what it did not. Rejected.

**Use an LLM as the labeller.** Scales, but makes the benchmark a comparison between
two models with an unknown grader, and cannot detect a defect neither model knows.
Rejected.

**Score against a public dataset's labels.** Would give volume, but the categories and
the five-field contract would have to be mapped onto someone else's taxonomy, and the
mapping is itself a judgement nobody has validated. Not rejected on principle —
deferred.
