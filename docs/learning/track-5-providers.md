# Track 5 — app/sarvam_provider.py and app/openai_compat_provider.py

## Prerequisite check

Run these from the repository root before reading. The first two need only `pydantic`;
the third is a grep, not an import, because the SDKs are optional by design.

```bash
python3 -c "from app.openai_compat_provider import OpenAICompatConfig; print(OpenAICompatConfig.__dataclass_fields__.keys())"
python3 -c "import app.openai_compat_provider, app.sarvam_provider; print('imports clean')"
grep -n "logger.warning" app/sarvam_provider.py app/openai_compat_provider.py
grep -rn "sarvam_provider" --include=*.py app/ | grep -v "^app/sarvam_provider.py"
```

You should be able to answer: how many distinct WARNING call sites exist across the two
modules (five), which module the app actually routes through (the adapter), and why
`import app.sarvam_provider` succeeds on a machine with neither `sarvamai` nor a key.

You should also have read `docs/decisions/0003-provider-agnostic-openai-compat.md` and
`docs/decisions/0004-degraded-path-calls-offline-findings-directly.md`. Track 5 is
mostly an explanation of those two documents against the code.

## What it does

`app/openai_compat_provider.py` is one OpenAI chat-completions adapter serving two
providers, Sarvam's hosted endpoint and any self-hosted OpenAI-compatible endpoint,
where the only difference between them is an `OpenAICompatConfig` value. It owns the
guards that are expensive to get right — JSON-mode request, one repair retry, payload
parsing, hallucination and line guards, key scrubbing, provenance labels — and a
degraded path that produces rule-engine findings instead of raising.
`app/sarvam_provider.py` is the Phase 4 module those guards live in: it still defines
`build_prompt`, `parse_findings_payload`, `LLMFinding` and `ProviderOutcome`, still
carries its own SDK-based live path for its own tests, and is no longer the app's live
path.

## Why it exists

Two endpoints, one protocol. Sarvam (`https://api.sarvam.ai/v1`) and LM Studio
(`http://localhost:1234/v1`) both speak OpenAI chat-completions, and the expensive part
of a provider is not the transport but the guards around it: the JSON-mode request, the
single repair retry, dropping findings for files that are not in the diff, snapping line
numbers onto added lines, scrubbing the key out of every message, sorting by severity,
and the invariant that no raw SDK exception escapes to a caller. Duplicating those per
provider means two places to fix each guard and two places to drift — the second copy
gets the "no key in a log record" rule wrong first (`docs/decisions/0003`, "Context").

The negative half of that decision is recorded too: an endpoint that is not
OpenAI-compatible cannot be used at all, and a provider needing different prompt framing
gets it by string surgery rather than a hook. That ceiling is accepted because both
endpoints speak the protocol today.

`app/sarvam_provider.py` exists for the older reason: it was the Phase 4 live path, built
on the `sarvamai` SDK, and it is where the fallback contract was first made concrete —
seven failure modes collapsed into one exception type, one WARNING, never a raise
(`app/sarvam_provider.py:7-12`). Phase 5.5 did not delete it; it reused its guards and
replaced its transport.

### What `app/sarvam_provider.py` is still for

The module is now a library of guards plus a legacy adapter, and the split is worth
memorising:

- **Reused by the adapter** (imported at `app/openai_compat_provider.py:53-59`):
  `LLMFinding` (`app/sarvam_provider.py:72`), `ProviderOutcome` (`:102`), `build_prompt`
  (`:429`), `parse_findings_payload` (`:727`), and `SarvamUnavailableError` (`:63`).
  `tests/test_openai_compat_provider.py:377` asserts the re-exports are the *same
  objects*, not copies, so a fix to a guard cannot land in only one module.
- **Retained for its own tests only**: `review_diff_live` (`app/sarvam_provider.py:832`)
  and `review_with_fallback` (`:914`), which build a `sarvamai.SarvamAI` client at
  `:313` and call `client.chat.completions(...)` at `:363`. `tests/test_sarvam_provider.py`
  exercises them directly. Nothing in `app/` calls them on the review path: the only
  import of the module outside itself is `app/cli.py:44`, which takes `ProviderOutcome`
  as a type, and the adapter's guard imports.
- **The app's actual live path**: `app/engine.py:45-51` imports `review_with_fallback`
  from `app.openai_compat_provider`, and `app/engine.py:380` is the only call site.
  Everything — Sarvam, LM Studio, degraded — goes through the adapter.

