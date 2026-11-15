# TESTING.md — what the suite covers, how to run part of it, and what it does not prove

The suite is 641 collected cases across sixteen files (568 app cases + 73 benchmark cases), all offline. The command that matters:

```bash
python -m pytest -q tests
```

**Real output, captured 2026-11-15:**

```text
........................................................................ [ 28%]
.....................s.................................................. [ 42%]
........................................................................ [ 56%]
........................................................................ [ 70%]
........................................................................ [ 84%]
........................................................................ [ 98%]
......                                                                   [100%]
640 passed, 1 skipped in 11.26s
```

The elapsed time moves between runs (under a second to a minute, depending on the machine); the counts
do not. `s` is the single skip, explained in §3.

---

## 1. Layer map

Counted with `python -m pytest --collect-only -q tests/<file> | tail -2` on the
checked-in tree.

| Layer | Module under test | Test file | Collected |
| --- | --- | --- | ---: |
| Parser | `app/parser.py` | `tests/test_parser.py` | 11 |
| Rules | `app/rules.py` | `tests/test_rules.py` | 187 |
| Providers — OpenAI-compatible adapter | `app/openai_compat_provider.py` | `tests/test_openai_compat_provider.py` | 51 |
| Providers — Sarvam SDK adapter | `app/sarvam_provider.py` | `tests/test_sarvam_provider.py` | 87 |
| Engine (provider selection) | `app/engine.py` | inside `tests/test_openai_compat_provider.py` (section K) | 12 of those 51 |
| API | `app/main.py` | `tests/test_api.py` | 47 |
| GitHub client | `app/github_client.py` | `tests/test_github_client.py` | 54 |
| GitHub posting — hardening | `app/github_client.py` | `tests/test_posting_hardening.py` | 32 |
| GitHub posting — webhook flow | `app/main.py` + `app/github_client.py` | `tests/test_webhook_posting.py` | 27 |
| CLI | `app/cli.py` | `tests/test_cli.py` | 14 |
| Storage | `app/db.py` | `tests/test_db.py` | 27 |
| Auth | `app/auth.py` | `tests/test_auth.py` | 13 |
| Audit gaps | several modules | `tests/test_audit_gaps.py` | 15 |
| Diagrams | `docs/diagrams/make_diagrams.py` | `tests/test_diagram_generator.py` | 3 |
| Benchmarks — matching | `benchmarks/matching.py` | `tests/test_matching.py` | 35 |
| Benchmarks — metrics | `benchmarks/metrics.py` | `tests/test_metrics.py` | 20 |
| Benchmarks — runner | `benchmarks/runner.py` | `tests/test_runner_mock.py` | 18 |
| **Total** | | | **641** |

641 collected = 640 passed + 1 skipped.

Two things in that table are worth stating rather than letting someone discover
them:

- **`app/engine.py` has no file of its own.** Its twelve tests live in section K
  of `tests/test_openai_compat_provider.py`, because the engine's job is to hand
  a config to that adapter and there is nothing else to assert against. They are
  the precedence tests: `sarvam > local > mock`, forced-provider degradation
  naming the missing variable, and `--offline` beating a fully configured
  provider.
- **The benchmarks layer has 73 tests, not zero.** `tests/test_matching.py`,
  `tests/test_metrics.py` and `tests/test_runner_mock.py` cover the harness's
  logic offline. What is not covered is the quality of its output: precision and
  recall over the golden set are a smoke check, not a quality claim (§6).

### Counted tests versus `def test_`

A `grep -c "def test_"` gives 347 for the same tree, not 583. The difference is
parametrisation: `tests/test_rules.py` has 34 test functions and collects 187
cases (one or more cases per rule id), `tests/test_sarvam_provider.py` has 56 and
collects 87, `tests/test_posting_hardening.py` has 15 and collects 32. Quote the
collected count, not the function count — the collected count is what ran.

---

## 2. Running a subset

One file:

```bash
python -m pytest -q tests/test_rules.py
```

**Real output, captured 2026-11-15:**

```text
........................................................................ [ 77%]
...........................................                              [100%]
187 passed in 1.67s
```

By keyword — `-k` matches test names and their parametrisation ids, so this is
how you follow one rule end to end:

```bash
python -m pytest -q tests -k "sql"
```

**Real output:**

```text
..............                                                           [100%]
14 passed, 569 deselected in 5.06s
```

