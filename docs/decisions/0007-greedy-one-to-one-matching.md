# 0007 — One-to-one greedy matching, largest overlap first

## Status

Accepted — 2026-11-14

## Context

Scoring requires deciding, for each sample, which human labels the reviewer
reproduced. The matching rule is fixed by `benchmarks/CONTRACT.md:19`: same file, and
overlapping line ranges, and a compatible category. Labels and findings are both sets
of ranges, and a naive matcher can count the same finding twice — once for the label
it truly matches and once for a neighbouring label that overlaps it — inflating
precision and recall together.

That forces an assignment problem: pairs must be consumed one-to-one.

## Decision

`match_sample` (`benchmarks/matching.py:473`) builds every viable (label, finding)
candidate pair, sorts them, and consumes them greedily.

- One-to-one: `used_labels` and `used_findings` sets (`benchmarks/matching.py:526`)
  are consulted before a pair is accepted (`benchmarks/matching.py:529`), so no label
  and no finding is counted twice.
- Largest overlap first: candidates sort on `(-overlap, file, expected line_start,
  actual line_start, ...)`, with the two element indices appended as a final
  discriminator so duplicate labels cannot make the result depend on input order.
  The rule is stated at `benchmarks/matching.py:10`: "One-to-one, greedy, largest
  overlap first."
- Determinism is a requirement, not a nicety: the same inputs must produce the same
  numbers across runs, so nothing iterates a set to decide an outcome.
- The limitation is documented where the code lives (`benchmarks/matching.py:26`)
  and restated in the generated report (`benchmarks/report.py:353`), so a reader of
  the numbers sees it too.

## Consequences

Positive: the matcher is about a screen of code, has no dependency, and is obviously
correct at what it does. It runs over a dataset small enough that per-sample cost is
irrelevant, and its output is reproducible byte for byte. The tie-break makes the
greedy order itself deterministic, which is the property the benchmark actually needs.

Negative: greedy can under-match, and the code says so. A label overlapping two
findings by 3 and 2 lines takes the 3-line finding and may strand a second label that
only the 3-line finding could have matched; an optimal assignment would have scored
two true positives where greedy scores one. The error is a systematic understatement
of recall in contrived overlaps, not random noise, so it does not average out. Every
reported precision/recall figure inherits that bias, small but real.

## Alternatives considered

**Optimal assignment (Hungarian / Jonker-Volgenant) over the overlap matrix.** Would
remove the bias entirely. It lost on cost: an exact solver is another dependency or
another hundred lines, it must still be made deterministic on ties, and the dataset it
would run on is a handful of hand-labelled samples where a one-pair difference is
already invisible in the reported figures. The contract locks greedy, so the harness
instead removes ambiguity by making every tie deterministic.

**First-match-in-label-order, without sorting by overlap.** Simplest of all, and it
makes the result depend on label order — the same data in a different order would
score differently. Rejected.

**Many-to-one (a label may match several findings, or vice versa).** Avoids stranding,
but it lets one finding satisfy two labels and quietly inflates recall. Rejected.
