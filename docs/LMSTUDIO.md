# LM Studio (local OpenAI-compatible provider)

This document covers the local inference path: the endpoint this project was
configured against, how to reproduce a demo run, how to move to a different
model or server without touching code, and what each failure looks like.

The path exists in one file: `app/openai_compat_provider.py`. Which endpoint it
talks to is decided in `app/engine.py`. Nothing else in the repository knows
what a model is.

---

## 1. What LM Studio is, and why it is the demo path

LM Studio is a desktop application that downloads GGUF model files, runs them
locally, and can expose the loaded model behind an OpenAI-compatible HTTP
server. Its default server address is `http://localhost:1234/v1`.

It is the demo path for three reasons:

- **Local.** The model runs on the presenter's machine. The review request and
  the diff do not leave the host.
- **No key.** LM Studio ignores the `Authorization` header, but the `openai` SDK
  will not build a client without a key string, so `LMSTUDIO_API_KEY` defaults
  to the literal `lm-studio` (`app/config.py`).
- **OpenAI-compatible.** The adapter sends
  `POST {base_url}/chat/completions` with `model`, `messages`, `temperature` and
  `max_tokens` (plus `response_format` on the first attempt — see §3), and
  nothing else. Sarvam's endpoint
  (`https://api.sarvam.ai/v1`) speaks the same protocol, which is why a single
  adapter serves both providers; the only difference between them is an
  `OpenAICompatConfig` built by `app/engine.py`.

### Configuration surface

All four variables are read once, in `app/config.py`. Field names are lowercase
there because pydantic-settings is configured `case_sensitive=False`.

| Variable | Default | Effect |
| --- | --- | --- |
| `LMSTUDIO_BASE_URL` | unset (`None`) | Endpoint root, e.g. `http://localhost:1234/v1`. **Setting it is what selects the local provider.** Must include `/v1`. |
| `LMSTUDIO_MODEL` | `qwen2.5-coder-7b-instruct` | Model id sent with every request. Must match an id the server serves. |
| `LMSTUDIO_API_KEY` | `lm-studio` | Bearer key. LM Studio ignores the value; the SDK requires one to exist. |
| `LMSTUDIO_TIMEOUT` | `120` | Per-request timeout in seconds (`gt=0`). Separate from `REQUEST_TIMEOUT_S` (20 s), which is the Sarvam timeout. |

Provider precedence is locked in `app/engine.py`: `sarvam` > `local` > `mock`.
`SARVAM_API_KEY`, when set, wins over `LMSTUDIO_BASE_URL`. To force the local
endpoint anyway:

```bash
python reviewer.py samples/sample.diff --provider local
```

`config_for_local()` requires **both** `LMSTUDIO_BASE_URL` and
`LMSTUDIO_API_KEY` to be non-blank. The second is satisfied by its default, so
in practice the base URL is the only thing a user must supply.

---

## 2. The model this project was configured against

| Field | Value |
| --- | --- |
| Model | Qwen2.5-Coder-7B-Instruct |
| Format / quantization | GGUF, **Q4_K_M** |
| Context length | 32k (per the model card; not measured in this repository) |
| Default id in `app/config.py` | `qwen2.5-coder-7b-instruct` |

Why that size: a 7B model at Q4_K_M is roughly 4–5 GB of weights — small enough
to load on a 16 GB laptop alongside an editor and a browser, with 32k of context
for a diff prompt and enough code competence that its review output is not noise.

**This was the configured target. No real model run is recorded in this
repository.** There is no LM Studio server in CI and none in the development
sandbox used to write this document, and no model output is checked in as a
fixture or a transcript. The single skipped test in the suite is the live smoke
test — `tests/test_openai_compat_provider.py::test_live_smoke_review_against_a_real_endpoint`,
skipped because `LMSTUDIO_BASE_URL` is unset. Everywhere below that shows
`mode : live` is describing the shape the code prints, not an observed
transcript.

The default id `qwen2.5-coder-7b-instruct` is a lower-case convenience. LM
Studio's own model ids often carry a publisher prefix and a quantization suffix.
Do not type the id from memory — copy it from the server (§5, step 4).

---

## 3. This model may not exist in 2027

