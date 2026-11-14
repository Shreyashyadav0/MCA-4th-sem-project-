# 7 Reports and Layouts

## 7.1 What the system reports, and to whom

The reviewer produces four distinct outputs, and each exists for a different reader.

**The command-line report** is for the developer who is about to commit. It is a human
summary printed to standard output: the target, the mode and provider that actually ran, the
changed files with their added-line spans, one numbered block per finding, and a verdict. It
is the format an examiner sees first and the format the demonstration uses, because it
requires nothing but a terminal.

**The JSON document** is for a machine. The same run with `--json` emits one JSON object on
standard output — the same five-field findings, plus the parsed file summaries, the anchor
status of every finding and the verdict — so a continuous-integration job, a script or another
tool can consume the review without parsing prose. The `--json` flag also moves all narration
to standard error, so standard output stays a single valid document.

**The pull-request comment** is for the code's author, in the place where they are already
working. It takes two forms: inline comments anchored to the changed lines, and one summary
comment carrying the verdict, the severity counts, and every finding that could not be placed
inline. Both carry an idempotency marker so a re-run does not duplicate them.

**The benchmark artefacts** are for the person evaluating the system, and consist of four
files written to a directory: `metrics.csv`, `summary.json`, `summary.md` and `chart.png`.

Every block quoted in this chapter was produced by running the command shown above it, on the
checked-in tree, while this report was being written.

## 7.2 Sample layout: the command-line report

```bash
python reviewer.py samples/sample.diff --offline
```

Real output:

```text
target   : samples/sample.diff
mode     : mock
provider : mock
model    : local-rules
files    : 2 changed
findings : 4 (CRITICAL 3, HIGH 0, MEDIUM 1, LOW 0)
note     : mock mode: offline mode requested; local rule engine used
note     : local rule engine: 63 deterministic rules, no network, no API key

changed lines:
  modified  app/db.py  (+4: 3-4, 7-8)
  added     app/report.py  (+5: 1-5)

1. File          : app/db.py
   Line          : 3
   Severity      : CRITICAL
   Issue         : A GitHub token literal is committed here, granting every scope the token holds to anyone who reads the repository. (rule: secret/github-token)
   Suggested Fix : Revoke the token, then read it at runtime: `token = os.environ["GITHUB_TOKEN"]`.
   Anchor        : anchored @ @@ -1,5 +1,8 @@

2. File          : app/db.py
   Line          : 3
   Severity      : CRITICAL
   Issue         : `API_TOKEN` is assigned a literal credential, so the secret is committed to git history and stays readable to anyone with repo access even after it is rotated. (rule: secret/hardcoded-credential)
   Suggested Fix : API_TOKEN = os.environ["API_TOKEN"]  # load from the environment; fail loudly when it is unset
   Anchor        : anchored @ @@ -1,5 +1,8 @@

3. File          : app/db.py
   Line          : 7
   Severity      : CRITICAL
   Issue         : SQL is assembled by string interpolation, so any value reaching this line can change the statement and read, alter or drop the table. (rule: unsafe/sql-injection)
   Suggested Fix : Pass parameters instead: `db.execute("SELECT * FROM users WHERE id = ?", (uid,))` — the driver quotes them, interpolation does not.
   Anchor        : anchored @ @@ -1,5 +1,8 @@

4. File          : app/report.py
   Line          : 1
   Severity      : MEDIUM
   Issue         : `render` is a public function without full annotations, so callers and the reviewer cannot tell what goes in or what comes out. (rule: quality/missing-type-hints)
   Suggested Fix : Annotate it: `def render(value: str) -> str:` — every parameter and the return type.
   Anchor        : anchored @ @@ -0,0 +1,5 @@

verdict  : block
```

