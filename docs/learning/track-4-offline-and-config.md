# Track 4 — app/mock_provider.py and app/config.py

## Prerequisite check

Run these four commands from the repository root. Each one should print something you
can already explain before you start reading.

```bash
python3 -c "from app.rules import RULES; print(len(RULES))"                  # 63
python3 -c "from app.mock_provider import ENGINE_NOTE; print(ENGINE_NOTE)"
grep -n "os.environ" app/*.py | grep -v '"""' | grep -v '^app/rules.py'
grep -n "class Settings" -A 50 app/config.py
```

You should be able to answer, from the output alone:

- How many settings fields exist, and which of them are `str | None` credentials.
- How many `has_*` properties exist on `Settings`, and what each one guards.
- Why the `grep` for `os.environ` finds nothing outside prose and rule fixtures.

`pydantic` and `pydantic-settings` must be importable (`pip install pydantic
pydantic-settings`); nothing here needs a network, a key or the `sarvamai` SDK.

## What it does

`app/config.py` is the only module in the package that reads the process environment:
it declares every runtime setting as a pydantic-settings field with a safe default and
exposes two `has_*` properties that answer "is this credential present" without ever
raising. `app/mock_provider.py` is the deterministic offline review path: it turns
either one source file or an already-parsed diff into findings produced by `app.rules`,
with no network call and no API key. Between them they fix the two assumptions the rest
of the codebase is allowed to make — settings always arrive as a validated object, and a
review can always be produced without a model.

## Why it exists

The project has to survive three hostile conditions: a machine with no credentials, a
machine with no network, and a demo that is being watched. Any of those turns "the model
is unavailable" from an exceptional state into the normal state, so the code cannot be
allowed to treat a missing key as an error. `Settings` therefore types both credentials
as `str | None` with `default=None` (`app/config.py:30`, `:32`) and the module docstring
states the rule outright: a missing key is data, the reviewer switches mode, never an
exception (`app/config.py:3-5`).

The same pressure produces `app/mock_provider.py`. It is the module that answers "the
LLM is not available, what do you do instead?", and since Phase 3 the answer is the real
rule engine rather than a hardcoded fixture. The module keeps its Phase 1/2 name and
signatures because it is still exactly one thing — the offline path — even though the
findings now come from `app.rules` (`app/mock_provider.py:3-7`).

Two consequences worth noticing now, because they constrain everything in Track 5:

- There is exactly one implementation of "review this diff without a model". Every
  provider's degraded path ends up in `review_diff`, and `ENGINE_NOTE` is derived from
  the rule registry rather than written by hand.
- Configuration is not consulted at import time. `Settings()` is constructed per entry
  point — `app/cli.py:502`, `app/main.py:488`, `:697`, `:973`, and lazily inside
  `app/github_client.py:617`, `:632`, `:1007` — so a test can construct a `Settings`
  with any field set without touching the real environment.

## Key references

- `app/config.py:23` — `model_config = SettingsConfigDict(...)`: `.env` is loaded, field
  matching is case-insensitive, and unknown variables are ignored rather than fatal
  (`extra="ignore"`), so a stray variable in a deployment cannot crash startup.
- `app/config.py:30` — `sarvam_api_key: str | None = Field(default=None, ...)`: the
  optional type *is* the design statement. The same shape is used for `github_token`
  (`:32`) and `github_webhook_secret` (`:39`).
- `app/config.py:43` — `review_mode: Literal["auto", "live", "mock"] = "auto"`: a closed
  set of three values, defaulting to the one that decides at runtime instead of at
  deploy time.
- `app/config.py:75` — `has_sarvam_key`: returns `True` only for a non-blank key, so
  `SARVAM_API_KEY=` (empty in `.env`) counts as missing.
- `app/config.py:79` — `resolve_mode`: the degrade-not-raise decision point;
  `force_offline` wins, then `REVIEW_MODE=mock`, then a missing key, else `"live"`
  (`:88-92`).
- `app/mock_provider.py:23` — `ENGINE_NOTE`, an f-string computed from `len(RULES)` at
  import time, so the note cannot drift from the registry.
