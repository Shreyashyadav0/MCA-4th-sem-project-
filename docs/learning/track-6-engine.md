# Track 6 — app/engine.py (provider selection)

## Prerequisite check

You should already be able to answer these without opening the file. If not, go
back before starting this track.

- Which module holds the 63 rules, and what does it accept as input? (Track 3:
  `app/rules.py`, `review_diff(bundle, ...)` over a parsed `DiffBundle`.)
- What is the difference between `sarvam` and `local` at the transport level?
  (Track 4: nothing — both are `OpenAICompatConfig` values handed to
  `app/openai_compat_provider.review_with_fallback`.)
- Where does the process read `SARVAM_API_KEY` from, and what does a blank value
  mean? (Track 1: `Settings` in `app/config.py`; blank counts as unset.)

One command to confirm you are in the right tree before reading:

```bash
python -c "from app.engine import PROVIDERS, select_provider; print(PROVIDERS)"
# ('sarvam', 'local', 'mock')
```

## What it does

`app/engine.py` turns a `Settings` object plus an optional provider request into
exactly one routing decision, `ProviderSelection(provider, config, reason)`, where
`config` is a ready-to-use `OpenAICompatConfig` for a live provider and `None` for
the rule engine. Its single public entry point, `review()`, applies that decision
— with `force_offline` and the `min_severity`/`categories` filters — and returns a
`ProviderOutcome` whose `mode`, `provider` and `model` fields describe what
actually ran. Nothing else in the codebase chooses a provider: the CLI, the HTTP
API and the webhook all call `review()` and read the outcome's labels.

## Why it exists

Three front ends (CLI, FastAPI, webhook) times three providers is nine code paths
that can disagree about what `auto` means, and a reviewer that reports `sarvam` on
a run that actually used the rule engine is worse than no reviewer at all. This
module collapses that matrix into one pure function plus one entry point, so
"which provider runs?" has a single answer with a single written rationale, and
the precedence rule (`sarvam` > `local` > `mock`) is testable in isolation with no
credentials, no network and no server. It also owns the *degradation* half of the
contract: a missing variable is data, not an exception, because a demo that dies
on stage because someone forgot to export a key has failed at the only thing it
was demonstrating.

## Key references

- `app/engine.py:64` — `PROVIDERS: tuple[str, ...] = ("sarvam", "local", "mock")`.
  Precedence order is the tuple order; `auto` is a request, not a provider.
- `app/engine.py:80` — `@dataclass(frozen=True)` on `ProviderSelection`: a
  decision, once made, cannot be edited by a caller.
- `app/engine.py:97` — `_non_blank()`, the definition of "set" used by both config
  builders. It mirrors `Settings.has_sarvam_key` (`app/config.py:74`) so an empty
  environment variable degrades instead of sending an unauthenticated request.
- `app/engine.py:111` — `config_for_sarvam()`: the base URL is the module constant
  `_SARVAM_BASE_URL` (`app/engine.py:73`), the timeout is the short
  `REQUEST_TIMEOUT_S`.
- `app/engine.py:133` — `config_for_local()`: needs both `LMSTUDIO_BASE_URL` and
  `LMSTUDIO_API_KEY`, and uses the long `LMSTUDIO_TIMEOUT` because a laptop model
  is slow.
- `app/engine.py:198` — `select_provider(settings, *, requested="auto")`, the only
  function that decides. `app/engine.py:227` starts the `auto` branch;
  `app/engine.py:230` is the sarvam-first check that makes sarvam win when both
  keys are set.
- `app/engine.py:251` — the forced-`sarvam` branch: a missing key returns
  `_mock_selection(...)` naming `SARVAM_API_KEY`, it does not raise.
  `app/engine.py:263` is the `local` twin, which uses `_local_missing()`
  (`app/engine.py:157`) to name the variable the user has to supply.
- `app/engine.py:276` — the one `raise ValueError` in the module, for an unknown
  provider *name* only.
- `app/engine.py:318` — `review()`, the single entry point. `app/engine.py:355`
  calls `select_provider` inside `try/except ValueError`; `app/engine.py:364`
  applies `force_offline`; `app/engine.py:372` sends `config is None` down the mock
  path; `app/engine.py:380` hands a real config to
  `review_with_fallback` (`app/openai_compat_provider.py:652`).

## The three hardest ideas

### (a) Selection is a pure function of `Settings` and never does I/O

`select_provider` reads fields off a `Settings` object and returns a dataclass. It
does not construct an HTTP client, does not open a socket, does not check whether
the endpoint is up, and does not log. That is why it can be called on every
`GET /health` request (`app/main.py:706`) without cost, and why the whole
precedence table is testable in microseconds.

The distinction that makes this work: *configuration* is the question "was a key
supplied?", *availability* is the question "does the endpoint answer?". Only the
first is the selector's business. The second belongs to
`review_with_fallback`, which degrades when the call fails. Conflating them would
put a network timeout inside a function that `/health` calls.

Worked mini-example (executed against this tree, no environment variables set):

```python
from app.config import Settings
from app.engine import select_provider

s = Settings(sarvam_api_key=None, lmstudio_base_url="http://localhost:1234/v1")
print(select_provider(s))
```

```
ProviderSelection(provider='local',
                  config=OpenAICompatConfig(base_url='http://localhost:1234/v1',
                                            model='qwen2.5-coder-7b-instruct',
                                            provider_name='local', timeout=120.0),
                  reason='LMSTUDIO_BASE_URL is set; local endpoint selected')
```

No request was made to `localhost:1234`; the config object is a value, and
`api_key` is absent from the `repr` because the dataclass declares it
`repr=False` (`app/openai_compat_provider.py:125`).

### (b) A forced provider with a missing config degrades; only a bad *name* raises

