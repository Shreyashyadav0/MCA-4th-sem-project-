# Project Synopsis

**Course:** MCSP-232 (Project), MCA_NEW
**Student:** Shreyash Yadav
**Enrolment Number:** `[FILL: enrolment number]`
**Study Centre:** `[FILL: study centre]`
**Regional Centre:** `[FILL: regional centre]`
**Guide:** `[FILL: guide name and designation]`
**Session:** `[FILL: July 2026 / January 2027 session]`

---

## 1. Title of the Project

**Autonomous AI Code Reviewer & PR Assistant**

---

## 2. Introduction and Objectives

### 2.1 Introduction

Code review is the practice of reading a change before it becomes part of a shared
branch. Its purpose is not only to find defects; it is to catch them while they are
still cheap, to keep a codebase consistent in style and structure, and to move
knowledge of a change from its author to at least one other person. In a team using
a distributed version-control system, the practice is formalised in the pull request:
a branch is proposed, a diff is displayed, a reviewer comments — often on individual
lines — and the change is merged when the objections are resolved.

The practice is expensive. A reviewer must reconstruct the intent of a change from a
diff that shows only what moved, usually in a domain they know less well than their
own; small changes wait behind large ones; review quality varies with the reviewer's
remaining attention; and the same defect — an interpolated SQL string, a committed
credential, a disabled certificate check — is caught in one repository and missed in
another by the same person on a different afternoon.

Automated assistance has arrived in two waves. The first is pattern-based static
analysis: a tool scans the changed lines, applies checks and reports findings. These
tools are fast, deterministic, explainable and cheap, and they are limited by
construction to what a pattern can express. The second is the large language model,
asked to read the change and comment. Such systems can identify problems that require
context and intent, and they bring three difficulties — they need a hosted endpoint,
so availability is somebody else's; they are not reproducible between runs; and their
output is prose that is difficult to audit or to attach to a line.

This project builds a reviewer that treats the first wave as the foundation and the
second as an optional layer above it. The system accepts a unified diff or a single
source file, parses it into files and hunks, and produces findings with exactly five
fields: the file, the line, a severity, a one-sentence statement of the issue, and a
concrete suggested fix. Every finding is anchored against the changed lines of the
diff, so a consumer knows whether the finding can be attached to an inline comment.
A deterministic engine of 63 rules, each mapped onto the OWASP Top Ten, always runs
and needs no network, no credential and no model. An optional model layer adds
findings the rules cannot express, and when it is unavailable the review degrades to
the rule engine, announces the degradation in a single warning, and still returns a
complete review. The result is presented on a command line, over an HTTP interface
and through a GitHub webhook, and can be published to a pull request as inline
comments plus one summary comment without duplicating a review it has already made.

### 2.2 Objectives

The objectives are stated so that each can be marked as achieved or not achieved, and
each is followed by the chapter of the report that demonstrates it.

1. To parse a unified diff into files and hunks, and to anchor every finding to the
   changed line range it concerns, distinguishing findings that can be attached to a
   line comment from those that cannot. (Chapters 3 and 4)
2. To detect a defined set of security and quality defects deterministically, with
   every rule mapped to a published taxonomy, so that the same input always produces
   the same findings in the same order. (Chapters 4 and 8)
3. To add an optional language-model review layer that parses the model's answer
   strictly, repairs one malformed answer, and degrades to the deterministic engine
   without failing when the model is unavailable, misconfigured or unusable.
   (Chapters 4 and 8)
4. To publish a review to a GitHub pull request as inline comments and a summary,
   idempotently, so that a re-run of the same review posts nothing new. (Chapter 4)
5. To measure the system on a human-labelled dataset and report precision, recall,
   F1, false-positive rate and latency per mode. (Chapters 5 and 8)

The fifth objective is the one that is partially met, and the report says so: the
measurement harness is built and runs, but the labelled dataset it needs does not yet
exist, so the report states the methodology and carries placeholders where the
figures will go rather than quoting figures that two format examples would produce.

---

## 3. Project Category

The project falls in the **Artificial Intelligence and Machine Learning** category.

The justification is not that the system calls a model, because a call to a model is
an integration and not a contribution. The system belongs in this category because
its subject matter is the composition of two kinds of automated reasoning over the
same artefact. One is symbolic and deterministic: a rule set that encodes a
security engineer's knowledge as patterns with a taxonomy and a severity ladder. The
other is statistical: a language model that has learned the distribution of code and
of review comments, and that can therefore notice an inconsistency no rule was
written for. The engineering problem the project addresses — how to place a
non-deterministic reasoner above a deterministic one so that the composite is
strictly more capable than the base, never less available than the base, and still
auditable — is a machine-learning systems problem, and it is the part of the work
that is transferable to other domains in which a model is added to an existing
rule-based process.