The layout is deliberately mechanical. A fixed-width header block answers "what ran and on
what" before any finding is shown, and the three labelling lines — `mode`, `provider`,
`model` — are what stop a degraded run from being mistaken for a live one. The
`changed lines` section is the parse made visible, so a reader can check that the diff was
understood before trusting what was found in it. Each finding block is one screen-width
record with a stable field order, and the rule identifier is appended to the issue text in
parentheses, so a reader can look the policy up with `GET /rules/{id}`. The anchor line names
the hunk the finding was placed in, or states that it could not be placed. The final
`verdict` is the only line a script needs to grep: `block` when any finding is CRITICAL or
HIGH, `approve with comments` when any is MEDIUM or LOW, and `approve` when there are none.

One detail is visible in the capture and worth naming: the run prints a single
`WARNING reviewer.openai_compat: ...` line on standard error, which does not appear above
because only standard output is quoted. A degraded run is never silent, and the warning goes
to the stream that will not corrupt a redirected report.

## 7.3 Sample layout: the JSON document

```bash
python reviewer.py samples/sample.diff --offline --json
```

Real output, trimmed — the full document repeats the anchor block for all four findings, and
that repetition is marked with a comment that is not part of the emitted JSON:

```json
{
  "mode": "mock",
  "target": "samples/sample.diff",
  "files": [
    {
      "path": "app/db.py",
      "change": "modified",
      "added_spans": ["3-4", "7-8"],
      "added_line_count": 4,
      "hunk_count": 1,
      "binary": false
    },
    {
      "path": "app/report.py",
      "change": "added",
      "added_spans": ["1-5"],
      "added_line_count": 5,
      "hunk_count": 1,
      "binary": false
    }
  ],
  "findings": [
    {
      "file": "app/db.py",
      "line": "3",
      "severity": "CRITICAL",
      "issue": "A GitHub token literal is committed here, granting every scope the token holds to anyone who reads the repository. (rule: secret/github-token)",
      "suggested_fix": "Revoke the token, then read it at runtime: `token = os.environ[\"GITHUB_TOKEN\"]`."
    }
  ],
  "anchors": [
    {
      "finding": { "file": "app/db.py", "line": "3", "severity": "CRITICAL", "issue": "...", "suggested_fix": "..." },
      "status": "anchored",
      "hunk_header": "@@ -1,5 +1,8 @@",
      "detail": "added line: 3"
    }
  ],
  "notes": [
    "mock mode: offline mode requested; local rule engine used",
    "local rule engine: 63 deterministic rules, no network, no API key"
  ],
  "verdict": "block"
}
```

The document has seven top-level keys — `mode`, `target`, `files`, `findings`, `anchors`,
`notes`, `verdict` — and the shape is a contract rather than a convenience. `findings` is the
five-field list and nothing more; `anchors` carries the placement decision separately, so a
consumer that only wants the findings never has to know what an anchor is; `files` is the
parse summary; `notes` is the human explanation of the mode; and `verdict` is a computed field
that is present in the serialised form and ignored on the way back in, so the document
round-trips through the model without the caller having to strip it. The `--json` contract is
also why posting narration is redirected to standard error: a single stray line on standard
output would break every consumer of this format.

## 7.4 Sample layout: the pull-request comment

Posting produces two artefacts on the pull request. The first is one inline comment per
anchored finding, attached to the changed line. Real capture, rendered from the same four
findings by the shipped code:

```markdown
**CRITICAL** — `app/db.py:3`

- **Issue:** A GitHub token literal is committed here, granting every scope the token holds to anyone who reads the repository. (rule: secret/github-token)
- **Suggested fix:** Revoke the token, then read it at runtime: `token = os.environ["GITHUB_TOKEN"]`.

<!-- ai-code-reviewer:3f42ce195e754f16 -->
```

The second is the summary comment, which is the home for everything that cannot be an inline
comment: findings in a file the diff does not touch, findings whose line was not changed, and
anchored findings that overflowed the inline cap or were demoted after a rejection. A worked
example, captured by rendering a payload of five findings with the inline cap deliberately set
to two:

```markdown
## Autonomous AI Code Review

