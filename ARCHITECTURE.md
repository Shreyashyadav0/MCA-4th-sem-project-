# Architecture

System shape of the Autonomous AI Code Reviewer & PR Assistant (v0.1.0).
Every statement here is traceable to a file in this tree; the check used for
each section is named at the end of it. For orientation and commands, read
`README.md` first.

The design can be stated in one sentence: **one review entry point, three
providers, one transport, one mock implementation, and a result that always says
what actually ran.**

---

## 1. System diagram

```
+-----------------------------------------------------------------------------+
| FRONT ENDS                                                                  |
|                                                                             |
|   shell  ----------> reviewer.py ------> app/cli.py : run / main            |
|   python -m app ---> app/__main__.py --> app/cli.py                         |
|   HTTP   ----------> app/main.py (FastAPI)                                  |
|   GitHub webhook --> POST /webhook, POST /review, GET|POST /test-review,    |
|                     /rules, /health, /docs                                  |
+-----------------------------------------------------------------------------+
                                      | diff text or one source file
                                      v
+-----------------------------------------------------------------------------+
| app/parser.py                                                               |
|   parse_diff / parse_diff_file / bundle_from_source  -->  DiffBundle        |
|   FileDiff -> Hunk -> DiffLine   (added line numbers, spans, hunk headers)  |
+-----------------------------------------------------------------------------+
                                      | DiffBundle
                                      v
+-----------------------------------------------------------------------------+
| app/engine.py : review(bundle, settings, provider=..., force_offline=...)   |
|   select_provider  -->  ProviderSelection(provider, config, reason)         |
+-----------------------------------------------------------------------------+
                 |                     |
                 | config is None      | config present
                 v                     v
+----------------------------------+   +--------------------------------------+
| DEGRADED / MOCK PATH             |   | app/openai_compat_provider.py        |
| review_with_fallback(            |   | review_with_fallback(bundle,         |
|   bundle, None, ...)             |   |                     config)          |
|                                  |   |                                      |
|   one WARNING                    |   |   review_diff_live                   |
|   -> offline_diff_findings       |   |   _build_client (openai SDK)         |
|      -> app.rules.review_diff    |   |   build_prompt                       |
|                                  |   |   POST {base_url}/chat/completions   |
|                                  |   |   parse_findings_payload             |
|                                  |   |   [1 repair retry, then empty]       |
+----------------------------------+   +--------------------------------------+
                 |                     | findings
                 |                     | SarvamUnavailableError
                 |                     |   -> degrade (left)
                 |                     v
                 v
+-----------------------------------------------------------------------------+
| app/rules.py : review_diff(bundle, min_severity=..., categories=...)        |
|   63 deterministic rules over added lines only; no network, no key          |
|   RULES / RULES_BY_ID / RULE_COUNT                                          |
+-----------------------------------------------------------------------------+
                                      | list[Finding]  (exactly 5 fields, frozen)
                                      v
+-----------------------------------------------------------------------------+
| app/parser.py : anchor_findings(bundle, findings)                           |
|   --> list[AnchoredFinding]   anchored | file_only | unanchored             |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
| app/github_client.py                                                        |
|   build_payload(max_inline=...)  -->  ReviewPayload                         |
|   render_inline_body / render_summary_body                                  |
|   fingerprint  -->  <!-- ai-code-reviewer:<16 hex> -->                      |
|   post_review(owner, repo, pr_number, payload)  -->  PostResult             |
+-----------------------------------------------------------------------------+

Result shape at each stage:
  ProviderOutcome  (mode, provider, model, findings, reason, latency_ms)
  DiffReviewResult (mode, target, files, findings, anchors, notes, verdict)
  PostResult       (ok, inline_posted, inline_demoted, marker_seen,
                    skipped_dup, error)
```

Two properties the diagram is meant to show:

- **No provider-specific live path.** Sarvam and LM Studio both enter through
  `app/openai_compat_provider.py`; the only difference is an
  `OpenAICompatConfig` built in `app/engine.py` (`config_for_sarvam`,
  `config_for_local`).
