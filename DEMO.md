# DEMO.md — three ways to run this reviewer, and how honest each one is

Three variants, in ascending order of what they require: a deterministic rule
engine that works on any machine with Python, a local model served by LM Studio,
and a hosted Sarvam model.

**Read the label before you run anything.** Only variant A has been run end to
end and captured. Variant B has never had a real model behind it in this
repository. Variant C has never had a real key.

| Variant | What runs | Status |
| --- | --- | --- |
| A — offline mock | `app/rules.py` (63 rules, no network) | **Exercised.** Transcripts in §2 are real, captured 2026-11-14. |
| B — local via LM Studio | `app/openai_compat_provider.py` against a real model | **Unexercised in this repo.** The live branch was verified with the real `openai` SDK against a stub OpenAI-compatible server, not a real model. §3 shows the code's output *shape*, not a recorded run. |
| C — Sarvam | the same adapter against `https://api.sarvam.ai/v1` | **Unverified.** No real key was ever used. The failure path is real and reproduced in §4.2; no successful Sarvam review exists. |

Nothing below presents a fabricated run as real. Where a block is the code's
output shape rather than an observation, it says so on the line above it.

---

## 1. Setup

```bash
cd ai-code-reviewer          # the repository root; every command below assumes it
pip install -q -r requirements.txt -r requirements-dev.txt
```

Versions used for every transcript in this document: Python 3.12.13,
`fastapi 0.162.5`, `openai 3.51.0`, `pydantic 2.14.3`,
`pydantic-settings 2.15.0`, `sarvamai 0.1.46`, `pytest 8.4.2` — the pins in
`requirements.txt` and `requirements-dev.txt`, which agree with
`requirements.lock` on all seven runtime packages.

Every command in this file is copy-pasteable from the repository root. None of
them needs an environment variable, a key, or a network route except where it
says so.

---

## 2. Variant A — offline mock (works today, no setup)

### 2.1 The review

```bash
python reviewer.py samples/sample.diff --offline
```

`samples/sample.diff` is two files: `app/db.py` modified (a committed GitHub
token literal and an f-string SQL query) and `app/report.py` added (an
unannotated public function with a quadratic string build).

**Real output, captured 2026-11-14.** The first line is stderr; everything from
`target` down is stdout (see §2.4):

```text
WARNING reviewer.openai_compat: local review degraded to the local rule engine: no OpenAI-compatible provider selected; local rule engine used
target   : samples/sample.diff
mode     : mock
provider : mock
model    : local-rules
files    : 2 changed
findings : 4 (CRITICAL 3, HIGH 0, MEDIUM 1, LOW 0)
note     : mock mode: offline mode requested; local rule engine used
note     : local rule engine: 63 deterministic rules, no network, no API key

changed lines:
  modified  app/db.py  (+4: 3-4, 7-8)
  added     app/report.py  (+5: 1-5)

1. File          : app/db.py
   Line          : 3
   Severity      : CRITICAL
   Issue         : A GitHub token literal is committed here, granting every scope the token holds to anyone who reads the repository. (rule: secret/github-token)
   Suggested Fix : Revoke the token, then read it at runtime: `token = os.environ["GITHUB_TOKEN"]`.
   Anchor        : anchored @ @@ -1,5 +1,8 @@

2. File          : app/db.py
   Line          : 3
   Severity      : CRITICAL
   Issue         : `API_TOKEN` is assigned a literal credential, so the secret is committed to git history and stays readable to anyone with repo access even after it is rotated. (rule: secret/hardcoded-credential)
   Suggested Fix : API_TOKEN = os.environ["API_TOKEN"]  # load from the environment; fail loudly when it is unset
   Anchor        : anchored @ @@ -1,5 +1,8 @@

3. File          : app/db.py
   Line          : 7
   Severity      : CRITICAL
   Issue         : SQL is assembled by string interpolation, so any value reaching this line can change the statement and read, alter or drop the table. (rule: unsafe/sql-injection)
   Suggested Fix : Pass parameters instead: `db.execute("SELECT * FROM users WHERE id = ?", (uid,))` — the driver quotes them, interpolation does not.
   Anchor        : anchored @ @@ -1,5 +1,8 @@

4. File          : app/report.py
   Line          : 1
   Severity      : MEDIUM
   Issue         : `render` is a public function without full annotations, so callers and the reviewer cannot tell what goes in or what comes out. (rule: quality/missing-type-hints)
   Suggested Fix : Annotate it: `def render(value: str) -> str:` — every parameter and the return type.
   Anchor        : anchored @ @@ -0,0 +1,5 @@

verdict  : block
```

