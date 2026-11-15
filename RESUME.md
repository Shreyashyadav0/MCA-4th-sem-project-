# RESUME — picking this project up after a year

Audience: you, twelve months from now, with no memory of this repository.

Scope: this file only gets you from a cold machine to a working review, and then
tells you what is still unfinished and by whom. It is not a tutorial and it does
not explain the design. For that, read `README.md` and `ARCHITECTURE.md`.

Rules for this document: every command below was run against the tree it ships
with. Where a number appears, it is a number the tool printed. Nothing here is an
estimate.

---

## 0. What this is, in two sentences

A Python service that reviews a unified diff or a source file and returns
findings in a fixed five-field contract (File, Line, Severity, Issue, Suggested
Fix), using a deterministic 63-rule OWASP-mapped engine and, when a model is
configured, an LLM layer that falls back to that engine on any failure. It runs
with no credentials and no network; a missing key is a mode, not an error.

---

## Before you touch the code

Read these four things first. They take under an hour and each one prevents a
specific class of wasted afternoon.

1. **`README.md`** — the operational truth: CLI flags, endpoints, the live/offline
   routing table, the rule inventory, the output contract. Everything else in
   this repository is a deeper cut of something summarised there.

2. **`ARCHITECTURE.md`** — why the code is shaped this way: the config boundary,
   the finding contract, the anchor model, the single router, the single
   OpenAI-compatible adapter. Read it before proposing a refactor; most of the
   odd-looking structure is load-bearing.

3. **`docs/decisions/0004`** — skim this one even if you read nothing else in
   `docs/decisions/`. It records the one place where the code deliberately does
   the non-obvious thing. It will read like a bug. It is not a bug: it is a
   documented, tested deviation, and "fixing" it silently will either break a
   test or break a guarantee the report makes. If you think it should change,
   write a new decision record; do not edit the old one.

4. **`.python-version`** — this file pins the interpreter to `3.12.13`. Check it
   before you install anything. Do not install into whatever `python3` your
   machine happens to have and then conclude the project is broken; `make verify`
   builds its own virtualenv from the pin. Note that Python 3.10 reaches
   end-of-life in October 2026, so the pin itself is a known, dated liability —
   `docs/REPRODUCIBILITY.md` §3 states the risk and what moving off it involves.
   Treat an interpreter change as a project, not a chore.

Two further cautions, both cheap to obey:

- **Do not hand-edit `requirements.lock`.** It is generated; `docs/REPRODUCIBILITY.md`
  §2 gives the exact regeneration procedure. Editing versions in place makes the
  lock a lie and the "640 passed" claim unreproducible.
- **There is no `.gitignore` in this tree.** `README.md` suggests `cp .env.example .env`.
  If you put a real key in `.env`, nothing in this repository stops you from
  committing it. Prefer environment variables in the shell for a live run, or add
  a `.gitignore` that covers `.env`, `.venv*` and `benchmarks/out/` before you
  create any of them.

---

## The 7-step checklist

Each step states the command, what you should see, and what to do when you see
something else. Steps 1–4 are mandatory. Steps 5–6 are optional. Step 7 is the
actual decision.

### Step 1 — Open the repository and read `README.md` (5 minutes)

```bash
cd ai-code-reviewer
```

Read `README.md`. Nothing to run. When you finish you should know: what the CLI
does, what the five endpoints are, and that no key is required.

If `README.md` does not answer "how do I run the tests", stop and fix that first —
this file and the README disagreeing means the tree has drifted.

### Step 2 — Run the whole health check

```bash
make verify
```

Expected: `scripts/verify.sh` builds or reuses `.venv-verify`, installs
`requirements.lock`, runs the suite, runs the zero-network proof, and ends with

```
PASS: tests and zero-network proof succeeded
```

with `640 passed, 1 skipped` in the pytest output above it. The one skip is the
live LM Studio test, which cannot run without a local model — it is expected.

This is the entire health check. There is no separate lint gate to remember and
no manual smoke test that `make verify` misses. If this passes, the code is fine
and any problem you are having is configuration, not code.