- **One mock implementation.** The degraded path calls
  `offline_diff_findings` from `app/mock_provider.py`, which calls
  `app.rules.review_diff`. There is no second rule engine anywhere.
- **Persistence is a side branch, not a stage.** `app/db.py` and
  `app/auth.py` attach at `app/main.py` only: a review is produced by the chain
  above and *then* stored. Nothing in `parser`, `rules`, `engine` or either
  provider imports them, so the pipeline drawn here runs unchanged with
  `DATABASE_PATH=` blank. The diagram therefore shows the review path, not the
  store.

*Checks:* `grep -n "def review" app/engine.py`, `grep -n "PROVIDERS" app/engine.py`,
`grep -n "def review_with_fallback" app/openai_compat_provider.py`.

---

## 2. Provider precedence

`app/engine.py` holds the whole rule. `PROVIDERS: tuple[str, ...] = ("sarvam",
"local", "mock")` — "every provider name, in precedence order"; `auto` is a
request, not a provider.

| Request | `SARVAM_API_KEY` | `LMSTUDIO_BASE_URL` | `REVIEW_MODE` | Selected | Reason string |
|---|---|---|---|---|---|
| `auto` | set | any | `auto`/`live` | `sarvam` | `SARVAM_API_KEY is set; sarvam selected` |
| `auto` | unset | set | `auto`/`live` | `local` | `LMSTUDIO_BASE_URL is set; local endpoint selected` |
| `auto` | unset | unset | `auto`/`live` | `mock` | `no SARVAM_API_KEY or LMSTUDIO_BASE_URL configured; local rule engine used` |
| `auto` | any | any | `mock` | `mock` | `REVIEW_MODE=mock; local rule engine used` |
| `sarvam` | set | any | any | `sarvam` | `provider forced to sarvam` |
| `sarvam` | unset | any | any | `mock` | `provider sarvam requested but SARVAM_API_KEY is not set; local rule engine used` |
| `local` | any | set | any | `local` | `provider forced to local` |
| `local` | any | unset | any | `mock` | `provider local requested but LMSTUDIO_BASE_URL is not set; ...` (names `LMSTUDIO_API_KEY` instead when only that is blank) |
| `mock` | any | any | any | `mock` | `provider forced to mock` |
| `--offline` | any | any | any | `mock` | `offline mode requested; local rule engine used` |

Two notes that matter more than they look:

- **Both keys set means sarvam wins.** Rationale in the module docstring: sarvam
  is the only provider reachable from a machine with no GPU and no local server,
  so a developer who sets both wants the hosted model unless they say otherwise
  — and saying otherwise is one flag (`--provider local`, `provider=local`).
- **A blank value counts as unset.** `_non_blank` in `app/engine.py` mirrors
  `Settings.has_sarvam_key`, so `SARVAM_API_KEY=` in a `.env` file degrades
  instead of attempting an unauthenticated call.

Only an unknown provider *name* raises (`ValueError` in `select_provider`); the
CLI rejects it earlier as an `argparse` usage error, and `review()` catches it
defensively so a bad query parameter cannot 500 a request.

*Checks:* `grep -n "PROVIDERS" app/engine.py`, `grep -n "def select_provider" -A 80 app/engine.py`.
Precedence was additionally executed for the four environment combinations; the
observed reasons matched the table above.

---

## 3. The fallback chain, step by step

Two functions share the work. `engine.review` decides *which* provider; the
adapter's `review_with_fallback` decides *what happens when it fails*.

1. **No provider selected.** `select_provider` returns `provider="mock"` and
   `config=None`. `engine.review` calls `review_with_fallback(bundle, None, ...)`.
   The adapter takes its `config is None` branch: one WARNING on
   `reviewer.openai_compat`, then `offline_diff_findings`. Result `mode="mock"`,
   `provider="mock"`, `model="local-rules"`. This is the no-setup path.
