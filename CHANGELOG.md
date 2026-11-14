# Changelog

All phases were built in one continuous session on 2026-11-13 and 2026-11-14. Test counts
are the collected cases at the end of each phase, measured by `pytest --collect-only`.

## Phase 1 — scaffold, config boundary, finding contract, CLI (2026-11-13)
Folder layout, `Settings` (credentials read once, absence is data), Pydantic v2 `Finding`
with the five-field contract, `reviewer.py` CLI with mock fallback. 14 tests.

## Phase 2 — diff parsing and anchoring (2026-11-13)
`app/parser.py`: unified-diff state machine driven by hunk counters, `FileDiff`/`Hunk`
models, `anchor_findings` producing anchored / file_only / unanchored. 11 tests.

## Phase 3 — local rule engine and FastAPI surface (2026-11-13)
`app/rules.py` grew to 63 deterministic OWASP-mapped rules across 10 categories, with
`# noqa` suppression, a ReDoS bound and a per-rule registry. `app/main.py`: `/review`,
`/test-review`, `/webhook`, `/rules`, `/health`. 234 tests.

## Phase 4 — Sarvam LLM layer with a guaranteed local fallback (2026-11-13)
`app/sarvam_provider.py`: `sarvamai` SDK adapter, strict JSON parsing, hallucination and
line guards, one repair-free call, degradation to the rule engine. Never exercised with a
real key. 87 tests.

## Phase 5 — GitHub PR comment posting (2026-11-13)
`app/github_client.py`: idempotency marker, inline cap, 422 demotion, 429 retry, typed
errors; `--post-to-pr`; webhook posting that always answers 200 to GitHub. 113 tests
(54 client, 27 webhook, 9 CLI, 23 hardening).

## Phase 5.5 — one OpenAI-compatible adapter, two configs (2026-11-14)
`app/openai_compat_provider.py` (one transport for LM Studio and Sarvam) and
`app/engine.py` (the only provider selector: sarvam > local > mock). 51 tests.

## Phase 5b — benchmark harness (2026-11-14)
`benchmarks/`: loader, matching (greedy one-to-one, documented as a limitation), metrics
(TP/FP/FN, per-category, nearest-rank latency), runner (rules / local / merged), report
(CSV, JSON, MD, chart), `eval` entry point, `collect_candidates` and `label_helper`. Two
FORMAT-EXAMPLE samples only; no evaluation dataset exists. 73 tests.

## Phase 6 — reproducibility, documentation, curriculum (2026-11-14)
Pinned requirements plus `requirements.lock`, `.python-version` 3.12.13, Dockerfile and
compose, CI, `make verify`, the docs pack (README, ARCHITECTURE, DEMO, TESTING, RESUME,
ADRs, report and deck skeletons), the 7-track learning curriculum with rebuild scaffold and
`learning_progress.py`, and the PPTX + PDF. 582 tests passing, 1 skipped.

**Totals: 598 collected, 582 passing, 1 skipped (a live-LM-Studio test that must not run in
CI). 30 sub-agents across six waves, each wave gated before the next.**
