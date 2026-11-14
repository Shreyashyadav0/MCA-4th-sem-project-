# Chapter 2: System Analysis

## 2.1 Identification of Need

The need was identified from the three failure modes of manual review set out in Section
1.1, each of which requires a different remedy.

**Latency.** A review is a queue: a change waits for a person, and the queue lengthens as
the number of changes grows, so the delay falls hardest on the small changes that are
cheapest to review and most valuable to merge quickly. The remedy is an immediate first
pass, available when the change is opened, which raises the obvious defects before a human
begins to read.

**Inconsistency.** Two reviewers apply different thresholds, and the same reviewer applies a
different threshold on a different day, so the standard a change is held to depends on who
read it. The remedy is a stated policy: an enumerated set of checks, each with an
identifier, a severity and a published rationale, applied identically to every change. A
policy that is enumerated can be inspected, disputed and amended; one that lives in a
reviewer's judgement cannot.

**Attention decay.** Scrutiny is spread over the length of a diff rather than concentrated on
its risk, so the mechanically detectable defect in the fortieth hunk is missed while the
design question in the first is discussed at length. The remedy is to remove the mechanical
work from the human, leaving the reviewer's attention for what a machine cannot judge.

Two candidate remedies exist for that mechanical pass, and the argument between them
determined the design. A **model-only** reviewer addresses all three failure modes in
principle and introduces two of its own: its output is not reproducible, so a reviewer
cannot be evaluated against a fixed expectation or serve as a stable gate, and its output is
not guaranteed to exist, because the review depends on a credential, a network path and a
remote service. The two weaknesses are connected, since an output that cannot be reproduced
cannot be traced to a rule and corrected; it can only be re-rolled. A **rule-only** reviewer
is deterministic, offline and cheap, and blind in a predictable way: a pattern over a line
cannot see that a value flowed from untrusted input into a query three functions away, cannot
recognise that a configuration change removes a security control, and cannot read intent.

The need identified was therefore for a reviewer that is **deterministic by default and
semantic when a model is available**, with the deterministic layer holding the floor. In that
arrangement the enumerated policy always runs, so a review always exists and always has a
stable baseline against which any other layer can be measured; the model layer is an
additional opinion over the same parsed input, and its absence is a degradation rather than
an outage. This is why the 63-rule engine in `app/rules.py` is mandatory and the model in
`app/openai_compat_provider.py` is optional.

## 2.2 Existing System and Its Limitations

Current practice is a human reviewer reading a diff in a pull-request interface, assisted in
most projects by a pipeline that runs a formatter, a linter and a test suite, and in some
projects by a commercial AI review service. Its limitations were examined under four
headings.

**The human pass is unbounded in cost and variable in coverage.** It has no enumerated
policy, no severity scale comparable across reviewers, and no record of what it decided not
to report. The same reviewer passes on a Friday a change that would have been blocked on a
Monday, and no artefact records the difference.

**The linter pass is bounded but shallow.** It checks syntax, formatting, import order and,
where a security rule pack is installed, a fixed catalogue of patterns. It does not know
which changed lines are security-relevant, it reports against the whole file rather than the
change, and its rule set is not extendable without a plugin in the linter's own idiom. It is
also commonly configured to fail the build, so a stylistic finding and a committed credential
arrive through the same channel and are read with the same urgency.

**The AI review service pass is neither reproducible nor guaranteed.** It requires a paid
endpoint and a network path at the moment of review, returns different findings for identical
input, and may name a line the change did not touch. Its comments are fluent, which makes an
incorrect comment harder to dismiss than a silent linter.

**None of the three states what it actually did.** A reviewer who sees no comments cannot
distinguish a clean change from a pipeline that failed to start, from a service that timed
out, from a rule pack that was never installed. This limitation was treated as the most
serious of the four, because it converts every other limitation into an invisible one.

The gap, stated precisely: existing practice provides either a bounded and deterministic pass
that cannot see security semantics, or an unbounded and non-deterministic pass that cannot be
relied upon to run. Nothing examined provides a deterministic security-aware pass that is
guaranteed to run, with a semantic pass above it and a result that states which of the two
produced it.

## 2.3 Proposed System

The proposed system is a hybrid reviewer: a mandatory deterministic engine with an optional
model layer above it, behind a single entry point, with a result that always declares which
layer ran.