2. **Config present but unusable.** `provider_available(config)` is False for a
   blank `base_url` or `api_key`; the adapter degrades the same way with a reason
   naming what is missing.
3. **Live call fails, non-repairably.** `review_diff_live` raises
   `SarvamUnavailableError` for credential, permission, connection, timeout,
   rate-limit and 5xx failures — the class names are in
   `_UNREPAIRABLE_ERROR_NAMES` and matched on the exception MRO, so a test double
   can raise a lookalike without the SDK. `review_with_fallback` catches it,
   builds a one-line key-scrubbed reason, and degrades: `mode="mock"`, rule-engine
   findings, **exactly one WARNING** per degraded run.
4. **First attempt is repairable.** A `BadRequestError` (endpoint rejected
   `response_format={"type": "json_object"}`) or a parse/validation failure costs
   exactly one repair retry, with the error appended to the prompt and
   `response_format` dropped (`_repair_prompt`, `_without_json_mode`).
5. **Repair fails too.** `_warn_after_double_failure` logs one WARNING and
   `review_diff_live` returns `[]`. The run **stays live with zero findings** —
   it does not switch to mock, because the endpoint answered; it answered badly.
   Result `mode="live"`, `provider=config.provider_name`, `model=config.model`,
   0 findings.
6. **Live succeeds.** Findings are re-labelled with provenance —
   `f"{issue} (source: {provider_name})"` — then `min_severity` is applied and
   the list is severity-sorted.

The budget is therefore at most **two model calls per review**, and the invariant
is: a run either produces findings, or says it is degraded, or says it is live and
empty. It never raises to the caller for any of these reasons.

| Situation | `mode` | `provider` | findings | log |
|---|---|---|---|---|
| nothing configured | `mock` | `mock` | rule engine | 1 WARNING |
| forced provider, config missing | `mock` | `mock` | rule engine | 1 WARNING |
| 401 / 403 / timeout / 5xx / connection | `mock` | `mock` | rule engine | 1 WARNING |
| unparseable answer, repair parses | `live` | `sarvam`\|`local` | model's | — |
| unparseable answer twice | `live` | `sarvam`\|`local` | none | 1 WARNING |
| success | `live` | `sarvam`\|`local` | model's | — |

*Checks:* `grep -n "def review_with_fallback" -A 90 app/openai_compat_provider.py`,
`grep -n "_UNREPAIRABLE_ERROR_NAMES\|_REPAIRABLE_ERROR_NAMES" app/openai_compat_provider.py`.
Rows 3 and 5 were executed against the shipped adapter with scripted fake
clients: a `401` produced `mode=mock` with the 4 rule findings of
`samples/sample.diff` and one WARNING; two prose answers produced `mode=live`
with 0 findings and one WARNING.

---

## 4. Frozen interfaces

These names are the contract. They are what the tests patch and what the front
ends call; renaming one is a breaking change, not a refactor.

### `app/models.py` — the output contract
`Severity` (LOW/MEDIUM/HIGH/CRITICAL, `.rank`), `AnchorStatus`
(ANCHORED/FILE_ONLY/UNANCHORED), `Finding` (frozen, `extra="forbid"`, exactly
five fields: `file`, `line`, `severity`, `issue`, `suggested_fix`; `line` is
`"42"` or ascending `"42-45"`), `AnchoredFinding` (`finding`, `status`,
`hunk_header`, `detail`), `ReviewResult` (`mode`, `target`, `findings`, `notes`,
computed `verdict`), plus `severity_counts`, `verdict_for`, `sort_findings`.

Anchoring wraps a finding rather than extending it: anchoring is review metadata
(can GitHub attach this comment?), not part of the finding contract.

