# Track 5 — app/sarvam_provider.py + app/openai_compat_provider.py — answer key

Answers to the five questions at the end of `track-5-providers.md`.
Each answer names the file and line you can check it against.

1. **How the repair call drops `response_format` without a fourth parameter.**
   A module-level `ContextVar[bool]` (`_JSON_MODE`) is set to `False` by the
   `_without_json_mode()` context manager for the duration of the repair call, and
   `_call_model` reads it when it builds the request kwargs. A fourth parameter was
   rejected because `_call_model(client, prompt, config)` is the frozen, patchable seam
   the tests substitute with a three-argument double; changing its arity would break every
   fake client and the published interface.
   Check: `app/openai_compat_provider.py:121` (`_JSON_MODE`), `:452` (`_without_json_mode`),
   `:425` (`if _JSON_MODE.get()`).

2. **Where repairable and unrepairable failures are separated.**
   In the two frozensets `_UNREPAIRABLE_ERROR_NAMES` and `_REPAIRABLE_ERROR_NAMES`, applied
   in `_translate_call_error`, which `review_diff_live` calls from its `except` block.
   If `APIConnectionError` were treated as repairable, the repair call would hit the same
   dead socket, so a single unreachable endpoint would cost two timeouts per sample
   (up to `2 × LMSTUDIO_TIMEOUT`), and the log would say "failed twice" instead of naming
   the connection failure — hiding the real cause and doubling the wait for no chance of
   success.
   Check: `app/openai_compat_provider.py:99`, `:112`, `:337`.

3. **Why two prose answers stay live but one timeout degrades.**
   From the caller's point of view the two outcomes describe different facts. Two prose
   answers mean the endpoint is reachable and the model replied, but its output was
   unusable after one repair: there is nothing more to retry, and inventing rule findings
   would mislabel their source, so the run reports `mode="live"` with zero findings and one
   WARNING. A timeout means no answer at all, so a review still has to happen — the rule
   engine runs and the outcome says `mode="mock"` with a reason. The first case is decided
   by the `return []` after `_warn_after_double_failure(...)` in `review_diff_live`.
   Check: `app/openai_compat_provider.py:557-571`.

4. **The two defects of the delegation, why `setLevel` is unacceptable, and the locking test.**
   (a) `sarvam_provider.review_with_fallback(force_offline=True)` logs a WARNING that names
   *sarvam* — untrue on a local run; (b) it would be a second WARNING for one event, since
   the adapter logs its own. Silencing it with `setLevel` is unacceptable because logger
   levels are process-global: two concurrent webhook requests would race, one could
   suppress the other's warning or leave the level raised. The decision is locked by
   `tests/test_openai_compat_provider.py::test_double_failure_logs_exactly_one_warning`,
   which asserts exactly one record and `warning_records(caplog, "reviewer.sarvam") == []`.
   See `docs/decisions/0004`.

5. **What the adapter imports, what still calls the SDK path, and what breaks first.**
   The adapter imports `LLMFinding`, `ProviderOutcome`, `SarvamUnavailableError`,
   `build_prompt` and `parse_findings_payload` — the guards, not the transport. The
   SDK-based `review_diff_live` / `review_with_fallback` in `app/sarvam_provider.py` is now
   called only by that module's own tests; `app/engine.py` routes every live review through
   the OpenAI-compatible adapter. If the module were deleted, the adapter would fail at
   import time (five names), so `app.engine`, `app.cli` and `app.main` would all fail to
   import, and `tests/test_sarvam_provider.py` (87 tests) would fail first in the suite.
   Check: `app/openai_compat_provider.py:46-55`, `app/engine.py:45`, `tests/test_sarvam_provider.py`.
