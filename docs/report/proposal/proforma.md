# Proforma for Approval of Project Proposal

**Indira Gandhi National Open University**
School of Computer and Information Sciences
MCA (Revised) Programme — Master of Computer Applications

*Course: MCSP-232 (Project). To be completed by the student and forwarded, through
the study centre, to the regional centre for approval before the project work
begins. Fields marked `[FILL: ...]` are to be completed by the student in
consultation with the guide.*

---

## Part A — Details of the Student

| Field | Entry |
|---|---|
| Name of the student | Shreyash Yadav |
| Enrolment number | `[FILL: enrolment number]` |
| Programme code | MCA_NEW |
| Programme name | Master of Computer Applications (Revised) |
| Course code | MCSP-232 |
| Course title | Project |
| Study centre code and name | `[FILL: study centre]` |
| Regional centre | `[FILL: regional centre]` |
| Session | `[FILL: July 2026 / January 2027 session]` |
| Mobile number | `[FILL: mobile number]` |
| Email address | `[FILL: email address]` |
| Postal address for correspondence | `[FILL: postal address]` |

## Part B — Details of the Project

| Field | Entry |
|---|---|
| Title of the project | Autonomous AI Code Reviewer & PR Assistant |
| Project category | Artificial Intelligence and Machine Learning |
| Area of specialisation | Software engineering; applied machine learning; application security |
| Type of project | Design and development of a working software system with an evaluation component |
| Language and platform of implementation | Python 3.12 on Linux; FastAPI for the HTTP surface; Pydantic for the data contract; a deterministic rule engine plus an optional OpenAI-compatible model layer |
| Front end, if any | Command line; HTTP interface with a generated interactive schema; GitHub pull request comments |
| Back end, if any | A single-host service with no database server, message broker or shared storage |
| Does the project use data supplied by an external organisation? | No. All input is a code diff; the evaluation dataset, when it exists, is to be labelled by the student |
| Does the project require an ethical clearance? | No. No human participants are involved and no personal data is processed |
| Is the project related to the student's place of work? | `[FILL: yes / no]` |

## Part C — Objectives of the Project

| # | Objective |
|---|---|
| 1 | Parse a unified diff into files and hunks, and anchor every finding to the changed line range it concerns |
| 2 | Detect a defined set of security and quality defects deterministically, with every rule mapped onto the OWASP Top Ten |
| 3 | Add an optional language-model review layer that degrades to the deterministic engine without failing when the model is unavailable |
| 4 | Publish a review to a GitHub pull request as inline comments plus one summary, idempotently |
| 5 | Measure the system on a human-labelled dataset and report precision, recall, F1, false-positive rate and latency per mode |

## Part D — Details of the Guide

| Field | Entry |
|---|---|
| Name of the guide | `[FILL: guide name and designation]` |
| Designation | `[FILL: designation]` |
| Department and institution | `[FILL: department, institution]` |
| Highest qualification | `[FILL: highest qualification]` |
| Area of specialisation | `[FILL: area of specialisation]` |
| Full postal address | `[FILL: postal address of the guide]` |
| Email address | `[FILL: guide email address]` |
| Telephone number | `[FILL: guide telephone number]` |
| Is the guide on the approved panel of the regional centre? | `[FILL: yes / no]` |
| Number of students currently guided | `[FILL: number]` |

## Part E — Place of Work and Facilities

| Field | Entry |
|---|---|
| Place where the project will be carried out | `[FILL: place of work]` |
| Address of the place of work | `[FILL: address]` |
| Hardware available | A personal computer with a modern multi-core processor, at least 2 GB of free memory and 1 GB of free disk; no GPU is required for the deterministic path |
| Software available | Python 3.12, a command-line shell, Git, a web browser, and optionally a container runtime |
| Network available | `[FILL: yes / no]` — an internet connection is needed only for the optional hosted model and for publishing to GitHub |
| Does the student have access to the equipment outside working hours? | `[FILL: yes / no]` |

## Part F — Duration and Schedule

| Field | Entry |
|---|---|
| Total duration of the project | Approximately thirteen working weeks of planned effort, as scheduled in the PERT network and Gantt chart of the synopsis |
| Proposed date of commencement | `[FILL: date of commencement]` |
| Expected date of completion | `[FILL: expected date of completion]` |
| Expected date of submission of the report | `[FILL: expected date of submission]` |
| Number of phases | Six build phases, plus a reproducibility and documentation phase and an evaluation phase |
| Mode of supervision | `[FILL: mode of supervision — in person / online / both]` |
| Frequency of progress review | `[FILL: frequency of review]` |

## Part G — Deliverables

| # | Deliverable |
|---|---|
| 1 | A working software system: a command-line reviewer, an HTTP service and a GitHub webhook receiver |
| 2 | A deterministic rule engine of 63 rules mapped onto the OWASP Top Ten, with a registry that can be listed and inspected |
| 3 | A provider layer that serves a hosted model and a self-hosted model through one adapter, with a specified and tested degradation path |
| 4 | A benchmark harness with a frozen interface, a documented matching rule and a documented metric definition |
| 5 | A test suite that runs with no network access, and a verifier that proves it |
| 6 | Reproducibility material: a pinned dependency lock, a pinned interpreter, a two-stage container image and a continuous-integration workflow |
| 7 | A project report, a project synopsis and this proforma |

## Part H — Declaration and Signatures

**Declaration by the student.** I declare that the project proposal described in this
proforma is my own work, that it has been prepared under the supervision of the guide
named in Part D, and that it has not been submitted for any other course or
programme. The software described is being developed by me, and the sources used will
be acknowledged in the report.

| | |
|---|---|
| Signature of the student | |
| Name | Shreyash Yadav |
| Enrolment number | `[FILL: enrolment number]` |
| Date | `[FILL: date]` |
| Place | `[FILL: place]` |

**Recommendation by the guide.** I have discussed the proposal with the student and
recommend it for approval by the regional centre.

| | |
|---|---|
| Signature of the guide | |
| Name | `[FILL: guide name and designation]` |
| Date | `[FILL: date]` |

**Forwarded by the study centre.**

| | |
|---|---|
| Signature of the coordinator | |
| Name of the study centre | `[FILL: study centre]` |
| Date | `[FILL: date]` |
| Seal | |

**Approved by the regional centre.**

| | |
|---|---|
| Signature of the Regional Director | |
| Regional centre | `[FILL: regional centre]` |
| Date | `[FILL: date]` |
| Seal | |

---

## Instructions for the Student

1. Complete every field marked `[FILL: ...]`. A proforma with an unresolved field
   will be returned, and a returned proforma costs a cycle of the schedule.
2. The title must match, word for word, the title on the synopsis and on the title
   page of the report. An examiner checks the three against each other.
3. The synopsis accompanying this proforma follows the order prescribed in the
   project guidelines, from the title through the introduction and objectives, the
   project category, the tools and platform requirements, the problem definition with
   requirement specifications, literature review and project planning, the scope, the
   analysis, the database details, the module structure, the network architecture, the
   security mechanisms, the future scope and the bibliography.
4. Keep a signed copy of the approved proforma. It is required at the time of
   submission of the final report.