### `app/parser.py` — diff in
`parse_diff(raw, *, source) -> DiffBundle`, `parse_diff_file(path)`,
`bundle_from_source(path, source)`, `anchor_findings(bundle, findings) ->
list[AnchoredFinding]`, `normalize_path(raw)`, `DiffParseError`. Models:
`DiffLine`, `Hunk`, `FileDiff` (`path`, `change`, `hunks`, `added_line_numbers`,
`added_spans`, `added_line_count`, `hunk_for_line`), `FileSummary`, `DiffBundle`
(`files`, `file_for`, `summaries`, `files_changed`, `added_line_count`,
`is_empty`), `DiffReviewResult` (`mode`, `target`, `files`, `findings`, `anchors`,
`notes`, `sorted_anchors`, `counts`, `verdict`, `to_json`).

### `app/rules.py` — deterministic review
`Rule` (frozen dataclass: `id`, `title`, `category`, `owasp`, `severity`,
`check`), `RuleHit` (`issue`, `suggested_fix`), `RuleCategory` (ten values:
secrets, injection, deserialisation, crypto, auth, config, reliability, quality,
complexity, style), `LineContext` (`path`, `lineno`, `text`, `added`, `index`,
`scan_text`, `indent`, `is_test_file`), `RULES`, `RULES_BY_ID`, `RULE_COUNT`,
`review_diff`, `review_lines`, `rule_ids`, `rule_by_id`, `shannon_entropy`.
`RULE_COUNT` is 63.

### `app/mock_provider.py` — the offline paths
`offline_review(target, source, reason, *, min_severity) -> ReviewResult`,
`offline_diff_findings(bundle, reason, *, min_severity) -> list[Finding]`,
`ENGINE_NOTE`. Both delegate to `app.rules.review_diff`; the module name and
signatures survive from Phase 1/2 on purpose.

### `app/sarvam_provider.py` — the Phase 4 layer and the reused guards
`PROVIDER_NAME`, `SarvamUnavailableError`, `LLMFinding`, `ProviderOutcome`
(`mode`, `provider`, `model`, `findings`, `reason`, `latency_ms`),
`provider_available`, `build_prompt`, `parse_findings_payload`, `review_diff_live`,
`review_with_fallback`. Phase 5.5 imports `LLMFinding`, `ProviderOutcome`,
`SarvamUnavailableError`, `build_prompt` and `parse_findings_payload` from here
rather than reimplementing them.

### `app/openai_compat_provider.py` — the single transport
`OpenAICompatConfig` (frozen dataclass: `base_url`, `api_key` with
`repr=False`, `model`, `provider_name`, `timeout`), `PROVIDER_NAME`,
`PROVIDER_LOCAL`, `PROVIDER_SARVAM`, `provider_available`, `review_diff_live`,
`review_with_fallback`, and the re-exported guards above. Seam: `_build_client`
is the only place the `openai` SDK is imported, and the only thing tests patch.

### `app/engine.py` — routing
`PROVIDERS`, `REQUEST_AUTO`, `PROVIDER_MOCK`, `ProviderSelection` (frozen
dataclass: `provider`, `config`, `reason`), `config_for_sarvam`,
`config_for_local`, `select_provider`, `review`.

### `app/github_client.py` — publishing
`fingerprint(finding) -> str`, `render_inline_body(finding)`,
`render_summary_body(payload)`, `build_payload(findings, diff_files, *,
max_inline) -> ReviewPayload`, `post_review(owner, repo, pr_number, payload, *,
token, commit_id) -> PostResult`, `github_available(token)`; dataclasses
`InlineComment`, `ReviewPayload`, `PostResult`; constants `ANCHORED`,
`FILE_ONLY`, `UNANCHORED`, `COMMENT_MARKER_PREFIX`, `DEFAULT_EVENT`; errors
`GitHubError`, `GitHubAuthError`, `GitHubNotFoundError`, `GitHubRateLimitError`,
`GitHubUnavailableError`. Everything that decides *what the comment says* is a
pure function; everything that talks to GitHub is a patchable seam
(`_build_github_client`).

