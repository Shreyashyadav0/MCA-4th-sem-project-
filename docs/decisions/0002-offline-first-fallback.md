# 0002 — Every entry point degrades to the 63-rule engine

## Status

Accepted — 2026-11-14

## Context

The tool is demonstrated live, on a laptop, in front of people, sometimes without
network access and sometimes with a key that expired an hour ago. It is also run by
a webhook that must answer GitHub within a timeout: a 500 because a credential is
missing costs the whole review and shows up as a failed check on someone's PR.

So the question is not "what happens when the LLM fails" but "what is the normal
state when there is no LLM". The project answers that by treating a missing key as
configuration data rather than an error. `app/config.py:3` states it: "A missing key
is data — the reviewer switches mode — never an exception."

## Decision

Every entry point — CLI, HTTP API, webhook, benchmark runner — funnels into
`app.engine.review` (`app/engine.py`), which selects a provider and, when no live
provider is usable, runs the deterministic local rule engine: 63 rules, no network,
no key (`app/mock_provider.py:23`).

- Precedence is locked: `sarvam` > `local` > `mock`, decided in `select_provider`
  (`app/engine.py:198`). The final `mock` reason names the missing variables
  (`app/engine.py:245`).
- A degrade logs exactly one WARNING and never raises. `app/cli.py:17`: "mode
  selection degrades, logs one WARNING, and still exits 0." The exit code stays
  `0` (`app/cli.py:50`); only bad input (1) and usage errors (2) are non-zero.
- The reason is never dropped: it travels in `ReviewResult.notes`
  (`app/models.py:152`), in the CLI's `mock mode: <reason>` line, and in the API
  response's `provider` / `model` fields (`app/main.py:539`).
- The warning is owned by one place. `_log_mode` (`app/cli.py:203`) deliberately logs
  at DEBUG only: "the provider owns the single WARNING."

## Consequences

Positive: a demo cannot die on stage, and a webhook cannot 500 because of an
environment variable. The degraded output is still real review output — the same
rule engine that a fully offline user gets — not an empty stub, so the fallback is
useful rather than merely survivable. Behaviour is identical across surfaces because
the decision lives in one function.

Negative, honestly: a silent degrade can hide a misconfiguration. Someone who meant
to run the hosted model, typed the key into the wrong variable, and got a plausible
review may never notice they were on the rule engine. This is mitigated, not
eliminated: the reason string names the missing variable in `notes`, `mode` and
`provider` are in every response, and the single WARNING is on stderr. But a user who
pipes JSON and reads only the findings will not see any of it. That residual risk is
accepted because the alternative — failing hard — is worse for both the demo and the
webhook.

## Alternatives considered

**Fail fast when no key is configured.** Correct for a CI linter, wrong here: it
turns a missing environment variable into a failed review, and a webhook failure into
a red check on an unrelated PR. Rejected.

**Emit an empty review when degraded.** Cheaper, but it makes "no findings" and
"could not look" indistinguishable, which is the single worst property a reviewer can
have. Rejected.

**Retry the live provider indefinitely before degrading.** Multiplies latency against
a webhook deadline and still ends in the same place. Rejected.
