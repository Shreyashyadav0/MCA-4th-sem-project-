# 8 Results and Discussion

This chapter reports what the delivered system does, under one constraint that
overrides style: no number appears here that the software did not produce, and no
measurement is reported for anything that was not measured. Where a result exists,
the transcript is quoted and the file that produced it is named. Where a result
does not exist — and the quantitative evaluation does not — a placeholder says so
in words, and the discussion explains what that absence means for the conclusions.

## 8.1 Functional results achieved

The requirement register introduced in Chapter 2 is reproduced below with the
outcome of each requirement, using Chapter 2's own identifiers and status wording
so that the two tables can be read against each other row for row. *Satisfied*
means an artefact in the repository demonstrates the behaviour and the shipped test
suite exercises it; *Partially satisfied* means the behaviour exists but was
demonstrated only against a simulated counterpart, and the limitation is named in
the cell. The evidence column names the file a reader can inspect to check the
claim.

| ID | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| FR-01 | Parse a unified diff into files, hunks and lines | Satisfied | `app/parser.py::parse_diff`; `tests/test_parser.py` (11 cases) |
| FR-02 | Accept a single source file as a target | Satisfied | `app/parser.py::bundle_from_source`; `POST /review` with a source file |
| FR-03 | Represent every finding with exactly five fields | Satisfied | `app/models.py::Finding`; `test_finding_model_stays_five_fields` |
| FR-04 | Apply 63 deterministic rules across 10 categories | Satisfied | `app/rules.py` (63 rules, 10 categories); `tests/test_rules.py` (187 cases) |
| FR-05 | Scan added lines only | Satisfied | `app/rules.py::review_diff`; `test_findings_only_on_added_lines` |
| FR-06 | Honour an inline suppression marker | Satisfied | `app/rules.py::_suppressed_ids`; `test_targeted_noqa_suppresses_one_rule` |
| FR-07 | Bound the cost of pattern matching | Satisfied | `LineContext.scan_text` truncation; `test_regex_flood_does_not_blow_up` |
| FR-08 | Anchor each finding to the changed lines | Satisfied | `app/parser.py::anchor_findings`; `test_anchor_statuses` |
| FR-09 | Select one provider by fixed precedence | Satisfied | `app/engine.py::select_provider`; `tests/test_openai_compat_provider.py` |
| FR-10 | Serve both model endpoints through one transport | Satisfied | `app/openai_compat_provider.py::OpenAICompatConfig`; one transport, two configs |
| FR-11 | Bound the model interaction | Satisfied | `review_diff_live` two-call budget; `test_double_failure_logs_exactly_one_warning` |
| FR-12 | Reject an answer naming an unknown file or line | Satisfied | `parse_findings_payload` guards; `test_reexported_guards_are_the_same_objects` |
| FR-13 | Degrade to the rule engine without failing | Satisfied | `engine.review` → rule engine; 637 offline tests, no key required |
| FR-14 | Publish a review to a pull request | Partially satisfied: demonstrated against a simulated GitHub API | `app/github_client.py::post_review`; `tests/test_github_client.py` (54 cases) |
| FR-15 | Persist reviews, users and roles | **Satisfied**: six tables and three roles in `app/db.py`, exercised by `tests/test_db.py` (27 cases) and `tests/test_auth.py` (13 cases) | `app/db.py::SCHEMA_SQL`; `tests/test_db.py`, `tests/test_auth.py` |
| FR-16 | Verify the webhook signature and answer every delivery with 200 | Satisfied | `app/main.py::webhook`; `tests/test_webhook_posting.py` (27 cases) |
| FR-17 | Measure precision, recall, F1, false-positive rate and latency | Satisfied (harness); [FILL AFTER BENCHMARK: measured values] | `benchmarks/metrics.py`; `tests/test_metrics.py` (20 cases) |
| FR-18 | Prove the suite runs with no network access | Satisfied | `scripts/verify_offline.py`; 637 passed with sockets blocked |

The suite establishing the satisfied rows runs to 637 passed and 1 skipped; the
skip is the live model smoke test, guarded so it can run only where a model server
is listening. Seventeen of the eighteen rows read *Satisfied* and one, FR-14, is
partially satisfied: its code path exists and is proven at its seam, but its
counterpart in the real world — the GitHub review API — was never available to the
project, so posting was demonstrated against a simulated API and no request from
this project has ever been accepted by GitHub. One of the seventeen carries a
qualification that Chapter 2 also states: FR-17 is satisfied as a harness — the
instrument is built, tested and runs — and the measured values it exists to produce
are still the placeholder in its cell, not a result. The dataset and the running
local model that FR-17 needs are absent for the same reason FR-14's API is: they
were not available to the project.