Findings 1 and 2 sit on the same file and the same line, so the order between them
comes from the tie-break in `sort_findings` (`app/models.py`): `-severity.rank`,
then file, then line, then the issue text. `A GitHub token literal…` sorts before
`` `API_TOKEN` is assigned… `` because a capital `A` precedes a backtick in ASCII,
so `secret/github-token` prints first. The order is the sort key's, not the rule
registry's, and it is reproducible byte for byte.

What to point at, in this order:

- `mode : mock`, `provider : mock`, `model : local-rules` — three lines that
  cannot lie, because they are set from what actually ran
  (`ProviderOutcome.mode` / `.provider` / `.model`).
- `findings : 4 (CRITICAL 3, HIGH 0, MEDIUM 1, LOW 0)` — four findings, not a
  score and not a percentage.
- Each finding carries the rule id that fired, so every line of output is
  traceable to one rule in `app/rules.py`.
- `Anchor : anchored @ @@ -1,5 +1,8 @@` — the finding was mapped to a hunk in
  the diff, which is what makes inline PR comments possible later.
- `verdict  : block` — three CRITICALs outvote the MEDIUM.

Exit code is `0`. That is deliberate: a review that finds problems is a
successful run, not a failed process.

### 2.2 The same run as JSON

```bash
python reviewer.py samples/sample.diff --json | jq '.mode, .verdict'
```

**Real output:**

```text
"mock"
"block"
```

The JSON top level carries `anchors`, `files`, `findings`, `mode`, `notes`,
`target`, `verdict`. Note there is no `stats` key here — `stats` is an API
response field, not a CLI one (§2.3).

### 2.3 The HTTP surface

Terminal 1:

```bash
uvicorn app.main:app --port 8000
```

Terminal 2:

```bash
curl -s localhost:8000/test-review | jq '.stats'
```

**Real output** (`duration_ms` is a wall-clock measurement and differs on every
run — three captures showed `14.125`, `17.11` and `4.614`; the rest of the block
is stable):

```json
{
  "files": 2,
  "findings": 4,
  "critical": 3,
  "high": 0,
  "medium": 1,
  "low": 0,
  "verdict": "block",
  "rules_evaluated": 63,
  "duration_ms": 14.125
}
```

`GET /test-review` runs the engine over `samples/sample.diff` with no
credentials and no network. It answers with `comment`, `model`, `notice`,
`posting`, `provider`, `review`, `source`, `stats` — the review itself is nested
under `.review`, so `jq '.review.mode'` gives `"mock"` while `jq '.mode'` gives
`null`. Worth knowing before you type it on a projector.

Two more one-liners that hold up in a viva:

```bash
curl -s localhost:8000/health | jq '{status, mode, rules, provider}'
```

**Real output:**

```json
{
  "status": "ok",
  "mode": "mock",
  "rules": 63,
  "provider": "mock"
}
```

```bash
curl -s localhost:8000/test-review | jq '.review.mode, .stats.verdict'
```

**Real output:**

```text
"mock"
"block"
```

### 2.4 Where the WARNING goes

The `WARNING reviewer.openai_compat: ...` line is on **stderr**; the report is on
**stdout**. Verified by redirecting each separately:

```bash
python reviewer.py samples/sample.diff 2>/dev/null   # report only, no WARNING
python reviewer.py samples/sample.diff 2>&1 >/dev/null # WARNING only
```

This matters for two reasons: `--json` output stays machine-parseable even on a
degraded run, and `pytest`-style log capture in a script will not swallow the
report. Exactly one WARNING is emitted per degraded run.

---

## 3. Variant B — local model via LM Studio

> **UNEXERCISED IN THIS REPO.** The live branch of
> `app/openai_compat_provider.py` was verified with the real `openai` SDK
> against a *stub* OpenAI-compatible server, not a real model. No LM Studio
> server has ever served a request for this project, and no model output is
> checked in as a fixture or a transcript. The expected output in §3.3 is the
> **code's output shape**, not a recorded run. This is consistent with
> `docs/LMSTUDIO.md` §2, which says the same thing.

