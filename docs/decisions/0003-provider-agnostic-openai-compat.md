# 0003 — One OpenAI-compatible adapter, two configs

## Status

Accepted — 2026-11-14

## Context

The project has to work with a paid hosted model (Sarvam, `https://api.sarvam.ai/v1`)
and with a model running on the presenter's laptop (LM Studio,
`http://localhost:1234/v1`). Both speak the OpenAI chat-completions protocol. The
temptation is to write two adapters, or to write one against the vendor SDK, because
each feels like it deserves its own code path.

The guards around a model call are the expensive part, not the transport: JSON-mode
request, one repair retry, hallucinated-file dropping, line snapping, key scrubbing,
severity sorting, and the rule that no raw SDK exception escapes. Duplicating those
per provider means two places to fix every guard and two places to drift.

## Decision

There is exactly one adapter, `app/openai_compat_provider.py`, and the difference
between providers is a dataclass. `OpenAICompatConfig`
(`app/openai_compat_provider.py:120`) holds `base_url`, `api_key`, `model`,
`provider_name` and `timeout`; nothing else varies. The module docstring states the
rule: "there is exactly one transport here and no provider-specific live path: the
difference between them is an `OpenAICompatConfig` and nothing else"
(`app/openai_compat_provider.py:1`).

- `app/engine.py` is the only place that builds configs:
  `config_for_sarvam` (`app/engine.py:111`) with the base URL as data
  (`app/engine.py:73`), and `config_for_local` (`app/engine.py:133`) with the longer
  local timeout because a model on a laptop is slow.
- `provider_name` is carried through to `ProviderOutcome.provider`, so every response
  says which endpoint really ran; live findings also carry `(source: local)` or
  `(source: sarvam)` in their issue text.
- Error text is relabelled per run: `_present` rewrites the word "sarvam" to this
  run's label, because the reused Phase 4 guards word their errors for Sarvam.
- The `openai` SDK is imported inside `_build_client`, so the module imports without
  the SDK installed.

## Consequences

Positive: one set of guards, one repair-retry budget, one key-scrubbing routine, one
mock path. A fix to the hallucination guard helps both providers at once. Adding a
third OpenAI-compatible endpoint is a config function and a test, not an adapter.

Negative: an endpoint that is not OpenAI-compatible cannot be used at all — no native
Anthropic messages API, no vendor-specific tool calling, no SDK feature the protocol
does not expose. If Sarvam or LM Studio diverge from the protocol, the shared
`BadRequestError` repair path is the only adaptation available, and a provider that
needs different prompt framing gets it by string surgery rather than a clean hook.
That is a real ceiling, accepted because the demo's job is two endpoints that both
speak the protocol today.

## Alternatives considered

**Two adapters, one per provider.** The stated design cost is duplicate guards and
drift: two places to remember the "no key in a log record" rule, and the second one
gets it wrong first. Rejected.

**The `sarvamai` SDK as the only live path.** It would lock the demo to a paid key
and to a network connection, which is precisely the situation the local provider
exists to avoid — the presenter would have no offline-capable live model. It also
pulls a second SDK into a codebase that already has `openai` as an optional import.
Rejected, though `sarvamai` remains a supported dependency of the older
`app/sarvam_provider.py` path.

**A generic "provider" protocol with a class per backend.** More layers than two
configs justify at this size; the abstraction would be invented before the second
divergent requirement existed. Rejected.