`14` because the SQL-injection rule is asserted through several layers: the rule
itself, the parser anchor, the adapter's hallucination filter, the API response
and the GitHub payload. That is the shape of a good keyword — it crosses layers
instead of re-testing one.

By layer:

```bash
python -m pytest -q tests/test_openai_compat_provider.py -k "selects or degrades_to_mock or engine_review or forced"
```

**Real output:**

```text
................                                                         [100%]
16 passed, 35 deselected in 6.02s
```

Provider-selection only, in six seconds, without the 187 rule cases.

Slowest first — the right first command when the suite starts creeping:

```bash
python -m pytest -q tests --durations=5
```

**Real output (tail), captured 2026-11-15:**

```text
============================= slowest 5 durations ==============================
0.09s call     tests/test_api.py::test_openapi_documents_every_endpoint
0.09s call     tests/test_api.py::test_no_endpoint_requires_a_key
0.06s call     tests/test_rules.py::test_regex_flood_does_not_blow_up
0.05s call     tests/test_webhook_posting.py::test_duplicate_delivery_is_skipped_without_any_post
0.05s call     tests/test_webhook_posting.py::test_test_review_endpoints_never_post
640 passed, 1 skipped in 8.47s
```

Nothing is slow. The top entry is 90 ms, which is itself the finding: no test
sleeps, no test waits on a socket, and the whole suite is CPU-bound on rule
matching.

Stop at the first failure and show locals:

```bash
python -m pytest -q tests -x -l
```

Run one test by node id:

```bash
python -m pytest -q "tests/test_openai_compat_provider.py::test_auto_with_both_configured_sarvam_wins_over_local"
```

---

## 3. What "640 passed, 1 skipped" means

One test did not run, and it is correct that it did not run. `-rs` names it:

```bash
python -m pytest -q tests -rs
```

**Real output (tail):**

```text
SKIPPED [1] tests/test_openai_compat_provider.py:1062: needs a live LM Studio server
640 passed, 1 skipped in 11.02s
```

The test is `tests/test_openai_compat_provider.py::test_live_smoke_review_against_a_real_endpoint`,
guarded by:

```python
LIVE_BASE_URL = os.getenv("LMSTUDIO_BASE_URL")          # module level, line 66

@pytest.mark.skipif(not LIVE_BASE_URL, reason="needs a live LM Studio server")
```

### Why skipping is the right answer, not a gap being hidden

1. **It cannot pass in CI.** CI has no LM Studio server, so the skipif is
   evaluated at import time and the test is never collected for execution. If it
   were not skipped it would fail on a connection error — and a suite that goes
   red for an environmental reason teaches people to ignore red.
2. **It would not prove what it looks like it proves.** The test asserts that the
   run *completes* and returns a `ProviderOutcome`, and it explicitly accepts
   `mode` of either `live` or `mock`, because a configured-but-silent server is a
   legitimate degradation. It is a wiring check, not a model-quality check.
3. **Everything it would exercise is already covered without a server.** The
   adapter's request shape, retry budget, repair retry, parsing, guards and
   degradation are covered by the other 50 tests in the same file against a
   scripted fake client with the real `openai` exception classes.
4. **It is opt-in by one variable**, so the skip is not a wall:

```bash
LMSTUDIO_BASE_URL=http://localhost:1234/v1 python -m pytest -q tests/test_openai_compat_provider.py
```

That turns `640 passed, 1 skipped` into `641 passed` on a machine with LM Studio
running. **This has not been done in this repository** — no LM Studio server has
ever been available here, so the un-skipped path is unverified. See `DEMO.md` §3.

So the honest reading is: 640 tests prove the offline behaviour of every layer;
1 test is a live-model wiring check that CI must not run.

---

## 4. The zero-network proof

`pytest` passing on a machine with internet does not prove the suite is offline.
`scripts/verify_offline.py` does:

```bash
python scripts/verify_offline.py
```

**Real output, captured 2026-11-15:**

```text
Network blocked: outbound connections are disabled for this run (socket.create_connection and non-loopback getaddrinfo raise; new AF_INET/AF_INET6 sockets are refused; AF_UNIX/loopback stay available for asyncio's self-pipe).
........................................................................ [ 14%]
........................................................................ [ 28%]
.....................s.................................................. [ 42%]
........................................................................ [ 56%]
........................................................................ [ 70%]
........................................................................ [ 84%]
........................................................................ [ 98%]
......                                                                   [100%]
640 passed, 1 skipped in 11.79s
```