**Verdict:** block · **Findings:** 5 (CRITICAL 3, HIGH 1, MEDIUM 1, LOW 0)
**Inline comments:** 2 · **In this summary:** 3

### `app/db.py`

- **HIGH** `app/db.py:99` — Unanchored demonstration finding. (rule: unsafe/sql-injection)
  - Suggested fix: Pass parameters instead.

### Additional findings

_Anchored findings that could not be attached inline (inline cap reached or GitHub rejected the position)._

- **CRITICAL** `app/db.py:7` — SQL is assembled by string interpolation, so any value reaching this line can change the statement and read, alter or drop the table. (rule: unsafe/sql-injection)
  - Suggested fix: Pass parameters instead: `db.execute("SELECT * FROM users WHERE id = ?", (uid,))` — the driver quotes them, interpolation does not.
- **MEDIUM** `app/report.py:1` — `render` is a public function without full annotations, so callers and the reviewer cannot tell what goes in or what comes out. (rule: quality/missing-type-hints)
  - Suggested fix: Annotate it: `def render(value: str) -> str:` — every parameter and the return type.

<!-- ai-code-reviewer:0abd0888128f685c -->
```

Three properties of this layout carry weight. Every path is rendered through the code-span
fence described in Chapter 6, so a hostile path is displayed and never interpreted. Every
body ends with a marker line whose fingerprint is derived from the findings rather than from
the commit, so an identical re-review of an unchanged diff is skipped while any change in the
findings produces a new marker. And the summary always states both counts — how many comments
are inline and how many are in the summary — so a reader can tell the difference between a
review with two findings and a review that placed two of five.

## 7.5 Sample layout: benchmark artefacts

```bash
python -m benchmarks.eval --modes rules --dataset benchmarks/golden --out /scratch/work/out
```

Real output:

```text
benchmark: dataset=benchmarks/golden modes=rules samples=2

mode       samples  skipped  precision     recall         f1        fpr      p50ms      p95ms  note
---------  -------  -------  ---------  ---------  ---------  ---------  ---------  ---------  --------
rules            2        0     0.8000     1.0000     0.8889     1.0000      0.755      1.819  all 2 sample(s) are format examples; these numbers are a smok...

  metrics.csv  written      /scratch/work/out/metrics.csv
  summary.json written      /scratch/work/out/summary.json
  summary.md   written      /scratch/work/out/summary.md
  chart.png    written      /scratch/work/out/chart.png
```

The `metrics.csv` header, which is the machine-readable contract of the harness:

```text
mode,samples,skipped,precision,recall,f1,fpr,tp,fp,fn,tn,latency_p50_ms,latency_p95_ms,note,cat_tp_config,cat_fp_config,cat_fn_config,cat_tp_injection,cat_fp_injection,cat_fn_injection,cat_tp_quality,cat_fp_quality,cat_fn_quality,cat_tp_secrets,cat_fp_secrets,cat_fn_secrets
```

One row follows per mode, so a spreadsheet or a plotting script reads the aggregate metrics
and the per-category tallies from the same line. The corresponding row for this run was:

```text
rules,2,0,0.8000,1.0000,0.8889,1.0000,4,1,0,0,0.755,1.819,"all 2 sample(s) are format examples; these numbers are a smoke test, not evaluation data",1,0,0,1,0,0,1,0,0,1,1,0
```

An excerpt of `summary.md`, the human-readable form:

```markdown
# Benchmark summary

Modes reported: rules.

## Modes

| Mode | Samples | Skipped | Precision | Recall | F1 | FPR | TP | FP | FN | TN | p50 (ms) | p95 (ms) | Note |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| rules | 2 | 0 | 0.8000 | 1.0000 | 0.8889 | 1.0000 | 4 | 1 | 0 | 0 | 0.755 | 1.819 | all 2 sample(s) are format examples; these numbers are a smoke test, not evaluation data |

## Per category