- `app/mock_provider.py:46` — `bundle_from_source(target, source)`: a whole file is
  wrapped as one all-added hunk so diff rules apply unchanged to a single-file review.
- `app/mock_provider.py:75` — the entire body of `offline_diff_findings` is one call to
  `review_diff(bundle, min_severity=min_severity)`; the module adds no checks of its own.

## The three hardest ideas

### (a) Credentials are read once, at the boundary, and absence is data

`Settings` has eleven fields. Nine have non-credential defaults; two are nullable
credentials; and the two `has_*` properties are the only sanctioned way to ask whether a
credential is usable:

| Field | Line | Type / default | Role |
|---|---|---|---|
| `sarvam_api_key` | 30 | `str \| None = None` | Sarvam credential |
| `sarvam_model` | 31 | `str = "sarvam-m"` | model id |
| `github_token` | 32 | `str \| None = None` | GitHub credential |
| `github_max_inline` | 33 | `int = 30`, `gt=0, le=100` | inline-comment budget |
| `github_webhook_secret` | 39 | `str \| None = None` | HMAC secret |
| `review_mode` | 43 | `Literal["auto","live","mock"] = "auto"` | mode request |
| `request_timeout_s` | 47 | `float = 20.0`, `gt=0` | hosted-endpoint timeout |
| `lmstudio_base_url` | 48 | `str \| None = None` | local endpoint |
| `lmstudio_model` | 55 | `str = "qwen2.5-coder-7b-instruct"` | local model id |
| `lmstudio_api_key` | 59 | `str = "lm-studio"` | local bearer key |
| `lmstudio_timeout` | 63 | `float = 120.0`, `gt=0` | local timeout |

The two properties are not convenience wrappers around `if key:`. They encode a rule
that has to be identical everywhere: **blank equals absent**.

```python
# app/config.py:75-77
@property
def has_sarvam_key(self) -> bool:
    """True only for a non-blank key; an empty env var counts as missing."""
    return bool(self.sarvam_api_key and self.sarvam_api_key.strip())
```

`has_webhook_secret` (`:70-72`) is the same test for the HMAC secret, and it is what
makes signature checking optional rather than mandatory: `app/main.py:975` wraps
verification in `if settings.has_webhook_secret:`, so an unconfigured deployment accepts
unsigned webhooks instead of rejecting every one of them.

Why it is shaped this way, in three parts:

1. **One place reads the environment.** `Settings` is the boundary; every other module
   receives a `Settings` object. A `grep -rn "os.environ\|getenv" app/` finds no live
   read outside `app/config.py` — the remaining hits are the docstring at
   `app/config.py:5` and rule fixtures in `app/rules.py` that *detect* `os.environ` in
   reviewed code. That is what makes the whole configuration surface testable by
   constructing an object.
2. **Absence must not be an exception**, because the common case is absence. If a
   missing key raised, `import app.main` on a developer laptop with no `.env` would
   fail, and every test would need a key.
3. **The decision is pushed to a function, not a field.** `resolve_mode`
   (`app/config.py:79-92`) is the single place that converts presence into behaviour,
   and it degrades in both directions: `REVIEW_MODE=live` without a key still returns
   `"mock"` (`:90-91`).

Worked mini-example. Take `.env` containing `SARVAM_API_KEY=` (present, empty) and
nothing else:

```
Settings().sarvam_api_key        -> ""            # a real string, not None
Settings().has_sarvam_key        -> False         # because .strip() is empty
Settings().resolve_mode()        -> "mock"        # app/config.py:90-91
```

Now the same run with `SARVAM_API_KEY=sample-not-a-real-key`: `has_sarvam_key` is
`True`, `resolve_mode()` is `"live"` — and whether a network call actually happens is
still not decided here. That is `app/engine.py:198` (`select_provider`), which builds a
config and lets the adapter decide (Track 5).

One detail the table makes visible: the "is it configured" test exists in three
spellings in the tree. `Settings.has_sarvam_key` (`app/config.py:75`),
`engine._non_blank` (`app/engine.py:97`, applied to `sarvam_api_key` and the
`lmstudio_*` pair), and an inline truthiness test for the GitHub token
(`github_token="configured" if settings.github_token else "missing"`, `app/main.py:704`) — there is no `has_github_token`. They all implement the same
blank-equals-absent rule; only the spelling differs.

