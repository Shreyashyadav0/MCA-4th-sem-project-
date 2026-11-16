# Labelling — how to produce the benchmark's missing input

There is no precision, recall or F1 figure for this tool, and lesson 10.10 says so.
The reason is not that the harness is missing — it is written, tested and scored. The
reason is that **the labels are missing**, and labels have to come from a person.

This file is about producing them. Read it once, then work through it in the order
below. It is written for you, not for an agent.

---

## What a label is

A label says: *for this diff, a careful reviewer would raise these findings, at these
lines, of these severities.* It is a judgement about code, not a copy of the tool's
output.

One label is one finding:

| Field | Meaning |
|---|---|
| `file` | Post-change path, exactly as the diff's `+++` line spells it |
| `line_start` | First new-side line, 1-based, inclusive |
| `line_end` | Last new-side line; equal to `line_start` for a single line |
| `category` | One of the rule categories, or `llm` for something only a model would catch |
| `severity` | `LOW`, `MEDIUM`, `HIGH` or `CRITICAL` |

An empty label file — `{"findings": []}` — is a real and valuable label. It says this
change is clean, and that is what the tool's false positives are measured against.
**Do not skip clean diffs.** A set of only-buggy diffs cannot measure false positives
at all.

---

## The one rule that matters

**Never label by agreeing with the tool.**

A label set built from the tool's own suggestions measures the tool against itself and
produces a number near 1.0 that means nothing. `docs/decisions/0006` exists for this
reason, and the labelling tool is built so the predictions arrive as questions rather
than answers.

Two habits keep you honest:

1. **Read the diff before you look at the tool's findings.** The tool prints them after
   the diff, but scroll back. Decide what you think is wrong, then compare.
2. **Always answer the "did the tool miss anything?" prompt.** That is where the
   tool's recall actually gets measured. A session where you never add a finding is a
   session where you were reading the tool's output instead of the code.

---

## Which samples, and how many

Start with **20 to 30 samples**. That is enough for the first honest number and small
enough to finish in one or two sittings.

**A small honest set beats a large careless one.** Thirty diffs you read properly give
a figure with a stated sample count beside it. Three hundred you skimmed give a figure
that looks authoritative and is not — and the harness prints the sample count next to
every number precisely so a reader can see which one they are looking at.

Where the samples come from:

- **Your own commits.** `git show <sha> --format= > sample.diff` gives a real diff with
  a real reason behind it. You already know what was wrong with it, which makes
  labelling faster and more accurate.
- **Pull requests you have reviewed.** Same advantage.
- **Deliberately broken code.** Useful for CRITICAL cases, but do not let the set become
  only these: a benchmark of synthetic bugs measures detection of synthetic bugs.

Aim for a mix: roughly half with something genuinely wrong, a quarter clean, a quarter
borderline. If every sample has a CRITICAL, precision will look excellent and tell you
nothing.

---

## Running the tool

```console
$ python benchmarks/labelling.py --list                      # what is done, what is left
$ python benchmarks/labelling.py                             # label the next pending one
$ python benchmarks/labelling.py --sample 0003               # one specific sample
$ python benchmarks/labelling.py --force --sample 0003       # relabel one you got wrong
```

For each sample it shows the diff, then the rule engine's findings one at a time. For
each: is this a real finding? If yes, keep or change the severity and category. Then it
asks whether the tool missed anything, and takes a file, a line, a severity and a
category for each one you add.

**It is resumable.** A sample is only written once every finding in it has a verdict.
Ctrl-D or `q` quits and keeps everything already written; re-running continues at the
first sample with no label file. You can leave in the middle of a sample and lose
nothing but that sample's partial answers.

It refuses to overwrite an existing label without `--force`, because relabelling by
accident is how a set quietly loses the labels you were proudest of.

No network, no keys, no timestamps in the output — a label file is the same bytes
whenever you write it.

---

## The judgement calls

### A line range that overlaps but does not match

The matcher pairs a finding with a label when they are in the same file and their
lines overlap by at least one. It does not require an exact range match.

So when the tool says lines 12–14 and you think 12–13: **label what you actually
believe**, 12–13. The overlap means it will still score as a match, and the label file
stays honest about what you think. Do not widen your label to meet the tool's range —
that is agreeing with the tool by another route.

If the tool flags line 20 and you think the problem is line 12, they do not overlap and
you should label line 12. That will score as one false negative and one false positive,
and that is the correct outcome: the tool found the right file and the wrong place.

### When you are uncertain

Ask: *would I leave a review comment here?* If yes, it is a finding. If you would
mention it to a colleague but not block on it, label it `LOW`. If you would not mention
it at all, do not label it.

Do not label a finding you cannot articulate in one sentence. If you cannot say what is
wrong, it is not a label, it is a feeling — and it will make the benchmark measure your
mood.

If a sample is genuinely too ambiguous to judge, **skip it entirely** rather than
guessing. Delete its directory from the set and move on. A sample you were unsure about
is a sample that adds noise to every figure.

### Severity

Use the tool's own ladder, because the benchmark compares severities: `CRITICAL` for
something that must block, `HIGH` for something that should, `MEDIUM` for something
worth a comment, `LOW` for style and hygiene. If you disagree with the tool's severity
but agree there is a finding, **change the severity** — the tool asks, and the
disagreement is data.

### Category

Pick the rule category that fits. Use `llm` only for something a rule could not catch —
a design flaw, a wrong abstraction, a comment that contradicts the code. Those are the
most valuable labels in the set, because they are what a model is supposed to add over
the rule engine.

---

## Knowing when enough is enough

Stop when **adding ten more samples changes no figure by more than a few hundredths**.
Practically: score at 20, score again at 30. If precision moved from 0.61 to 0.60, you
have enough for a claim. If it moved from 0.61 to 0.45, keep going.

Stop earlier if you notice you are labelling faster than you are reading. That is the
signal that the set is becoming careless, and a careless set is worse than a small one.

---

## After labelling

```console
$ python -m benchmarks.eval --labels
```

That prints precision, recall and F1 per mode, latency p50 and p95, and **the sample
count beside every figure**. With no labels it prints `no labels yet` and exits 3 — it
will not print a number computed from an empty set.

Then lesson 10.10 can be updated from the harness's own output. `MAINTAINING.md`
records that step; do not type a figure into the lesson by hand.

---

## What not to do

- Do not label by accepting every suggestion. The tool will tell you how many of your
  labels it did not report — if that number is zero across a whole session, re-read the
  diffs.
- Do not label from the tool's output without opening the diff.
- Do not add samples you have not read, to make the count look better.
- Do not quote a figure without the sample count beside it.
- Do not put a figure in a lesson, a README or a commit message unless it came out of
  `benchmarks.eval`.