| Category | Mode | TP | FP | FN |
| --- | --- | ---: | ---: | ---: |
| config | rules | 1 | 0 | 0 |
| injection | rules | 1 | 0 | 0 |
| quality | rules | 1 | 0 | 0 |
| secrets | rules | 1 | 1 | 0 |
```

The numbers in that table are **not** a quality result. Both samples in the dataset are format
examples, the harness labels them as such in its own note column, and the manifest keeps
`evaluation_samples` empty. What the artefacts demonstrate is that the pipeline computes
precision, recall, F1, a false-positive rate, per-category tallies and nearest-rank latency
percentiles, writes them in four consistent forms, and states its own limitations in the file
it writes. A row whose mode could not run carries `skipped` with an explanatory note rather
than a zero, which is why an unconfigured local model appears as a skipped row rather than as
a poor score.

## 7.6 Screenshot placeholders

Three screenshots should be captured from a live instance before submission. Each is
described here so that the capture is reproducible and the caption can be written once.

**[SCREENSHOT PLACEHOLDER: Swagger UI at /docs]**
Start the server with `uvicorn app.main:app --port 8000` and open `http://127.0.0.1:8000/docs`.
The image should show the generated OpenAPI page with every documented operation visible in
the collapsed list — the ops group (`/`, `/health`), the rules group (`/rules`,
`/rules/{rule_id}`), the review group (`GET /review`, `POST /review`, `GET|POST /test-review`)
and the webhook group (`POST /webhook`) — together with at least one expanded operation showing
its response schema. Caption: *Figure 7.1 — The generated OpenAPI interface, showing every
documented endpoint and its response model.* It demonstrates that the API is described by its
own code rather than by a separate document that can drift.

**[SCREENSHOT PLACEHOLDER: CLI report]**
Run `python reviewer.py samples/sample.diff --offline` in the repository root and capture the
terminal, including the single `WARNING` line on standard error above the report. The image
should show the header block, the `changed lines` section, all four numbered findings and the
`verdict  : block` line. Caption: *Figure 7.2 — The command-line review of the sample diff,
with the degraded-mode warning visible above the report.* It demonstrates the offline path,
the labelling lines, and the fact that the warning and the report are on different streams.

**[SCREENSHOT PLACEHOLDER: benchmark chart]**
Run `python -m benchmarks.eval --modes rules --dataset benchmarks/golden --out benchmarks/out`
and open `benchmarks/out/chart.png`. The image should show the per-mode bar chart with its
axis labels and the sample count visible. Caption: *Figure 7.3 — The benchmark chart written by
the harness; the two samples are format examples, so the figure illustrates the artefact rather
than a measurement.* The caption must carry that qualification, because a chart is the most
persuasive form a number can take and the least qualified.

A fourth capture is optional but recommended for the appendix: the posted pull-request review,
showing one inline comment attached to a changed line and the summary comment beneath it.
Caption: *Figure 7.4 — A posted review on a pull request, with inline and summary comments.*
This one cannot be produced from this repository, because no request has ever been sent to
`api.github.com` from it; producing it requires a real pull request and a token.

## 7.7 Summary

Four outputs, one source of truth. The CLI report, the JSON document, the pull-request comment
and the benchmark artefacts are all renderings of the same review result, which is why they
cannot disagree: the findings are computed once, and each surface formats the same list. The
layouts differ because the readers differ — a terminal, a script, a code author and an
evaluator — and each format states its own provenance, so a mock run, an overflowed inline cap
and a skipped benchmark mode are all visible in the artefact rather than left to be inferred.

Two qualifications belong in this chapter rather than in a footnote. The benchmark numbers
quoted in §7.5 are a harness smoke test over two format examples and are not a measurement of
the reviewer. And Figure 7.4, the posted review, is the one layout this repository cannot
produce, because no request has ever reached GitHub from it; the comment layouts in §7.4 were
rendered by the shipped code but have never been accepted by the service they are addressed
to.
