# 0001 — Strict Pydantic v2 models at every boundary

## Status

Accepted — 2026-11-14

## Context

The reviewer has three boundaries where data of unknown quality arrives: an LLM's
JSON reply, an HTTP request body, and a decoded diff. The first is the dangerous one.
A model asked for a JSON array will happily return `{"file": ..., "line": ..., "confidence": 0.8}`,
or a `category` key, or `"line": "42-45"` where a number was expected. If that text
is turned into a `dict` and passed around, a stray key is silently ignored at the
point it arrives and surfaces much later as a `KeyError` inside comment rendering,
or never surfaces at all because nobody reads the extra field.

The project already needed a wire shape that the model could satisfy and a domain
shape the rest of the code could trust. `app/models.py` states the intent in its
module docstring: "A stray key from a future LLM response fails at the boundary
instead of leaking into a PR comment" (`app/models.py:6`).

## Decision

Every structured value in the system is a Pydantic v2 model, and every model that
faces untrusted input forbids unknown keys.

- `Finding` is `ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)`
  with exactly five fields — `file`, `line`, `severity`, `issue`, `suggested_fix`
  (`app/models.py:64`). Immutability matters because findings are passed into
  renderers, matchers and posting code; nothing may rewrite one in place.
- `AnchoredFinding` wraps a `Finding` rather than extending it (`app/models.py:104`),
  so anchoring metadata can never widen the finding contract.
- `ReviewResult.verdict` is a `@computed_field` (`app/models.py:171`) derived from
  `verdict_for` (`app/models.py:134`). It is computed, not stored: a stored verdict
  can disagree with the findings that produced it.
- `LLMFinding` (`app/sarvam_provider.py:72`) is the wire model, also `extra="forbid"`
  (`app/sarvam_provider.py:79`), with `line: str | int` because models answer `42`
  and `"42"` interchangeably. `parse_findings_payload`
  (`app/sarvam_provider.py:725`) converts it to `Finding` only after the hallucination
  and line guards.
- Validation failure is data, not a crash: `_validate_items`
  (`app/sarvam_provider.py:623`) validates the whole list, then item by item, and
  raises `SarvamUnavailableError` only when nothing survived.

## Consequences

Positive: a malformed payload is rejected where it enters, and the rejection is
typed (`ValidationError`) rather than a scattered `KeyError`. Field constraints are
executable documentation — `line` must match `^\d+(?:-\d+)?$` and ascend, enforced
by a `field_validator`, so no downstream code re-checks it. The API's OpenAPI schema
and the CLI's JSON output are generated from the same models, so they cannot drift.

Negative: there is real boilerplate — five models, several validators, and a
conversion step between wire and domain shape that a plain `dict` would not need.
Validation errors also have to be handled everywhere: the live path turns a
`ValidationError` into a repair retry and then into a degrade, the loader turns one
into a `DatasetError`. That is more code than trusting the input, and it is the price
of not trusting the input.

## Alternatives considered

**Plain dictionaries with key checks.** Cheap to write and impossible to keep
honest: every consumer would need its own `if "severity" not in finding` guard, and
a stray key would be invisible by construction. Rejected.

**`dataclasses` with manual `__post_init__` validation.** Gives immutability and
typing but no coercion, no JSON schema, no error aggregation; the wire layer would
still need a separate parser with its own rules. Rejected as duplicate machinery.

**Pydantic with `extra="ignore"`.** Tolerant, and it hides exactly the failure this
project cares about: a model inventing a field that a future version is expected to
honour. Rejected.