## 8.2 Demonstration results

These behaviours were observed on the submitted tree, on a machine with no
credentials configured and no environment variables exported. They are quoted
rather than paraphrased, because the output cannot misrepresent itself: the mode,
provider and model lines are set from what actually ran.

### 8.2.1 The command-line interface

`python reviewer.py samples/sample.diff` reviews the bundled two-file patch — a
modified `app/db.py` carrying a committed token literal and an interpolated SQL
statement, and a newly added `app/report.py` with an unannotated public function.
It printed the following. The first line is a warning on standard error;
everything from `target` onwards is the report on standard output, a split verified
by redirecting the streams separately.

```text
WARNING reviewer.openai_compat: local review degraded to the local rule engine: no OpenAI-compatible provider selected; local rule engine used
target   : samples/sample.diff
mode     : mock
provider : mock
model    : local-rules
files    : 2 changed
findings : 4 (CRITICAL 3, HIGH 0, MEDIUM 1, LOW 0)
note     : mock mode: no SARVAM_API_KEY or LMSTUDIO_BASE_URL configured; local rule engine used
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

Four properties of that transcript are the project's functional claims. Each
finding names the rule that produced it, so every line is traceable to one registry
entry. Each carries an anchor naming the hunk it landed in, which is what makes an
inline comment possible later. The verdict is derived from the severity mix by a
documented rule rather than by a model's opinion: three CRITICAL findings outvote
one MEDIUM. And the exit code is zero, deliberately, because a review that finds
problems is a successful run, not a failed process.

With `--json` the same run emits a top-level object keyed `mode`, `target`,
`files`, `findings`, `anchors`, `notes` and `verdict`; with `--min-severity HIGH`
it reports three findings and no MEDIUM, verdict unchanged — a threshold changes
what is shown, not what the code is judged to contain.

### 8.2.2 The HTTP interface

The server was started with `uvicorn app.main:app` and queried on loopback.
`GET /health` returned `status: ok`, `mode: mock`, `rules: 63`, `provider: mock`,
the ten category names, and `missing` for the Sarvam key, the GitHub token and the
webhook secret — the process reports which credentials it can actually see, which
settles most questions about why a run chose the offline path. `GET /test-review`
returned `stats` with two files, four findings, three CRITICAL, one MEDIUM, verdict
`block` and `rules_evaluated: 63`, the assertion that the whole registry ran. Its
`duration_ms` varies on every call and is not quoted as a constant anywhere here.

`POST /review` accepts a diff or a source file. With the bundled diff and a
threshold of HIGH it returned the same three findings under the source label
`inline_diff`; with a two-line snippet it returned source `raw_code` and one
CRITICAL finding, reporting the file as `added` with span `1-2`. A request carrying
an extra key was rejected with status 422 and a detail naming the forbidden field —
the five-field contract enforced at the boundary. `GET /rules/unsafe/sql-injection`
returned that rule's record: title, category `injection`, mapping
`A03:2021-Injection`, severity CRITICAL.

### 8.2.3 The webhook

With a configured secret, a delivery carrying a deliberately wrong
`X-Hub-Signature-256` header was rejected with status 401 and the detail
`X-Hub-Signature-256 does not match`; the same body signed correctly with an
HMAC-SHA256 digest of the secret was accepted. A correctly signed delivery whose
action was outside the reviewed set answered 200 with `{"status": "ignored"}` and a
detail naming the action, because a webhook GitHub has to wait for is a webhook
GitHub will eventually disable. A `ping` event was likewise answered 200 and
ignored.

Two further observations belong here, and both were made by accident, which is the
best way to make them. With a placeholder GitHub token exported, the webhook tried
to fetch the pull-request diff from `api.github.com` and received a real 401; the
run degraded to the bundled fixture and the response carried a notice that the diff
could not be fetched and that nothing was posted — one genuine outbound rejection,
observed rather than scripted. Separately, the posting path was exercised only
against a scripted fake HTTP client: the happy path, the duplicate skip, the
demotion of a rejected inline comment into the summary, the retry after a rate-limit
response and the handling of authentication, permission, server and transport
errors are all covered by tests, but no request from this project has ever been
accepted by GitHub. The posting state machine is therefore proven at its seam and
unproven end to end.

## 8.3 Benchmark methodology

The harness is a separate package with a frozen interface documented in
`benchmarks/CONTRACT.md`. It is described here as methodology; the numbers it would
produce are not available, and the placeholders mark where they go.

A sample is a directory holding a real unified diff and a hand-written
`expected.json` listing what a human says should be reported, each entry a file, an
inclusive new-side line range, a category and a severity. An empty list is a
legitimate label: it asserts the change is clean, the only way a true negative can
be measured. Labels must be written by a person; a label copied from the rule
engine's output, or generated by a model, would score the tool against itself. The
dataset directory ships two samples explicitly labelled as format examples and
excluded from every metric, and its manifest keeps the evaluation list empty.

Three modes run over the same samples: `rules` for the deterministic engine alone,
`local` for the model path against a local OpenAI-compatible endpoint, and `merged`
for both combined. A mode whose endpoint is unconfigured is skipped cleanly and
reported as skipped rather than failing the run.

Matching is where a benchmark is easiest to get quietly wrong, so it is specified.
An actual finding matches an expected one when it names the same file, its range
overlaps the expected range, and its category is equal or in a declared equivalence
class. Matching is one-to-one and greedy: the largest overlap is taken first, both
sides are consumed, and the process repeats; ties break on file, then expected line
start, then actual line start, so the result is deterministic. Matched pairs are
true positives, unmatched expected findings are false negatives, unmatched actual
findings are false positives. Precision, recall, F1 and the false-positive rate
follow from those counts, kept per category as well as in aggregate so a mode's
losses can be attributed to a defect class. Latency is recorded per sample and
reported as p50 and p95 by the nearest-rank definition, which needs no
interpolation and is reproducible from the recorded samples. The greedy rule is a
documented limitation: a maximum-cardinality matching would score better whenever
several findings of one category cluster on adjacent lines, and an optimal
assignment was rejected because it obscures which finding was paired with which —
and an evaluation whose pairing cannot be read off the output is one an examiner
cannot check.

`[FILL AFTER BENCHMARK: precision/recall/F1 per mode]`

`[FILL AFTER BENCHMARK: latency p50/p95]`

`[FILL AFTER BENCHMARK: false-positive rate per mode and per-category breakdown]`

The harness has been run: it writes `metrics.csv`, `summary.json`, `summary.md` and
`chart.png` under `benchmarks/out/`, and prints its own warning that every sample is
a format example and the figures are a smoke test. Those figures are not reproduced
here. Two samples cannot support a quality claim, and a number quoted from them
would be indistinguishable, to a reader, from a real result.

## 8.4 Discussion

Three decisions account for most of the shape of this system, and each carries a
cost that should be stated rather than assumed away.

**Offline-first.** The rule engine is not an error handler that is rarely reached;
it is the layer that always runs and the only one that requires nothing of the
environment. The consequence is that the reviewer works with no network, no key and
no model, which is the condition under which it will be demonstrated and marked.
The cost is that the base layer finds only what a pattern can express. A rule sees
that a string is interpolated into a SQL statement; it cannot see that a value
flows from an HTTP handler through two functions into that statement, because the
engine builds no data-flow graph. The system therefore under-reports precisely the
defect class where a language model is strongest, and the architecture keeps the
model layer additive rather than load-bearing.

**Provider-agnosticism.** One adapter serves the hosted and the self-hosted model,
both speaking the same chat-completions protocol, and one router chooses between
three providers by fixed precedence. The gain is that the review layer is written
once and swapping a vendor is a configuration change; the cost is that the adapter
can use only the intersection of what the endpoints support. The precedence —
hosted wins when both are configured — favours the endpoint reachable from a
machine without a GPU, with the awkward consequence that a stray key in a shell
silently overrides a working local setup. Hence the explicit override, and hence a
health endpoint that reports what the process actually sees.

**A deterministic base under a non-deterministic layer.** Determinism is what makes
the system evaluable: the same diff and rule version produce the same findings in
the same order, so a regression is real and not sampling noise. The model layer is
admitted only behind guards — files outside the diff dropped, line numbers snapped
or discarded, duplicates collapsed, the list capped — and only on the understanding
that its contribution is unmeasured until the benchmark exists. This project has
built the instrument and has not yet taken the reading, and the design keeps the
instrument useful while the reading is missing.

A fourth decision is visible in the demonstration output. The pipeline never raises
for an environmental reason: a missing credential, a dead endpoint, a rejected key
and an unparseable answer all produce a review with a mode label and one warning
saying what happened. The cost is that failures are quieter than they would
otherwise be — a caller ignoring the mode field can mistake a degraded run for a
live one — which is why the three labels are treated as contract rather than
logging, and why every provider test asserts all three.

## 8.5 Comparison with existing tools

The comparison is restricted to properties establishable from public documentation
or from the deployment model each tool states for itself. It makes no claim about
the internal detection technique, accuracy or architecture of any commercial
product, because none of that is verifiable from outside, and a report that guesses
at a competitor's internals is worth less than one that says it cannot tell.

| Dimension | This system | CodeRabbit | GitHub Copilot code review | Qodo |
|---|---|---|---|---|
| Deployment model | Self-hosted single-host service, run as a process or container on the reviewer's machine | Hosted SaaS, installed as a GitHub/GitLab app | Hosted feature of GitHub, enabled per repository or organisation | Hosted SaaS, with an open-source pull-request agent that can be self-hosted |
| Key requirement | None for the engine; a key or local endpoint only for the model layer | Account and app installation; vendor-side model access is part of the service | A Copilot subscription and repository access | Account and app installation; subscription for the hosted service |
| Offline capability | Full for the rule engine, which is the default | No offline mode documented; not verified | Not applicable; not verified | The open-source component runs locally; offline behaviour not verified here |
| Cost model | No licence cost; only optional inference, which can be local | Subscription with a free tier for public repositories; exact prices not verified | Bundled with a Copilot subscription; exact prices not verified | Subscription with a free tier; exact prices not verified |
| Published evaluation data | None — the project's stated gap | Not verified | Not verified | Not verified |
| Review output | Five-field findings anchored to changed lines, plus a gate verdict | Line and file comments plus a summary, per vendor documentation | Line comments plus a summary, per vendor documentation | Line and file comments plus a summary, per vendor documentation |

Two differences are substantive. The first is deployment: all three commercial
tools are hosted services reached over HTTPS, whereas this system is a process the
reviewer starts — which is what makes the no-network claim possible, and what makes
it unsuitable, as it stands, for an organisation that wants a managed service. The
second is where availability lives: for the commercial tools it is the vendor's;
here it is a property of the code, and the rejected-key transcript in section 8.2.3
is the consequence.

The table is not a claim of superiority on any row. A hosted service sees more
repositories than a local tool can be tuned on, and the products named have been
exercised on far more real pull requests than this one. What this system offers
that they do not is a base layer whose output is reproducible, inspectable rule by
rule, and available with no network and no account.

## 8.6 Limitations

The evaluation dataset does not exist as labelled data. The repository ships two
samples that demonstrate the format and are excluded from every metric, so this
report contains no precision, recall or F1 figure for any mode; detection quality
is asserted by tests, not measured by the benchmark.

The local-model path was verified against a stub server, not a real model. Request
shape, retry budget, parsing and guards are covered against the genuine client
library's exception classes, but whether a quantised model produces usable findings
on a real diff, and how long it takes, is unmeasured.

The hosted-model path has never run successfully; no real key was used at any point.
What is proven is the failure path — a placeholder key reached the vendor's endpoint,
was rejected, and the run degraded correctly.

Labels, when written, will be one person's judgement; inter-annotator agreement is
not measured and the harness cannot detect a label a competent reviewer would
dispute. Matching is greedy and file-and-line based, so a correct finding on the
right line under a neighbouring category scores as both a false positive and a
false negative.

The rule set is pattern-based and reports on changed lines only: a defect
introduced by a change but located in untouched code is invisible to it, as is any
defect requiring data flow across functions.

The idempotency marker is a public HTML comment, so anyone able to comment on the
pull request can suppress a review by pasting one; closing that gap changes the
frozen marker format, so it is an open decision rather than an oversight. Posting
has never been exercised against GitHub itself, so whether GitHub accepts these
comment positions is unverified.

The container image has never been built in the development environment, because no
daemon was available; the compose file parses and the runtime steps were rehearsed
from the lock file. The interpreter is pinned to a release that is in security support until October
2028 — acceptable for an archived academic submission, not for a deployment.

## 8.7 Summary

The system submitted here parses a unified diff, anchors findings to changed lines,
detects a defined set of security and quality defects with a deterministic engine
of 63 rules mapped to the OWASP Top Ten, optionally adds a model layer that degrades
without failing, publishes results to a pull request idempotently, and proves that
all of it runs without network access. Seventeen of the eighteen functional
requirements are satisfied, one of them (FR-14) only against a simulated GitHub
API, and one of the seventeen (FR-17) only as a harness whose measured values are
still placeholders. The transcripts in section 8.2 are
evidence a reader can reproduce in four commands on a machine with no credentials.
The quantitative evaluation is the one part designed, implemented and not yet
populated, and this chapter marks the three places its results will go rather than
filling them with figures from two format examples.