If it fails: `docs/REPRODUCIBILITY.md` §5 has a symptom-to-cause table
(version conflict, newer interpreter, PyPI unavailable, local-vs-CI divergence).
Read that before changing anything.

### Step 3 — Review the bundled diff

```bash
python reviewer.py samples/sample.diff
```

Expected, in this order:

- one `WARNING reviewer.openai_compat: ...` line on stderr — normal in mock mode,
  it says the local rule engine was chosen;
- `mode     : mock`, `provider : mock`, `model : local-rules`;
- `files    : 2 changed`;
- `findings : 4 (CRITICAL 3, HIGH 0, MEDIUM 1, LOW 0)`;
- four numbered findings, each with File, Line, Severity, Issue, Suggested Fix and
  an `Anchor` line;
- a final `verdict  : block` line.

Exit code `0`. If you get zero findings, you are not in the repository root (the
sample path is relative). If you get `mode: live`, something in your environment
has a key or an LM Studio URL set — check `env | grep -E 'SARVAM|LMSTUDIO'`.

### Step 4 — Start the API and ask it what it is

```bash
uvicorn app.main:app --port 8000
# in a second shell:
curl -s localhost:8000/health
```

Expected: HTTP 200 with a JSON object reporting `status`, `mode`, `provider`,
`rules` (63), the ten `categories`, and the credential fields — with no key
configured, `sarvam_key`, `github_token` and `webhook_secret` all read `missing`,
`mode` and `provider` read `mock`.

This endpoint is the fastest way to answer "what is this process actually
configured to do", which is a different question from "what did I configure".

Stop the server with Ctrl-C when done. `make run` is the same command with
`--reload` if you are editing.

### Step 5 — Optional: the local-model path

Only if you want to see a real model review a diff. Follow `docs/LMSTUDIO.md` §5
step by step: install LM Studio, download the GGUF build, load it, start the
server on port 1234, then copy the model id from `/v1/models` verbatim and export
it. Then re-run step 3.

Expected: `mode : live`, `provider : local`, and findings labelled
`(source: local)`. Skip this entirely if you only need to work on the rule engine
or the report — nothing downstream requires a model.

### Step 6 — Optional: run the benchmark harness

```bash
python -m benchmarks.eval --modes rules --dataset benchmarks/golden --out benchmarks/out
```

Expected: a one-line header, a table with one row for the `rules` mode, and four
artifacts written to `benchmarks/out/`:

```
metrics.csv   summary.json   summary.md   chart.png
```

Exit code `0`. The mode note in that table says the samples it scored are format
examples — because they are. `benchmarks/golden/manifest.json` has an empty
`evaluation_samples` list and two `format_examples`. The run therefore proves the
harness works end to end; it does **not** produce an evaluation result, and the
precision/recall numbers it prints must never be quoted in the report.

To run the other modes: `--modes rules local merged`. A mode whose provider is
not configured skips cleanly and the command still exits 0.

### Step 7 — Decide what to do next

There are exactly two productive directions, and they are different kinds of work.

**Label the evaluation set** if you are finishing the project. This is the only
thing standing between the harness and a real result. Start at
`benchmarks/golden/README.md`, which defines the label format, the category and
severity vocabulary, and the five-step procedure for adding a sample; the labels
must be written by a human reading the diff. Note that the dataset README refers
to helper scripts (`collect_candidates.py`, `label_helper.py`) that are **not
present in this tree** — the README's manual procedure is what exists, so follow
that.

**Study** if you are re-learning the codebase. Start at `docs/learning/README.md`,
which indexes a seven-track curriculum written for exactly this situation.

If you are not sure which: read `docs/learning/README.md` first. It costs ten
minutes and will tell you how far you have drifted.

---

## Recovery path if you have forgotten everything

Two weeks, sequenced, not parallel. Read the track descriptions in
`docs/learning/README.md` before you start; the ordering below is the intended
one, and the descriptions there are authoritative for what each track contains.

