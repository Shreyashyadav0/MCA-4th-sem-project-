# 3. System Design

This chapter describes how the Autonomous AI Code Reviewer and PR Assistant is
decomposed, how its data is constrained, how one review request travels through
the system, what the user sees, and how the design defends itself against bad
input and unavailable services. Every structural claim here is traceable to a
module in `app/`; the code itself is quoted in chapter 4.

## 3.1 Design goals and constraints

Five goals shaped every later decision, and they conflict often enough that
naming them first is worth the space.

**G1 — Availability must not depend on a third-party API.** A reviewer that
cannot run is worthless, so a missing credential is configuration data, not an
error: `app/config.py` states that "a missing key is data — the reviewer switches
mode — never an exception", and every entry point funnels into one function,
`app.engine.review`, which degrades instead of failing.

**G2 — The base layer must be deterministic.** Output that changes between
identical runs cannot be measured, regression-tested or trusted in a gate. The
fallback is 63 hand-written rules with no clock, no randomness and no network.

**G3 — Provider-agnostic above the transport.** Sarvam's hosted endpoint and a
local LM Studio server both speak the OpenAI chat-completions protocol, so there
is one transport (`app/openai_compat_provider.py`) and the difference between
providers is a five-field dataclass. A third compatible endpoint is a
configuration function and a test, not an adapter.

**G4 — Interfaces are frozen.** `Finding` has exactly five fields, is frozen and
is `extra="forbid"`; each module's exported names are the contract that tests
patch and front ends call. That is what lets the design grow — anchoring,
posting, benchmarking — without the output shape drifting underneath it.

**G5 — The result must say what actually ran.** Mode, provider, model and a
one-line reason appear in the CLI report, the JSON document and every HTTP
response. "No findings" and "could not look" must never be indistinguishable.

The binding constraints were Python 3.12 only; no GPU and no guaranteed local
model server; a webhook deadline of seconds; a single process with an embedded database
file rather than a database server; and a repository that installs and passes its suite with no network.

## 3.2 Modular decomposition

The system is fifteen modules in one package plus one entry-point script at the
repository root — sixteen files, listed in Table 3.1 in fifteen rows, with the
two entry points (`app/__main__.py` and `reviewer.py`) sharing the last row.

**Table 3.1 — Module decomposition**

| # | Module | Responsibility | Public surface | Depends on |
|---|---|---|---|---|
| 1 | `app/__init__.py` | Package identity and version. | `__version__` | — |
| 2 | `app/config.py` | Credential boundary; reads the environment once, every field defaulted. | `Settings`, `ReviewMode` | pydantic-settings |
| 3 | `app/models.py` | Frozen output contract: severity ladder, anchor status, five-field finding. | `Finding`, `AnchoredFinding`, `ReviewResult`, `Severity`, `AnchorStatus`, `severity_counts`, `verdict_for`, `sort_findings` | pydantic |
| 4 | `app/parser.py` | Unified diff to line-numbered hunks; anchors findings to changed lines. | `parse_diff`, `parse_diff_file`, `bundle_from_source`, `anchor_findings`, `normalize_path`, `DiffBundle`, `DiffReviewResult`, `DiffParseError` | `models` |
| 5 | `app/rules.py` | The 63 deterministic rules over added lines, each with id, category, OWASP mapping and fixed severity. | `RULES`, `RULES_BY_ID`, `RULE_COUNT`, `review_diff`, `review_lines`, `Rule`, `RuleHit`, `RuleCategory`, `LineContext` | `models`, `parser` |
| 6 | `app/mock_provider.py` | The offline answer to "the LLM is unavailable"; delegates to the rule engine, never reimplements it. | `offline_review`, `offline_diff_findings`, `ENGINE_NOTE` | `models`, `parser`, `rules` |
| 7 | `app/sarvam_provider.py` | Live layer and reusable guards: prompt, payload parsing, hallucination and line snapping, key scrubbing. | `PROVIDER_NAME`, `SarvamUnavailableError`, `LLMFinding`, `ProviderOutcome`, `provider_available`, `build_prompt`, `parse_findings_payload`, `review_diff_live`, `review_with_fallback` | `config`, `mock_provider`, `models`, `parser`, `rules` |
| 8 | `app/openai_compat_provider.py` | The single transport for every OpenAI-compatible endpoint: one repair retry, one degrade path. | `OpenAICompatConfig`, `PROVIDER_NAME`, `PROVIDER_LOCAL`, `PROVIDER_SARVAM`, `provider_available`, `review_diff_live`, `review_with_fallback` | `mock_provider`, `models`, `parser`, `rules`, `sarvam_provider` |
| 9 | `app/db.py` | The persistence and identity store: the schema constant, review and finding persistence, user and role management, API-key hashing and lookup. | `SCHEMA_SQL`, `Database`, `get_database`, `hash_api_key`, `ROLE_NAMES`, `ROLE_PERMISSIONS`, `DEFAULT_DB_PATH`, `SEED_ADMIN_USERNAME`, `SEED_ADMIN_EMAIL` | `config`, `models` |
| 10 | `app/auth.py` | The authorisation dependency: resolves `X-API-Key` to a `UserContext` and enforces the role capability for each guarded route. | `UserContext`, `ANONYMOUS`, `require`, `auth_enabled`, `ROLE_LEVELS` | `config`, `db` |
| 11 | `app/engine.py` | Provider routing: precedence rule and the single `review()` entry point. | `PROVIDERS`, `REQUEST_AUTO`, `ProviderSelection`, `config_for_sarvam`, `config_for_local`, `select_provider`, `review` | `config`, `models`, `openai_compat_provider`, `parser`, `rules` |
| 12 | `app/github_client.py` | Publishing: pure renderers plus patchable I/O seams; idempotency by marker. | `fingerprint`, `render_inline_body`, `render_summary_body`, `build_payload`, `post_review`, `github_available`, `InlineComment`, `ReviewPayload`, `PostResult`, five typed errors | `config`, `models`, `parser` |
| 13 | `app/cli.py` | Command line: flags, mode selection, readable report, exit codes. | `build_parser`, `read_source`, `looks_like_diff`, `parse_post_target`, `run`, `main`, `ReviewInputError` | `app`, `config`, `github_client`, `mock_provider`, `models`, `parser`, `rules`, `sarvam_provider` |
| 14 | `app/main.py` | FastAPI surface: review, demo, rule listing, health, webhook with HMAC. | `app`, `render_comment`, `ReviewRequest`, `ReviewResponse`, `ReviewStats`, `PostingInfo`, `HealthResponse`, `RuleInfo` | `app`, `config`, `github_client`, `mock_provider`, `models`, `parser`, `rules` |
| 15 | `app/__main__.py`, `reviewer.py` | Entry points; both call `app.cli.main`. | `main` | `app.cli` |