A change arrives as a unified diff or a single source file. The parser converts it into a
structured bundle of files, hunks and lines, recording which line numbers were added, which
spans are contiguous and which hunk each line belongs to; nothing downstream reads raw diff
text. The router is the only place where a provider decision is made: it reads the
configuration once, applies a fixed precedence (hosted endpoint, then self-hosted endpoint,
then the rule engine) and returns the choice with a one-line reason. A blank variable counts
as unset, so an empty key degrades rather than producing an unauthenticated call.

The rule engine scans the added lines and only the added lines, with 63 rules in 10 categories
mapped to nine of the ten OWASP Top Ten (2021) categories, and returns findings in a
five-field contract: file, line, severity, issue and suggested fix. The contract forbids a
sixth field, so a malformed value fails where it enters rather than leaking into a published
comment.

The model layer, when it runs, uses one OpenAI-compatible transport for both endpoints. It
sends a prompt built from the same parsed bundle, requests a JSON reply, validates it against
the same five-field contract, discards any file the diff does not contain, snaps any line
number to an added line, and allows exactly one repair attempt. Its budget is at most two
model calls per review.

The anchorer places every finding against the changed lines as anchored, file only or
unanchored. The poster renders anchored findings as inline comments up to a configurable cap,
renders the rest in one summary comment, and embeds a fingerprint marker so that an identical
review is skipped rather than duplicated. Three surfaces expose the same pipeline: a
command-line interface, an HTTP API with a documented schema, and a webhook endpoint that
verifies a delivery signature and always answers the delivery. The data flow is presented as
Figure 2.3 and decomposed in Figures 2.4 and 2.5.

## 2.4 Software Requirement Specification

The specification is stated as eighteen functional and eight non-functional requirements. Each
is numbered, each carries a testable acceptance criterion, and each records its status in
version 0.1.0. A requirement is satisfied only when an artefact in the repository demonstrates
it; one demonstrated only against a simulated counterpart is marked partially satisfied, and
the word simulated is used deliberately.

**Table 2.1: Functional requirements**

| ID | Requirement | Acceptance criterion | Status |
|---|---|---|---|
| FR-01 | Parse a unified diff into files, hunks and lines | Added line numbers, added spans and hunk headers exposed per file; a malformed diff raises a typed error | Satisfied |
| FR-02 | Accept a single source file as a target | A file with no diff headers is treated as wholly added and reviewed | Satisfied |
| FR-03 | Represent every finding with exactly five fields | A sixth field is rejected at the boundary; a non-ascending line range is rejected | Satisfied |
| FR-04 | Apply 63 deterministic rules across 10 categories | The registry reports 63 rules, 10 categories and no duplicate identifiers; identical input yields byte-identical output | Satisfied |
| FR-05 | Scan added lines only | A defect in context or removed lines is not reported | Satisfied |
| FR-06 | Honour an inline suppression marker | A bare marker suppresses every rule on the line; a targeted marker suppresses one rule | Satisfied |
| FR-07 | Bound the cost of pattern matching | Each line is truncated before scanning; no pattern uses nested quantifiers | Satisfied |
| FR-08 | Anchor each finding to the changed lines | Every finding is classified anchored, file only or unanchored, with a stated reason | Satisfied |
| FR-09 | Select one provider by fixed precedence | Hosted wins over self-hosted, which wins over the rule engine; a forced provider without configuration degrades | Satisfied |
| FR-10 | Serve both model endpoints through one transport | One adapter imports the model SDK; the endpoints differ only in configuration data | Satisfied |
| FR-11 | Bound the model interaction | At most two calls per review: one attempt and one repair | Satisfied |
| FR-12 | Reject an answer naming an unknown file or line | Unknown files dropped and line numbers snapped to added lines before publication | Satisfied |
| FR-13 | Degrade to the rule engine without failing | A missing, rejected, unreachable or malformed provider yields rule-engine findings, one warning and exit status 0 | Satisfied |
| FR-14 | Publish a review to a pull request | Anchored findings become inline comments up to the configured cap, the rest are summarised, and every failure becomes a recorded error | Partially satisfied: demonstrated against a simulated GitHub API |
| FR-15 | Persist reviews, users and roles | A relational store records each review, its requesting user and that user's role | **Satisfied**: six tables and three roles in `app/db.py`, exercised by `tests/test_db.py` (27 cases) and `tests/test_auth.py` (13 cases) |
| FR-16 | Verify the webhook signature and answer every delivery with 200 | An unsigned delivery is rejected with 401 when a secret is set; a posting failure never changes the status | Satisfied |
| FR-17 | Measure precision, recall, F1, false-positive rate and latency | The harness reports TP/FP/FN, per-category scores and nearest-rank p50/p95 per mode | Satisfied (harness); [FILL AFTER BENCHMARK: measured values] |
| FR-18 | Prove the suite runs with no network access | `python scripts/verify_offline.py` blocks sockets and the suite still passes | Satisfied |

