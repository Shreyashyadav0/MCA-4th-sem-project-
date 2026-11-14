# Handoff — what is real, what is simulated, what is deferred

This file is the honesty ledger. If any other document disagrees with it, this one is right.

## Real — executed in this environment, output captured

| What | Evidence |
|---|---|
| The 63-rule engine on real diffs | `python reviewer.py samples/sample.diff` → 4 findings, verdict `block` |
| Diff parsing and anchoring | 638 tests, including anchored/file_only/unanchored cases |
| The offline mock path end to end | CLI, API, webhook, all with no credentials |
| The FastAPI surface | every endpoint exercised in-process through `TestClient`, plus a threaded `uvicorn` server on 127.0.0.1 for the demo checks |
| The webhook posting state machine | fake `httpx` client at the `_build_github_client` seam: happy path, duplicate skip, 422 demotion, 429 retry, 401/403/500, transport error |
| One real network rejection | `SARVAM_API_KEY=fake` reached `api.sarvam.ai` and returned a real 403, which degraded correctly |
| The OpenAI-compatible transport | the real `openai` SDK drove a stub OpenAI-compatible server over HTTP: `mode=live`, `provider=local`, `response_format` sent, hallucinated file dropped |
| The benchmark harness | `python -m benchmarks.eval --modes rules --dataset benchmarks/golden` writes metrics.csv, summary.json, summary.md, chart.png |
| Zero-network guarantee | `python scripts/verify_offline.py` → 637 passed, 1 skipped with outbound connections blocked |

## Simulated — the code path is real, the counterpart is a fake

| What | How it was exercised | What is NOT proven |
|---|---|---|
| A real local model | a stub OpenAI-compatible server returning fixed JSON | that Qwen2.5-Coder-7B actually produces usable findings, or how long it takes |
| A real Sarvam review | the SDK seam plus a real 403 | that any Sarvam call ever succeeded |
| Real GitHub posting | a fake `httpx` client | that GitHub accepts these comment positions, or that a real 422 looks like the simulated one |
| The live LM Studio smoke test | shipped as `@pytest.mark.skipif(not os.getenv("LMSTUDIO_BASE_URL"))` | it has never run |

## Deferred — needs a human, cannot be produced by an agent

| # | Task | Why deferred | Exact command | Done when |
|---|---|---|---|---|
| 1 | Label the evaluation dataset | Labels must be human-authored (ADR 0006); the shipped samples are format examples | `python -m benchmarks.label_helper --dataset benchmarks/golden`, then add each id to `evaluation_samples` in `benchmarks/golden/manifest.json` | `manifest.json` has a non-empty `evaluation_samples` and the benchmark note stops saying every sample is a format example |
| 2 | Run the benchmark with a local model | No LM Studio endpoint existed here; `local`/`merged` skip cleanly | `export LMSTUDIO_BASE_URL=http://localhost:1234/v1`, `export LMSTUDIO_MODEL='<id from /v1/models>'`, `python -m benchmarks.eval --modes rules local merged --dataset benchmarks/golden --out benchmarks/out` | `summary.md` shows non-skipped `local` and `merged` rows |
| 3 | Report prose | Every result sentence depends on tasks 1-2 | work `docs/report/SKELETON.md`, then `grep -rn "FILL AFTER BENCHMARK" docs/report` | the grep returns nothing |
| 4 | Deck placeholders | Mirrors the report; notes need the same numbers | edit slide 9 of `docs/presentation/project_overview.pptx` (or `docs/presentation/build_deck.py` and rebuild), then `grep -rn "FILL AFTER BENCHMARK" docs/report docs/presentation` | the grep returns nothing |
| 5 | Sarvam key (optional) | Nothing in the suite needs one and no code path assumes one | `export SARVAM_API_KEY=<key>`, `python reviewer.py samples/sample.diff` | `mode : live`, `provider : sarvam` |
| 6 | Record the GGUF hash | A hash proves which weights produced any future local-mode number | `sha256sum <model>.gguf` (macOS: `shasum -a 256`), then add a row to `docs/MODEL_HASHES.md` | the table has a hash, a quant, a date and a source URL |

## Known limitations, stated rather than hidden

- The idempotency marker is a public HTML comment: anyone who can comment on the PR can
  suppress a review by pasting one. Fixing it needs author filtering or an HMAC marker.
- Posting requires an authenticated delivery: with `GITHUB_TOKEN` set and
  `GITHUB_WEBHOOK_SECRET` unset, `/webhook` reviews but refuses to post unless
  `WEBHOOK_ALLOW_UNSIGNED=1` is set explicitly (a local-demo escape hatch, not a default).
- Matching is greedy, not optimal (ADR 0007).
- `app/openai_compat_provider._mock_outcome` calls `offline_diff_findings` directly rather
  than delegating to `sarvam_provider.review_with_fallback` — deliberate, see ADR 0004.
  It looks like a bug and must not be "fixed" back.
- Python is pinned to 3.12.13, which is in security support until October 2028 in October 2026. Move to 3.12+
  before deploying anywhere real.
- The Dockerfile has never been built (no daemon in this environment); its compose file
  parses and its runtime steps were simulated from the lock.