**Why the boundaries fall where they do.** Dependencies point inward to
`models`, `parser` and `rules`; nothing below `engine` imports a front end; and
`engine` is the only module that knows both the adapter and the rule engine.
Three cuts carry most of the weight.

The first separates *what the reviewer believes* from *where the claim can be
attached*. `Finding` is the belief and has five fields; anchoring is review
metadata on `AnchoredFinding`, which wraps a finding instead of extending it. A
sixth field would have forced every provider, renderer and test to carry a value
that has nothing to do with the finding.

The second separates *which provider runs* (`select_provider`) from *what
happens when it fails* (`review_with_fallback`). Two questions, two functions,
one call site — which is why the fallback cannot be bypassed by accident.

The third keeps every decision about *what a comment says* in pure functions and
every network call behind a patchable seam (`_build_github_client`,
`_build_client`). The consequence is visible in the suite: 637 tests run with no
socket open, because nothing that renders text needs a client.

## 3.3 Data integrity and constraints

Integrity is enforced at three levels, in order of distance from the user.

**At the boundary — validation.** Every structured value is a Pydantic v2 model
and every model facing untrusted input forbids unknown keys. `Finding` is
`extra="forbid", frozen=True`, so a stray key from a future model response fails
where it arrives instead of surfacing as a `KeyError` inside comment rendering.
`line` is checked against `^\d+(?:-\d+)?$` and must ascend, so nothing downstream
re-checks it. `ReviewResult.mode` is a two-value literal; `ReviewRequest` rejects
NUL bytes and unknown body fields with 422; `Settings` bounds `github_max_inline`
to 1–100; the CLI refuses any input file above 2,000,000 bytes before reading it.

**At the diff — anchoring.** A finding is eligible for an inline comment only
when the file is in the diff and the reported range touches an added line
(`anchored`); otherwise it is `file_only` or `unanchored` and travels in the
summary. That is a constraint on claims, not on storage: it stops the system
asserting a position GitHub will reject.

**At rest — the database.** The six tables of §3.4 carry `NOT NULL` on every
field a row cannot exist without, `CHECK` on exactly four enumerated columns —
`roles.name IN ('admin', 'reviewer', 'viewer')`,
`reviews.mode IN ('live', 'mock')`,
`reviews.verdict IN ('block', 'approve with comments', 'approve')` and
`findings.severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')` — `UNIQUE` on the
natural keys (`roles.name`, `users.username`, `users.email`,
`users.api_key_hash`), and foreign keys with explicit delete behaviour. There is
no `CHECK` on `reviews.provider`, on `reviews.target` or on the integer flags;
those columns are constrained by `NOT NULL` and by the writer that fills them,
and the six column tables of §3.4 mark each of the four in place. The DDL is quoted in §4.2.