There are two different kinds of "wrong" here, and the module treats them
differently on purpose.

*Wrong configuration* is a runtime state a user can fix by exporting a variable,
and the review must still happen — so `select_provider` returns a mock selection
carrying a reason that names the variable. *A wrong name* is a programming error:
no environment change makes `--provider gpt4` meaningful, so `select_provider`
raises `ValueError` at `app/engine.py:276`.

`review()` then re-catches that `ValueError` (`app/engine.py:355`) and degrades
anyway, because on the HTTP path the name arrives from a query string and a bad
query parameter must not produce a 500. The `ValueError` still exists — it is the
contract `select_provider` publishes, and the CLI never reaches it because
`argparse` rejects the name first.

Worked mini-example (executed):

```python
select_provider(s, requested="sarvam")   # s has LMSTUDIO_BASE_URL but no SARVAM_API_KEY
# ProviderSelection(provider='mock', config=None,
#   reason='provider sarvam requested but SARVAM_API_KEY is not set; local rule engine used')

select_provider(s, requested="gpt4")
# ValueError: unknown provider 'gpt4'; expected one of auto, sarvam, local, mock
```

And through the entry point, where the same bad name is degraded rather than
raised:

```python
review(bundle, Settings(), provider="gpt4")
# mode='mock' provider='mock' model='local-rules' findings=4
# reason="unknown provider 'gpt4'; local rule engine used"
```

Note the second line of that behaviour: the reason string the caller sees is
written by `review` (`app/engine.py:360`), not by `select_provider`, because the
caller knows the more useful fact.

### (c) The selector is the only place that decides, so surfaces cannot disagree

`review()` is called from exactly three places — `app/cli.py:432` (diff mode),
`app/cli.py:516` (single-file mode) and `app/main.py:499` (the API funnel that
every endpoint goes through) — and each of them passes the request's provider
string through unchanged. There is no second `if settings.sarvam_api_key:`
anywhere in the tree.

The payoff is a property you can check mechanically: the labels a surface prints
come from the outcome, never from the surface's own guess. The CLI passes
`outcome.provider` and `outcome.model` into the renderer (`app/cli.py:452` for diff
mode, `app/cli.py:537` for single-file mode) and repeats them in the note line
(`app/cli.py:198`), and the API copies `outcome.provider` into
`ReviewResponse.provider` (`app/main.py:539`). `/health` asks the same selector
what the *next* review would use (`app/main.py:706`), so the advertised mode and
the actual mode cannot drift.

Worked mini-example — the same decision, three surfaces, one answer:

```
$ python reviewer.py samples/sample.diff        # no keys exported
mode     : mock
provider : mock
model    : local-rules

$ curl -s localhost:8000/health | jq -r .provider
mock

$ curl -s -X POST localhost:8000/review -d '{"diff": "<any diff>"}' | jq -r .provider
mock
```

If you change the precedence rule, all three change together — because they are
not three rules. That is the invariant to preserve in any refactor: grep for
`select_provider` and for `engine.review`, and expect one decision site and three
callers.

## Rebuild exercise

Write `app/engine.py` from the following spec without reading the original, then
diff your version against it.

1. `PROVIDERS` is a tuple in precedence order; `REQUEST_AUTO = "auto"` is a
   request, not a member of that tuple.
2. `ProviderSelection` is a frozen dataclass with `provider`, `config`, `reason`.
3. `config_for_sarvam(settings)` returns a config labelled `sarvam` or `None`;
   `config_for_local(settings)` returns a config labelled `local` or `None`. Both
   treat blank as unset.
4. `select_provider(settings, *, requested="auto")` normalises the request
   (strip, lower) and implements: `auto` → `REVIEW_MODE=mock` short-circuit, then
   sarvam, then local, then mock; a forced name → that provider if configured,
   otherwise mock with a reason naming the missing variable; an unknown name →
   `ValueError`.
5. `review(bundle, settings, *, provider, force_offline, min_severity, categories)`
   is the only entry point; it catches `ValueError` and degrades, honours
   `force_offline`, sends `config is None` to the mock outcome, and otherwise calls
   `review_with_fallback`.

Acceptance checks (all offline):

```bash
python -c "from app.engine import PROVIDERS; assert PROVIDERS == ('sarvam','local','mock')"
SARVAM_API_KEY= LMSTUDIO_BASE_URL=http://x/v1 python -c \
  "from app.config import Settings; from app.engine import select_provider as s; \
   assert s(Settings()).provider == 'local'"
SARVAM_API_KEY=k LMSTUDIO_BASE_URL=http://x/v1 python -c \
  "from app.config import Settings; from app.engine import select_provider as s; \
   assert s(Settings()).provider == 'sarvam'"
python -m pytest -q tests/test_api.py tests/test_cli.py
```

The last line is the real test: both surfaces assert on the labels, so a rebuild
that routes correctly but labels wrongly fails.

## Self-test questions

1. `SARVAM_API_KEY` and `LMSTUDIO_BASE_URL` are both set and the request is
   `auto`. Which provider runs, and which line of `app/engine.py` decides that?
2. `REVIEW_MODE=mock` is set and the caller passes `--provider local` with
   `LMSTUDIO_BASE_URL` configured. What runs, and why does the flag win?
3. `select_provider` raises `ValueError` in exactly one situation and degrades to
   mock in every other failure. Name both situations and say why the difference is
   deliberate — and what `review()` does with the exception.
4. Why does `config_for_local` require `LMSTUDIO_API_KEY` to be non-blank when LM
   Studio ignores the value entirely?
5. You are asked to add a fourth provider. List every function in `app/engine.py`
   that must change, and state why `app/cli.py` and `app/main.py` need edits even
   though neither contains a precedence rule.