### `app/db.py` — the persistence store
`SCHEMA_SQL` (one DDL string, six tables), `Database` (`init_schema`,
`store_review`, `list_reviews`, `get_review`, `store_pr_post`,
`store_benchmark_run`, `create_user`, `list_users`, `set_user_active`,
`authenticate`, `seed_defaults`, `stats`, `close`), `get_database(settings=None)`
as the process-wide accessor, `hash_api_key(api_key) -> str` (SHA-256, the only
place a key is converted), `DEFAULT_DB_PATH`, `ROLE_NAMES`, `ROLE_PERMISSIONS`,
`SEED_ADMIN_USERNAME`, `SEED_ADMIN_EMAIL`. Parameterised `text()` statements
throughout; every write inside one `engine.begin()` transaction. A blank
`DATABASE_PATH` switches persistence off, and `GET /health` then reports
`database: disabled`.

### `app/auth.py` — role-based access control
`UserContext` (frozen dataclass: user id, username, role, permissions),
`require(role)` — the FastAPI dependency factory — and `auth_enabled()`. The flag
is read per request, so `API_AUTH_ENABLED` takes effect on the next call rather
than at import; with it false every route behaves exactly as it did before the
module existed. 401 for a missing or unknown key, 403 for a role that is too
weak, 503 when the user store is unreachable.

### `app/config.py` — the credential boundary
`Settings` (pydantic-settings, `.env`, every field defaulted, `extra="ignore"`),
`ReviewMode`. "Nothing else in the codebase reads `os.environ`."

### `app/cli.py`, `app/main.py`, `reviewer.py`
`build_parser`, `read_source`, `looks_like_diff`, `parse_post_target`, `run`,
`main`, `ReviewInputError`; `app`, `render_comment`, `ReviewRequest`,
`ReviewResponse`, `ReviewStats`, `PostingInfo`, `HealthResponse`, `RuleInfo`;
`reviewer.py` is thirteen lines that call `app.cli.main`.

*Checks:* `grep -n "^__all__" -A 20 app/*.py`, `grep -n "^def \|^class " app/*.py`.

---

## 5. The anchoring model

A finding is a claim about a line. GitHub only accepts an inline comment on a
line that is part of the diff, so the claim has to be placed before it can be
published. `anchor_findings` assigns one of three statuses, stored on
`AnchoredFinding.status` and never inside `Finding`:

| Status | Condition | Consequence |
|---|---|---|
| `anchored` | the file is in the diff **and** the reported range touches an added line | eligible for an inline comment (`side="RIGHT"`, `line` = end of range) |
| `file_only` | the file is in the diff, but the reported line was not changed | summary only — GitHub would drop or 422 the inline comment |
| `unanchored` | the file is not in the diff at all | summary only, under "General findings" |

Why it exists as a separate axis: the model is an unreliable narrator about line
numbers. `parse_findings_payload` already drops files that are not in the diff and
snaps line numbers to the nearest added line (or drops the finding when the file
added nothing), but the *rule engine* reports on added lines only by
construction, and a future provider may not. Anchoring is the single, provider-
agnostic check that decides "can this be attached?", and it runs after the review
regardless of who produced it. Keeping it out of `Finding` is what lets the five-
field contract stay frozen while review metadata grows.

Measured on `samples/sample.diff`:

```
app/db.py line 3   -> anchored    | added line: 3
app/db.py line 1   -> file_only   | app/db.py is in the diff but line 1 was not changed; GitHub would drop this inline comment
nope.py   line 1   -> unanchored  | nope.py is not part of this diff
```

Downstream, `build_payload` turns `anchored` findings into inline comments up to
`max_inline` (default 30, `GITHUB_MAX_INLINE`, 1-100) and pushes everything else
— `file_only`, `unanchored`, and anchored findings past the cap — into the
summary. A comment demoted by a 422 at post time is rebuilt into that same
summary, so a rejected inline comment never fails the post.

*Checks:* `grep -n "def anchor_findings" -A 55 app/parser.py`,
`grep -n "def build_payload" -A 70 app/github_client.py`.

---

## 6. Idempotency marker

Every body the poster generates ends with a marker line:

```
<!-- ai-code-reviewer:<16 lowercase hex> -->
```