Within the category the work spans three recognised sub-areas: static program
analysis for the rule engine, applied natural language processing over code for the
model layer, and evaluation methodology for the benchmark harness. No model is
trained by this project. The model layer uses a pre-trained model through a standard
interface, and the report is explicit that the contribution is the architecture,
the contract and the measurement, not a new model.

---

## 4. Tools, Platform and Requirement Specifications

### 4.1 Hardware requirements

The deterministic path is deliberately modest, because a reviewer that requires
special hardware is a reviewer that will not be run.

| Component | Minimum | Recommended | Notes |
|---|---|---|---|
| Processor | Any x86-64 or ARM64 processor | A modern multi-core processor | All rule evaluation is CPU-bound and single-threaded per request |
| Memory | 1 GB free | 2 GB free | The rule engine holds no model in memory |
| Disk | 200 MB | 1 GB | Source, dependencies and the generated benchmark artefacts |
| Display | None | Any | The system is a command-line and HTTP service |
| GPU | Not required | 8 GB of video memory for the optional local model | The model path is optional; the system is fully functional without it |
| Network | Not required for the deterministic path | Outbound HTTPS for the hosted model and for GitHub | The offline path is proven by a test that blocks outbound sockets |

The optional local model path is configured for a 4-bit quantised build of roughly
four to five gigabytes, which runs on a modern laptop without a discrete GPU, more
slowly. No measurement of that path on real hardware is reported in this project,
because no model server was available in the development environment.

### 4.2 Software requirements

| Layer | Software | Version | Why this version |
|---|---|---|---|
| Language | Python | 3.12.13 | Pinned in `.python-version` and in both container stages; the `match` statement, modern typing syntax and the current `re` behaviour are used |
| Web framework | FastAPI | 0.162.5 | Request and response models generated from type annotations, and an OpenAPI schema served at `/docs` |
| ASGI server | Uvicorn (standard extras) | 0.54.0 | Serves the application; the standard extras supply the event loop and the reload watcher |
| Validation | Pydantic | 2.14.3 | Strict models with `extra="forbid"`, frozen instances and computed fields |
| Configuration | pydantic-settings | 2.15.0 | Typed environment loading with defaults and a `.env` file |
| HTTP client | httpx | 0.28.1 | The GitHub client, and the transport the model client library uses |
| Model client | openai | 3.51.0 | The chat-completions client used for both the hosted and the self-hosted endpoint |
| Hosted SDK | sarvamai | 0.1.46 | The vendor SDK retained for the Phase 4 path and its exception mapping |
| Testing | pytest | 8.4.2 | The suite, with parametrisation and skip markers |
| Container | Docker, two-stage build | any current release | The runtime image installs from a wheelhouse with `--no-index`, so it cannot reach the network at build time |
| Version control | Git | any current release | The project is developed as a repository and the diff format it produces is the system's input |
| Documentation | Markdown, assembled to PDF | — | Chapters are separate Markdown sources assembled into the bound report |

The seven direct runtime dependencies are pinned in `requirements.txt`; the resolved
closure of thirty-six packages is pinned in `requirements.lock`, which is what the
container and the continuous-integration workflow install. The lock exists because a
reviewer whose behaviour depends on an unpinned transitive dependency cannot be
evaluated reproducibly.

### 4.3 Platform

The system is a single-host service. It runs as a process on the developer's own
machine, as a container on any host with a container runtime, or behind any reverse
proxy that terminates TLS. It requires no separate database server (SQLite is embedded), no message broker, no
cache and no shared filesystem; its only external dependencies are optional and
outbound — a model endpoint and the GitHub API.

---

## 5. Problem Definition, Requirement Specifications, Literature Review and Project Planning

### 5.1 Problem definition

A review tool must answer three questions about a change: what is wrong with it,
where in the change the problem is, and what to do instead. Existing tools answer
them unevenly. A pattern-based analyser answers the second question precisely and
the first narrowly, because it can only report the defect classes someone encoded as
a pattern. A language-model reviewer answers the first question more broadly and the
second question unreliably, because a model is an unreliable narrator about line
numbers. Neither answers the third question consistently: a linter's message often
names a rule rather than a fix, and a model's fix is prose.

The problem this project addresses is therefore the composition problem. Given a
deterministic detector that is always available and a statistical detector that is
available sometimes, how should they be arranged so that the composite (a) never
fails to produce a review, (b) never presents a degraded result as a complete one,
(c) places every finding on a line the review platform will accept, and (d) can be
evaluated at all? The fourth constraint is why the base layer had to be
deterministic: a reviewer whose output changes between identical runs cannot be
measured, and one that cannot be measured cannot be improved. The problem is bounded
deliberately — diffs rather than whole repositories, no execution of the code under
review, no data-flow graph, no automatic fixing — and the boundary is stated in
section 6 and again as limitations in the report.

