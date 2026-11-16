# Handover — read this first

For an examiner. Ten minutes, and every claim here is traceable to a file or a command
you can run. Where something is not proven, it says so.

---

## 1. What the project is

A code review tool for unified diffs. It runs 63 deterministic rules over the added
lines of a diff and reports findings with a severity, a fix and an OWASP citation; an
optional model layer may add findings on top. It runs with no network and no
credentials, and every result states which path produced it.

There is also a learning site: 110 lessons across 13 parts that teach how the tool is
built, with every example executed and its real output recorded.

---

## 2. Opening the site

Three ways, cheapest first.

**One file, no server.** Open `site/standalone.html` in a browser directly from the
file system. It has every stylesheet and script inlined and works from `file://`.

```console
$ open site/standalone.html          # macOS
$ xdg-open site/standalone.html      # Linux
```

**From the repo, with a server.** The multi-file version needs HTTP, because a
`file://` page cannot load its own scripts under some browsers' rules:

```console
$ python -m http.server 8080 --directory site
```

Then open <http://localhost:8080/>.

**Published.** `.github/workflows/pages.yml` publishes the site to GitHub Pages, but the
workflow is **manual-only** in this tree: Pages was never enabled for the repository, and
enabling it needs a repository owner's click in Settings → Pages → Source: GitHub
Actions. Do not claim a live URL; there is not one.

---

## 3. The whole gate, one command

```console
$ bash scripts/verify.sh
```

It installs from `requirements.lock`, runs the suite with outbound connections blocked,
and validates the learning site. The individual checks, if you want them separately:

```console
$ python site/tools/validate_lessons.py      # schema, counts, manifest wiring
$ python site/tools/check_ranges.py          # every line reference
$ python site/tools/check_quiz.py            # option length, per-part answer spread
$ python site/tools/embed_sources.py --check
$ python site/tools/build_standalone.py --check
$ python -m pytest -q tests
```

---

## 4. What is real, what is simulated, what is deferred

Copied from `HANDOFF.md`, which is the ledger and wins any disagreement.

### Real — executed here, output captured

| What | Evidence |
|---|---|
| The 63-rule engine on real diffs | `python reviewer.py samples/sample.diff` → 4 findings, verdict `block` |
| Diff parsing and anchoring | 641 collected, including anchored / file_only / unanchored cases |
| The offline mock path end to end | CLI, API and webhook, all with no credentials |
| The FastAPI surface | every endpoint exercised in-process through `TestClient`, plus a threaded `uvicorn` server on 127.0.0.1 |
| The webhook posting state machine | fake `httpx` client: happy path, duplicate skip, 422 demotion, 429 retry, 401/403/500, transport error |
| One real network rejection | `SARVAM_API_KEY=fake` reached `api.sarvam.ai` and returned a real 403, which degraded correctly |
| The OpenAI-compatible transport | the real `openai` SDK drove a stub OpenAI-compatible server: `mode=live`, `provider=local`, hallucinated file dropped |
| The benchmark harness | `python -m benchmarks.eval --modes rules --dataset benchmarks/golden` writes its four artifacts |
| Zero-network guarantee | `python scripts/verify_offline.py` → 640 passed, 1 skipped with outbound connections blocked |

### Simulated — the code path is real, the counterpart is a fake

| What | How | What is NOT proven |
|---|---|---|
| A real local model | a stub OpenAI-compatible server returning fixed JSON | that a real model produces usable findings, or how long it takes |
| A real Sarvam review | the SDK seam plus a real 403 | **that any Sarvam call ever succeeded** |
| Real GitHub posting | a fake `httpx` client | that GitHub accepts these comment positions |
| The live LM Studio smoke test | shipped as a `skipif` on `LMSTUDIO_BASE_URL` | it has never run |

### Deferred — needs a human

1. **Labelling the evaluation dataset.** Labels must be human-authored (ADR 0006).
   `benchmarks/labelling.py` is the tool; `LABELLING.md` is the procedure.