`fingerprint(finding)` is the first 16 hex characters of SHA-256 over exactly four
identity fields, joined by `\x1f`: `file`, `line`, `severity`, and the
whitespace-normalised `issue`. The suggested fix is deliberately excluded, so
rewording the advice does not make the same finding look new.

Flow: one listing call reads the PR's existing comment bodies (paging further only
when GitHub reports more pages, at most 5), and if the summary marker is already
present the whole post is skipped — `PostResult(ok=True, marker_seen=True,
skipped_dup=True)` and the CLI exits 0. The marker hashes the findings, not the
commit, so an identical re-review of a later push is treated as a duplicate on
purpose. Measured:

```
$ python -c "... render_inline_body(Finding(...))"
<!-- ai-code-reviewer:f4d4dd288a329952 -->
```

Known limitation, stated in the module docstring and worth repeating: the marker
is a public HTML comment, so anyone who can comment on the PR can suppress a
review by pasting one. Closing that needs author filtering on the listing or an
HMAC-derived marker — both change the frozen marker format, so it is a deliberate
open decision, not a silent change.

*Checks:* `grep -n "COMMENT_MARKER_PREFIX\|def fingerprint" app/github_client.py`,
`grep -n "def _get_existing_markers" -A 40 app/github_client.py`.

---

## 7. Module dependency table

`app` = intra-package import; `ext` = third-party or stdlib at module import
time. `openai` and `sarvamai` are imported lazily inside the client builders, so
importing any module works without either SDK installed.

| Module | Depends on (in-package) | External | Role |
|---|---|---|---|
| `app/__init__.py` | — | — | `__version__` |
| `app/config.py` | — | pydantic, pydantic-settings | credential boundary; the only reader of the environment |
| `app/models.py` | — | pydantic, enum, re | frozen output contract |
| `app/parser.py` | `app.models` | pydantic, re, pathlib | diff parsing + anchoring |
| `app/rules.py` | `app.models`, `app.parser` | re, math, dataclasses, enum | 63 deterministic rules |
| `app/mock_provider.py` | `app.models`, `app.parser`, `app.rules` | pathlib | the offline paths |
| `app/sarvam_provider.py` | `app.config`, `app.mock_provider`, `app.models`, `app.parser`, `app.rules` | pydantic, httpx, json, re, logging, sarvamai (lazy) | Phase 4 live layer + reusable guards |
| `app/openai_compat_provider.py` | `app.mock_provider`, `app.models`, `app.parser`, `app.rules`, `app.sarvam_provider` | openai (lazy), contextvars, dataclasses, logging | the single transport |
| `app/engine.py` | `app.config`, `app.models`, `app.openai_compat_provider`, `app.parser`, `app.rules` | dataclasses | provider selection + `review()` |
| `app/github_client.py` | `app.config`, `app.models`, `app.parser` | httpx, hashlib, dataclasses, math, re, time | PR posting |
| `app/cli.py` | `app`, `app.config`, `app.github_client`, `app.mock_provider`, `app.models`, `app.parser`, `app.rules`, `app.sarvam_provider` | argparse, httpx, logging, re, sys | CLI |
| `app/db.py` | `app.auth` (function-local import), `app.config`, `app.models` | sqlalchemy (+ `.engine`, `.pool`), hashlib, threading, logging, datetime, pathlib | persistence and identity store: `SCHEMA_SQL` (six tables), review/finding/post/benchmark writes, users, `hash_api_key` |
| `app/auth.py` | `app.config`, `app.db` | fastapi, sqlalchemy.exc, dataclasses, collections.abc | role-based access control: `UserContext`, `require(role)`, `auth_enabled` — opt-in through `API_AUTH_ENABLED` |
| `app/main.py` | `app`, `app.auth`, `app.config`, `app.db`, `app.github_client`, `app.mock_provider`, `app.models`, `app.parser`, `app.rules` | fastapi, pydantic, hmac, hashlib, httpx, logging, pathlib, sqlalchemy.exc, time | HTTP API + webhook; stores each review and serves `/reviews` and `/stats` from `app/db.py` |
| `app/__main__.py`, `reviewer.py` | `app.cli` | — | entry points |