### 5.2 Functional requirements

The register is the same eighteen rows, with the same identifiers and the same
requirement wording, as Table 2.1 of the project report, so that the proposal and
the report cannot state two different specifications. The Priority column is this
document's own; the report's table carries the achieved status of the same rows.

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | Parse a unified diff into files, hunks and lines | Essential |
| FR-02 | Accept a single source file as a target | Desirable |
| FR-03 | Represent every finding with exactly five fields | Essential |
| FR-04 | Apply 63 deterministic rules across 10 categories | Essential |
| FR-05 | Scan added lines only | Essential |
| FR-06 | Honour an inline suppression marker | Desirable |
| FR-07 | Bound the cost of pattern matching | Essential |
| FR-08 | Anchor each finding to the changed lines | Essential |
| FR-09 | Select one provider by fixed precedence | Essential |
| FR-10 | Serve both model endpoints through one transport | Essential |
| FR-11 | Bound the model interaction | Essential |
| FR-12 | Reject an answer naming an unknown file or line | Essential |
| FR-13 | Degrade to the rule engine without failing | Essential |
| FR-14 | Publish a review to a pull request | Essential |
| FR-15 | Persist reviews, users and roles | Essential |
| FR-16 | Verify the webhook signature and answer every delivery with 200 | Essential |
| FR-17 | Measure precision, recall, F1, false-positive rate and latency | Essential |
| FR-18 | Prove the suite runs with no network access | Essential |

### 5.3 Technical requirements

| ID | Requirement | How it is satisfied |
|---|---|---|
| TR-01 | No credential may be required for the core function | The rule engine is the default; a missing key selects a mode rather than raising |
| TR-02 | The output contract must be enforced at the boundary, not downstream | A frozen model with `extra="forbid"` on every finding, and the same model at every front end |
| TR-03 | One provider decision, not one per front end | A single selector module; the command line, the API and the webhook all call one review function |
| TR-04 | One transport for two model providers | A single OpenAI-compatible adapter, because both endpoints speak the same protocol |
| TR-05 | Reproducible installs | Seven direct pins and a thirty-six package lock, installed by the container and the CI workflow |
| TR-06 | The suite must run without network access | A verifier that blocks outbound socket creation in-process and re-runs the suite in the same interpreter |
| TR-07 | Secrets must never reach a log record | Credentials are read once, excluded from representations, and scrubbed from every degradation reason |
| TR-08 | The service must run unprivileged in a container | A two-stage image that installs from a wheelhouse offline and drops to a fixed non-root user |
| TR-09 | Every architectural decision must be recorded | Numbered decision records stating the decision, the alternatives and the consequence |
| TR-10 | The system must be deployable as one process | No database server, broker or shared filesystem is required |

### 5.4 Literature review

Four strands inform the design. Static-analysis literature establishes that pattern rules find
a stable, explainable subset of defects and that their weakness is false positives rather than
misses; the OWASP Top Ten supplies the taxonomy the rule set is mapped onto. Work on
model-based review shows large language models produce useful comments but also plausible
non-existent findings, which is why this system validates every model answer against a strict
schema and drops any finding that names a file outside the diff. Benchmark work on code review
shows that evaluation requires human-authored labels and that precision, recall and
false-positive rate must be reported per category, which is why the harness ships a labelling
tool and an empty evaluation set rather than a guessed one. Finally, the reproducibility
literature motivates the pinned lock file, the container and the zero-network test gate.

### 5.5 Project planning and scheduling

The work was planned as six build phases with documentation and evaluation as
separate tracks, and scheduled with a PERT network and a Gantt chart, reproduced
here as Figure 5.1 (PERT network) and Figure 5.2 (Gantt chart). The plan is
recorded as ten activities, A to J, each matched to the module or pack that
delivers it; the three-point estimates below are the only inputs, and the expected
duration, the float and the critical path are derived from them. Durations are
working days at five days per week, and they are planned effort, not measured
elapsed time. The expected duration of an activity is te = (O + 4M + P) / 6, and
its variance is ((P − O) / 6)².

| Activity | ID | O / M / P (days) | te (days) | Depends on | Float (days) | Critical |
|---|---|---|---|---|---|---|
| Requirements and scope | A | 4 / 6 / 11 | 6.50 | — | 0.00 | yes |
| System design and contracts | B | 5 / 8 / 13 | 8.33 | A | 0.00 | yes |
| Rule engine (63 rules) | C | 8 / 12 / 18 | 12.33 | B | 0.00 | yes |
| Parser and anchoring | D | 6 / 9 / 14 | 9.33 | B | 3.00 | no |
| Provider layer (adapter and engine) | E | 10 / 15 / 24 | 15.67 | C, D | 0.00 | yes |
| API surface (FastAPI and webhook) | F | 7 / 10 / 16 | 10.50 | C, D | 5.17 | no |
| GitHub posting (marker, 422, 429) | G | 8 / 11 / 18 | 11.67 | E, F | 0.00 | yes |
| Benchmark harness | H | 5 / 8 / 14 | 8.50 | E | 3.17 | no |
| Testing and hardening | I | 6 / 10 / 16 | 10.33 | G, H | 0.00 | yes |
| Documentation and reproducibility | J | 4 / 6 / 10 | 6.33 | I | 0.00 | yes |