### (b) `offline_diff_findings` delegates to the rule engine instead of reimplementing checks

The function is two lines of substance:

```python
# app/mock_provider.py:59, :75
def offline_diff_findings(bundle, reason, *, min_severity=None) -> list[Finding]:
    return review_diff(bundle, min_severity=min_severity)
```

Everything the name promises — every check, every severity, every ordering rule — lives
in `app/rules.py:1574` (`review_diff`). `app/mock_provider.py` imports it at `:19` and
adds nothing but a signature: `reason` is accepted and documented as "recorded by the
caller" (`:69`) because the function has nowhere to put it — it returns findings, not a
`ReviewResult`.

Why delegate rather than own the checks:

- **One definition of "wrong".** The rule engine is also the thing the benchmark harness
  scores and the thing `/rules` advertises at runtime (`app/main.py` health and rule
  listing both read `RULES`). A second copy of the checks inside the mock provider would
  be a second answer to "what is a finding", and the two would diverge on the first
  rule change.
- **The offline path is the fallback for the live path.** `app/sarvam_provider.py:899`
  and `app/openai_compat_provider.py:641` both call this function when a live review
  fails. If it held its own logic, a degraded review and a `--offline` review would be
  two different reviews, and the difference would only show up in production.
- **Filtering stays where the filter can see.** `offline_diff_findings` has no
  `categories` parameter, because a category filter must run *inside* the rule engine
  (categories are a property of a rule, not of a `Finding`). Both callers handle that by
  calling `review_diff` directly when `categories` is set — `app/sarvam_provider.py:901`
  and `app/openai_compat_provider.py:639` — with a comment saying "same rules, same
  order".

Worked mini-example. Add one rule to `app/rules.py` with
`@_rule("PY999", Severity.HIGH, "example", RuleCategory.SECURITY, "A03")` on a check
that fires on `print(`. With no edit anywhere else:

- `len(RULES)` becomes 64, so `ENGINE_NOTE` (`app/mock_provider.py:24`) changes on next
  import.
- A `--offline` CLI review reports the new finding, because the CLI reaches
  `review_diff` through the adapter's degraded path.
- A review that degraded after a 401 reports the same new finding, through the same
  call.
- The `/rules` endpoint lists it, and the benchmark harness scores against it.

That is what the delegation buys: one edit, one behaviour, everywhere.

The one part of the module that is *not* delegation is `offline_review`
(`app/mock_provider.py:28`), which additionally does the file-to-bundle conversion
(`:46`), builds the notes list (`:48`) and wraps the result in a `ReviewResult` with
`mode="mock"`. Note that this function has no caller in the tree — `grep -rn
"offline_review"` outside the module returns nothing, including tests. It is retained
for the Phase 1/2 single-file surface; the diff-shaped function is the one on every live
code path.

### (c) `ENGINE_NOTE` exists to make an offline review unmistakable, and it is computed

```python
# app/mock_provider.py:23-25
ENGINE_NOTE = (
    f"local rule engine: {len(RULES)} deterministic rules, no network, no API key"
)
```

Evaluated at import, the string is:

```
local rule engine: 63 deterministic rules, no network, no API key
```

The reason it exists is a reporting problem, not an engineering one. A degraded review
and a live review produce the same `ReviewResult` shape, and a reader of the CLI output
or the JSON body cannot tell them apart from the findings alone — rule findings are
plausible enough to pass for model output. The note states three facts in one line: what
produced the findings, that it is deterministic, and that neither network nor credential
was involved. The `mode` field says `"mock"`; `ENGINE_NOTE` says *why that is fine*.

The count is interpolated rather than typed for the same anti-drift reason as (b). A
hardcoded "40 rules" would be wrong the first time a rule was added, and wrong in the
most damaging place — the line a reader trusts to tell them what ran.

Where it surfaces, and where it does not:

| Surface | Line | Notes list |
|---|---|---|
| `offline_review` | `app/mock_provider.py:48` | `["mock mode: <reason>", ENGINE_NOTE]` |
| CLI | `app/cli.py:200` | `["mock mode: <reason>", ENGINE_NOTE]` |
| HTTP API | `app/main.py:512` | `[ENGINE_NOTE, "mock mode: <reason>"]` |
| live run | `app/cli.py:197-199` | replaced by `"live review: <provider>/<model> in <ms> ms"` |