So the module named `sarvam_provider` no longer serves Sarvam requests. The name is a
Phase 4 artefact; read it as "the review-guards module with a legacy SDK adapter
attached". Its `review_with_fallback(force_offline=True)` still works and still logs on
`reviewer.sarvam`, which is precisely why the adapter does not call it (see idea (c)).

## Key references

- `app/openai_compat_provider.py:124` — `@dataclass(frozen=True) class
  OpenAICompatConfig`: the whole provider abstraction, frozen so a run's label and
  endpoint cannot be mutated mid-review.
- `app/openai_compat_provider.py:138` — the five fields begin here (`base_url`,
  `api_key`, `model`, `provider_name`, `timeout`); nothing else varies between
  providers.
- `app/engine.py:124` — `config_for_sarvam` builds the Sarvam config, with the base URL
  as data (`_SARVAM_BASE_URL`, `app/engine.py:73`) and the hosted timeout.
- `app/engine.py:148` — `config_for_local` builds the LM Studio config, with the longer
  `lmstudio_timeout` because a model on a laptop is slow.
- `app/openai_compat_provider.py:425` — `if _JSON_MODE.get():` adds
  `response_format={"type": "json_object"}` to the request; the ContextVar is what lets
  the repair retry omit it without changing the `_call_model` signature.
- `app/openai_compat_provider.py:554` — `if findings is None:` — the single gate that
  decides whether the repair retry runs at all; there is no third attempt anywhere.
- `app/openai_compat_provider.py:591` — `logger.warning(...)`: the one WARNING emitted
  when both attempts fail; the run stays live with zero findings.
- `app/openai_compat_provider.py:641` — the degraded path calls `_offline_findings`
  (i.e. `app.mock_provider.offline_diff_findings`, imported at `:51`) directly, which is
  the documented deviation from the Phase 5.5 contract.

## The three hardest ideas

### (a) The provider-agnostic design: five fields, and where each one is consumed

`OpenAICompatConfig` is the entire difference between Sarvam and LM Studio:

```python
# app/openai_compat_provider.py:124-142
@dataclass(frozen=True)
class OpenAICompatConfig:
    base_url: str
    api_key: str = field(repr=False)
    model: str
    provider_name: str
    timeout: float
```

Five fields, and each has exactly one job:

| Field | Consumed at | What it decides |
|---|---|---|
| `base_url` | `provider_available` `:250`, `OpenAI(base_url=...)` `:292` | whether a live attempt is even possible, and which endpoint answers |
| `api_key` | `provider_available` `:251`, `OpenAI(api_key=...)` `:291`, `_scrub` `:185-187` | availability, auth, and removal from every message |
| `model` | `_call_model` `:417`, `ProviderOutcome(model=...)` `:734` | the request body, and the `model` field the caller reports |
| `provider_name` | `_label` `:214-227` → `_present` `:209`, both WARNING sites `:591`,`:635`, `outcome.provider` `:733`, finding provenance `:574-576` | the honest label on logs, outcomes and findings |
| `timeout` | `OpenAI(timeout=...)` `:293` | per-request patience |

Three design details are load-bearing:

1. **`api_key` is `field(repr=False)`.** The config object travels into tracebacks and
   debuggers; excluding the key from `repr` is the cheapest way to keep it out of both.
2. **`provider_name` is data, not a class.** It is the only field with no protocol
   meaning, and it is what makes every log line and every finding tell the truth about
   which endpoint ran. Because the reused Phase 4 guards word their errors for Sarvam
   ("sarvam response was not JSON"), `_present` (`:191-211`) rewrites the word:
   `if label != PROVIDER_SARVAM: text = text.replace("sarvam", label).replace("Sarvam",
   label.capitalize())` (`:209-210`). Without that, a local run would emit sarvam-named
   messages — the same class of lie ADR 0004 rejects for the degrade warning.
3. **The adapter never reads `Settings`.** `provider_available` takes a config
   (`:235-252`), not settings; `app/engine.py` is the only place that turns environment
   into a config. Adding a third OpenAI-compatible endpoint is a function like
   `config_for_local` plus a test, not an adapter.

Worked mini-example. Two runs, same diff, same code:

```
config_for_sarvam(Settings(SARVAM_API_KEY="sample-not-a-real-key"))
  -> OpenAICompatConfig(base_url="https://api.sarvam.ai/v1",
                        model="sarvam-m", provider_name="sarvam", timeout=20.0)

config_for_local(Settings(LMSTUDIO_BASE_URL="http://localhost:1234/v1"))
  -> OpenAICompatConfig(base_url="http://localhost:1234/v1",
                        model="qwen2.5-coder-7b-instruct", provider_name="local",
                        timeout=120.0)
```