**Table 3.2 — Referential actions and why**

| Relationship | Action | Reason |
|---|---|---|
| `findings.review_id` → `reviews.id` | `ON DELETE CASCADE` | A finding has no meaning without its review; deleting one must not leave orphan claims about a diff nobody kept. |
| `pr_posts.review_id` → `reviews.id` | `ON DELETE SET NULL` | A posting record is evidence an external side effect happened; the audit line survives the review row, the link becomes null. |
| `users.role_id` → `roles.id` | plain `REFERENCES` (no action clause) | SQLite refuses to delete a role that still has users, which is the behaviour we want; there is no `ON UPDATE` clause because a role id is never renumbered. |
| `PRAGMA foreign_keys = ON` | session pragma | SQLite enforces foreign keys only when asked; the schema sets it per connection and the constraints are inert without it. |

**The five-field contract as an integrity mechanism.** `Finding` is the only
shape in which a finding exists: `file`, `line`, `severity`, `issue`,
`suggested_fix`. Three mechanisms depend on that being true rather than merely
intended. The idempotency fingerprint hashes four identity fields and excludes
the suggested fix, so rewording advice does not make an old finding look new.
The rule engine deduplicates on `(path, lineno, rule.id)`, so one line cannot
produce the same finding twice. The database row is the same five fields plus a
surrogate key and a foreign key, which is why §4.3 needs no mapping layer. A
sixth field would break all three at once — the argument for `extra="forbid"`.

## 3.4 Database design

