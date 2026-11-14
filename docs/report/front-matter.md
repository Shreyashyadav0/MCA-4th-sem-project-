# Front Matter

*This file carries the parts of the report that precede Chapter 1. The assembler
places it first, in the order given below, and generates the table of contents from
the headings of the assembled document. Every `[FILL: ...]` marker is a field only
the student can supply; nothing else in this file is provisional.*

---

## Title Page

<div align="center">

**AUTONOMOUS AI CODE REVIEWER & PR ASSISTANT**

A project report submitted in partial fulfilment of the requirements
for the degree of

**Master of Computer Applications (MCA)**

Programme Code: **MCA_NEW**

Course Code: **MCSP-232** (Project)

Submitted by

**Shreyash Yadav**

Enrolment Number: `[FILL: enrolment number]`

Study Centre: `[FILL: study centre]`

Regional Centre: `[FILL: regional centre]`

Under the supervision of

`[FILL: guide name and designation]`

`[FILL: July 2026 / January 2027 session]`

`[FILL: date of submission]`

</div>

---

## Certificate

**Indira Gandhi National Open University**
School of Computer and Information Sciences

---

This is to certify that the project report entitled

**"Autonomous AI Code Reviewer & PR Assistant"**

submitted by **Mr. Shreyash Yadav**, Enrolment Number `[FILL: enrolment number]`, in
partial fulfilment of the requirements for the award of the degree of **Master of
Computer Applications (MCA)**, under the programme code **MCA_NEW**, for the course
**MCSP-232 (Project)**, is a record of original work carried out by him under my
supervision and guidance.

The work embodied in this report has been carried out by the candidate himself. To
the best of my knowledge, the report has not been submitted, either in part or in
full, to this university or to any other university or institution for the award of
any other degree or diploma. The candidate has acknowledged all sources of
information, data and software used in the preparation of this work, and the
software described in it has been developed by the candidate.

The work is, in my opinion, of a standard appropriate to the award of the degree for
which it is submitted, and it is fit to be placed before the examiners.

<br>

| | |
|---|---|
| Signature of the Guide | |
| Name | `[FILL: guide name and designation]` |
| Designation | `[FILL: designation]` |
| Department and Institution | `[FILL: department, institution]` |
| Date | `[FILL: date]` |
| Place | `[FILL: place]` |

<br><br>

| | |
|---|---|
| Signature of the Student | |
| Name | Shreyash Yadav |
| Enrolment Number | `[FILL: enrolment number]` |
| Study Centre | `[FILL: study centre]` |
| Regional Centre | `[FILL: regional centre]` |
| Date | `[FILL: date]` |

<br>

*(Seal of the Study Centre / Regional Centre)*

The certificate is a separate page in the bound report and appears at
`proposal/certificate-of-originality.md` in this repository. It is placed after the
title page and before the acknowledgement, and it carries the guide's signature and
the student's signature.

---

## Acknowledgement

I record my sincere gratitude to `[FILL: guide name]`, my project guide, for the
supervision of this work. The direction of this project — towards a reviewer that
remains useful when the model is unavailable, and whose output can be checked rather
than merely trusted — came from that supervision, and the insistence that no result
be reported which had not been measured shaped both the software and this report.

I thank the faculty and staff of the School of Computer and Information Sciences,
Indira Gandhi National Open University, and the staff of my study centre
`[FILL: study centre]`, for their guidance through the programme and for the
administrative support that made the project submission possible.

I thank my family and my colleagues for their patience during the months in which
this work was built and written, and for the many conversations in which an
unclear idea was made clear.

Any error that remains in this report is my own.

**Shreyash Yadav**
`[FILL: enrolment number]`

---

## Abstract

Code review is the last checkpoint before a change reaches a shared branch, and it
is under pressure: reviewer attention is finite, small pull requests wait for a
reader, and human judgement varies between reviewers and between days. Tooling that
addresses this pressure divides into two families. Pattern-based analysers are fast,
deterministic and explainable, but they detect only what a pattern can express.
Language-model reviewers can comment on intent and on defects that require context,
but they depend on a hosted endpoint, they are not reproducible between runs, and
they fail in ways that are difficult to audit.

This project builds a reviewer that takes the strengths of the first family as its
foundation and admits the second only as an optional layer above it. The system
parses a unified diff into files and hunks, anchors every finding to the changed
lines it concerns, and produces findings with exactly five fields — file, line,
severity, issue and suggested fix. A deterministic engine of 63 rules, mapped onto
the OWASP Top Ten, always runs and requires no network, no credential and no model.
An optional model layer, reached through a single OpenAI-compatible adapter that
serves both a hosted endpoint and a self-hosted one, adds findings the rules cannot
express. When that layer is unavailable, misconfigured, or answers unusably, the
review degrades to the rule engine, announces the degradation in one warning, and
still returns a complete review. The result is published to a GitHub pull request as
inline comments plus one summary comment, idempotently, and the whole pipeline is
demonstrable from a command line, over HTTP, and from a webhook.

`[FILL AFTER BENCHMARK: abstract result sentence]`

**Keywords:** static analysis, code review automation, large language models, OWASP
Top Ten, unified diff, offline-first design, degradation contract, GitHub pull
requests.

---

## Table of Contents

The table of contents is generated, not written. The assembler walks the assembled
document, collects every heading from level one to level three, and emits an entry
per heading with a page number resolved in a second pass once the page layout is
fixed. Two consequences follow, and both are worth stating in the report itself so
that a reader who notices an omission knows why it is there:

- Chapter and section numbers in the entries come from the headings as written.
  Editing a heading changes the contents entry, and nothing else needs touching.
- The contents must be regenerated after any structural edit. A contents page that
  disagrees with the body is the first defect an examiner notices, so the assembler
  regenerates it on every build rather than caching it.

The assembled order is: title page, certificate of originality, acknowledgement,
abstract, table of contents, list of figures, list of tables, list of abbreviations,
Chapters 1 to 12, and the appendices. The appendices are lettered A to F and are
referenced from the chapters by letter rather than by page.

*List of figures and list of tables:* both are generated by the assembler from the
captions of the figures and tables it finds, in document order, with page numbers
resolved in the same second pass as the contents. Neither list is written by hand.

---

