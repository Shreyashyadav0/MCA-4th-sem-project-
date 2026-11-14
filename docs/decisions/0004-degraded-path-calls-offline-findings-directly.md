# 0004 — The degraded path calls the rule engine directly, not through `review_with_fallback`

## Status

Accepted — 2026-11-14

## Context

When the OpenAI-compatible adapter cannot complete a live review, it must produce the
rule engine's findings. The codebase holds two functions that do that:
`app.sarvam_provider.review_with_fallback(bundle, settings, force_offline=True)`
(`app/sarvam_provider.py:912`, `:916`), and
`app.mock_provider.offline_diff_findings` (`app/mock_provider.py:59`), which
`review_with_fallback` itself calls.

Delegating to `review_with_fallback(force_offline=True)` looks like the obvious way to
keep one mock implementation. It has two defects on a local run. First, it logs its
own WARNING on the `reviewer.sarvam` logger with text naming *sarvam*
(`app/sarvam_provider.py:957`, `:971`) — on a run whose provider is LM Studio that
message is simply false. Second, both that function and the adapter would log, so one
degrade produces two warnings.

The obvious fix — silence the delegated logger around the call — is worse. `setLevel`
is process-global; in a webhook server two concurrent reviews would race, and one
request muting `reviewer.sarvam` would mute the other request's legitimate warnings.

## Decision

`app/openai_compat_provider._mock_outcome` (`app/openai_compat_provider.py:598`)
builds the degraded outcome itself, calling `offline_diff_findings` and
`review_diff` directly (imported as `_offline_findings` / `_rule_review` at
`app/openai_compat_provider.py:45`), and logs the single honest WARNING with this
run's provider label (`app/openai_compat_provider.py:630`). Its docstring records why
(`app/openai_compat_provider.py:609`):

> The local rule engine is invoked directly rather than through
> `app.sarvam_provider.review_with_fallback`: that path logs its own warning naming
> *sarvam*, which would be a lie on a local run and would also mean two warnings for
> one event. Delegating through it and muting its logger is worse — `setLevel` is
> process-global and would race between concurrent webhook requests.
> `offline_diff_findings` is the same function that module calls, so there is still
> exactly one mock implementation.

What that buys, concretely: the same function produces the findings in both paths, so
there is no second mock implementation to drift; the warning names the provider that
actually failed; `tests/test_openai_compat_provider.py:667` asserts
`warning_records(caplog, "reviewer.sarvam") == []`, locking the "no lie, no double
log" property.

## Consequences

Positive: honest log text and exactly one WARNING per degrade, verified by test. No
process-global logger mutation anywhere in `app/` (a grep for `setLevel` finds only
the comment explaining why it is not used). Concurrency-safe by construction.

Negative, and this is the important one: it **deviates from the Phase 5.5 written
contract**, which said the adapter delegates the degraded path to
`review_with_fallback(force_offline=True)`. That deviation is deliberate, and it must
stay documented or a future reader will "fix" it back — reintroduce the delegation,
see two warnings and a sarvam-named message on a local run, then reach for
`setLevel` and reintroduce the race. The residue from the earlier design was removed at
the final audit: the module docstring now states the direct call and its reason, and the
unused `_DELEGATED_MOCK_LOGGER` constant is gone. The code, not the prose, is the
contract here.

## Alternatives considered

**Delegate and mute the logger.** Rejected: process-global state, races between
concurrent webhook requests, and it silences real warnings from other requests.

**Delegate and accept two warnings.** Rejected: duplicate log lines for one event
train operators to ignore the log, and the sarvam-named one is actively misleading on
a local run.

**Keep delegating and change `review_with_fallback`'s message to be provider-neutral.**
Attractive, but it couples the Phase 4 module's wording to the Phase 5.5 adapter's
needs and still leaves two log sites for one event.