### 3.1 Steps

**Step 1 — start LM Studio and download a Qwen2.5-Coder model.** In LM Studio's
search tab, search `Qwen2.5-Coder`, pick a **GGUF** build (Q4_K_M is the
configured target — roughly 4–5 GB of weights). Record the SHA-256 of the file
you actually downloaded; `docs/LMSTUDIO.md` §4 has the commands and the table to
put it in.

**Step 2 — load the model.** Select it and load it. Wait until it reports
loaded; the first load reads several GB from disk.

**Step 3 — start the server.** Developer tab → **Start Server**. Default port is
**1234**.

**Step 4 — copy the exact model id.** Do not type it from memory — LM Studio's
ids usually carry a publisher prefix and a quantization suffix:

```bash
curl -s http://localhost:1234/v1/models
```

Read `data[].id` and copy one string verbatim. If this command fails, the
problem is LM Studio, not the reviewer.

**Step 5 — point the reviewer at it.**

```bash
export LMSTUDIO_BASE_URL=http://localhost:1234/v1
export LMSTUDIO_MODEL='<the exact id from data[].id>'
```

The `/v1` suffix is required (without it the SDK posts to `/chat/completions` and LM Studio answers 404). A trailing slash after `/v1` is tolerated — the SDK normalises it. The
key is not needed: `LMSTUDIO_API_KEY` defaults to the literal `lm-studio`
because the SDK insists on a key string and LM Studio ignores it.

**Step 6 — run the review.**

```bash
python reviewer.py samples/sample.diff
```

### 3.2 What selects this path

`app/engine.py::select_provider` picks `local` when `LMSTUDIO_BASE_URL` is
non-blank and `SARVAM_API_KEY` is not set. If both are set, Sarvam wins by the
locked precedence `sarvam > local > mock`; force the local endpoint with:

```bash
python reviewer.py samples/sample.diff --provider local
```

### 3.3 Expected output — output shape, unverified

```text
target   : samples/sample.diff
mode     : live
provider : local
model    : <the model id you exported>
files    : 2 changed
findings : <n> (CRITICAL <n>, HIGH <n>, MEDIUM <n>, LOW <n>)
note     : live review: local/<model id> in <n> ms
```

`mode : live` and `provider : local` are the two lines to check. Both are set
only after a live review returned *and* parsed; a model that answers with prose
twice produces `mode : live` with `findings : 0` and a WARNING, which is a
different outcome from a degradation. The finding count is not predictable: it
is whatever the model says, filtered by the guards in
`app/openai_compat_provider.py` (hallucinated files dropped, invented line
numbers snapped or dropped, duplicates collapsed, capped at 50).

To exercise the one skipped test against a real server:

```bash
LMSTUDIO_BASE_URL=http://localhost:1234/v1 python -m pytest -q tests/test_openai_compat_provider.py
```

That turns the skip into a run. It asserts only that the review completes and
returns a `ProviderOutcome`; it accepts `mode` of `live` or `mock`.

### 3.4 What to do if you need this path to be real

Run it once, and record what happened — including the model id, the GGUF hash,
and the raw output. Until someone does, §3.3 stays labelled unverified and this
document will keep saying so.

---

## 4. Variant C — Sarvam

> **UNEXERCISED AND UNVERIFIED.** No real `SARVAM_API_KEY` was ever used with
> this code. Nobody has produced a successful Sarvam review. **Do not claim
> this path works.** What *is* proven is the failure path (§4.2) and the
> adapter's protocol (§4.1).

### 4.1 What exists

The adapter exists and is selected the same way as the local one. `app/engine.py`
builds an `OpenAICompatConfig` labelled `sarvam` pointing at
`https://api.sarvam.ai/v1` when `SARVAM_API_KEY` is non-blank, and hands it to
the single OpenAI-compatible adapter — Sarvam speaks the same
chat-completions protocol as LM Studio, so there is no Sarvam-specific
transport in the selected path.

### 4.2 The failure path — proven

With a fake key, the request reaches `api.sarvam.ai` and is rejected with a real
403. First, the raw endpoint:

```bash
curl -s -o /dev/null -w "HTTP=%{http_code}\n" -X POST https://api.sarvam.ai/v1/chat/completions \
  -H "Authorization: Bearer sk-fake-not-a-real-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"sarvam-m","messages":[{"role":"user","content":"hi"}]}'
```

**Real output, captured 2026-11-14:**

```text
HTTP=403
```

Body: `{"error":{"message":"Invalid or missing authentication credentials","code":"invalid_api_key_error","request_id":"..."}}`

Then the same fake key through the reviewer:

```bash
SARVAM_API_KEY=sk-fake-not-a-real-key python reviewer.py samples/sample.diff
```

**Real output, captured 2026-11-14:**

```text
WARNING reviewer.openai_compat: sarvam review degraded to the local rule engine: sarvam request failed: PermissionDeniedError (403); local rule engine used
target   : samples/sample.diff
mode     : mock
provider : mock
model    : local-rules
files    : 2 changed
findings : 4 (CRITICAL 3, HIGH 0, MEDIUM 1, LOW 0)
note     : mock mode: sarvam request failed: PermissionDeniedError (403); local rule engine used
note     : local rule engine: 63 deterministic rules, no network, no API key
```

Exit code `0`. This is the whole safety argument in one transcript: a rejected
hosted key does not crash the run, it degrades to the same four findings and
says why. The adapter reports exception class names and HTTP statuses only,
never the SDK's message text.

### 4.3 Configuration and expected shape — unverified

```bash
export SARVAM_API_KEY='<your key>'
export SARVAM_MODEL=sarvam-m          # optional; this is the default
python reviewer.py samples/sample.diff
```

Expected shape on success — **unverified, never observed:**

```text
target   : samples/sample.diff
mode     : live
provider : sarvam
model    : sarvam-m
files    : 2 changed
findings : <n> (CRITICAL <n>, HIGH <n>, MEDIUM <n>, LOW <n>)
note     : live review: sarvam/sarvam-m in <n> ms
```

Related settings: `REQUEST_TIMEOUT_S` (default 20 s) is the Sarvam request
timeout, separate from `LMSTUDIO_TIMEOUT` (120 s). `SARVAM_API_KEY` wins over
`LMSTUDIO_BASE_URL`, so a stray key in your shell will silently override a
working local setup — use `--provider local` to say otherwise.

---

## 5. What to show in a viva, in order (~4 minutes)

Each step is one command and one sentence. Do not open an editor.

**Step 1 — the review, 0:00–0:45.**

```bash
python reviewer.py samples/sample.diff
```

Say: "Deterministic rule engine, 63 rules, no network, no key. Four findings —
three CRITICAL, one MEDIUM. The mode, provider and model lines are set from what
actually ran, so this output cannot misrepresent itself. Exit code 0."

**Step 2 — the same result as data, 0:45–1:30.**

```bash
python reviewer.py samples/sample.diff --json | jq '.mode, .verdict'
```

Say: "`mock` and `block`. Every finding carries the rule id that fired, so the
report is traceable to one function in `app/rules.py`, and the verdict is a rule,
not a model's opinion."

**Step 3 — the same engine over HTTP, 1:30–2:15.**

```bash
uvicorn app.main:app --port 8000
curl -s localhost:8000/test-review | jq '.stats'
```

Say: "Same four findings through FastAPI. `rules_evaluated: 63` proves the whole
rule set ran. No credential of any kind is required for this endpoint — that is
asserted by a test, `test_no_endpoint_requires_a_key`."

**Step 4 — prove the suite needs no network, 2:15–3:00.**

```bash
python scripts/verify_offline.py
```

Say: "This blocks `socket.create_connection`, non-loopback `getaddrinfo`, and new
IP sockets in-process, then runs the whole suite. 637 passed, 1 skipped, with
the network unavailable. So the green suite is not an artefact of this machine
having internet."

**Step 5 — break it on purpose, 3:00–3:45.**

```bash
LMSTUDIO_BASE_URL=http://localhost:1234/v1 python reviewer.py samples/sample.diff
```

Say: "Nothing is listening on 1234. One WARNING, mode falls back to `mock`, the
same four findings, exit 0. A demo cannot die on stage — that is a design
constraint, not an accident."

Close, 3:45–4:00: "The one test that is skipped is the live-model smoke test; it
needs a real LM Studio server, so CI skips it rather than pretending."

