# Chapter 1: Introduction

## 1.1 Introduction

A code review is the stage at which a proposed change is read by someone other than its
author before it is merged. Its purpose is to catch the class of defect that a compiler and
a test suite do not catch: a credential written literally into a source file, a database
query assembled by string concatenation, a TLS verification flag switched off so that a
test would pass, an exception handler broad enough to swallow every failure. The practice
is sound. What does not scale is the practice as it is normally performed, by a person
reading a diff in a browser tab between other work.

Three failure modes recur, and they compound one another. The first is latency: a change
waits in a queue for a reviewer to become free, and the wait is longest for exactly the
small, frequent changes that a modern workflow produces in volume. The second is
inconsistency: two competent reviewers presented with the same diff will raise different
findings, because each applies a private and tacit threshold for what is worth a comment.
The third is attention decay: a reviewer working through a large diff spends attention in
proportion to the diff's length rather than in proportion to its risk, so the hundredth
hunk receives less scrutiny than the first. None of the three is a criticism of reviewers;
all three follow from asking a person to perform a deterministic, repetitive, exhaustively
enumerable task unaided. No prevalence figure is quoted, because none was measured in this
project.

Tooling exists in two families, and neither closes the gap. The first is static analysis:
linters and security scanners that check syntax, formatting and a fixed catalogue of
patterns. These are fast, deterministic and reproducible, and they carry no security model
beyond the rule pack their author shipped. The second family is the large language model
applied directly to a diff. These comment fluently and can describe a defect no pattern
would match, and they are neither deterministic nor reliably available: the same diff
reviewed twice returns different findings, and a finding that names a line may name a line
the change never touched.

Both families also share an assumption that is rarely stated and frequently false. The
tooling assumes a paid model endpoint and a working network connection at the moment of
review. That assumption holds in a funded continuous integration pipeline and fails in the
places where this project was demonstrated and evaluated: an examination room with no
network, a runner with no outbound egress, a laptop with no graphics processor, and an API
key that expired an hour before the demonstration. A reviewer that cannot start produces no
review, and a review that produces nothing is indistinguishable, to the person waiting for
it, from a review that found nothing.

The system described in this report was built around that observation. It is a reviewer in
which the model is optional and the rule engine is mandatory. A unified diff is parsed into
files, hunks and added line numbers; a deterministic engine of 63 rules, grouped into 10
categories and mapped to nine of the ten OWASP Top Ten (2021) categories, scans the added
lines and nothing else; every finding is placed against the changed lines of the diff
before it is published; and, when a model endpoint is configured and reachable, one
OpenAI-compatible transport obtains a second opinion over the same parsed diff. Three
providers exist (a hosted endpoint, a self-hosted endpoint and the rule engine), and
exactly one function decides which of them runs. When no live provider is usable the review
still happens, exactly one warning is logged, the process still exits with status 0, and
the result states in one line why the rule engine was used.

That property, and not the model call, is the contribution this report defends. The claim
is narrow and testable: the system degrades rather than fails, and every result says which
mode produced it, which provider produced it and, where it degraded, why. Whether the model
layer detects defects the 63 rules miss, and at what cost in latency and false positives,
is a separate empirical question, answered or not answered in Chapter 6 on the evidence of
a benchmark whose labelled dataset did not exist at the time of writing.

## 1.2 Objectives

The project set eight objectives. Each is phrased so that it can be marked achieved or not
achieved against an artefact in the repository rather than against an impression, and each
names the chapter that presents the evidence.

**O-1. To parse a unified diff into files, hunks and added line numbers.** The parser was
required to consume the output of `git diff` unmodified, to expose the added line numbers
and contiguous added spans of every file, and to reject a malformed diff with a typed error
rather than a partial bundle. *Achieved:* `app/parser.py`, with 11 collected cases in
`tests/test_parser.py`; Chapter 4, Section 4.2.