From `review_diff_live` (`:491`) onwards the two are indistinguishable except through
`_label(config)`. The request body differs only in `model` (`:417`); the parse, the
guards, the retry and the sorting are the same bytes of code. The observable outputs
differ in exactly three places: `outcome.provider` is `"sarvam"` vs `"local"`, the
finding text ends `(source: sarvam)` vs `(source: local)` (`:574-576`), and any warning
names the matching provider.

Precedence is not the adapter's business either. `app/engine.py:198` (`select_provider`)
implements the locked order sarvam > local > mock, and `app/engine.py:227-246` shows the
reasoning as code: a developer who sets both keys wants the hosted model, because it is
the one that works on a machine with no GPU and no LM Studio running.

### (b) The two-call retry budget

The contract: at most **two** model calls per review. Never three, never a loop, and
never an SDK-level retry underneath — `max_retries=0` is passed to the client
(`app/openai_compat_provider.py:294`) precisely so the SDK cannot multiply the wait
behind the module's back.

Walk the exact path through `review_diff_live` (`:491`):

1. **Availability** (`:516-519`). `provider_available(config)` false → raise
   `SarvamUnavailableError` naming the missing piece. No call, no retry; this becomes a
   degrade upstream.
2. **Client** (`:521-530`). `_build_client` (`:260`) raises for a blank key or URL, a
   missing `openai` SDK, or a construction failure. Not repairable — a client that was
   never built cannot be retried into existence.
3. **Prompt, once** (`:531-533`). `build_prompt(bundle)` and the two guard maps are
   computed before the first call and reused by the repair, so both attempts see
   identical inputs apart from the appended error.
4. **First call** (`:538-539`): `_call_model(client, prompt, config)`. Because
   `_JSON_MODE` defaults to `True` (`:121`), the request carries
   `response_format={"type": "json_object"}` (`:425-426`).
5. **Classify the failure.** `_call_model` raises one of two types:
   - `_RepairableCallError` (`:145`) for a `BadRequestError`, a `TypeError`/`ValueError`
     (the endpoint rejected the argument), a response with no
     `choices[0].message.content` (`:436`), or an empty completion (`:441`). The mapping
     lives in `_translate_call_error` (`:337-359`).
   - plain `SarvamUnavailableError` for credentials, permission, connection, timeout,
     rate limit, 5xx and other transport failures — the names in
     `_UNREPAIRABLE_ERROR_NAMES` (`:99-108`) matched on the exception's MRO
     (`_error_names`, `:305`).
   At `:540-543` the first is recorded as `failure` and the second is re-raised
   immediately, so an unrepairable failure never reaches the retry.
6. **Parse the first answer** (`:544-552`). If the call succeeded, `parse_findings_payload`
   runs; a `SarvamUnavailableError` from it (prose, wrong shape, nothing valid) becomes
   `failure`. Note what does *not* become a failure: a guard that drops every candidate
   returns `[]` legitimately, because an empty review is a valid live answer
   (`app/sarvam_provider.py:759-763`).
7. **The one repair gate** (`:554`). `if findings is None:` — nothing else in the module
   can trigger a second call. Inside it:
   - `logger.debug` records why (`:555`), at DEBUG, because the WARNING is reserved for
     a double failure;
   - `with _without_json_mode():` (`:557`) sets the ContextVar to `False` (`:452`) for
     the duration of the block, so `:425` skips `response_format` — the retry asks for
     the same JSON without demanding the endpoint implement the parameter;
   - the prompt is `_repair_prompt(prompt, failure)` (`:464-483`): the original message,
     a `---`, `Your previous answer was rejected: <error>`, and an explicit instruction to
     answer with a bare JSON array and no wrapper object.
8. **Second failure is terminal** (`:559-561`, `:570-572`). Either branch calls
   `_warn_after_double_failure` and returns `[]`:
   `logger.warning("%s review failed twice; returning an empty review (%s)", ...)`
   (`:591-595`). The run **stays live with zero findings** — `mode="live"`,
   `provider=config.provider_name`, no `reason`, no switch to mock. The endpoint
   answered; it answered badly. `tests/test_openai_compat_provider.py:651-667` pins
   exactly one WARNING on `reviewer.openai_compat` and none on `reviewer.sarvam`.
9. **Success** (`:574-578`). Findings are re-labelled `(source: <provider_name>)` and
   returned; `review_with_fallback` then applies `min_severity` (`:727-729`) and sorts.

Worked mini-example — a local server that does not implement `response_format`:

```
call 1: kwargs has response_format={"type":"json_object"}
        -> openai.BadRequestError (400)
        -> _translate_call_error -> _RepairableCallError
        -> failure = "local request failed: BadRequestError (400)"
call 2: _without_json_mode() -> response_format absent
        messages[1] = build_prompt(...) + "\n---\nYour previous answer was rejected: ..."
        -> "[]"
        -> parse_findings_payload -> []
total: 2 calls, 0 findings, mode="live", 0 warnings
```

And the double-failure variant, a model that answers prose twice: two calls, one WARNING
reading `local review failed twice; returning an empty review (local response was not
JSON (...) at column 1)`, findings `[]`, `mode="live"`. `docs/LMSTUDIO.md:149-157` states
the same contract for anyone replacing the model.

The reason the budget is a hard two rather than "retry until it works" is that every
extra call is unbounded latency on a webhook thread. Two is the smallest number that can
distinguish "the endpoint dislikes the request" from "the endpoint dislikes the task".

### (c) The fallback chain, and why the degraded path calls `offline_diff_findings` directly

The chain, outermost first:

```
app/cli.py:502 / app/main.py:488,697,973   Settings()
  -> app/engine.py:356                     select_provider(settings, requested=...)
       - REVIEW_MODE=mock                  -> mock selection   (:228-229)
       - SARVAM_API_KEY set                -> sarvam config    (:230-236)
       - LMSTUDIO_BASE_URL set             -> local config     (:237-243)
       - nothing                           -> mock selection   (:244-246)
  -> app/engine.py:364                     force_offline -> _mock_outcome (:365)
  -> app/engine.py:372                     mock/no config -> _mock_outcome (:373)
  -> app/engine.py:380                     review_with_fallback(bundle, config)
       -> adapter :693  config is None                -> _mock_outcome
       -> adapter :703  provider_available false      -> _mock_outcome
       -> adapter :715  review_diff_live raises       -> _mock_outcome (:716-725)
       -> adapter :731  success                       -> mode="live"
```

Every `_mock_outcome` ends in the same two functions — `_offline_findings`
(`app.mock_provider.offline_diff_findings`) or, when a category filter is set,
`_rule_review` (`app.rules.review_diff`) — imported at
`app/openai_compat_provider.py:51-52` and called at `:639`/`:641`. One WARNING is logged
per degrade, at `:635`:

```python
logger.warning("%s review degraded to the local rule engine: %s", provider_label, reason)
```

with `provider_label` being this run's honest label. `app/engine.py:307-315` then calls
`review_with_fallback(bundle, None)` for the mock cases and *replaces only the reason*,
so the router can say "provider forced to mock" while the adapter still owns the
findings and the single WARNING.

**The deviation.** The obvious implementation is to delegate: have the adapter call
`app.sarvam_provider.review_with_fallback(bundle, settings, force_offline=True)` and let
the Phase 4 module produce the mock outcome. It is rejected, deliberately, in
`docs/decisions/0004-degraded-path-calls-offline-findings-directly.md`, for two defects:

1. **It lies.** `review_with_fallback(force_offline=True)` logs
   `logger.warning("sarvam unavailable: %s", reason)` (`app/sarvam_provider.py:959`) on
   `reviewer.sarvam`. On a run whose provider is LM Studio, that message names a
   provider that was never contacted.
2. **It doubles the log.** Both modules would log, so one degrade would produce two
   WARNING lines for one event — the fastest way to train an operator to ignore the log.

The tempting fix is worse than the disease: wrapping the delegated call in
`logging.getLogger("reviewer.sarvam").setLevel(...)` is **process-global** state. In the
webhook server, two concurrent reviews would race, and one request muting
`reviewer.sarvam` would silence the other request's legitimate warnings. A grep for
`setLevel` in `app/` finds only the comment explaining why it is not used
(`app/openai_compat_provider.py:618`).

So the adapter builds the degraded outcome itself and says why, in the docstring at
`app/openai_compat_provider.py:612-620`:

> The local rule engine is invoked directly rather than through
> `app.sarvam_provider.review_with_fallback`: that path logs its own warning naming
> *sarvam*, which would be a lie on a local run and would also mean two warnings for one
> event. Delegating through it and muting its logger is worse — `setLevel` is
> process-global and would race between concurrent webhook requests.
> `offline_diff_findings` is the same function that module calls, so there is still
> exactly one mock implementation.

