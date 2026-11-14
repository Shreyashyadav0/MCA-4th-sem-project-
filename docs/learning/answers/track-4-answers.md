# Track 4 — app/mock_provider.py + app/config.py — answer key

Answers to the five questions at the end of `track-4-offline-and-config.md`.
Each answer names the file and line you can check it against.

1. **Why `sarvam_api_key` is `str | None` and `lmstudio_api_key` defaults to `"lm-studio"`.**
   Because a placeholder key is only safe where the endpoint ignores it. LM Studio accepts
   any bearer token, so `"lm-studio"` is a working default that keeps the local path
   zero-config. Sarvam rejects anything that is not a real key, so a non-empty default
   would make `has_sarvam_key` true on every machine, the selector would choose `sarvam`
   everywhere, and every run would spend a network round trip failing with 401/403 before
   degrading. Absence has to be representable for the provider that actually authenticates.
   Check: `app/config.py:30` (`sarvam_api_key`) and `app/config.py:59` (`lmstudio_api_key`).

2. **Who overrides `resolve_mode`, and why it is not a bug.**
   `app/engine.py` does, in `select_provider`, inside the `auto` branch:
   `if settings.review_mode == "mock": ...`. `resolve_mode` is the Phase-1 helper and is
   kept for its own tests; the selector is the single decision point every surface calls.
   It honours `REVIEW_MODE=mock` for `auto` and lets an explicit
   `--provider` / `?provider=` override it, because a per-request choice should beat an
   environment default. Check: `app/engine.py:227-230`.

3. **Where the category filter runs, and why not over the returned findings.**
   `offline_diff_findings` has no `categories` parameter by design; callers that need a
   category filter call `app.rules.review_diff(bundle, min_severity=..., categories=...)`
   directly. It cannot run afterwards because `Finding` has no structured rule-id field —
   the id is appended to the issue prose as `(rule: unsafe/sql-injection)`, so filtering
   over output would mean parsing English.
   Check: `app/mock_provider.py:59` (no `categories`) and `app/openai_compat_provider.py:639`.

4. **Two behaviours that update when a rule is added, and one artefact that would go stale.**
   `ENGINE_NOTE` interpolates `len(RULES)`, so adding a rule automatically changes (a) the
   note line in every CLI report and API response, and (b) `RULE_COUNT`, which is what
   `GET /health` reports as `rules`. If the count were hardcoded, the README's "63 rules"
   and the deck's "63 deterministic rules" would go stale silently.
   Check: `app/mock_provider.py:23`, `app/rules.py` (`RULE_COUNT`), `app/main.py` `/health`.

5. **What would catch a change to the note's wording, and what would not.**
   Nothing in the test suite pins `ENGINE_NOTE`'s text: no test imports
   `app/mock_provider` or asserts the note string. What *is* pinned is the mock *reason*
   strings (e.g. `tests/test_sarvam_provider.py` asserts `"...; local rule engine used"`),
   so a change to the note would pass CI and surface only as a doc mismatch — which is why
   this limitation is written down here rather than assumed away.