**O-2. To apply 63 deterministic rules, mapped to the OWASP Top Ten, over added lines
only.** The engine was required to be deterministic, to scan only added lines, to carry an
identifier, title, category and OWASP mapping for every rule, and to publish the whole
policy through one endpoint. *Achieved:* `app/rules.py` holds 63 rules in 10 categories
mapped to 9 distinct OWASP Top Ten (2021) labels; `RULE_COUNT` reports 63 and is asserted
by the suite; 187 collected cases in `tests/test_rules.py`; Chapter 4, Section 4.3.

**O-3. To anchor every finding to the changed lines of the diff.** A finding is a claim
about a line, and a pull request accepts an inline comment only on a line the diff
contains. The anchorer was required to assign one of three statuses (anchored, file only,
unanchored) so that a finding which cannot be attached is published in the summary rather
than silently dropped. *Achieved:* `anchor_findings` in `app/parser.py`; Chapter 3, Section
3.5.

**O-4. To support one OpenAI-compatible transport serving two providers.** A hosted and a
self-hosted endpoint were both required to be reachable through a single adapter, with the
difference expressed as configuration data rather than as a second code path, so that the
guards around a model call exist in one place. *Achieved:* `app/openai_compat_provider.py`
is the only module importing the model SDK; both configurations are built in
`app/engine.py`; 51 collected cases in `tests/test_openai_compat_provider.py`; Chapter 4,
Section 4.6.

**O-5. To degrade to the rule engine whenever no provider is available.** Every entry point
(command line, HTTP API, webhook and benchmark runner) was required to produce a review
when no credential is configured, when the credential is rejected, when the endpoint is
unreachable and when it answers in prose instead of JSON; the degrade was required to log
exactly one warning and never to raise. *Achieved:* the contract in
`docs/decisions/0002-offline-first-fallback.md`, enforced in `app/openai_compat_provider.py`
and `app/engine.py`; Chapter 3, Section 3.3.

**O-6. To post an idempotent review to a pull request.** The poster was required to publish
anchored findings as inline comments up to a configurable cap, to publish everything else
in one summary comment, and to detect an identical earlier review so that a re-run does not
duplicate it. *Achieved against a simulated counterpart:* `app/github_client.py` computes a
16-hexadecimal-digit fingerprint over four identity fields and embeds it in a marker
comment; 113 collected cases across three test files exercise the flow, none of which
contacted `api.github.com`; Chapter 4, Section 4.5.

**O-7. To persist reviews, users and roles.** A relational store was to hold the review
history with the users who requested reviews and the roles governing what each could do.
*Achieved.* The store is implemented in `app/db.py` on SQLAlchemy 2.x Core over SQLite, with six tables, three roles, hashed API keys and the DDL in one auditable `SCHEMA_SQL` string; `tests/test_db.py` and `tests/test_auth.py` cover it. An object-relational dependency now appears in
`requirements.lock`, the schema exists in `app/db.py`, and `tests/test_db.py` asserts that a stored review round-trips with its findings.
The requirement is recorded in the specification (Section 2.4, FR-15) and
unsatisfied rather than deleted, because deleting it would misrepresent what the system was
specified to do. The schema is implemented in `app/db.py` with six tables and three roles, and `tests/test_db.py` asserts that each constraint rejects bad data.

**O-8. To provide a test suite that verifies the system with no network access.** The suite
was required to run to completion with outbound connections blocked, so that the offline
claim is demonstrated rather than asserted. *Achieved:* `python -m pytest -q tests` reported
**637 passed, 1 skipped** in 17.31 s on the tree described here, and
`python scripts/verify_offline.py` re-runs the suite in process with socket creation
blocked. The single skip is a live-endpoint smoke test guarded by an environment variable.
Chapter 5, Section 5.1.

## 1.3 Scope of the Solution

The scope is stated as two explicit lists, because a report that describes only what was
built invites the reader to assume the rest.

