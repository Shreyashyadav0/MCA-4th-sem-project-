# Autonomous AI Code Reviewer & PR Assistant

A code-review engine that runs with **no API key, no network and no model** — and uses a model only when one is available.

[![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](.python-version)
[![Tests](https://img.shields.io/badge/tests-640%20passing%20%C2%B7%201%20skipped-2ea44f)](tests)
[![Offline](https://img.shields.io/badge/suite-zero%20network-1F4E79)](scripts/verify_offline.py)
[![Licence](https://img.shields.io/badge/licence-MIT-blue)](LICENSE)

`MCSP-232` project · MCA (semester IV) · IGNOU · Shreyash Yadav

---

## What it does

Point it at a unified diff or a source file. It returns findings with exactly five fields — file, line, severity, issue, suggested fix — and can post them to a pull request as inline comments.

| Mode | Requires | What runs |
|---|---|---|
| `mock` | nothing | 63 deterministic OWASP-mapped rules |
| `local` | an OpenAI-compatible endpoint (e.g. LM Studio) | the model, with the rule engine as fallback |
| `sarvam` | a Sarvam API key | the hosted model, same adapter |

Provider precedence is `sarvam > local > mock`, decided in one place (`app/engine.py`) and reported honestly in every response: a local review is never labelled `sarvam`.

```console
$ python reviewer.py samples/sample.diff --offline
target   : samples/sample.diff
mode     : mock
provider : mock
model    : local-rules
files    : 2 changed
findings : 4 (CRITICAL 3, HIGH 0, MEDIUM 1, LOW 0)

1. File          : app/db.py
   Line          : 3
   Severity      : CRITICAL
   Issue         : A GitHub token literal is committed here, granting every scope it
                   carries to anyone who can read the repository. (rule: secret/github-token)
   Suggested Fix : Revoke the token, then read it at runtime: TOKEN = os.environ["TOKEN"]

verdict  : block
```

---

## Why this exists

Most review tooling assumes a paid endpoint and a working network. That makes it useless in the two places review matters most: a CI runner with no egress, and a laptop on a train.

This project inverts the assumption. The deterministic engine is the product; the model is an upgrade. If the key is missing, the endpoint is down, the answer does not parse or the rate limit bites, the review still completes — with one `WARNING` explaining what happened, never an exception and never a silent downgrade.

Three design rules follow from that, and they are the reason the code is shaped the way it is:

- **Added lines only.** A rule never reports a line the pull request did not touch, so every finding can be anchored to a real diff position.
- **One adapter, two providers.** Sarvam and LM Studio differ by an `OpenAICompatConfig`, not by a transport.
- **Frozen contracts.** `Finding` has five fields and forbids a sixth; a stray key from a model fails at the boundary instead of reaching a comment.

---

## Quick start

```bash
git clone https://github.com/<your-username>/mca-4th-sem-project.git
cd mca-4th-sem-project

pip install -r requirements.lock     # 37 pinned distributions
python -m pytest -q tests            # 640 passed, 1 skipped
python reviewer.py samples/sample.diff --offline
```

No key, no network, no configuration. To run the whole gate the way CI does:

```bash
make verify        # venv, install from the lock, full suite, zero-network proof
```

---

## Usage

### Command line

```bash
python reviewer.py path/to/file.py                  # review a whole file
python reviewer.py path/to/change.diff              # review a unified diff
python reviewer.py change.diff --json               # machine-readable result
python reviewer.py change.diff --min-severity HIGH  # filter
python reviewer.py change.diff --provider local     # auto | local | sarvam | mock
python reviewer.py change.diff --post-to-pr owner/repo#42
python reviewer.py --list-rules                     # all 63 rules
```

Exit codes: `0` review produced (live or mock) · `1` bad input or failed post · `2` usage error.

### HTTP API

```bash
uvicorn app.main:app --port 8000
```

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/review` | review a diff or a source file |
| `POST` | `/webhook` | GitHub `pull_request` event, HMAC-verified |
| `GET` | `/test-review` | offline demo on the bundled fixture |
| `GET` | `/rules` · `/rules/{id}` | the rule registry |
| `GET` | `/reviews` · `/reviews/{id}` · `/stats` | stored reviews (needs `X-API-Key` when auth is on) |
| `POST` `GET` `PATCH` | `/users` · `/users/{id}` | user and role management (admin only) |
| `GET` | `/health` | liveness, credential state, selected provider |

Interactive docs at `/docs`.

### Benchmark

```bash
python -m benchmarks.eval --modes rules local merged --dataset benchmarks/golden --out benchmarks/out
```

Writes `metrics.csv`, `summary.json`, `summary.md` and `chart.png`. `local` and `merged` skip cleanly when no endpoint is configured.

---

## How it works

```
diff ──► parser ──► rule engine (63 rules) ──► findings ──► anchor ──► report
                        │                                              │
                        └── optional: OpenAI-compatible adapter ───────┴──► pull request
                                    (Sarvam | LM Studio)                     (inline + summary)
```

`app/engine.py` is the only place that chooses a provider. Everything else is a pure function of its input, which is what makes the suite deterministic and the offline path trustworthy.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the module graph, the fallback chain and the frozen interfaces; [docs/decisions/](docs/decisions) for the seven ADRs, including the one that documents a deliberate deviation which looks like a bug.

---

## Project structure

```
app/                 15 modules, 9,250 lines
  models.py            the five-field finding contract
  parser.py            unified-diff parser and line anchoring
  rules.py             63 OWASP-mapped deterministic rules
  engine.py            provider selection (sarvam > local > mock)
  openai_compat_provider.py   one transport for both providers
  github_client.py     idempotent posting, 422 demotion, 429 retry
  db.py  auth.py       SQLite persistence, API keys, roles
  cli.py  main.py      the two surfaces
benchmarks/           offline evaluation harness
tests/                640 tests, no network
docs/                 report, diagrams, ADRs, learning curriculum
samples/              a real git diff used by every example above
scripts/              verify.sh, verify_offline.py, learning_progress.py
```

---

## Testing

```bash
python -m pytest -q tests             # 640 passed, 1 skipped
python scripts/verify_offline.py      # same, with outbound sockets blocked
```

The one skip is a live-model smoke test guarded by `@pytest.mark.skipif(not os.getenv("LMSTUDIO_BASE_URL"))`; it runs on a machine with LM Studio and skips everywhere else. Nothing in the suite touches the network, needs a credential, or depends on execution order.

What is deliberately **not** tested: a real model's output, a real GitHub post, and a real Sarvam call. See the honest ledger below.

---

## Project status

This is a semester-IV submission, so the repository states plainly what has been run and what has not.

| | |
|---|---|
| **Real** | the 63-rule engine on real diffs, diff parsing and anchoring, the offline path end to end across CLI/API/webhook, every endpoint over HTTP, the posting state machine against a fake client, the benchmark harness, one genuine `403` from `api.sarvam.ai` |
| **Simulated** | the local model path (real SDK, stub server — no Qwen has been run), a successful Sarvam review (never happened), a real GitHub post (fake client) |
| **Deferred** | a human-labelled evaluation set, a benchmark run with real numbers, report and deck placeholders, eleven screenshots |

[HANDOFF.md](HANDOFF.md) is the authority on this, and [RESUME.md](RESUME.md) is the checklist for picking the project up again.

---

## Limitations

Stated because a reviewer will find them anyway:

- Detection quality is **unmeasured** — the harness works, the labelled dataset does not exist yet.
- Rules are line-local: they catch a tainted value used on the same line, not one that flows through three functions.
- The idempotency marker is a public HTML comment, so anyone who can comment can suppress a review.
- Posting requires an authenticated delivery: with `GITHUB_TOKEN` set and `GITHUB_WEBHOOK_SECRET` unset, `/webhook` reviews but refuses to post unless `WEBHOOK_ALLOW_UNSIGNED=1` is set deliberately.
- Matching in the benchmark harness is greedy, not optimal.
- Authentication is opt-in (`API_AUTH_ENABLED`), so the default deployment is open — correct for a demo, wrong for the internet.

---

## Documentation

| Document | For |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | module graph, provider precedence, fallback chain |
| [DEMO.md](DEMO.md) | three demo variants with expected output |
| [TESTING.md](TESTING.md) | what the layers cover and what they do not |
| [docs/decisions/](docs/decisions) | seven ADRs, each with context, decision and consequences |
| [docs/report/](docs/report) | the MCSP-232 report and synopsis, with their generator |
| [docs/diagrams/](docs/diagrams) | eleven figures, each generated from the code |
| [docs/learning/](docs/learning) | a seven-track curriculum for rebuilding this from memory |
| [RESUME.md](RESUME.md) · [HANDOFF.md](HANDOFF.md) | recovery checklist and the honesty ledger |
| [CHANGELOG.md](CHANGELOG.md) | phase-by-phase history with test counts |

---

## Roadmap

1. Label a human-authored evaluation set and publish real precision/recall per mode.
2. Multi-language AST rules to complement the pattern layer.
3. Incremental review on push rather than full re-review.
4. SARIF export so results land in an existing code-scanning dashboard.

---

## Licence

[MIT](LICENSE) © Shreyash Yadav