Two things to notice in that table. First, the note is on the *mock* branch only; a live
run gets a different line naming provider, model and latency, which is the honest
counterpart. Second, the ordering is not consistent: the CLI puts the reason first and
the note second, the API puts the note first. Nothing asserts either order, and no test
in the tree asserts the `ENGINE_NOTE` text at all — `grep -rn "local rule engine:
63\|ENGINE_NOTE" tests/` is empty, while the *reason* strings are asserted extensively
(e.g. `tests/test_sarvam_provider.py:269`, `:310`, `:324`). If you change the note's
wording, no test will tell you.

Worked mini-example. `REVIEW_MODE=mock` with a valid key present, reviewing
`samples/sample.diff` through the CLI: `resolve_mode` is never consulted by the router
(`app/engine.py:228` checks `review_mode` directly), the selection is `mock` with reason
`"REVIEW_MODE=mock; local rule engine used"`, and the printed notes are exactly:

```
mock mode: REVIEW_MODE=mock; local rule engine used
local rule engine: 63 deterministic rules, no network, no API key
```

Delete the key and rerun: the findings are identical and the first line becomes
`mock mode: no SARVAM_API_KEY or LMSTUDIO_BASE_URL configured; local rule engine used`.
Only the reason moves; the engine note is a constant of the build.

## Rebuild exercise

Reconstruct both modules in an empty directory, then check yourself against the tree.

1. Write `app/config.py` from scratch: a `Settings(BaseSettings)` with the eleven fields
   above, `env_file=".env"`, `extra="ignore"`, `case_sensitive=False`. Type both
   credentials `str | None` with `default=None`. Add `has_sarvam_key` and
   `has_webhook_secret` as properties, not fields, and make both strip before testing.
   Add `resolve_mode(force_offline=False)` returning the `ReviewMode` literal.
2. Prove the boundary holds: `grep -rn "os.environ\|getenv" app/` must show no live read
   outside your new module.
3. Write `app/mock_provider.py` with `offline_review`, `offline_diff_findings` and
   `ENGINE_NOTE`. Import `review_diff` and `RULES` from `app.rules`; do not write a
   single check. Make `offline_review` wrap its input with `bundle_from_source` and
   return `ReviewResult(mode="mock", ...)` with the two-element notes list.
4. Verify three properties without running the network path:
   - `ENGINE_NOTE` equals `f"local rule engine: {len(RULES)} deterministic rules, no
     network, no API key"` after you add a dummy rule (the count moves).
   - `Settings(sarvam_api_key="   ").has_sarvam_key is False`.
   - `Settings(review_mode="live").resolve_mode()` returns `"mock"` with no key.
5. Then diff your version against the tree and account for every difference. The
   interesting ones are the ones you did not think of: `extra="ignore"`, the
   `Field(..., gt=0, le=100)` constraints on `github_max_inline`, and the fact that
   `offline_diff_findings` takes a `reason` it never uses.

## Self-test questions

1. `Settings` types `sarvam_api_key` as `str | None` with `default=None`, while
   `lmstudio_api_key` is a plain `str` defaulting to `"lm-studio"`. What property of the
   two providers forces that asymmetry, and what breaks if you give the Sarvam key a
   non-empty default?
2. `resolve_mode` returns `"mock"` when `REVIEW_MODE=live` and no key is set. Which
   other module overrides that decision, at which line, and why is the override not a
   bug?
3. `offline_diff_findings` accepts `categories=None` implicitly by not accepting the
   parameter at all, yet both callers can still filter by category. Where does the
   filter run, and why can it not run over the returned findings?
4. `ENGINE_NOTE` interpolates `len(RULES)` instead of naming a count. Name two
   behaviours that change automatically when a rule is added, and one artefact in the
   tree that would go stale if the count were hardcoded.
5. The API and the CLI both emit `ENGINE_NOTE`, in different positions relative to the
   `mock mode:` reason line. What in the repository would catch a change to the note's
   wording, and what would not?