**In scope.** The system accepts a unified diff or a single source file, parses it into
files, hunks and added line numbers, and reviews the added lines with 63 deterministic
rules across 10 categories, honouring an inline suppression marker. It reviews the same
diff through one OpenAI-compatible transport when a hosted or self-hosted endpoint is
configured, with a single repair retry and guards against a model that names files or lines
the diff does not contain. It selects one of three providers by a fixed precedence and
degrades to the rule engine on any failure, anchors every finding to the changed lines, and
renders a review as text, JSON, an HTTP response or a set of pull-request comments carrying
an idempotency marker. It verifies the signature of an incoming webhook delivery, runs
without credentials, and its suite runs without a network.

**Out of scope, deliberately.** The system does not modify code: it reports a finding and a
suggested fix as prose, and no code path writes to a repository. It does not perform
multi-language abstract syntax tree analysis; the rule engine is a line-and-pattern engine
with a deliberately shallow view of a file, so a defect that requires following a value
across function or module boundaries is outside what it can detect, as Chapter 7 states
again. It does not parse a language grammar, build a symbol table or resolve imports. It is
not a hosted service: no multi-tenancy, account system, billing or uptime commitment, and
the persistence layer of O-7 stores reviews and users, it holds no source code of its own. It is not a GitHub App: no installation is
registered, no installation token is requested, and it reacts to no event other than a pull
request event delivered to its webhook, posting with a token supplied by the operator. It
does not train, fine-tune or evaluate a model; the model is used as supplied. It does not
claim a benchmark result, because the labelled evaluation dataset described in Section 2.4
was not produced.

## 1.4 Project Category

The project falls in the category **Artificial Intelligence and Machine Learning**.

The justification rests on what the artefact does rather than on the presence of a model in
the dependency list. The mandatory layer is a knowledge-based expert system in the classical
sense: 63 rules, each carrying an identifier, a title, a category, an OWASP mapping and a
severity, applied by a forward-chaining evaluator over a structured representation of a
change. The knowledge is explicit, inspectable and enumerable through an API endpoint; the
inference is deterministic and reproducible. That is symbolic artificial intelligence, and
it is the layer that always runs. The optional layer is machine learning in the ordinary
sense: a pre-trained large language model is queried over an OpenAI-compatible
chat-completions interface with a prompt constructed from the parsed diff, and its
structured reply is validated and reconciled against the diff before any of it is
published.

The engineering interest sits at the seam between the two layers, which is why the design is
called hybrid rather than model-based. Three properties of that seam are the subject of this
report: the deterministic layer must remain the floor rather than a fallback of last resort;
the model's output must be constrained by a schema that forbids a sixth field and by guards
that reject a file or line the diff does not contain; and the arrangement must be
evaluable, which requires that the same input produce the same output at least in the layer
that is measured.

Two clarifications prevent a misreading. The project does not train a model, curate a
training corpus or report a learning result; no gradient was computed and no weights
changed. Nor is it a study whose subject is a dataset: the dataset exists, in the design,
only as an instrument for measuring the artefact, and at the time of writing that instrument
is not populated. The category is claimed on the strength of a symbolic reasoning engine and
a constrained model interface, both present and both tested.

## 1.5 Tools, Platform and Environment

The implementation is a single Python package of 15 modules totalling 9,250 lines as counted
by `wc -l`, including the package initialiser and the module entry point, with a
thirteen-line command-line entry script, a benchmark harness, a test suite and a
documentation set. Table 1.1 records the tool chain at the versions installed and executed
while this chapter was written.

**Table 1.1: Tool chain**

