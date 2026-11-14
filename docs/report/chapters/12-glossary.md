# 12 Glossary

Terms are defined as they are used in this project, not in their most general sense.
Where a term has a wider meaning elsewhere, the definition below states the narrower
one that the code and this report rely on.

**Anchoring.** Placing a finding against the changed lines of a parsed diff and
recording the result as `anchored`, `file_only` or `unanchored`, so that a consumer
knows whether the finding can be attached to a line comment at all.

 **Anchor status.** The field on an anchored finding that carries the outcome of
anchoring; it lives outside the five-field finding contract because it is review
metadata rather than a claim about the code.

**ADR (Architecture Decision Record).** A short numbered document under
`docs/decisions/` that records one decision, the alternatives rejected and the
consequence accepted; seven exist, from the strict-model choice to the greedy
matching rule.

**AST (abstract syntax tree).** The structural parse of a source file that a rule
would need in order to reason about program shape rather than line text; this
engine deliberately does not build one, which is the limitation listed in section
9.2.

 **Chunk.** One request-sized portion of a diff; the engine batches hunks into
chunks so that a large pull request does not exceed a model's context window.

**Degradation.** The transition from a live model review to the deterministic rule
engine when the model is unreachable, rejects the credential or answers unusably;
it is announced by exactly one warning and never by an exception.

**Deterministic engine.** The 63-rule reviewer that produces the same findings in
the same order for the same input, with no network access and no model; it is the
base layer and the fallback.

**DFD (data flow diagram).** A diagram showing processes, data stores, external
entities and the flows between them, drawn at levels 0, 1 and 2 in the synopsis to
show the review pipeline at increasing detail.

 **Diff bundle.** The parsed representation of one patch: a list of file diffs, each
carrying its hunks, its change kind and its added-line spans.

**ER diagram.** An entity-relationship diagram showing entities, their attributes
and the cardinality of the relationships between them; the persistence design in
Appendix B is presented that way.

**Fallback chain.** The ordered sequence of decisions that ends in a review
regardless of environment: no provider selected, configuration unusable, live call
failed, repair retry, double parse failure, success. Its budget is at most two model
calls per review.

**False negative (FN).** An expected finding that no mode reported; in the harness,
an expected finding left unmatched after one-to-one matching.

**False positive (FP).** A reported finding that no label expected; in the harness,
an actual finding left unmatched.

**Finding.** The five-field record — file, line, severity, issue, suggested fix —
that is the system's entire output contract; a sixth field is a validation error
rather than an extension.

**Frozen contract.** An interface that tests patch and front ends call, declared
unchangeable without a deliberate version bump; the finding model, the provider
outcome and the benchmark dataclasses are frozen.

**Gantt chart.** A calendar bar chart of project tasks against elapsed time, used in
the synopsis to show phase duration and overlap.

**Greedy one-to-one matching.** The benchmark's pairing rule: take the largest
overlap first, consume both sides, repeat; deterministic, and documented as a
limitation because an optimal assignment could score higher.

**HMAC (hash-based message authentication code).** The construction used to verify
that a webhook delivery came from GitHub, computed over the raw request body with a
shared secret and compared in constant time.

**Hunk.** One contiguous block of changed lines in a unified diff, introduced by a
header such as `@@ -1,5 +1,8 @@` that gives the old and new line ranges.

**Idempotency marker.** The HTML comment `<!-- ai-code-reviewer:<16 hex> -->` that
ends every generated comment body and lets a re-run recognise its own earlier
output and skip the post.

**Live mode.** A review produced by a language model, labelled `mode: live` with the
provider and model that answered; the label is set only after a successful parse.

**Mock mode.** A review produced by the deterministic engine, labelled
`mode: mock`; it is the default state and needs no configuration.

**Nearest-rank latency.** The percentile definition used for p50 and p95: sort the
recorded durations and take the value at rank ⌈p/100 × n⌉, with no interpolation,
so the figure is reproducible from the samples.

**OWASP Top Ten (2021).** The ten-category taxonomy of web application security
risks that every rule in the registry is mapped onto, recorded per rule as an
`A0n:2021` identifier.

**PAT (personal access token).** A GitHub credential with explicit scopes, supplied
to this system through the environment; the app-authentication alternative is
section 9.4.

**PERT (program evaluation and review technique).** The network of tasks with
optimistic, most-likely and pessimistic durations used in the synopsis to derive an
expected schedule and identify the critical path.

**Precedence (provider).** The locked rule `sarvam > local > mock` that decides
which reviewer runs when more than one is configured, overridable per run by an
explicit provider request or by the offline flag.

 **Provider.** One of the three things that can review a diff: the hosted model, a
self-hosted OpenAI-compatible model, or the local rule engine.

**Provider outcome.** The record returned by the review layer carrying the findings
together with the mode, provider, model and reason labels; it is what stops a
degraded run from looking like a live one.

**ReDoS (regular-expression denial of service).** A pathological input that makes a
backtracking pattern run for a time disproportionate to its length; the engine caps
the input length and the pattern shape to bound it.

**Repair retry.** The single second model call made after an unparseable answer, with
the error appended to the prompt and structured-output mode dropped.

**Rule id.** The stable identifier of one check, of the form `category/name`, quoted
in every finding and exposed through the rules endpoint.

**SARIF (static analysis results interchange format).** A JSON schema for exchanging
analysis results between tools; a proposed export format in section 9.5, not
implemented here.

**Severity.** One of four values — LOW, MEDIUM, HIGH, CRITICAL — that ranks a
finding, orders the report and drives the gate verdict.

**SSE (server-sent events).** The streaming response format a chat-completions
endpoint uses when asked to stream tokens; this system never streams, because it
parses a complete JSON array of findings.

**Suppression.** The `# noqa` annotation on a changed line that stops a rule firing
there, allowing a reviewed exception to be recorded in the code itself.

**3NF (third normal form).** The normalisation target for the persistence design: no
repeating groups, no partial dependency on part of a key, and no transitive
dependency between non-key attributes.

 **True negative.** A clean sample that produced no findings; measured through
samples whose expected list is deliberately empty.

**Unified diff.** The line-oriented patch format produced by `git diff`, with
`---`/`+++` file headers, `@@` hunk headers and one-character change markers, which
is the system's only structured input.

**Verdict.** The gate decision derived from the severity mix — approve, approve with
comments, or block — computed by rule rather than by opinion.