2. **A real Sarvam key.** No successful Sarvam review exists in this repository.
3. **The report prose and the viva rehearsal.**
4. **A browser on a real machine, and printed pages on paper.** Headless Chromium is
   evidence, not proof.

---

## 5. Known limits

Stated plainly, because they are the first thing an examiner should test.

**Running the examples needs two things.** 51 of the examples run Python in the
browser, and that runner downloads Pyodide (about 10 MB) from `cdn.jsdelivr.net` the
first time you press Run. With no internet, Run is unavailable; the other 60 lessons
are unaffected, and reading, search, quizzes and print all work offline. Separately,
7 of the examples are `curl` calls against `http://127.0.0.1:8000` and need a running
`uvicorn`. With nothing listening they fail with `000` — that is the environment, not a
fabricated capture.

**No precision, recall or F1 figure exists.** The labelled dataset has not been built,
so there is nothing to score against and lesson 10.10 says so in those words.
`benchmarks/labelling.py` and `LABELLING.md` are the path to producing it;
`python -m benchmarks.eval --labels` prints `no labels yet` and exits 3 rather than
compute a figure from an empty set.

**The Sarvam path is unexercised and no live model has run in this environment.** One
real 403 from `api.sarvam.ai` was captured and degraded correctly; no successful Sarvam
review exists. The OpenAI-compatible transport was proven against a stub server, not a
model. GitHub posting has never happened for real — the state machine is tested against
a fake client.

**The submission tag is `v1.1.2-site`.** `v1.1-site` and `v1.1.1-site` are earlier
points in the history and are not the submission.

---

## 6. The seven ADRs

In `docs/decisions/`, one decision each:

| # | Decides |
|---|---|
| [0001](docs/decisions/0001-strict-pydantic-v2.md) | Strict Pydantic v2 models at every boundary — no silent coercion, no unknown fields |
| [0002](docs/decisions/0002-offline-first-fallback.md) | Every entry point degrades to the 63-rule engine; a missing key is data, never an exception |
| [0003](docs/decisions/0003-provider-agnostic-openai-compat.md) | One OpenAI-compatible adapter serves every endpoint; two configs, not two transports |
| [0004](docs/decisions/0004-degraded-path-calls-offline-findings-directly.md) | The degraded path calls the rule engine directly, keeping one mock implementation and one WARNING per run |
| [0005](docs/decisions/0005-422-demotes-single-finding-not-whole-post.md) | A 422 demotes one finding into the summary; it never fails the post |
| [0006](docs/decisions/0006-labels-must-be-human-authored.md) | Benchmark labels are human-authored only, so the tool is never scored against itself |
| [0007](docs/decisions/0007-greedy-one-to-one-matching.md) | Matching is one-to-one greedy, largest overlap first |

---

## 7. The architecture in one picture

From `ARCHITECTURE.md`, which carries the full diagram and a check for each section:

```
front ends          reviewer.py / python -m app / app/main.py (FastAPI) / POST /webhook
                              |
                              v
app/parser.py       parse_diff / parse_diff_file  ->  DiffBundle (FileDiff -> Hunk -> DiffLine)
                              |
                              v
app/engine.py       review(bundle, settings, provider=..., force_offline=...)
                    select_provider -> ProviderSelection(provider, config, reason)
                              |
              config is None  |  config present
                              v
app/mock_provider.py  <->  app/openai_compat_provider.py  ->  local or Sarvam
                              |
                              v
                    ProviderOutcome(mode, provider, model, findings, reason, latency_ms)
```

One review entry point, three provider names, one transport, one mock implementation,
and a result that always says what actually ran.

---

## 8. Where to look next

| Question | File |
|---|---|
| How do I change or add a lesson? | `MAINTAINING.md` |
| How do I produce the missing benchmark numbers? | `LABELLING.md` |
| What is proven, and how? | `HANDOFF.md` |
| How is the tool built, and why? | `ARCHITECTURE.md` |
| How do I run each demo variant? | `DEMO.md` |
| What does the test suite cover? | `TESTING.md` |