| When | What | Why this one |
|---|---|---|
| Days 1–4 | Track 1 | Establishes the baseline the later tracks assume. Do not skip ahead; the rest of the curriculum presumes it. |
| Days 5–9 | Track 3 | The design core — the part that explains why the code looks like this. |
| Days 10–13 | Track 6 | The evaluation and reporting layer, which is where the unfinished work lives. |
| Day 14 | `make verify` | The only acceptance test. If it prints `640 passed, 1 skipped`, you are back. |

If day 14 fails, you have learned the codebase but not the environment. Go to
`docs/REPRODUCIBILITY.md` §5, not to the source.

Tracks 2, 4, 5 and 7 are deliberately not in this path. They are worth reading,
but none of them is required to make a change or run a benchmark.

---

## Deferred manual tasks

Everything below is work that cannot be automated away, could not be done in the
environment the code was built in, or requires a human judgement. Each row has
the command to run and the condition that closes it.

| # | Task | Why it is deferred | Exact command | Done when |
|---|---|---|---|---|
| 1 | Label the evaluation set | Labels must be written by a human reading the diff. A label copied from the rule engine's own output scores the tool against itself and measures nothing. | `mkdir -p benchmarks/golden/<short-id>` then write `change.diff` and a hand-written `expected.json`, add `<short-id>` to `evaluation_samples` in `benchmarks/golden/manifest.json`, then `python -m benchmarks.eval --modes rules --dataset benchmarks/golden --out benchmarks/out` | `manifest.json` lists at least one id under `evaluation_samples`, and the benchmark's mode note no longer says every sample is a format example. |
| 2 | Run the benchmark with a local model | No LM Studio endpoint or local model existed in the build environment. The `local` mode has only been exercised against a stub server, never a real model. | Start LM Studio per `docs/LMSTUDIO.md` §5, `export LMSTUDIO_BASE_URL=http://localhost:1234/v1`, `export LMSTUDIO_MODEL='<exact id from /v1/models>'`, then `python -m benchmarks.eval --modes rules local merged --dataset benchmarks/golden --out benchmarks/out` | `summary.md` has non-skipped rows for `local` and `merged`, and the `local` row's note is empty. |
| 3 | Produce the report prose | Every result sentence depends on task 1 and task 2, so the prose cannot precede them. | Work through `docs/report/SKELETON.md`; fill each placeholder, then `grep -rn "FILL AFTER BENCHMARK" docs/report` | That grep returns nothing, and every number in the report traces to a file in `benchmarks/out/`. |
| 4 | Fill the deck placeholders | The deck mirrors the report; its speaker notes depend on the same numbers. | Work through `docs/report/DECK_SKELETON.md`, then `grep -rn "SPEAKER NOTE PLACEHOLDER" docs/report` | That grep returns nothing. |
| 5 | Obtain a Sarvam API key (optional) | Never required. The project was built and verified with no key; the Sarvam branch has never run against the live hosted model. | `export SARVAM_API_KEY=<key>` then `python reviewer.py samples/sample.diff` | Output reads `mode : live`, `provider : sarvam`, and findings carry `(source: sarvam)`. Skip freely — this is a demonstration, not a dependency. |

A sixth item, small but easy to forget: record the GGUF hash of whatever local
model you use, per `docs/LMSTUDIO.md` §4. Without it the local-mode numbers are
not reproducible, because model files change under the same name.

---

## Where things live

| You want | Go to |
|---|---|
| How to run it, flags, endpoints, rules | `README.md` |
| Why it is built this way | `ARCHITECTURE.md` |
| Decisions, including the one that looks like a bug | `docs/decisions/` |
| The pinned interpreter and lock, and what to do when they drift | `docs/REPRODUCIBILITY.md` |
| The local model, end to end | `docs/LMSTUDIO.md` |
| Containers | `docs/DOCKER.md` |
| The benchmark harness and its frozen interfaces | `benchmarks/CONTRACT.md`, `benchmarks/golden/README.md` |
| The report and the deck | `docs/report/SKELETON.md`, `docs/report/DECK_SKELETON.md` |
| Re-learning the codebase | `docs/learning/README.md` |