Read the table for its shape, not its length: dependencies point **inward** to
`models`, `parser` and `rules`; nothing below `engine` imports a front end; and
`engine` is the only module that knows both the adapter and the rule engine.

`app/db.py` and `app/auth.py` are a **side branch, not part of the review
pipeline**: nothing in `parser`, `rules`, `engine` or either provider imports
them, so a review runs identically with persistence disabled (`DATABASE_PATH=`).
They are reached only from `app/main.py`, after a review has already been
produced. The one import between them runs in both directions — `auth` imports
`db` at module level for the `Database` type, and `db` imports `auth` inside
`Database.authenticate` (`from app.auth import UserContext  # local import: auth
imports this module`) — which is why the local import exists and why the cycle is
deliberate rather than accidental.

*Check:* an AST pass over `app/*.py` and `reviewer.py` collecting `Import` and
`ImportFrom` nodes, printed as `module: app=[...] ext=[...]`.

---

## 8. Why the degraded path calls `offline_diff_findings` directly

`app/openai_compat_provider.py: _mock_outcome` calls
`app.mock_provider.offline_diff_findings` instead of delegating to
`app.sarvam_provider.review_with_fallback(force_offline=True)`. Three reasons,
from that function's docstring:

1. The sarvam wrapper logs its own WARNING naming *sarvam*. On a local or
   no-provider run that message would be a lie about which provider failed.
2. Going through it would log **two** warnings for one event, breaking the
   one-WARNING-per-degraded-run invariant.
3. Delegating and then muting its logger is worse: `setLevel` is process-global
   and would race between concurrent webhook requests.

`offline_diff_findings` is the same function the sarvam wrapper calls, so the
"exactly one mock implementation" property survives the shortcut.

The decision record this implements is
`docs/decisions/0004-degraded-path-calls-offline-findings-directly.md`, which is
present in this tree (`ls docs/decisions` lists seven records, `0001`–`0007`). The
three reasons above are also readable from
`app/openai_compat_provider.py: _mock_outcome`.

*Checks:* `grep -n "def _mock_outcome" -A 45 app/openai_compat_provider.py`,
`ls docs/decisions`.

---

## 9. Where the guarantees are enforced

| Guarantee | Enforced in |
|---|---|
| A missing credential is data, never an exception | `app/config.py: Settings`, `app/engine.py: select_provider` |
| Exactly one WARNING per degraded run | `app/openai_compat_provider.py: _mock_outcome`, `_warn_after_double_failure` |
| The API key never reaches a log, reason, finding or comment | `_scrub`/`_present` in both providers; `api_key` with `repr=False` |
| At most two model calls per review | `review_diff_live` (attempt + one repair) |
| The model cannot invent files or lines | `parse_findings_payload` (allowed files, snapped added lines) |
| A finding is exactly five fields | `Finding` with `extra="forbid"`, `frozen=True` |
| No test touches the network | fake-client seams; `scripts/verify_offline.py` blocks sockets and re-runs the suite |
| GitHub never sees a 5xx from us | `post_review` converts every failure into `PostResult.error` |
| A database problem never changes an HTTP response | every `Database` call in `app/main.py` is wrapped in `try/except` and logs one WARNING on `reviewer.db`; `/health` reports `database: ok|disabled|error` |
| Authentication is opt-in, never implied | `app/auth.py: auth_enabled` reads `API_AUTH_ENABLED` per request; false short-circuits to an anonymous context |

Verification used for this document:

```
$ python -m pytest -q tests
637 passed, 1 skipped in 39.75s

$ python scripts/verify_offline.py
637 passed, 1 skipped in 19.93s

$ grep -n "def review(" app/engine.py
318:def review(

$ grep -n "PROVIDERS: tuple" app/engine.py
64:PROVIDERS: tuple[str, ...] = ("sarvam", "local", "mock")
```