The critical path is A → B → C → E → G → I → J, and it totals 71.17 working days,
which is 14.23 weeks at five days per week. The plan is drawn inside a
**sixteen-week frame** — 80 working days — so the network finishes 8.83 days, or
1.77 weeks, before the frame closes; the Gantt chart shows that buffer as a shaded
band from week 14.23 to week 16 that carries no activity. The standard deviation of
the critical path is 4.23 days, so one standard deviation above the mean is 75.40
days (15.08 weeks), which still fits inside the sixteen weeks. Three activities
carry float: D (3.00 days), F (5.17 days) and H (3.17 days), the last two because
G waits on E and not on them. The provider layer, E, is the longest single activity
at 15.67 days and it is on the critical path, which is why the plan does not
compress it.

The Gantt chart places the same ten activities on that sixteen-week frame. A bar
runs from ES / 5 to EF / 5 in week units, so its right edge is an earliest finish
and not a calendar date; bars on the critical path are outlined in red and bars with
float in grey. Milestones M1 to M6 sit at the earliest finish of the activity that
closes each: design frozen at B, rules and parser green at C, provider layer green
at E, posting and benchmark green at G, the suite green at I, and the report and
release at J. Read off the earliest starts and finishes, weeks nought to three carry
the requirements and the design; weeks three to five and a half carry the rule engine
with the parser in parallel; weeks five and a half to eight and a half carry the
provider layer with the API surface in parallel; weeks eight and a half to eleven
carry posting with the benchmark in parallel; weeks eleven to thirteen carry the
testing; weeks thirteen to fourteen and a quarter carry the documentation and the
report; and weeks fourteen and a quarter to sixteen are plan buffer.

Two honest notes belong here. The sixteen weeks are a plan and not a record: the
six phases were in fact built across 13 and 14 November 2026, far inside the frame,
and the changelog is the authority on what was delivered and when. And the labelled
dataset the benchmark needs is not an activity in this network at all — it was
carried as an optional parallel track that never touched the critical path. That is
the schedule's honest weakness: the one task that would turn this project's
methodology into its results was the one scheduled as expendable, and it is the
task that did not finish.

---



![Figure 5.1 — PERT network with the critical path highlighted](docs/diagrams/pert-chart.png)



![Figure 5.2 — Gantt chart of the sixteen-week schedule](docs/diagrams/gantt-chart.png)

## 6. Scope of the Solution

The system reviews a change, not a codebase. Its input is a unified diff or a single
source file; its output is a set of findings, each on a line of that input, each
attributable to a rule or to a model, each carrying a suggested fix. It runs as a
command-line tool, as an HTTP service, and as a webhook receiver for GitHub pull
requests, and it publishes its result to a pull request as inline comments plus one
summary comment.

Within scope: the parsing and anchoring of unified diffs; a deterministic rule set of
63 checks mapped onto the OWASP Top Ten, with suppression, severity and a gate
verdict; an optional model layer over two interchangeable endpoints; a guaranteed
degradation path that never fails a run; idempotent publication to a pull request;
signature-verified webhook handling; a benchmark harness with a frozen interface; and
a test suite that runs with no network access.

Outside scope, and stated as such: whole-repository or historical analysis; execution
or dynamic analysis of the code under review; data-flow or taint analysis across
functions; automatic application of the suggested fixes; support for programming
languages other than the pattern vocabulary the rules are written for; a graphical
user interface; multi-tenant hosting, authentication and rate limiting for the HTTP
service; and the training or fine-tuning of any model. Each of these is a defensible
extension, and several are listed in section 12.

The delivered system is also scoped by evidence. What has been executed, what has
been simulated with a scripted counterpart, and what has been deferred are recorded
separately in the project's handover ledger, and the report preserves that
distinction: the rule engine, the parsing, the API, the webhook state machine and the
zero-network guarantee were executed; the model layer was exercised against a stub
server and the publication path against a fake HTTP client; the hosted model, a real
local model and real GitHub posting were not exercised at all.

---

## 7. Analysis of the System

The analysis is presented as three views of the same system: what it does (data flow
diagrams at three levels), what it stores (an entity-relationship model, detailed in
section 8) and how its parts relate in time and in structure (activity, class and
state diagrams).

### 7.1 Data flow diagram, level 0