**Table 2.2: Non-functional requirements**

| ID | Attribute | Requirement | Verification |
|---|---|---|---|
| NFR-1 | Availability | A review is produced with no credential, no network and no model server | Default path runs the rule engine; the suite passes with sockets blocked |
| NFR-2 | Determinism | Identical input produces identical findings in the rule layer | Repeated runs over the bundled sample diff are compared |
| NFR-3 | Security of secrets | No credential appears in a log, a reason string, a finding or a comment | Credential fields excluded from representation; reason strings scrubbed |
| NFR-4 | Testability | The whole system is verifiable offline | 637 cases pass and 1 is skipped with outbound connections blocked |
| NFR-5 | Observability | Every result states mode, provider, model and, where degraded, the reason | Asserted on the command line, the API response and the review record |
| NFR-6 | Portability | The environment is reproducible from the repository alone | Interpreter pinned at 3.12.13; 37 pinned dependencies; two-stage container |
| NFR-7 | Maintainability | One entry point, one transport, one rule engine, dependencies pointing inward | Module dependency table in `ARCHITECTURE.md`, Section 7 |
| NFR-8 | Response time | A rule-engine review completes within a webhook deadline on a developer machine | `[FILL AFTER BENCHMARK: p50 and p95 review latency per mode]` |

Two properties deserve emphasis. FR-13 carries the project's central claim, and it is stated
as an outcome (a review, one warning, exit status 0) rather than as a mechanism, so that it
can be tested through every surface independently. Every requirement in the table is met; the
it is recorded as unmet rather than dropped, because the specification states what the system
was required to do and not what was convenient to build.

## 2.5 Software Engineering Paradigm Applied

The system was built by **incremental and iterative delivery**: six increments, each producing
a working system, each ending with the whole suite green, and each gated before the next
began. The increments were a scaffold with the configuration boundary, the finding contract
and the command line; diff parsing and anchoring; the rule engine and the HTTP surface; the
hosted model layer with a guaranteed fallback; pull-request posting; and the single
OpenAI-compatible transport with the provider router. The collected test count after each was
14, 11, 234, 87, 113 and 51 cases, which sums to 510 of the 638 collected cases in the
suite; the remaining 15 are in `tests/test_audit_gaps.py`, added at the final audit.

**Waterfall** was considered and rejected for three reasons, each evidenced in the repository
rather than asserted.

First, the requirement set was not knowable in advance. The specification contains eighteen
requirements; the first increment was built against roughly half of them. Requirements such as
the three-state anchoring model (FR-08) and the two-call budget (FR-11) were discovered by
building the layer beneath them and finding that a finding could not be attached to a line,
and that a model could loop. A sequential model would have fixed the wrong specification and
then defended it.

Second, the sixth increment was a **revision** of the fourth rather than an addition to it.
The hosted layer was built first with its own adapter and guards; when a second, self-hosted
endpoint was required, the guards were extracted into one transport and the provider
difference reduced to a configuration object. That is iteration in the strict sense, and it
produced the single most important structural property of the codebase. Waterfall would have
shipped two adapters with two sets of guards, the drift that
`docs/decisions/0003-provider-agnostic-openai-compat.md` was written to prevent.

Third, every increment had to be demonstrable on its own, since the project was assessed
through a demonstration. The consequence is that the offline path worked from the first
increment onward, which is why the degradation contract is a property of the architecture
rather than a feature added at the end.

The cost was accepted knowingly: interfaces were re-opened twice, and one deliberate deviation
from a written phase contract had to be documented so that a future reader would not undo it
(`docs/decisions/0004-degraded-path-calls-offline-findings-directly.md`).

## 2.6 Project Planning and Scheduling

The plan is recorded as artefacts rather than as prose, and this section points at them
instead of restating them.

The **PERT chart** is Figure 2.2 (`docs/diagrams/pert-chart.png`). It shows the six increments
as activities with their dependencies, including the dependency that made the sixth a revision
of the fourth, and carries the three-point estimates from which expected durations were
computed. The **Gantt chart** is Figure 2.1 (`docs/diagrams/gantt-chart.png`); it places the
same activities on a calendar with their overlaps and shows where testing overlapped
implementation.

