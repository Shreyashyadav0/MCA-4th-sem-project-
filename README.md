# AI Code Reviewer & GitHub PR Assistant

> **Status: FROZEN — 2026-11-14.** This repository is intentionally dormant for ~12 months
> while the author finishes MCA coursework. It runs fully offline with zero API keys.
> All 582 tests pass from a fresh extraction. To resume work, start at
> [`RESUME.md`](RESUME.md) — step 2 (`make verify`) is the only health check that matters.
> The benchmark dataset, report prose, and viva rehearsal are deliberately deferred.

An autonomous code reviewer and GitHub PR assistant, built as an MCA final project.
It combines **63 OWASP-mapped deterministic rules** with an **optional LLM review layer**
behind a provider-agnostic adapter — Sarvam-105B, LM Studio (or any OpenAI-compatible
endpoint), or an offline mock. Designed to run **fully offline** so the live viva
demonstration works without Wi-Fi, API keys, or billing risk.

---

## What this is

Three pieces, layered:

1. **A deterministic review engine** — 63 rules across 10 security/quality categories,
   mapped to OWASP, with line-local `# noqa` suppression and false-positive regression tests.
2. **A diff parser with anchoring** — parses unified diffs by hunk-header counters and
   classifies every finding as `anchored`, `file_only`, or `unanchored`, so findings map
   to real changed lines rather than guessed ones.
3. **A provider-agnostic LLM layer** — one adapter shape, three configurations (mock,
   local, sarvam). Every LLM path degrades cleanly to the rule engine if anything is
   missing. Nothing requires a key to run.

Surfaces: a CLI (`reviewer.py`) and a FastAPI backend (`app/main.py`) with `/review`,
`/test-review`, `/rules`, `/rules/{id}`, `/health`, and an HMAC-verified GitHub webhook.
A Phase 5 GitHub PR-comment client exists and is tested against a fake `httpx` client.

---

## Design principles

- **Offline-first.** The full suite runs with outbound connections blocked. No API key,
  network, or local model instance is required for any test or for the default CLI path.
- **Absence as data.** A missing key is a *configuration state*, not an error. The system
  reports `provider: "mock"` and a reason, and keeps working.
- **Strict schemas.** Pydantic v2 with `extra="forbid"` and `frozen=True` on every finding
  model. LLM output is coerced into the same schema the rule engine emits; malformed
  output is repaired once, then dropped — never allowed to crash a review.
- **Frozen interfaces.** Provider, engine, and GitHub client boundaries were frozen before
  parallel implementation. The ADRs in [`docs/decisions/`](docs/decisions/) record the
  trade-offs, including the one deviation from the original contract
  ([ADR-0004](docs/decisions/0004-degraded-path-calls-offline_diff_findings-directly.md)).

---

## Quick start

```bash
make verify                                          # full suite — expect 582 passed, 1 skipped
python reviewer.py samples/sample.diff               # offline mock review, exit 0
python -m uvicorn app.main:app --reload --port 8000  # HTTP surface
```

No API key, network access, or LM Studio instance is required for any of the above.

**Optional — live local LLM path.** Start LM Studio with an OpenAI-compatible server on
port 1234, then:

```bash
export LMSTUDIO_BASE_URL="http://localhost:1234/v1"
export LMSTUDIO_MODEL="qwen2.5-coder-7b-instruct"   # exact id from GET /v1/models
export LMSTUDIO_TIMEOUT="180"
python reviewer.py samples/sample.diff               # mode: live, provider: local
```

Full steps, expected output, and a third (unexercised) Sarvam variant are in
[`DEMO.md`](DEMO.md).

---

## Provider selection

`app/engine.py` is the single selector. Precedence is fixed and tested:

| Environment | Provider | Model | Notes |
|---|---|---|---|
| neither set | `mock` | — | 63-rule engine, no network |
| `LMSTUDIO_BASE_URL` | `local` | from `LMSTUDIO_MODEL` | OpenAI-compatible endpoint |
| `SARVAM_API_KEY` | `sarvam` | `sarvam-m` | `https://api.sarvam.ai/v1` |
| both set | `sarvam` | `sarvam-m` | Sarvam wins — documented, tested |

`--provider mock|local|sarvam` overrides on the CLI. API responses report the provider
honestly; local findings are never labelled as Sarvam.

---

## Where things are

| Path | What |
|---|---|
| `app/` | Production code — models, parser, 63 rules, engine selector, providers, CLI, FastAPI app, GitHub client |
| `tests/` | 582 tests, all offline |
| `benchmarks/` | Evaluation harness (matching, metrics, runner, reporting). **Dataset is not labeled yet** — see [`benchmarks/golden/README.md`](benchmarks/golden/README.md) |
| `docs/decisions/` | Seven ADRs. Read [0004](docs/decisions/0004-degraded-path-calls-offline_diff_findings-directly.md) first if you touch the fallback path |
| `docs/learning/` | Seven-track curriculum, answer keys, and [`PACE.md`](docs/learning/PACE.md) schedule |
| `rebuild/` | Empty scaffold — 59 verification tests skip cleanly until each module is rebuilt from memory |
| `docs/presentation/` | `project_overview.pptx` (14 slides) and `naive_to_pro_guide.pdf` (21 pages) |
| `RESUME.md` | Start here after a gap — seven-step recovery checklist |
| `HANDOFF.md` | Honest ledger: what is real, what is simulated, what is deferred |