The level-0 diagram shows the system as a single process with three external entities.
The **developer** submits a diff or a source file and reads the findings; the
**pull-request platform** delivers webhook events and receives comments; the **model
endpoint** receives a prompt built from the diff and returns candidate findings. The
flow entering from the developer is the change under review; the flow leaving is the
review — findings, anchors, a verdict and the rendered comment.

![Figure 7.1 — Context diagram (DFD level 0)](docs/diagrams/dfd-level-0.png)

### 7.2 Data flow diagram, level 1

The level-1 diagram decomposes that process into seven: **ingest**, which accepts a
diff, a file or a webhook payload and decides which it has; **parse**, which turns the
text into files and hunks and computes added-line spans; **select**, which chooses a
provider by precedence and yields a configuration or a decision to run offline;
**review**, which runs the model path or the rule engine and returns findings with
the mode, provider and model labels; **anchor**, which places each finding against the
parsed diff and assigns one of three statuses; and **render and publish**, which builds
the report, the JSON, the comment markdown and, when a pull request is the target, the
inline and summary comments. Two data stores appear: the rule registry, read by the
review process, and the configuration, read by the selection process. A dashed control
flow carries the degradation decision back to the renderer, because a degraded review
must be labelled as one.



![Figure 7.2 — DFD level 1: processes and data stores](docs/diagrams/dfd-level-1.png)

### 7.3 Data flow diagram, level 2

The level-2 diagram explodes two level-1 processes. Under **review**, the model path
appears as five steps — build the prompt from the hunks, call the endpoint, parse the
answer strictly, repair once if it does not parse, and apply the guards that drop
unknown files, snap line numbers, collapse duplicates and cap the list — and the rule
path as three: iterate the registry over the changed lines, apply the suppression
annotation, and collect findings with their rule identifiers. Under **anchor**, it
shows the three-way test — is the file in the diff, does the range touch an added
line, is the range inside the hunk — and the three outcomes that follow.

![Figure 7.3 — DFD level 2: decomposition of rule application and provider review](docs/diagrams/dfd-level-2.png)

### 7.4 Entity-relationship model

The model has six tables. `roles` holds the three permission bundles; `users` holds one row per
API-key holder, with a unique username, a unique email and a SHA-256 digest of the key rather
than the key itself, and a foreign key to `roles`. `reviews` holds one row per completed review
with its mode, provider, model, target, finding count and verdict. `findings` holds the five
contract fields with a foreign key to `reviews` that cascades on delete. `pr_posts` records each
attempt to publish a review, with a nullable foreign key to `reviews` that is set to null if the
review is deleted. `benchmark_runs` holds the metrics of each harness run. Cardinality is one
role to many users, one review to many findings, and one review to many posting attempts.

![Figure 7.4 — Entity-relationship diagram of the six-table schema](docs/diagrams/er-diagram.png)

### 7.5 Activity, class and state diagrams

The **activity diagram** follows one review from submission to publication: receive
the input; decide its kind; parse it, or fail with a bad-input exit code; select a
provider; run the model path, and on any unrecoverable failure branch to the rule
engine with a warning; anchor the findings; derive the verdict; render the report;
and, if a pull request was named, list the existing comments, decide whether this
review is a duplicate, and either post or skip. The branch for degradation and the
branch for duplicate detection are the two decision nodes the diagram exists to show. The **class diagram** carries the object model.

![Figure 7.5 — Activity diagram of the end-to-end review flow](docs/diagrams/activity-diagram.png)



![Figure 7.6 — Class diagram of the domain and provider types](docs/diagrams/class-diagram.png)



![Figure 7.7 — State diagram of the pull-request posting machine](docs/diagrams/state-diagram.png)

## 8. Database and Table Details

The database is embedded SQLite, created from the `SCHEMA_SQL` constant in `app/db.py`.
It holds six tables. Every table has an integer primary key, foreign keys are declared
with explicit referential actions, and the enumerated columns carry `CHECK` constraints
so an invalid mode, verdict or severity cannot be stored.

| Table | Purpose | Rows created by |
| --- | --- | --- |
| `roles` | The three permission bundles the system recognises | `app/db.py` |
| `users` | One row per API-key holder; only the SHA-256 of the key is stored | `app/db.py` |
| `reviews` | One row per completed review, whatever surface produced it | `app/db.py` |
| `findings` | The five contract fields, attached to their review | `app/db.py` |
| `pr_posts` | One row per attempt to publish a review to a pull request | `app/db.py` |
| `benchmark_runs` | One row per benchmark run, with its metrics | `app/db.py` |