![Figure 2.1 — Gantt chart of the sixteen-week schedule](docs/diagrams/gantt-chart.png)

![Figure 2.2 — PERT network for the project, with the critical path highlighted](docs/diagrams/pert-chart.png)

The **PERT table, the activity list, the three-point estimates, the expected duration and
variance of each activity and the identified critical path** are held in
`docs/diagrams/planning.md`, which is the authority for every scheduling figure in this
report. No duration and no date is quoted in this chapter, because a figure restated in prose
cannot be checked against the plan and would drift from it. The change log records that the
increments were in fact built across 13 and 14 November 2026; that is a record of what
happened, not the plan, and the difference between the two is visible in the artefacts.

**Table 2.3: Increments and their deliverables**

| Increment | Scope | Modules | Collected cases |
|---|---|---|---|
| 1 | Scaffold, configuration boundary, finding contract, command line | `app/config.py`, `app/models.py`, `app/cli.py`, `reviewer.py` | 14 |
| 2 | Diff parsing and anchoring to changed lines | `app/parser.py` | 11 |
| 3 | 63-rule engine and HTTP surface | `app/rules.py`, `app/main.py` | 234 |
| 4 | Hosted model layer with guaranteed local fallback | `app/sarvam_provider.py`, `app/mock_provider.py` | 87 |
| 5 | Pull-request posting: inline, summary, idempotent | `app/github_client.py` | 113 |
| 6 | One OpenAI-compatible transport, two providers, one router | `app/openai_compat_provider.py`, `app/engine.py` | 51 |
| Audit | Cross-cutting gaps found at the final audit | `tests/test_audit_gaps.py` | 15 |

A later wave produced the benchmark harness, contributing 73 collected cases, and a further
wave produced the documentation and reproducibility artefacts; neither is counted in Table 2.3
because neither adds a runtime capability. The application and harness totals are therefore
565 and 73 against a collected total of 638.

## 2.7 System Analysis Models

The analysis is recorded as ten figures. Figures 2.1 and 2.2, the schedule artefacts, were
referenced in Section 2.6; the remaining eight are described here.

Discussed in Section 2.6.

Discussed in Section 2.6.

![Figure 2.3 — Context diagram (DFD level 0)](docs/diagrams/dfd-level-0.png)

The system is
drawn as a single process with its external agents: a developer at a command line, an HTTP
client, a continuous integration runner, the GitHub review API and an OpenAI-compatible model
endpoint. It fixes the system boundary and shows that only one of the three external entities is a model
endpoint, which the level-1 diagram develops.

![Figure 2.4 — DFD level 1 - major processes and data stores](docs/diagrams/dfd-level-1.png)

The single
process is decomposed into seven: parse the change, select a provider, review, anchor the
findings, publish the result, persist the review and authenticate the caller. Configuration is drawn as a one-way flow into selection, and
the finding list is the only artefact crossing from review to anchoring, which is what lets
either review layer feed the same publication path.

![Figure 2.5 — DFD level 2 - decomposition of rule application and provider review](docs/diagrams/dfd-level-2.png)

The review
process of Figure 2.4 is decomposed into rule evaluation over added lines, prompt
construction, the transport call, validation of the returned payload and the degradation
branch. It makes the two-call budget and the one-warning rule visible as control flow rather
than as prose.

![Figure 2.6 — Entity-relationship diagram of the six-table schema](docs/diagrams/er-diagram.png)

It presents the physical data model of requirement FR-15 as implemented in `app/db.py`: a
review and the findings it contains, the role a user holds, and the record of each attempt to
publish a review to a pull request. Every column in the figure exists in the `SCHEMA_SQL`
constant, and `tests/test_db.py` exercises each constraint. Note what the model deliberately
does not carry: a review has no user column, so attribution is a property of the deployment
(the key holder) rather than of the row.
The entity and attribute list matches the `SCHEMA_SQL` constant in `app/db.py` and the tables created by `tests/test_db.py`.

![Figure 2.7 — Class diagram of the domain and provider types](docs/diagrams/class-diagram.png)

It records the frozen
interfaces of `app/models.py`, `app/parser.py`, `app/rules.py`, `app/engine.py` and
`app/github_client.py`: the five-field finding and the anchored finding that wraps it, the
bundle with its file, hunk and line parts, the rule and its hit, the provider outcome, the
provider configuration, the review payload and the post result. It is drawn at the level of
those types rather than of every function, because those types are what the tests patch and
what the surfaces consume.