**Warning: model ids and file names change. Qwen2.5-Coder-7B-Instruct, and the
`Q4_K_M` GGUF build of it, may be renamed, re-quantized, superseded or withdrawn
from LM Studio's catalogue by 2027. Nothing in this repository depends on that
particular model continuing to exist. If the download is gone, use any other
instruction-following model your endpoint serves — no code change is required.**

That is not a hope; it is the architecture:

- `app/openai_compat_provider.py` speaks the OpenAI **chat-completions
  protocol** and nothing else. It holds no model name, no tokenizer, no
  chat-template, no Qwen-specific prompt. Its system prompt is generic
  ("You are a senior code reviewer...").
- The model id is data, carried in `OpenAICompatConfig.model`, which comes from
  `LMSTUDIO_MODEL`.
- The endpoint is data, carried in `OpenAICompatConfig.base_url`, which comes
  from `LMSTUDIO_BASE_URL`.
- `app/engine.py` builds that config and hands it to the adapter. It does not
  branch on the model either.

So there is exactly one adapter and one selection point; switching models is a
configuration change.

### Swap recipe A — a different model on the same server

```bash
curl -s http://localhost:1234/v1/models
export LMSTUDIO_MODEL='<the exact id from the list above>'
```

### Swap recipe B — a different OpenAI-compatible server

Point `LMSTUDIO_BASE_URL` at any endpoint that implements
`POST /v1/chat/completions`. The variable name is historical; it is not
LM Studio-specific (`app/engine.py` calls the provider `local` and describes it
as "any self-hosted OpenAI-compatible endpoint"). Examples, each of which is a
URL you would set verbatim:

| Server | Typical base URL |
| --- | --- |
| llama.cpp `llama-server` | `http://localhost:8080/v1` |
| vLLM | `http://localhost:8000/v1` |
| Ollama (OpenAI-compatible endpoint) | `http://localhost:11434/v1` |
| A hosted OpenAI-compatible API | that provider's root, ending in `/v1` |

```bash
export LMSTUDIO_BASE_URL=http://localhost:8080/v1
export LMSTUDIO_MODEL='<model id that server serves>'
export LMSTUDIO_API_KEY='<key, or any non-blank string for a keyless server>'
```

A hosted endpoint needs its real key in `LMSTUDIO_API_KEY`; the default
`lm-studio` will be rejected there.

### What a replacement model has to do

1. **Answer on `chat/completions`** with `model`, `messages`, `temperature`,
   `max_tokens` accepted as sent.
2. **Tolerate or reject `response_format`.** The first request includes
   `response_format={"type": "json_object"}`. If the server rejects that with a
   400 (`BadRequestError`), the adapter makes exactly one repair retry with
   `response_format` omitted and the parse error appended to the prompt. A
   server that does not implement `response_format` therefore still works, at
   the cost of one extra call.
3. **Return findings as JSON.** Accepted shapes: a bare JSON array, a single
   object, or `{"findings": [...]}`; markdown code fences are stripped before
   parsing. Each item needs `file`, `line`, `severity`, `issue`, `suggested_fix`.
   Anything else — prose, a wrapper object with another key — is a parse failure
   and triggers the repair retry.
4. **Fit the prompt and the answer budget.** The prompt is the added lines of
   the diff; the answer is capped at `max_tokens=2000`
   (`_MAX_TOKENS` in the adapter). A model with a tiny context window will
   truncate.
5. **Be quick enough for `LMSTUDIO_TIMEOUT`** (default 120 s per request). A
   model that needs longer should have the timeout raised, not the code changed.

Two consecutive unusable answers are not a crash: the adapter logs one WARNING
and returns an empty **live** review — `mode : live` with zero findings, which
is a different outcome from the degraded `mode : mock`.

---

## 4. Record the GGUF hash on first download

A SHA-256 of the exact `.gguf` file is the only way to prove which weights
produced a given demo output. Two files with the same name and the same
quantization label from different mirrors are not necessarily the same bytes,
and a re-uploaded or re-quantized file keeps the name. Record the hash once, in
the repository, and the demo becomes citable later.

### Compute it

Linux:

```bash
sha256sum Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf
```

macOS (both are present; `shasum -a 256` is the portable one):

```bash
shasum -a 256 Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf
```