| Table | Primary key | Foreign keys | Constraints |
| --- | --- | --- | --- |
| `roles` | `id` | — | `name` unique; `name` ∈ {admin, reviewer, viewer} |
| `users` | `id` | `role_id` → `roles(id)` | `username`, `email`, `api_key_hash` unique (the SHA-256, never the key) |
| `reviews` | `id` | — | `mode` ∈ {live, mock}; `verdict` ∈ {block, approve with comments, approve} |
| `findings` | `id` | `review_id` → `reviews(id)` ON DELETE CASCADE | `severity` ∈ {LOW, MEDIUM, HIGH, CRITICAL} |
| `pr_posts` | `id` | `review_id` → `reviews(id)` ON DELETE SET NULL (nullable) | no CHECK; `pr_number` and `ok` NOT NULL |
| `benchmark_runs` | `id` | — | no CHECK; `mode` and `dataset` NOT NULL, every metric nullable |

The full DDL is reproduced in Appendix B of the project report and in `app/db.py`.
Three indexes are declared alongside the tables: `findings(review_id)`,
`pr_posts(pr_number)` and `reviews(created_at)`.

## 9. Module Structure, Process Logic and Implementation Methodology

### 9.1 Module structure and the process logic of each module

| Module | Process logic |
|---|---|
| `app/config.py` | Reads the environment once at start into a typed settings object with a default for every field. Distinguishes a blank value from an absent one, so an empty variable counts as missing. Exposes the credential-presence predicates and the mode resolution that the selector and the health endpoint both use. |
| `app/models.py` | Defines the five-field finding as a frozen model with a validator for the line field, and the anchored finding as a composition around it. Defines the review result, which computes its verdict and its severity counts. Provides the severity ordering and the gate rule. |
| `app/parser.py` | A state machine over the diff text, driven by the hunk counters in the header line, producing a bundle of file diffs and hunks with their added-line spans. Then the anchoring pass: for each finding, decide whether the file is in the diff and whether the range touches an added line, and record the status and the hunk header. |
| `app/rules.py` | A registry of 63 rules, each with an identifier, a title, a category, a taxonomy mapping, a severity and a check function. Evaluation iterates the changed lines, applies the suppression annotation, runs the checks under a bounded input length, and collects findings that carry their rule identifier. |
| `app/mock_provider.py` | The offline entry points: review a diff, review a raw source file as an all-added change, and produce the notes that explain which offline path ran. |
| `app/sarvam_provider.py` | The Phase 4 hosted layer: prompt construction, a strict parse of the model's answer, the hallucination and line guards, the fallback wrapper, and the shared guards reused by the adapter. |
| `app/openai_compat_provider.py` | The single transport: build a client from a configuration, call chat completions with structured output requested, retry once without structured output if the answer does not parse, apply the guards, and on any unrecoverable failure return the offline outcome with a one-line reason. Holds the two-call budget. |
| `app/engine.py` | The single provider decision: read the settings, honour an explicit request, apply the precedence, build the configuration for the chosen provider, and call the adapter. Returns a provider outcome carrying the three labels. |
| `app/github_client.py` | Builds the publication payload: inline comments for anchored findings up to the cap, a summary for everything else, and a marker line for every body. Lists existing comments to detect a duplicate, posts, retries once after a rate-limit response, and demotes a rejected inline comment into the summary. |
| `app/cli.py` | Argument parsing, the readable renderer, the JSON renderer, the rule listing, the severity filter, and the exit-code contract. |
| `app/main.py` | The HTTP surface: request models, the review, test-review, rules and health endpoints, the webhook receiver with signature verification and the always-succeed answer, and the comment renderer. |
| `benchmarks/` | The evaluation package: dataset loading, one-to-one greedy matching, metric computation with per-category counts and nearest-rank latency, three mode runners, artefact writers, and the label helper. |

### 9.2 Data structures and implementation methodology

The work was built in six phases, each closing an interface before the next opened
one, and each gated by its own tests.

The first phase fixed the two contracts everything else depends on: the settings
boundary, where a missing credential is data rather than an exception, and the
five-field finding. The second fixed the parser and the anchor model, which is what
makes a finding placeable. The third grew the rule registry to its full set and added
the HTTP surface. The fourth added the model layer and, with it, the degradation
contract. The fifth added publication. The sixth, numbered five and a half, collapsed
two adapters into one and one selector, which is the change that made the provider
precedence a single expression rather than three. A final phase produced the
reproducibility work — the lock file, the pinned interpreter, the two-stage image, the
continuous-integration workflow, the verifier and the documentation.

Three practices ran through every phase. Tests were written against a seam rather than
against a mock of the thing under test: the model client and the HTTP client are each
constructed in one function, and tests replace that function, so everything above it —
retries, guards, parsing, degradation, publication — runs for real. Every phase
recorded its non-goals as well as its goals, so that the limitation section of the
report could be written from the record rather than reconstructed from memory. And
every architectural decision that a reasonable person might reverse was written down
as a numbered decision record with the alternatives it rejected.

### 9.4 Reports generated by the system

