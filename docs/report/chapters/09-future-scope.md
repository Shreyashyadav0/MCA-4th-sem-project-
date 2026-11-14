# 9 Future Scope

The enhancements below are ordered by the constraint that blocks them rather than
by ambition. Each names what it would add, what it would cost, and why it was not
built in this project. None of them requires re-architecting what exists: the
provider precedence, the five-field finding contract and the anchoring model were
frozen in Phases 1 to 3 precisely so that the layer above them could be replaced
without disturbing the layer below.

## 9.1 A labelled benchmark at scale

The single most valuable enhancement, and the one every other measurement depends
on. It requires several hundred diffs drawn from real repositories, each labelled
by hand against a written protocol, and preferably labelled by two annotators so
that agreement can be reported. The harness already accepts such a dataset, the
collector already produces empty label templates, and the interactive label helper
already prompts a human; what is missing is the human time. Until it exists, every
precision and recall figure this project could quote would come from format
examples, which is why the report carries placeholders rather than numbers.

## 9.2 Multi-language abstract-syntax-tree rules

The current engine is line- and pattern-based, which is what makes it fast,
explainable and free of a parser dependency, and also what limits it: it reasons
about the shape of a line, not the structure of a program. Adding an abstract
syntax tree per language would let rules express facts such as "this call's argument
is a string built by concatenation" or "this loop body opens a file without closing
it", which no regular expression can state reliably. The cost is a parser per
language, a per-language rule set, and a much larger test surface — a rule that
fires on Python must be proven not to fire on Java.

## 9.3 Incremental review on push

Today a synchronised pull request is reviewed as a whole diff. On a long-lived
branch that means re-reporting findings the author has already seen and dismissed.
An incremental mode would keep the last reviewed commit per pull request, review
only the hunks that changed since then, and carry forward the prior verdicts. The
idempotency marker already hashes the findings rather than the commit, so the
suppression logic exists; what is missing is the state that records the reviewed
revision, which brings the next item with it.

## 9.4 GitHub App authentication instead of a personal token

The posting path uses a personal access token supplied in the environment. A GitHub
App installation would give per-repository scoped tokens, automatic rotation, a
verifiable identity in the pull-request timeline, and — most usefully — a way to
distinguish the bot's own comments from a human's. That last point closes the known
weakness of the public idempotency marker: with an authenticated app identity, the
listing can filter on the comment author, so a third party can no longer suppress a
review by pasting a marker.

## 9.5 SARIF export

The findings model is already a five-field record with a severity ladder and a rule
identifier, which maps closely onto the Static Analysis Results Interchange Format.
Emitting SARIF would let the same review be uploaded to a code-scanning dashboard
or consumed by an editor's diagnostics pane, and would let results be compared with
other analysers on a common vocabulary. It is a serialisation change plus a rule
metadata table, not a change to the engine.

## 9.6 A web interface

The API is complete enough to support one: every endpoint returns the review, the
rendered comment and the statistics in a single response. A small server-rendered
page would let a reviewer paste a diff, choose a severity threshold and read the
findings without a terminal, which matters for demonstrating the project to an
audience that does not use a command line. It would also need the authentication
and rate limiting that the API does not currently have, because a browser-reachable
endpoint that runs a model is an endpoint someone else can spend money on.

## 9.7 Rate limiting and audit retention

The service keeps a record of each review in `reviews` and `findings`, but it holds no record of who asked for what when authentication is disabled, and nothing
stops a caller from submitting a thousand diffs. Two additions would make it
deployable. A token-bucket limiter per client would bound the cost of the model
layer and the CPU cost of the rule engine. An append-only audit record — one row per
review, carrying the request identifier, the provider actually used, the finding
count and the duration — would answer the operational questions the current build
can only answer by reading logs. The schema for both is specified in section viii of
the synopsis and Appendix B; neither is implemented in the shipped service.

## 9.8 A fine-tuned local model

The local path currently prompts a general instruction-tuned coder model and relies
on guards to repair its output. A model fine-tuned on this project's own finding
format would need fewer guards, would produce the five fields more reliably, and
would be smaller — a quantised model in the low single-digit gigabytes can run on a
laptop CPU. The blocker is the same as section 9.1: fine-tuning needs labelled data,
and the labels do not yet exist. Any published figure for such a model would also
need the weights hash recorded alongside it, so that the number and the artefact
that produced it can be tied together.

## 9.9 Packaging as a continuous-integration action

The final step in making the tool part of a workflow rather than a thing one runs
is a packaged action: a container image with a pinned interpreter, a composite
action definition that passes the pull-request number and the token through, and a
documented exit-code contract so that a pipeline can gate a merge on the verdict.
The image recipe exists and the exit codes are already contractual; what is missing
is that the image has never been built in this development environment, so the
packaging has not been tested where it will actually run.

## 9.10 Ordering

Taken together, the list has a clear dependency order. Labelling the dataset
(section 9.1) unblocks measurement, and measurement is what makes the model work
(section 9.8) defensible. App authentication (9.4) unblocks the marker weakness.
Rate limiting and audit retention (9.7) unblock any deployment that is reachable by
anyone other than its author. The remaining items — syntax-tree rules, incremental
review, SARIF, a web interface and CI packaging — are independent of one another
and can be taken in whatever order the next maintainer's priorities dictate.