Windows PowerShell:

```powershell
Get-FileHash -Algorithm SHA256 .\Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf
```

Windows `cmd` with certutil:

```cmd
certutil -hashfile Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf SHA256
```

Each prints a 64-character lowercase hex digest. Copy it verbatim.

LM Studio's own download directory is under the application's data folder; find
the file with:

```bash
find "$HOME/.lmstudio" "$HOME/.cache/lm-studio" -name '*.gguf' 2>/dev/null
```

(Personal-model directories differ by version and OS. If neither path exists,
use LM Studio's "Reveal in Finder" / "Show in Explorer" on the model, and
treat the exact path as unverified until you have seen it.)

### Where to record it

Create `docs/MODEL_HASHES.md` — it is not created in advance, because a table
with a guessed hash is worse than no table. Fill one row per file you actually
downloaded:

```markdown
# Model hashes

Weights used for demo runs, with the digest of the exact file on disk.

| model | quant | sha256 | date | source URL |
| --- | --- | --- | --- | --- |
| Qwen2.5-Coder-7B-Instruct | Q4_K_M | <64 hex chars> | 2026-11-14 | <the URL or catalogue entry you downloaded from> |
```

Rules for that file:

- One row per **file**, not per model. A re-download that produces a different
  digest is a new row with the date it replaced the old one.
- The `date` is the download date, not the demo date.
- The `source URL` is the page or catalogue entry the file came from, not "LM
  Studio".
- Never edit an existing hash to make it match a new file. Add a row.

---

## 5. Demo steps

Prerequisites: LM Studio installed, a machine with enough RAM to hold the model
(~5 GB of weights plus KV cache; 16 GB total is the target), and this repository
checked out.

**Step 1 — install the app dependencies.**

```bash
python -m venv .venv
. .venv/bin/activate
PIP_USER=0 python -m pip install -r requirements.lock
```

**Step 2 — open LM Studio and download the model.** In the search / discover
tab, search for `Qwen2.5-Coder-7B-Instruct`. Pick a **GGUF** build labelled
**Q4_K_M**. Note the file name LM Studio writes to disk, and record its hash per
§4 before doing anything else.

**Step 3 — load the model.** Select it in the chat or "My Models" tab and load
it. Wait until it reports loaded. The first load reads several GB from disk and
can take minutes.

**Step 4 — start the server.** Open the **Developer** tab and press **Start
Server**. The default port is **1234**. If you need to reach it from a container,
enable "Serve on Local Network" — see `docs/DOCKER.md` §5.

Confirm it is up and copy the model id verbatim:

```bash
curl -s http://localhost:1234/v1/models
```

The response lists `data[].id`. Use exactly that string in the next step; do not
lower-case it, strip a prefix, or guess it.

**Step 5 — point the reviewer at it.**

```bash
export LMSTUDIO_BASE_URL=http://localhost:1234/v1
export LMSTUDIO_MODEL='<the exact model id LM Studio reports>'
```

Optional, if the model is slow to load:

```bash
export LMSTUDIO_TIMEOUT=300
```

**Step 6 — run the review.**

```bash
python reviewer.py samples/sample.diff
```

Expected output on a successful live run — the first three lines are the
contract; the `note` line reports provider, model and wall time:

```
target   : samples/sample.diff
mode     : live
provider : local
model    : <the model id you exported>
files    : 2 changed
findings : <n> (CRITICAL <n>, HIGH <n>, MEDIUM <n>, LOW <n>)
note     : live review: local/<model id> in <n> ms
```

`mode : live` and `provider : local` are the two lines to check. They come from
`ProviderOutcome.mode` and `ProviderOutcome.provider`, which the adapter sets
only after a live review returned and parsed. This expected block is the code's
output shape, not a recorded run: no live run has been captured in this
repository.

For the full result as JSON:

```bash
python reviewer.py samples/sample.diff --json
```

To run the live smoke test — the one test skipped in the normal suite:

```bash
LMSTUDIO_BASE_URL=http://localhost:1234/v1 python -m pytest -q tests/test_openai_compat_provider.py
```

It asserts only that the run completes and returns a `ProviderOutcome`; it
accepts `mode` of either `live` or `mock`, because a configured-but-silent
server is a legitimate degradation.