| Report | Produced by | Contents |
|---|---|---|
| Readable review | The command line | Target, mode, provider, model, file count, severity tally, the notes explaining the mode, the changed-line summary, and each finding with its rule identifier and anchor |
| JSON review | The command line with the JSON flag | The same content as a structured object, for consumption by another program |
| Comment markdown | The API and the publication path | A heading, a mode line, a file table, and one section per finding with the issue, the fix and the anchor |
| Inline comment | The publication path | One finding, rendered with a fenced suggestion, ending with the marker line |
| Summary comment | The publication path | The overview plus every finding that could not be posted inline, ending with the summary marker |
| Health report | The HTTP surface | Status, mode, rule count, categories and credential state |
| Rule listing | The command line and the HTTP surface | Every rule with its category, severity and taxonomy mapping |
| Benchmark artefacts | The harness | A per-mode metrics table as CSV, a summary as JSON and as Markdown, and a chart |

---

## 10. Security Mechanisms at Various Levels at Various Levels

Security is addressed at five levels, and the treatment is stated at each level
rather than asserted once.

**At the boundary.** The request model forbids unknown fields, so a request cannot
smuggle a parameter past the schema; an unknown field is a validation error with a
named location. When the API is asked to read a file by path, the resolved path is
confined to the project root and anything that escapes it is refused, which closes the
directory-traversal hole that a path parameter creates the moment the service is
exposed. The size of what is accepted is bounded by the request model, and the review
itself is bounded by the rule engine's input cap.

**At execution.** Pattern evaluation is bounded so that a pathological input cannot
make a backtracking expression run for a time disproportionate to its length; the
suite includes a test that floods the engine with such an input and asserts that it
completes. The system never evaluates the code it reviews, never imports it, and
never executes a suggested fix. Where a rendered value could close a Markdown code
span — a file path from a pull request is attacker-chosen — the renderer sizes the
fence one backtick longer than the longest run in the value, because escaping does not
work inside a code span.

**At credential handling.** Credentials are read once, at process start, in one
module. They are excluded from object representations, so an accidental log of a
settings object does not print them. Every degradation reason is built from exception
class names and HTTP status codes only, never from the client library's message text,
and the suite asserts that a key does not appear in an outcome reason or in any log
record. A missing credential is a mode switch and never an exception, which means
there is no code path in which the absence of a secret produces a stack trace that
might quote one.

**At transport.** Webhook deliveries are authenticated with an HMAC-SHA256 signature
over the raw body, compared in constant time; a delivery whose signature does not
match is refused. When a token is configured but no webhook secret is, the endpoint
reviews but refuses to publish, and the escape hatch that allows unsigned publication
is an explicit opt-in that fails closed. Outbound calls use TLS, and certificate
verification is never disabled by this codebase — a rule in the registry exists
precisely to flag code that disables it.

**At deployment and storage.** The container runs as a fixed non-root user, installs
its dependencies from a wheelhouse with the index disabled so that a build cannot
silently fetch something the lock does not pin, and declares a health check that
probes the service with the interpreter already in the image. The persistence design
enforces its invariants in the schema — value sets, ascending ranges, non-blank text,
summed tallies, unique markers — so that a defect in application code cannot write a
row that the model says is impossible.

**Known weaknesses, stated rather than hidden.** The idempotency marker is a public
HTML comment, so anyone able to comment on a pull request can suppress a review by
pasting one; closing that needs author filtering on the listing, which needs an
authenticated application identity rather than a personal token. The service has no
authentication of its own, no rate limiting and no audit retention, so it is fit for a
single-tenant deployment on a trusted network and not for exposure to the internet.
Both are recorded as future work rather than presented as done.

---

## 11. Future Scope and Further Enhancement

The enhancements below are ordered by the constraint that blocks them.

**A labelled benchmark at scale.** The first requirement, because every other
measurement depends on it: several hundred diffs from real repositories, labelled by
hand against a written protocol, preferably by two annotators so that agreement can be
reported. The harness, the collector and the interactive label helper already exist;
what is missing is the human time.

**Multi-language syntax-tree rules.** The engine reasons about the shape of a line
rather than the structure of a program, which is why it cannot state that a call's
argument is a string built by concatenation. An abstract syntax tree per language
would allow such rules, at the cost of a parser per language and a much larger test
surface.

**Incremental review on push.** A synchronised pull request is currently reviewed as a
whole diff, which re-reports findings the author has already seen. Reviewing only the
hunks that changed since the last reviewed commit requires recording that commit,
which is the first thing the persistence design in section 8 provides.

**Application authentication instead of a personal token.** Per-repository scoped
tokens, automatic rotation, a verifiable identity in the pull-request timeline, and —
most usefully — the ability to filter the comment listing by author, which closes the
marker weakness described in section 11.

**A standard results export.** The finding model already maps closely onto the
industry interchange format for analysis results, so an export would let the same
review reach a code-scanning dashboard or an editor's diagnostics pane and be compared
with other analysers on a common vocabulary.