![Figure 2.8 — Use-case diagram with actors and included use cases](docs/diagrams/use-case-diagram.png)

The actors are the
developer, the continuous integration runner, the GitHub review API, the model endpoint and
the operator; the use cases are reviewing a diff, reviewing a single file, listing the rule
policy, forcing a provider, receiving a webhook delivery, posting a review and inspecting
health. The model endpoint is drawn as an actor that may be absent, which is FR-13 in the
notation of the model.

![Figure 2.9 — Activity diagram of the end-to-end review flow](docs/diagrams/activity-diagram.png)

It follows one review
from input to output and contains the decision that defines the system: whether a live
provider is configured and reachable. Both branches converge on the same rule-engine call, so
the degrade is drawn as a fork that rejoins, and publication receives the same finding list on
either path.

![Figure 2.10 — State diagram of the posting state machine](docs/diagrams/state-diagram.png)

It records the lifecycle
of a finding from production, through the three anchoring states and the two posting states,
to the terminal states of posted, demoted after a rejection and suppressed as a duplicate. The
duplicate state is reached from the fingerprint marker, which is why the marker is drawn as a
transition guard rather than as a data element.

## 2.8 Feasibility Study

**Technical feasibility.** The system was built, executed and verified within the stated
environment, which is the strongest form of technical evidence available. Every runtime
dependency is open source and installed from a 36-entry lock file, the interpreter is pinned at
3.12.13, and the seven direct dependencies are exact-version pins. The mandatory path needs no
graphics processor, no model server and no network, so the default configuration runs on an
ordinary developer machine. The package is 15 modules and 9,250 lines, which one developer can
hold in view, and the dependency table shows edges pointing inward with one module making the
provider decision. Three risks were addressed structurally rather than by assertion:
non-determinism, by making the rule engine mandatory; credential leakage, by excluding
credential fields from representation and scrubbing reason strings; invented locations, by
discarding unknown files and snapping line numbers before publication. The residual risk is
that the model path has never been driven by a real model: it was exercised against a stub
server speaking the same protocol, so the transport, the guards and the degradation branch are
proven and the model's actual behaviour is not.

**Economic feasibility.** The default configuration has no recurring cost: no licence, no
subscription, no hosted endpoint and no network egress, on hardware the project already owns,
and the whole verification was performed with no paid service involved. A cost arises only if
the operator enables a hosted endpoint, and that choice is explicit and reversible, since
removing the credential returns the system to the rule engine with no code change. No price or
tariff is quoted in this report, because none was measured or obtained. The development cost
was one developer's time across the six increments of Section 2.6, and the maintenance cost is
bounded by the small dependency set and the frozen interfaces: a new provider is a
configuration function and a test, not a new adapter.

**Operational feasibility.** The system is operated with one command for a review and one for
the server, and needs no environment variable to start. Its exit codes distinguish a produced
review, including every degraded run, from a bad input path and from a usage error, so a
script can act on the outcome, and the webhook answers every delivery whether or not the
review succeeded, which is what a hosting platform requires. The operational risk accepted
knowingly is the one recorded in `docs/decisions/0002-offline-first-fallback.md`: a silent
degradation can hide a misconfiguration, so an operator who intended the hosted model and
mistyped the variable may receive a plausible rule-engine review without noticing. It is
mitigated (mode, provider and reason appear in every response, and exactly one warning is
written to standard error) and was accepted because failing hard on a missing credential
converts an environment variable into a failed review and a red status on an unrelated pull
request.

## 2.9 Summary

This chapter identified the need from three failure modes of manual review and from the
argument between a deterministic and a model-based remedy, concluding that the deterministic
layer must hold the floor and the model layer must be optional. It examined current practice
under four headings and stated the gap precisely: no existing pass is deterministic,
security-aware and guaranteed to run. It described the proposed hybrid system, fixed the
requirement in eighteen functional and eight non-functional requirements (sixteen satisfied,
one satisfied only against a simulated counterpart) and justified incremental
delivery over waterfall on three evidenced grounds. It pointed at the PERT chart, the Gantt
chart and the planning table as the authority for every scheduling figure, and presented the
ten analysis models that record the data flow, the data model, the class structure, the use
cases, the activity and the state lifecycle. The feasibility study concluded that the system
is technically built and verified, economically free in its default configuration and
operationally simple, with two residual risks stated rather than hidden. Chapter 3 presents
the design these requirements imply.