---

## 6. If the demo breaks

The governing rule: a provider failure never crashes the run. Every case below
degrades to `mode : mock` and exits `0`. The first thing to read is always the
`mode` line and stderr, never the exit code.

### No network at all

Nothing breaks. Variant A is entirely local: `python reviewer.py
samples/sample.diff` makes no socket call. This is not a claim, it is the gate in
`scripts/verify_offline.py`, which blocks outbound sockets and then runs the
suite — see `TESTING.md` §4.

### LM Studio is down, or was never started

Symptom — `mode : mock` and one WARNING. **Real output, captured 2026-11-14 with
`LMSTUDIO_BASE_URL=http://localhost:1234/v1` and nothing listening:**

```text
WARNING reviewer.openai_compat: local review degraded to the local rule engine: local request failed: APIConnectionError; local rule engine used
target   : samples/sample.diff
mode     : mock
provider : mock
model    : local-rules
files    : 2 changed
findings : 4 (CRITICAL 3, HIGH 0, MEDIUM 1, LOW 0)
note     : mock mode: local request failed: APIConnectionError; local rule engine used
```

Cause: nothing listening, or a different port, or bound to `127.0.0.1` while the
client is not. Fix: press **Start Server**, then confirm with
`curl -s http://localhost:1234/v1/models`. If that works and the reviewer still
degrades, the base URL is wrong — the `/v1` root is required.

The WARNING names `APIConnectionError`, not "connection refused": the adapter
reports exception class names and statuses only.

### The port is already in use

Symptom — the server will not start. **Real output, captured 2026-11-14:**

```text
ERROR:    [Errno 98] error while attempting to bind on address ('127.0.0.1', 8000): address already in use
```

Exit code `3`. Fix: use another port, and follow it in the curl.

```bash
uvicorn app.main:app --port 8001
curl -s localhost:8001/test-review | jq '.stats'
```

Verified working on 8001. Find the squatter with `lsof -i :8000` if you want the
old one back.

### The live path was configured but mock ran

`SARVAM_API_KEY` is set, so Sarvam won the locked precedence `sarvam > local >
mock`. By design. Either unset it, or say otherwise:

```bash
python reviewer.py samples/sample.diff --provider local
```

### You want mock, guaranteed, no matter what is exported

```bash
python reviewer.py samples/sample.diff --offline
```

**Real output, captured 2026-11-14**, abridged to the header block — the
`WARNING reviewer.openai_compat: ...` line precedes it on stderr exactly as in
§2.1, and the reason names the flag:

```text
target   : samples/sample.diff
mode     : mock
provider : mock
model    : local-rules
note     : mock mode: offline mode requested; local rule engine used
note     : local rule engine: 63 deterministic rules, no network, no API key
```

`--offline` wins over `--provider` and over any configured credential.

### Where to look when the output looks wrong

- stderr: exactly one WARNING per degraded run, naming the provider label and
  the reason.
- the `note` line in the report restates the same reason.
- `--verbose` raises the log level to DEBUG and prints the routing decision.
- `curl -s localhost:8000/health | jq .` shows which credentials the process
  actually sees — `"missing"` or `"configured"` — which settles most "why is it
  in mock mode" questions in one line.

---

## 7. What is not verified

Restating it plainly, so no one has to guess:

1. **No real model has ever reviewed a diff in this repository.** Variant B's
   live branch is tested against a stub OpenAI-compatible server with the real
   `openai` SDK; that proves the adapter's request shape, retry and parsing, not
   that a particular model produces useful findings.
2. **No real Sarvam key was ever used.** The 403 in §4.2 is real and reproducible;
   a successful Sarvam review is not.
3. **No real GitHub API call is recorded.** Posting is covered by fake clients
   only — see `TESTING.md` §5.
4. **No browser or end-to-end test exists.** `/docs`, `/test-review` and the
   webhook are exercised through the ASGI transport in-process, not through a
   browser.
5. **`duration_ms` and timing figures are not stable** and must not be quoted as
   constants.
6. **The Qwen2.5-Coder-7B-Instruct Q4_K_M build may not exist in 2027.** Nothing
   in the code depends on it; `docs/LMSTUDIO.md` §3 covers the swap.