**A web interface, with the controls it requires.** The API already returns the
review, the rendered comment and the statistics in one response, so a server-rendered
page is modest work — but a browser-reachable endpoint that runs a model needs
authentication and rate limiting first. A token bucket per client would bound the cost
of the model layer and the CPU cost of the engine, and an append-only record of each
review would answer operational questions the current build can only answer from logs.
The schema for both is specified; neither is implemented.

**A fine-tuned local model.** A model tuned on this project's own finding format would
need fewer guards and a smaller footprint. It is blocked by the same missing labels as
the benchmark, and any published figure would need the weights hash recorded beside
it.

**Packaging as a continuous-integration action.** A pinned image, an action definition
that passes the pull-request number and token through, and a documented exit-code
contract so a pipeline can gate a merge on the verdict.

---

## 12. Bibliography

[1] Indira Gandhi National Open University, School of Computer and Information
Sciences, *Project Guidelines for MCSP-232 (MCA Project)*. New Delhi: IGNOU.
https://www.ignou.ac.in/ — accessed 14 November 2026.

[2] Indira Gandhi National Open University, *MCA (Revised) Programme Guide*. New
Delhi: IGNOU. https://www.ignou.ac.in/ — accessed 14 November 2026.

[3] OWASP Foundation, *OWASP Top 10:2021 — The Ten Most Critical Web Application
Security Risks*, 2021. https://owasp.org/Top10/ — accessed 14 November 2026.

[4] C. Sadowski, E. Aftandilian, A. Eagle, L. Miller-Cushon and C. Jaspan, "Lessons
from Building Static Analysis Tools at Google", *Communications of the ACM*, vol. 61,
no. 4, pp. 58–66, 2018. https://dl.acm.org/doi/10.1145/3188720 — accessed 14 November
2026.

[5] H. Pearce, B. Ahmad, B. Dolan-Gavitt and R. Karri, "Asleep at the Keyboard?
Assessing the Security of GitHub Copilot's Code Contributions", *IEEE Symposium on
Security and Privacy*, 2022. https://arxiv.org/abs/2108.09293 — accessed 14 November
2026.

[6] N. Perry, M. Srivastava, D. Kumar and D. Boneh, "Do Users Write More Insecure Code
with AI Assistants?", *ACM SIGSAC Conference on Computer and Communications Security*,
2023. https://arxiv.org/abs/2211.03622 — accessed 14 November 2026.

[7] Z. Li et al., "Automating Code Review Activities by Large-Scale Pre-training",
*ESEC/FSE 2022*, pp. 1035–1047. https://arxiv.org/abs/2203.09095 — accessed
14 November 2026.

[8] R. Tufano, S. Masiero, A. Mastropaolo, L. Pascarella, D. Poshyvanyk and G. Bavota,
"Using Pre-Trained Models to Boost Code Review Automation", *ICSE 2022*, pp. 2291–2302.
https://arxiv.org/abs/2201.06850 — accessed 14 November 2026.

[9] Python Software Foundation, *Python 3.12 Documentation*.
https://docs.python.org/3.12/ — accessed 14 November 2026.

[10] S. Ramírez, *FastAPI Documentation*. https://fastapi.tiangolo.com/ — accessed
14 November 2026.

[11] Pydantic, *Pydantic v2 Documentation*. https://docs.pydantic.dev/latest/ —
accessed 14 November 2026.

[12] SQLAlchemy, *SQLAlchemy 2.0 Documentation*. https://docs.sqlalchemy.org/en/20/ —
accessed 14 November 2026.

[13] OpenAI, *API Reference*. https://platform.openai.com/docs/api-reference —
accessed 14 November 2026.

[14] LM Studio, *OpenAI Compatibility Endpoints*.
https://lmstudio.ai/docs/developer/openai-compat — accessed 14 November 2026.

[15] GitHub, *REST API — Pull request reviews*.
https://docs.github.com/en/rest/pulls/reviews — accessed 14 November 2026.

[16] GitHub, *Validating webhook deliveries*.
https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries —
accessed 14 November 2026.

[17] J. MacFarlane, ed., *CommonMark Specification*, version 0.31.2.
https://spec.commonmark.org/0.31.2/ — accessed 14 November 2026.

[18] Sarvam AI, *API Reference*. https://docs.sarvam.ai/api-reference/introduction —
accessed 14 November 2026.

[19] H. Krawczyk, M. Bellare and R. Canetti, "HMAC: Keyed-Hashing for Message
Authentication", RFC 2104, IETF, 1997. https://www.rfc-editor.org/rfc/rfc2104 —
accessed 14 November 2026.

[20] Git project, *git-diff(1)*. https://git-scm.com/docs/git-diff — accessed
14 November 2026.