| Component | Tool and version | Role in the system |
|---|---|---|
| Interpreter | CPython 3.12.13 | Pinned in `.python-version` and in both Dockerfile stages |
| Web framework | FastAPI 0.162.5 | `/`, `/health`, `/rules`, `/rules/{id}`, `/review`, `GET\|POST /test-review`, `/webhook`, `/docs` |
| Data validation | Pydantic 2.14.3 | The five-field finding contract and every boundary model, unknown keys forbidden |
| Settings | pydantic-settings 2.15.0 | The single credential boundary; the only reader of the environment |
| HTTP client | httpx 0.28.1 | GitHub API calls and the patchable transport seam |
| Model SDK | openai 3.51.0 | The one OpenAI-compatible transport, imported lazily |
| Vendor SDK | sarvamai 0.1.46 | The earlier hosted-model adapter, behind the same guards |
| Server | uvicorn 0.54.0 | Application server for the API and webhook |
| Test runner | pytest 8.4.2 | 638 collected cases across 15 files |
| Charting | matplotlib, optional and unpinned | Benchmark chart only; the report degrades to a warning without it |
| Container | Docker, two-stage `python:3.12-slim` | Image and compose definition; the image was not built here |

Two entries in the requested tool chain need a statement rather than a row. An
object-relational mapper and an embedded relational database are the basis of the persistence
layer described in O-7: `sqlalchemy==2.1.8` is pinned in `requirements.lock`, the six table
definitions live in `app/db.py` as the `SCHEMA_SQL` constant, and `get_database()` creates the
SQLite file on first use. The dependency set is therefore the seven direct runtime pins of
`requirements.txt` and the 37 pins of `requirements.lock`, the resolved closure that the Dockerfile and the
continuous-integration workflow install.

The hardware requirement follows from the mode. The rule engine, the parser, the HTTP
surface and the whole test suite were executed on a machine with no graphics processor, no
model server and no network egress; that path needs no more than an ordinary developer
machine. The self-hosted model path needs a host able to hold the selected model in memory
or video memory, a requirement `docs/LMSTUDIO.md` states qualitatively and does not
quantify. The tree records no minimum specification for either path, so none is asserted
here. `[FILL AFTER BENCHMARK: measured peak resident memory and per-review wall-clock latency on the submission machine, for the rules mode and the local mode]`

The environment is reproducible from the repository alone. These were the commands
executed, in this order, from the repository root:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pytest -q tests
.venv/bin/python reviewer.py samples/sample.diff
.venv/bin/python -m uvicorn app.main:app --port 8000
```

`make verify` performs the first three steps against its own virtual environment and then
re-runs the suite with sockets blocked, so one command reproduces the whole offline claim.
No environment variable is required by any command above; the model paths are enabled only
by exporting `SARVAM_API_KEY` or `LMSTUDIO_BASE_URL`.

## 1.6 Organisation of the Report

Chapter 1 states the problem, the objectives, the scope, the category and the environment.
Chapter 2 analyses the system: the need, current practice, the proposed design, the numbered
specification, the engineering paradigm, the plan and its schedule artefacts, the analysis
models and the feasibility study. Chapter 3 presents the design: the component map, the
finding contract, the anchoring model, the configuration boundary and the single router.
Chapter 4 describes the implementation phase by phase, naming for each its module, the
interface it fixed, the failure mode it closed and the non-goal it accepted. Chapter 5
separates testing from evaluation, Chapter 6 interprets the results, Chapter 7 states the
limitations, Chapter 8 marks each objective achieved or not and lists the future work, and
Chapter 9 holds the references. The appendices carry the commands that produced every
number, the screenshots and the repository map.

## 1.7 Summary

This chapter set out the problem: manual code review is slow, inconsistent between
reviewers and unreliable on large changes, while the tooling that exists either applies a
fixed rule pack with no security model or depends on a paid model endpoint and a live
network at the moment of review. It stated eight objectives in testable form, of which seven
are achieved in version 0.1.0 and one, the persistence of reviews, users and roles, is
 It drew the scope boundary, justified the classification of the
work as artificial intelligence and machine learning, and recorded the tool chain and the
commands that reproduce the environment. Chapter 2 now analyses the requirement in detail.