**This deviation is deliberate and must not be "fixed" back.** It deviates from the
Phase 5.5 written contract, which said the adapter delegates. A future reader who
"restores" the delegation will see two warnings and a sarvam-named message on a local
run, reach for `setLevel`, and reintroduce the race. ADR 0004's Consequences section says
this in as many words. The property is locked by test:
`tests/test_openai_compat_provider.py:667` asserts `warning_records(caplog,
"reviewer.sarvam") == []` for a double-failure run.

What the direct call costs: `_mock_outcome` now duplicates `sarvam_provider`'s
eight-line mock-outcome builder (compare `:603-649` with
`app/sarvam_provider.py:878-911`). That duplication is accepted because the two functions
differ in exactly the field that matters — the log line and the label — and because the
findings themselves still come from one function.

Worked mini-example. `--provider local` with `LMSTUDIO_BASE_URL` set and no server
running:

```
select_provider -> ProviderSelection(provider="local", config=<cfg>, reason="provider forced to local")
review_with_fallback(bundle, cfg)
  review_diff_live -> _call_model -> APIConnectionError
     _error_names contains "APIConnectionError" -> in _UNREPAIRABLE_ERROR_NAMES
     -> SarvamUnavailableError("local request failed: APIConnectionError")
  caught at :716 -> reason = "local request failed: APIConnectionError; local rule engine used"
  -> _mock_outcome(..., provider_label="local")
       logger.warning("local review degraded to the local rule engine: %s", reason)   # :635
       findings = _offline_findings(bundle, reason, min_severity=None)                 # :641
  -> ProviderOutcome(mode="mock", provider="mock", model="local-rules", reason=..., latency_ms=...)
```

One call attempt, one WARNING, no `reviewer.sarvam` record, and the rule engine's
findings — the same findings `--offline` would produce.

## Rebuild exercise

Build the adapter from scratch against a fake client, then diff against the tree.

1. Write `OpenAICompatConfig` as a frozen dataclass with the five fields, `api_key`
   excluded from `repr`. Write `provider_available(config)` returning `False` for
   `None`, a blank `base_url` or a blank `api_key`.
2. Write `_call_model(client, prompt, config)` with exactly three parameters. Put the
   JSON-mode flag in a `ContextVar` with a `@contextmanager` that sets it `False`, so the
   repair call can drop `response_format` without a fourth argument. Pass `max_retries=0`
   to the client and be able to say why.
3. Implement the budget: first call, classify the failure into repairable/not, one repair
   call inside the context manager with the error appended to the prompt, then — if the
   repair also fails — one `logger.warning` and `return []`. Assert in a test that the
   fake client recorded exactly two calls and that `response_format` is in
   `calls[0]` and absent from `calls[1]`.
4. Write `_mock_outcome` to call `app.mock_provider.offline_diff_findings` directly, and
   write the docstring paragraph explaining why it does not delegate. Then implement the
   delegation variant in a scratch branch, run a double-failure test with `caplog`, and
   confirm for yourself that you get two WARNING lines and one of them says *sarvam*.
   Delete the branch.
5. Wire `app/engine.py`: two config factories, the precedence order sarvam > local >
   mock, `force_offline` first, and `review_with_fallback` as the only live call site.
6. Check yourself: `grep -n "setLevel" app/` finds only a comment; `grep -c "logger.warning"
   app/openai_compat_provider.py` is 2; `python3 -m pytest tests/test_openai_compat_provider.py`
   passes with no `openai` SDK installed (the module imports lazily).

## Self-test questions

1. `_call_model` takes exactly three arguments, yet the repair retry must send a request
   without `response_format`. Name the mechanism that carries that difference, its
   definition line, and the reason a fourth parameter was rejected.
2. A `BadRequestError` on the first call costs one retry; an `APIConnectionError` on the
   first call costs a degrade. Both are SDK exceptions from the same call site. Where is
   that distinction made, and what would go wrong if `APIConnectionError` were treated as
   repairable?
3. Two prose answers in a row produce `mode="live"` with zero findings, while one
   timeout produces `mode="mock"` with rule findings. Justify both outcomes from the
   caller's point of view, and say which line in `review_diff_live` decides the first.
4. The adapter calls `offline_diff_findings` directly instead of
   `sarvam_provider.review_with_fallback(force_offline=True)`. State the two defects of
   the delegation, the one property that makes the "silence it with `setLevel`" fix
   unacceptable, and the test that locks the decision.
5. `app/sarvam_provider.py` still defines `build_prompt` and `parse_findings_payload` and
   still has a working `review_diff_live`. What does the adapter import from it, what
   calls the SDK-based path, and what would break first if that module were deleted?