---

## Testing

```bash
make verify                    # clean venv + locked install + full pytest
python -m pytest -q tests      # 582 passed, 1 skipped
python scripts/verify_offline.py   # same counts, network-blocked gate
```

- **582 passed, 1 skipped.** The skip is
  `test_live_smoke_review_against_a_real_endpoint`, guarded by `LMSTUDIO_BASE_URL`.
- A bare root-level `pytest` also collects the 59 rebuild placeholders and reports
  **582 passed, 60 skipped**. Both counts are correct; they measure different scopes.
- The suite is verified offline — `socket.create_connection` and `socket.getaddrinfo`
  are replaced with raisers during the offline gate.

---

## Benchmark

The harness is complete and produces four artifacts per run
(`metrics.csv`, `summary.json`, `summary.md`, `chart.png`) across three modes:
`rules`, `local`, `merged`.

**The evaluation set is empty.** No benchmark numbers exist in this repository. Two
format-example samples ship only to demonstrate the file format. Real numbers require
labeling 30–100 samples by hand:

```bash
python -m benchmarks.collect_candidates   # writes change.diff + empty expected.json
python -m benchmarks.label_helper         # interactive labeling, one sample at a time
python -m benchmarks.eval --modes rules,local,merged
```

Labels **must be human-authored** — not generated by the 63 rules, not generated by an
LLM. Auto-labeling would make the benchmark circular and invalid. This constraint is
recorded in [ADR-0006](docs/decisions/0006-labels-must-be-human-authored.md).

---

## Learning path

This repository ships a curriculum for the author to internalize the codebase over 3–4
months and be able to rebuild it module by module:

- [`docs/learning/README.md`](docs/learning/README.md) — the map: module dependency graph
  and the only correct reading order (seven tracks, strictly dependency-safe).
- [`docs/learning/PACE.md`](docs/learning/PACE.md) — week-by-week schedule, behind/ahead
  checkpoints at weeks 4, 8, 12, and a recovery plan (compress Tracks 3 and 4; never 1, 5, 6).
- `docs/learning/track-1…7` — per-track: what it does, why it exists, the key lines to
  read, the three hardest concepts, a rebuild exercise, and five self-test questions.
- `docs/learning/answers/` — answer keys, so the self-test is real.
- `rebuild/` — the verification mechanism. Each rebuild test imports **both**
  `rebuild.<module>` and `app.<module>` and asserts behavioral equivalence on shared
  inputs. Green means done; skip means not started yet.
- `python -m scripts.learning_progress status` — reads completion from pytest exit codes.

The hard rule: do not start Track N+1 until Track N's verification test is green.

---

## Documentation index

| Document | Purpose |
|---|---|
| [`RESUME.md`](RESUME.md) | Seven-step restart checklist after a gap |
| [`HANDOFF.md`](HANDOFF.md) | Real / simulated / deferred ledger |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System diagram, provider precedence, fallback chain |
| [`DEMO.md`](DEMO.md) | Viva demo script — three variants with expected output |
| [`TESTING.md`](TESTING.md) | Test layers, subsets, what the skip means |
| [`CHANGELOG.md`](CHANGELOG.md) | Phases 1–6 with test counts |
| `docs/decisions/` | Seven Architecture Decision Records |
| `docs/report/SKELETON.md` | MCA report structure with `[FILL AFTER BENCHMARK]` placeholders |
| `docs/report/DECK_SKELETON.md` | Slide-by-slide deck structure |
| `docs/presentation/` | Frozen PPTX and PDF artifacts |

---

## Honest limits

Stated plainly, because an examiner will ask and a future reader deserves the truth:

- **The local LLM path was exercised against a stub OpenAI-compatible server**, through
  the real `openai` SDK over real HTTP — never against a real Qwen2.5-Coder model. A real
  run is one command away (`DEMO.md` variant b), but it has not happened in this repo's
  recorded history.
- **Sarvam-105B has never been called with a real key.** The adapter is proven at the SDK
  seam, plus one genuine `403` from `api.sarvam.ai` with a fake key. The transport, error
  normalisation, and degradation are real; the model's answer is simulated.
- **GitHub posting is proven against a fake `httpx` client.** A fake token once reached
  `api.github.com` and returned a real `401` — that proves the failure path and nothing
  about a successful post.
- **No benchmark numbers exist.** The harness works; the dataset is empty.

The full ledger, including what was completed manually after partial agent returns, is in
[`HANDOFF.md`](HANDOFF.md).

---

## Freeze details

- Archive: `ai-code-reviewer-FROZEN-20261114.zip` — 137 files, 505 KB
- SHA-256: `f7530671cedd717ad38c0e04d65c7e61ab314fa73581549d9be77a306229115c`
- Git tag: `v1.0-frozen`
- Verified from a fresh extraction of the archive, with outbound connections blocked.

If this repository is ever re-cloned and `make verify` does not report **582 passed,
1 skipped**, do not start learning work — fix the dependency pins first. That failure is
dependency rot, and catching it early is the entire point of the pinned lockfile and the
`make verify` gate.

---

## Author

MCA final project. Built with the assistance of an AI coding agent across six sequenced
phases; the commit history, ADRs, and `HANDOFF.md` document what was agent-produced, what
was manually reviewed, and what was completed by hand. The architecture, interface
freezing, reviewer decisions, and honesty constraints were directed by the author.