Same counts as the unblocked run. That is the proof: nothing changes when the
network is taken away.

### How it works

The script imports `pytest`, `chdir`s to the repo root, installs three guards on
the `socket` module in-process, and then calls `pytest.main(["-q", "tests"])` —
so the suite runs in the *same* interpreter that has the guards installed. A
subprocess would not work; a `conftest.py` fixture could be bypassed.

What is blocked:

| Entry point | Effect |
| --- | --- |
| `socket.create_connection` | replaced by a function that records the attempt and raises `NetworkBlocked` |
| `socket.getaddrinfo` | raises for every non-loopback hostname, so no name resolves to an address |
| `socket.socket` | subclassed: constructing a new `AF_INET` / `AF_INET6` socket raises |

What is deliberately allowed, and why the allowance does not weaken the proof:

- **`AF_UNIX` sockets** — no network reachable through a Unix domain socket on a
  filesystem path.
- **`fileno`-wrapped sockets** — `socket.socketpair()`, which asyncio's event
  loop builds its self-pipe from. Blocking that breaks the event loop and every
  in-process ASGI test fails with an unrelated socket error. It wraps
  already-open descriptors; it cannot open a connection.
- **Loopback `getaddrinfo`** (`""`, `localhost`, `localhost.localdomain`,
  `127.0.0.1`, `::1`) — resolving a local name is local work. A resolved loopback
  name still cannot be connected to, because `create_connection` and IP socket
  construction are both refused.

The script exits with pytest's own exit code, and if any guard fired it prints a
`NOTE: <n> blocked network call(s) were attempted: [...]` line. A green run with
no NOTE means zero outbound attempts were made at all — not that they were
allowed.

The one-command wrapper that also builds a venv and installs the lock:

```bash
bash scripts/verify.sh
```

---

## 5. What is not covered

Stated plainly, because a coverage table that stops at the green line is
misleading.

- **No real model.** Every model call in the suite goes to a fake client. The
  adapter's request shape, retries and parsing are proven; the quality of any
  model's review is not, and no model output is checked in as a fixture.
- **No real GitHub.** `app/github_client.py` is tested against a fake
  `httpx.Client` that replays scripted responses. No request has ever been sent
  to `api.github.com`, so token scopes, real rate-limit behaviour, and whether
  GitHub accepts the payload's anchor positions are unverified. A `422` from
  GitHub on a real inline comment is exactly the kind of thing this cannot catch.
- **No real Sarvam.** The Sarvam SDK adapter (`app/sarvam_provider.py`) is tested
  against fakes too. A fake key returning a real 403 from `api.sarvam.ai` was
  reproduced once by hand (`DEMO.md` §4.2); a successful Sarvam review has never
  been produced.
- **No end-to-end browser test.** `/test-review`, `/review`, `/webhook` and
  `/docs` are exercised through the ASGI transport in-process. Nothing renders a
  page or drives a browser, so a JS-level breakage in `/docs` would not fail the
  suite.
- **No benchmark quality claim.** The harness's logic has 73 tests, but its
  precision, recall and F1 numbers come from two golden samples and are labelled
  a smoke check by the tool itself.
- **No test asserts latency or memory.** `--durations=5` reports what happened;
  nothing fails when it gets worse.
- **The skipped live test is the only thing that would touch a real endpoint**,
  and it asserts completion, not correctness.

---

## 6. Benchmarks, run by hand

There is no test file; the tool is the interface.

```bash
python -m benchmarks.eval
```

**Real output, captured 2026-11-15:**

```text
benchmark: dataset=benchmarks/golden modes=rules,local,merged samples=2

mode       samples  skipped  precision     recall         f1        fpr      p50ms      p95ms  note
---------  -------  -------  ---------  ---------  ---------  ---------  ---------  ---------  --------
local            0        2     0.0000     0.0000     0.0000     0.0000      0.000      0.000  skipped: LMSTUDIO_BASE_URL is not set, so no OpenAI-compatibl...
merged           2        0     0.8000     1.0000     0.8889     1.0000      0.398      0.572  local unavailable; merged is rules-only
rules            2        0     0.8000     1.0000     0.8889     1.0000      0.541      1.314  all 2 sample(s) are format examples; these numbers are a smok...
```

It writes `metrics.csv`, `summary.json`, `summary.md` and `chart.png` into
`benchmarks/out/` (generated, not checked in). Note the honest labels the tool
prints about itself: the `local` row is skipped because no endpoint is
configured, and the `rules` row says these are format examples and a smoke check.
Do not quote `f1 0.8889` as a quality claim; two samples cannot support one.