---

## 6. Troubleshooting

The governing rule: **a provider failure never crashes the run.** A connection
error, timeout, 404, rejected key or unparseable answer degrades to the local
rule engine, logs exactly one WARNING on the `reviewer.openai_compat` logger,
sets `mode : mock` / `provider : mock` / `model : local-rules`, and exits 0. So
the first thing to check is always the mode lines and stderr, not the exit code.

### Connection refused

Symptom — the report shows `mode : mock` and one WARNING; with a dead endpoint
the reason names the SDK class:

```
WARNING reviewer.openai_compat: local review degraded to the local rule engine: local request failed: APIConnectionError; local rule engine used
```

(The adapter reports exception class names and HTTP statuses only, never the
SDK's message text, so "connection refused" itself does not appear.)

Cause — nothing is listening. Either the server was never started, or it is on
a different port, or it is bound to `127.0.0.1` while the client is not.

Fix — press **Start Server** in the Developer tab, then:

```bash
curl -s http://localhost:1234/v1/models
```

If that fails, the problem is LM Studio, not the reviewer. If the reviewer runs
in a container, `localhost` is the container: see `docs/DOCKER.md` §5.

### 404 on `/v1`

Symptom — `mode : mock`, and the reason carries a 404:

```
... local request failed: NotFoundError (404); local rule engine used
```

Cause — wrong base URL. The SDK appends `/chat/completions` to whatever you
give it, so the base URL must be the `/v1` root. `http://localhost:1234`
produces `POST http://localhost:1234/chat/completions`, which does not exist;
`http://localhost:1234/v1` produces the correct path.

Fix:

```bash
export LMSTUDIO_BASE_URL=http://localhost:1234/v1
```

The trailing `/v1` is required, and there must be no trailing slash after it.

### Model not found

Symptom — `mode : mock`, a 404 or a 400 in the reason, and no findings from the
model. LM Studio returns an error for an unknown model id.

Cause — `LMSTUDIO_MODEL` does not match an id the server serves. The default
`qwen2.5-coder-7b-instruct` is not necessarily what LM Studio reports, which may
include a publisher prefix or quantization suffix; an id from a *different*
server is also wrong even if the model is the same.

Fix — read the id off the server and use it verbatim:

```bash
curl -s http://localhost:1234/v1/models
export LMSTUDIO_MODEL='<id from that response>'
```

### Timeouts on the first request

Symptom — `mode : mock` after a long pause, reason containing
`APITimeoutError`. A timeout is classified as non-repairable, so there is no
retry: one wait, then the degraded path.

Cause — the first request pays for a cold load: weights are read from disk and
may be moved to VRAM before the first token is produced. A large model on a slow
disk, or a GPU offload that has to re-page, can exceed 120 s. A long diff makes
it worse: `max_tokens=2000` at a few tokens per second on CPU is minutes.

Fix — raise the timeout rather than assuming a hang:

```bash
export LMSTUDIO_TIMEOUT=600
```

Then retry. If the second run is fast, it was the cold load; if it is not, the
model is too large for the hardware.

### The report is live but has zero findings

Symptom — `mode : live`, `provider : local`, `findings : 0`, and a WARNING
`local review failed twice; returning an empty review (...)`.

Cause — the model answered, but neither attempt parsed: prose instead of JSON, a
wrong key set, or an empty completion. This is deliberately **not** a
degradation: an empty live review is treated as a legitimate answer.

Fix — check what the model actually returns with the same prompt, and pick a
model that follows a JSON instruction (see §3, "What a replacement model has to
do"). A model tuned for chat prose is a poor fit here.

### Live mode was requested but mock ran

Cause — `SARVAM_API_KEY` is set, so `sarvam` won the locked precedence. This is
by design, not a bug.

Fix:

```bash
python reviewer.py samples/sample.diff --provider local
```

### Where to look

- stderr: exactly one WARNING per degraded run, naming the provider label and
  the reason.
- `--verbose` raises the log level to DEBUG, which prints the routing decision.
- The `note` line in the report restates the reason the rule engine ran.

The API surface reports the same facts: `/health` includes a `provider` field,
and every review response names the provider and model that actually ran.