The physical model is the `SCHEMA_SQL` constant in `app/db.py`, applied at start-up by
`Database.init_schema()`. It defines six tables, three indexes and four `CHECK`
constraints, and every statement below is reproduced from that constant rather than
described from memory; Appendix B carries the DDL verbatim. The model is in third
normal form: every non-key column depends on the whole key and nothing but the key, and
the only repeating group (a review's findings) is held in its own table with a cascading
foreign key.

Figure 2.6 in Chapter 2 shows the six tables and their cardinalities: one review to many findings, one
role to many users, and a nullable review reference on `pr_posts` so that posting history
survives the deletion of the review it belongs to.

### 3.4.1 `roles`

Primary key `id`. No foreign key. 

**Table 3.3 — `roles` columns**

| Column | Type | Constraints |
| --- | --- | --- |
| `id` | INTEGER | PK |
| `name` | TEXT | UNIQUE, NOT NULL, CHECK name IN ('admin', 'reviewer', 'viewer') |
| `can_review` | INTEGER | NOT NULL, DEFAULT 0 |
| `can_post` | INTEGER | NOT NULL, DEFAULT 0 |
| `can_admin` | INTEGER | NOT NULL, DEFAULT 0 |

### 3.4.2 `users`

Primary key `id`. Foreign key: `role_id`. 

**Table 3.4 — `users` columns**

| Column | Type | Constraints |
| --- | --- | --- |
| `id` | INTEGER | PK |
| `username` | TEXT | UNIQUE, NOT NULL |
| `email` | TEXT | UNIQUE, NOT NULL |
| `api_key_hash` | CHAR(64) | UNIQUE, NOT NULL |
| `role_id` | INTEGER | NOT NULL, FK → roles.id |
| `is_active` | INTEGER | NOT NULL, DEFAULT 1 |
| `created_at` | TEXT | NOT NULL |

### 3.4.3 `reviews`

Primary key `id`. No foreign key. 

**Table 3.5 — `reviews` columns**

| Column | Type | Constraints |
| --- | --- | --- |
| `id` | INTEGER | PK |
| `created_at` | TEXT | NOT NULL |
| `mode` | TEXT | NOT NULL, CHECK mode IN ('live', 'mock') |
| `provider` | TEXT | NOT NULL |
| `model` | TEXT | NOT NULL |
| `target` | TEXT | NOT NULL |
| `findings_count` | INTEGER | NOT NULL, DEFAULT 0 |
| `verdict` | TEXT | NOT NULL, CHECK verdict IN ('block', 'approve with comments', 'approve') |

### 3.4.4 `findings`

Primary key `id`. Foreign key: `review_id`. 

**Table 3.6 — `findings` columns**

| Column | Type | Constraints |
| --- | --- | --- |
| `id` | INTEGER | PK |
| `review_id` | INTEGER | NOT NULL, FK → reviews.id, ON DELETE CASCADE |
| `file` | TEXT | NOT NULL |
| `line` | TEXT | NOT NULL |
| `severity` | TEXT | NOT NULL, CHECK severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') |
| `issue` | TEXT | NOT NULL |
| `suggested_fix` | TEXT | NOT NULL |

### 3.4.5 `pr_posts`

Primary key `id`. Foreign key: `review_id`. 

**Table 3.7 — `pr_posts` columns**

| Column | Type | Constraints |
| --- | --- | --- |
| `id` | INTEGER | PK |
| `review_id` | INTEGER | FK → reviews.id, ON DELETE SET NULL |
| `owner` | TEXT | NOT NULL |
| `repo` | TEXT | NOT NULL |
| `pr_number` | INTEGER | NOT NULL |
| `ok` | INTEGER | NOT NULL |
| `inline_posted` | INTEGER | NOT NULL, DEFAULT 0 |
| `inline_demoted` | INTEGER | NOT NULL, DEFAULT 0 |
| `summary_posted` | INTEGER | NOT NULL, DEFAULT 0 |
| `skipped_dup` | INTEGER | NOT NULL, DEFAULT 0 |
| `error` | TEXT | — |
| `created_at` | TEXT | NOT NULL |

### 3.4.6 `benchmark_runs`

Primary key `id`. No foreign key. 

**Table 3.8 — `benchmark_runs` columns**

| Column | Type | Constraints |
| --- | --- | --- |
| `id` | INTEGER | PK |
| `created_at` | TEXT | NOT NULL |
| `mode` | TEXT | NOT NULL |
| `dataset` | TEXT | NOT NULL |
| `precision` | REAL | — |
| `recall` | REAL | — |
| `f1` | REAL | — |
| `fpr` | REAL | — |
| `tp` | INTEGER | — |
| `fp` | INTEGER | — |
| `fn` | INTEGER | — |
| `tn` | INTEGER | — |
| `latency_p50` | REAL | — |
| `latency_p95` | REAL | — |

## 3.5 Procedural and object-oriented design

### 3.5.1 The flow of one review request

The same eleven steps serve the CLI, the API and the webhook; only the first
differs.

1. **Input.** The CLI reads a path (`read_source`: 2 MB cap, UTF-8 only) or
   stdin. The API takes a `ReviewRequest` holding either `diff` or `code`. The
   webhook takes JSON, optionally verifies its `X-Hub-Signature-256` header, then
   tries in order: an inline `diff` field, the GitHub API when a token is set,
   the bundled fixture.
2. **Parsing.** `parse_diff` walks the text with a counter taken from the hunk
   header, producing `DiffBundle → FileDiff → Hunk → DiffLine`. Added-line
   numbers come from `@@ -1,5 +1,8 @@`, never from counting rows, so a hunk
   starting at 120 reports 120.
3. **Routing.** `engine.review` calls `select_provider`, which returns a frozen
   `ProviderSelection(provider, config, reason)`.
4. **Review.** A live selection goes to `review_with_fallback(bundle, config)`; a
   `mock` selection goes to the same function with `config=None`, which takes the
   degrade branch.
5. **Findings.** Either the model's parsed findings, re-labelled with
   `(source: local)` or `(source: sarvam)`, or `app.rules.review_diff` over the
   added lines. Both are `list[Finding]`, sorted CRITICAL first.
6. **Anchoring.** `anchor_findings` assigns `anchored`, `file_only` or
   `unanchored` and records the hunk header.
7. **Assembly.** `DiffReviewResult(mode, target, files, findings, anchors, notes,
   verdict)`; `verdict` is computed from the severity mix rather than stored, so
   it cannot disagree with the findings.
8. **Presentation.** The CLI renders the report or `--json`; the API returns
   `ReviewResponse` with `review`, `comment`, `stats`, `provider`, `model`.
9. **Publishing (optional).** `build_payload` splits anchored findings into inline
   comments (up to `max_inline`, default 30) plus a summary; `post_review` lists
   existing comments, checks the marker, posts.
10. **Idempotency.** Every body ends with `<!-- ai-code-reviewer:<16 hex> -->`. If
    the summary marker is already on the PR the whole post is skipped and the
    outcome is `PostResult(ok=True, marker_seen=True, skipped_dup=True)`.
11. **Outcome.** An exit code (CLI) or an HTTP status (API), both derived from the
    same result objects — so a duplicate and a success both exit 0.

### 3.5.2 Class responsibilities

The class diagram in Figure 2.7 (Chapter 2) shows the same types structurally:
the frozen models, the rule-engine types, the provider outcome, and the three
posting dataclasses. Table 3.9 gives them one row each.

**Table 3.9 — Principal types**

| Type | Kind | Responsibility | Key detail |
|---|---|---|---|
| `Finding` | Pydantic, frozen | What the reviewer believes about one line. | Five fields, `extra="forbid"`; `line` is a number or ascending range. |
| `AnchoredFinding` | Pydantic, frozen | A finding placed against the diff. | Wraps a finding; adds `status`, `hunk_header`, `detail`. |
| `Rule` | Frozen dataclass | One named check with fixed severity, category, OWASP mapping. | `id`, `title`, `category`, `owasp`, `severity`, `check` callable. |
| `LineContext` | Frozen dataclass | One added line plus the sibling added lines a rule needs. | `scan_text` truncates to 4,000 characters; `indent` expands tabs; `is_test_file` exempts noise rules. |
| `ProviderOutcome` | Pydantic | What actually ran, and what it produced. | `mode`, `provider`, `model`, `findings`, `reason`, `latency_ms`. |
| `InlineComment` | Frozen dataclass | One comment for a PR review or the summary. | `path`, `line`, `side`, `body`, `fingerprint`. |
| `ReviewPayload` | Frozen dataclass | Everything needed to publish one review. | `summary_body`, `inline_comments`, `event`, `dropped`, `marker_seen`. |
| `PostResult` | Frozen dataclass | The outcome of one post. Never an exception. | `ok`, `inline_posted`, `inline_demoted`, `summary_posted`, `skipped_dup`, `error`. |
| `UserContext` | Dataclass (design) | The authenticated principal for one request. | `user_id`, `username`, `role`, and the permission flags resolved from `roles`. |
| `Database` | Class (design) | The persistence boundary: one connection, schema applied once, parameterised statements only. | Owns `SCHEMA_SQL`, `insert_review`, `insert_findings`, `record_post`, `record_benchmark`. |

Two properties matter more than the list. Every type except the two persistence
types is frozen, because findings are passed into renderers, matchers and posting
code that must not rewrite one in place — `ReviewResult.verdict` is computed for
exactly that reason. And `PostResult` is a value, not an exception: the posting
layer's error model is "return a result that says what failed", which is what
lets a webhook answer 200 while still reporting a failed post.

## 3.6 User interface design

There is no graphical user interface, and that is a decision rather than an
omission. The three consumers are a developer at a shell, a CI job, and GitHub
itself. All three speak text: a command with flags and an exit code, an HTTP
request with JSON, or a webhook that answers with a comment. A GUI would add a
rendering surface, a session model and a fourth place for the provider label to
be wrong, and would serve none of them.

### 3.6.1 The command-line interface

**Table 3.10 — CLI flags**

| Flag | Argument | Effect |
|---|---|---|
| `path` | file | Source file, or `.diff`/`.patch` (by suffix, or forced with `--diff`). |
| `--diff` | — | Force diff mode regardless of suffix. |
| `--provider` | `auto` \| `local` \| `sarvam` \| `mock` | Which reviewer runs; `auto` follows sarvam > local > mock. |
| `--offline` | — | Force the rule engine; wins over `--provider`. |
| `--json` | — | Emit one JSON document instead of the report. |
| `--min-severity` | `LOW`…`CRITICAL` | Drop findings below this severity. |
| `--post-to-pr` | `OWNER/REPO#NUM` | Publish to a pull request; requires diff mode. |
| `--list-rules` | — | Print all 63 rules and exit. |
| `--verbose`, `--version` | — | DEBUG logs; version string. |

**Exit codes.** `0` success, including a degraded run, an empty review and a
skipped duplicate; `1` input or posting error (unreadable file, unparseable diff,
GitHub refused the post); `2` usage error (bad `--post-to-pr`, missing path,
unknown provider), which `argparse` raises before any work starts. A degraded run
is deliberately not a failure: a rule-engine review of a real diff is a real
review.

**Report layout.** Labelled header lines (target, mode, provider, model, files,
findings with per-severity counts, one `note` per reason), a "changed lines"
block giving each file's change kind and added spans, one numbered five-field
block per finding in severity order, and a final verdict line. `--json` carries
the same facts as a single document; provider and model are printed rather than
stored, so the JSON shape stays frozen.

**Sample output.** Real, from `python reviewer.py samples/sample.diff --offline`
(abridged after the second finding):

```text
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

verdict  : block
```

The single WARNING for the degraded run goes to stderr, so stdout stays
pipeable: `WARNING reviewer.openai_compat: local review degraded to the local
rule engine: no OpenAI-compatible provider selected; local rule engine used`.

### 3.6.2 The REST API

**Table 3.11 — Endpoints**

| Method | Path | Purpose | Auth |
|---|---|---|---|
| GET | `/` | Service banner: name, version, mode. | none |
| GET | `/health` | Liveness, credential state, provider the next review would use. | none |
| GET | `/rules` | All 63 rules: id, title, category, OWASP mapping, severity. | none |
| GET | `/rules/{rule_id}` | One rule by id; 404 when unknown. | none |
| POST | `/review` | Review a unified diff or a whole source file. | none |
| GET | `/test-review` | Demo: review the bundled `samples/sample.diff`. | none |
| POST | `/test-review` | Demo with a body, or a path confined to the project root. | none |
| POST | `/webhook` | GitHub `pull_request` event; verifies `X-Hub-Signature-256`. | HMAC when a secret is configured; posting needs `GITHUB_TOKEN` |
| GET | `/reviews` | Stored reviews, newest first. | `X-API-Key` when `API_AUTH_ENABLED` |
| GET | `/reviews/{review_id}` | One stored review with its findings; 404 when unknown. | `X-API-Key` when enabled |
| GET | `/stats` | Aggregate counts over the stored reviews. | `X-API-Key` when enabled |
| POST | `/users` | Create a user and issue an API key (the key is returned once). | admin only |
| GET | `/users` | List users and their roles. | admin only |
| PATCH | `/users/{user_id}` | Activate or deactivate a user. | admin only |
| GET | `/docs`, `/openapi.json` | Swagger UI and the generated OpenAPI document. | none |

Read endpoints are open by design: the rule set is public policy and the health
probe is what a supervisor polls. The write endpoints carry no bearer token
either — the deployment is the boundary, and the only privileged action,
commenting on someone else's repository, requires a GitHub token the operator
must supply. Where a per-user credential is wanted, `users.api_key_hash` and the
role matrix of §4.4 are the designed extension; §3.7 states the position plainly.

**Swagger UI.** Because every request and response is a Pydantic model, FastAPI
generates the OpenAPI schema and the interactive `/docs` page from the same
classes the code validates with, so the documentation cannot drift from the
behaviour. Each field carries a description and an example, `/review` publishes
two named body examples (a diff and a source file), and the documented error
responses (422 for an unparseable diff, 401 for a bad signature) are declared
rather than incidental. A test asserts the document names every endpoint.

**Sample API response.** Real, from `POST /review` with `samples/sample.diff` and
`"provider": "mock"`, abridged to the envelope (`review.findings` and
`review.anchors` are as printed by the CLI above):

```json
{
  "source": "inline_diff",
  "notice": "diff supplied in the request body",
  "stats": {
    "files": 2, "findings": 4,
    "critical": 3, "high": 0, "medium": 1, "low": 0,
    "verdict": "block",
    "rules_evaluated": 63,
    "duration_ms": 23.646
  },
  "provider": "mock",
  "model": "local-rules",
  "posting": null
}
```

### 3.6.3 The comment posted to a pull request

Three pure renderers produce three bodies. `render_comment` is the full document
— the API's `comment` field — and is what a reviewer reads when the review is one
message. Real output for `samples/sample.diff`, abridged after the second
finding:

```markdown
## Autonomous AI Code Review

**Mode:** `mock` · **Files:** 2 · **Findings:** 4 (CRITICAL 3, HIGH 0, MEDIUM 1, LOW 0)

| File | Change | Added lines |
|---|---|---|
| `app/db.py` | modified | 3-4, 7-8 |
| `app/report.py` | added | 1-5 |

### 1. CRITICAL — `app/db.py:3`

- **Issue:** A GitHub token literal is committed here, granting every scope the token holds to anyone who reads the repository. (rule: secret/github-token)
- **Suggested fix:** Revoke the token, then read it at runtime: `token = os.environ["GITHUB_TOKEN"]`.
- **Anchor:** anchored (`@@ -1,5 +1,8 @@`)

### 2. CRITICAL — `app/db.py:3`

- **Issue:** `API_TOKEN` is assigned a literal credential, so the secret is committed to git history and stays readable to anyone with repo access even after it is rotated. (rule: secret/hardcoded-credential)
- **Suggested fix:** API_TOKEN = os.environ["API_TOKEN"]  # load from the environment; fail loudly when it is unset
- **Anchor:** anchored (`@@ -1,5 +1,8 @@`)

**Verdict:** block
```

`render_summary_body` is the PR-level summary: heading, verdict line with
per-severity counts, the inline/summary split, one section per finding that could
*not* go inline, and the marker. When every finding is anchored and within the
inline cap it carries no sections at all — the honest outcome for `sample.diff`,
four inline comments and an empty summary:

```markdown
## Autonomous AI Code Review

**Verdict:** block · **Findings:** 4 (CRITICAL 3, HIGH 0, MEDIUM 1, LOW 0)
**Inline comments:** 4 · **In this summary:** 0

<!-- ai-code-reviewer:82b281a3ecfd76d9 -->
```

Each inline comment is shorter: a bold severity line naming the path and line
(`**CRITICAL** — app/db.py:3`), the issue, the suggested fix, and the marker line
`<!-- ai-code-reviewer:3f42ce195e754f16 -->`.

## 3.7 Security design

**API-key hashing.** Where a per-user key is issued, only `sha256(key)` is stored,
in `users.api_key_hash CHAR(64)`. The column is `CHAR(64)` and nothing more: no
`CHECK` constrains it to 64 lowercase hex characters. The format comes from
`hashlib.sha256(...).hexdigest()` inside `Database.create_user`, through
`hash_api_key`, so the width and the alphabet are guaranteed by the writer, not
by the schema — SQLite neither pads nor validates `CHAR(64)`, and a caller that
bypassed `create_user` could store any 64-character string. That is a recorded
limitation of the design rather than a property of the DDL, and it is revisited
with the other residual risks in Section 6.7. Verification recomputes the digest over the presented key and
looks the digest up with an indexed equality query (constant-time comparison is used for the webhook signature, not for the key lookup), so timing cannot be used to walk a key out
one byte at a time. A leaked database yields digests, not credentials.

**Role model.** Three roles, as data in `roles`: `viewer` (no write capability; `GET /reviews` requires the reviewer role and the
rule set), `reviewer` (additionally run reviews), `admin` (additionally manage
users, post to repositories, change configuration). The three `can_*` flags are
the authority; `name` is a label with a `CHECK` so the set cannot silently grow.
`users.role_id` is a plain reference, so a role that still has users cannot be removed from
under its holders. §4.4 gives the full matrix.

**Webhook HMAC.** When `GITHUB_WEBHOOK_SECRET` is configured, `POST /webhook`
verifies `X-Hub-Signature-256` over the raw body before parsing it:
`hmac.new(secret, body, sha256).hexdigest()` compared with `hmac.compare_digest`,
answering 401 on mismatch and on a malformed or non-ASCII header. The body is
read as bytes first, because re-serialising JSON would change the bytes and
invalidate a correct signature.

**Path confinement.** The demo endpoint reads files by path, which is a
directory-traversal hole the moment it is exposed. `_confine_to_project` resolves
the candidate and refuses anything that is not the project root or under it,
answering 403; a missing file answers 404. A second, independent guard rejects
NUL bytes in submitted code.

**Token hygiene.** `Settings` declares `repr=False` on every secret field, so a
`print(settings)` or a traceback cannot print a key. Every message that could
carry one passes through `_scrub`, which replaces an occurrence of the key with
`***`, and `_present`, which additionally relabels a reused Sarvam-worded error
to the provider that actually ran. The key never reaches a log record, a finding,
a reason string or a comment body. Repository targets from a webhook are
untrusted too, so `_validate_target` rejects empty values, characters GitHub does
not allow, `.`/`..` forms that pass the character class but resolve as traversal,
and non-positive PR numbers — before any client is built.

Chapter 6 revisits these controls as a threat model with residual risks,
including the one this design does not close: the idempotency marker is a public
HTML comment, so anyone who can comment on a pull request can paste one and
suppress a review. Closing it needs author filtering on the listing call or an
HMAC-derived marker, and both change a frozen format, so it is recorded as an
open decision rather than changed silently.

## 3.8 Error handling design

The model is one sentence: **a configuration or provider failure degrades and is
reported; a malformed input is rejected with a typed status; nothing else raises
to the caller.**

**Table 3.12 — The fallback chain**

| Situation | `mode` | `provider` | Findings | Log |
|---|---|---|---|---|
| Nothing configured | `mock` | `mock` | rule engine | 1 WARNING |
| Forced provider, config missing | `mock` | `mock` | rule engine | 1 WARNING |
| 401 / 403 / timeout / 5xx / connection failure | `mock` | `mock` | rule engine | 1 WARNING |
| Unparseable answer, repair parses | `live` | `sarvam` \| `local` | the model's | — |
| Unparseable answer twice | `live` | `sarvam` \| `local` | none | 1 WARNING |
| Success | `live` | `sarvam` \| `local` | the model's | — |

The budget is at most two model calls per review: the first attempt, and one
repair retry with the error appended to the prompt and JSON mode dropped. The
distinction between the third and fifth rows matters: when the endpoint answers,
it answered badly, so the run stays live with zero findings rather than
pretending a rule engine ran.

**One warning per degrade.** A degraded run logs exactly one WARNING, at the
level where the decision was made. That is why the degraded path calls
`offline_diff_findings` directly rather than delegating to the Sarvam wrapper
that would log its own warning naming the wrong provider, and why the CLI logs
its mode line at DEBUG only: "the provider owns the single WARNING." Muting a
delegated logger was rejected because `setLevel` is process-global and would race
between concurrent webhook requests.

**Never-raise contracts.** `engine.review` does not raise for a missing variable,
a missing SDK, a connection error, a timeout or a rejected key; all degrade, and
an unknown provider *name* is degraded there too because a bad query parameter
must not 500 a request. `post_review` converts a missing token, 401/403, 404,
429, a 422 on one comment, a 5xx and a transport error into a `PostResult`
carrying `error` — GitHub never sees a 5xx from this service, because GitHub
retries a 5xx forever. `POST /webhook` answers 200 for a posting failure and
reports it in the additive `posting` field; status codes are reserved for the two
things that are genuinely the caller's fault, 422 for an unparseable diff and 401
for a bad signature. And a 422 on one inline comment demotes that comment into
the summary and keeps the rest; only a credential, 404 or 5xx failure fails a
whole post.

## 3.9 Test design

The suite is 638 collected cases in 15 files, run offline: no socket is opened,
because every network seam is patchable. *Unit* cases test one module against
plain data — a rule against a line, a renderer against a finding, a validator
against a hostile string. *System* cases drive a whole surface end to end — the
CLI through `main(argv)`, the API through a test client, the webhook through a
JSON delivery — with the external world faked at the seam.

**Table 3.13 — Representative unit and system test cases**

| ID | Type | Description | Input | Expected | Actual |
|---|---|---|---|---|---|
| UT-01 | Unit | Every registered rule fires on its own sample line. | 63 (rule id, line) pairs | One hit per rule, id matching | Pass |
| UT-02 | Unit | A finding always carries all five contract fields. | Each rule's sample line | 5 keys, no extras, no empties | Pass |
| UT-03 | Unit | Anchoring assigns the three statuses correctly. | 4 findings against `sample.diff` | anchored / file_only / unanchored / anchored | Pass |
| UT-04 | Unit | Added-line numbers come from the hunk header. | Diff with `@@ -120,7 +120,9 @@` | First added line reported as 120 | Pass |
| UT-05 | Unit | A regex flood does not blow up. | 10 lines of `"if " * 5000 + "select " * 5000` | Completes in under 5 s | Pass |
| UT-06 | Unit | A very long line is bounded and flagged. | One 100,000-character line | Under 2 s, `style/long-line` present | Pass |
| UT-07 | Unit | `# noqa` suppresses one line; a targeted id suppresses one rule. | `# noqa: unsafe/sql-injection` | Only that rule silent, others fire | Pass |
| UT-08 | Unit | The fingerprint is stable and ignores the suggested fix. | Same finding twice; reworded fix | Identical 16-hex; unchanged on rewording | Pass |
| UT-09 | Unit | A hostile repository target never reaches the network. | `owner=".."`, `repo=".."` | `ok=False`, zero client calls | Pass |
| UT-10 | Unit | A 422 demotes only the rejected comment. | 2-comment payload, bulk 422, one per-comment 422 | 1 posted, 1 demoted, summary rebuilt | Pass |
| ST-01 | System | CLI reviews the bundled diff offline and exits 0. | `reviewer.py samples/sample.diff --offline` | 4 findings, verdict `block`, exit 0 | Pass |
| ST-02 | System | CLI reports a 401 as an error line, not a traceback. | `--post-to-pr owner/repo#1` with a fake 401 | Exit 1, `error    :` line naming 401 | Pass |
| ST-03 | System | The API rejects an unparseable diff with 422. | `{"diff": "just prose, no headers\n"}` | 422, detail contains `cannot parse diff` | Pass |
| ST-04 | System | The API rejects unknown fields and NUL bytes. | `{"diff": …, "bogus": 1}`; `{"code": "x = 1\x00"}` | 422 in both cases | Pass |
| ST-05 | System | A webhook posting failure still returns 200 with the review. | Delivery with a token, client raising | 200, `posting.ok` false, findings present | Pass |

"Actual" is the observed outcome of `python -m pytest -q tests`, which reports
`637 passed, 1 skipped`. The single skip is a benchmark case that needs a
labelled dataset, and it is counted as a skip rather than a pass on purpose.
Chapter 5 covers the layer map and what the suite does not prove.

## 3.10 Summary

The design is one entry point (`engine.review`), three providers, one transport,
one mock implementation, six constrained tables, and a result that always says
what actually ran. Its boundaries follow two lines: what the reviewer believes
(`Finding`, five frozen fields) versus where the claim can be attached
(`AnchoredFinding`); and which provider runs (`select_provider`) versus what
happens when it fails (`review_with_fallback`). Integrity is enforced at the
boundary by strict models, at the diff by anchoring, and at rest by `CHECK`,
`UNIQUE` and foreign keys with stated delete behaviour. The interfaces are three
text surfaces — a CLI with stable exit codes, a documented REST API with
generated Swagger, and a markdown comment — because a GUI would serve none of the
three consumers and would add a fourth place for the provider label to be wrong.
Chapter 4 turns this design into code: the DDL, the insertion path, the access
matrix, the standards, and the measured behaviour of the implementation.