```bash
python -m benchmarks.eval --modes rules --quiet      # one mode, no stdout
python -m benchmarks.eval --dataset benchmarks/golden --out /tmp/bench
```

---

## 7. Writing a new test

The suite has one rule: **never touch the network, and never fake the thing you
are testing.** Both live adapters hide their transport behind a single
module-level seam, and tests patch the seam only. Everything above it — retries,
guards, parsing, degradation, labelling — runs for real.

### The pattern: an OpenAI-compatible client

From `tests/test_openai_compat_provider.py`. The seam is
`app.openai_compat_provider._build_client`, and `install_client` replaces it with
a recorder that replays scripted replies:

```python
def install_client(monkeypatch, replies):
    completions = FakeCompletions(replies)
    monkeypatch.setattr(ocp, "_build_client", lambda config: FakeClient(completions))
    return completions          # .calls holds one kwargs dict per model call
```

A `str` reply becomes `response.choices[0].message.content`; a `BaseException`
reply is raised. Replies are consumed in order, so "first attempt, then repair
attempt" is one list:

The shipped test of exactly that, abridged (`tests/test_openai_compat_provider.py:574`):

```python
def test_prose_then_valid_json_repairs_without_response_format(monkeypatch, bundle, cfg):
    """A parse failure costs exactly one repair call, which drops JSON mode."""
    completions = install_client(monkeypatch, [PROSE, ONE_FINDING])

    findings = ocp.review_diff_live(bundle, cfg)

    assert len(completions.calls) == 2
    assert "response_format" in completions.calls[0]
    assert "response_format" not in completions.calls[1]
    assert len(findings) == 1
```

Two details that make this pattern worth copying:

- **The real exception classes are used, not stand-ins.** `openai.AuthenticationError(message, response=..., body=...)`
  and `openai.APIConnectionError(request=...)` are built against an `httpx.Request`
  that is never sent, so the adapter's `except` clauses and its MRO-name matching
  are exercised against the genuine hierarchy. A `RuntimeError` would test
  nothing.
- **The seam is a function, not a constructor.** Patching `_build_client` means
  the config the engine built is still asserted, and no test can accidentally
  construct a real `openai.OpenAI`.

### The pattern: an HTTP client

From `tests/test_github_client.py`. Same shape, one seam lower. The seam is
`app.github_client._build_github_client`, and the fake replays a queue of
`FakeResponse` objects and records every call, so the state machine is asserted
by exact call order and exact request bodies:

```python
def install_client(monkeypatch: pytest.MonkeyPatch, client: FakeClient) -> list[str]:
    """Patch the client seam and return the list of tokens it was called with."""
    built: list[str] = []

    def _fake_build(token: str) -> FakeClient:
        built.append(token)
        return client

    monkeypatch.setattr(github_client, "_build_github_client", _fake_build)
    return built


def install_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Patch ``time.sleep`` inside the module and return the recorded waits."""
    slept: list[float] = []

    def _fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(github_client.time, "sleep", _fake_sleep)
    return slept
```

Each queue item is either a `FakeResponse(status_code, payload, headers, text)` or
an exception instance to raise — which is how a transport failure and a `429`
with `Retry-After` are scripted without wall-clock cost.

### Checklist for a new test

1. Find the seam: `grep -n "^def _build" app/<module>.py`. If a module has no
   seam and does I/O inline, add one — that is a code change, and worth arguing
   for rather than working around.
2. Patch the seam with `monkeypatch.setattr`, never `unittest.mock.patch` on an
   import site.
3. Script the reply queue; assert on the recorded kwargs, not just the return.
4. Use the real exception class for the failure you are simulating.
5. For environment-driven behaviour, `monkeypatch.setenv` / `delenv` and build a
   real `app.config.Settings` — do not hand-build a settings object, or the test
   stops covering the shipped defaults.
6. Assert the three labels — `mode`, `provider`, `model` — whenever the test
   touches a provider path. They are the contract that stops a degraded run
   looking like a live one.
7. Finish in milliseconds. If a test needs a timeout, it is testing the wrong
   thing.
8. Then run it with the network off:

```bash
python scripts/verify_offline.py
```

If your new test needs the network, it is not a unit test — mark it
`skipif(not <ENV_VAR>)` like the live smoke test, and say so in its docstring.
