# 6 System Security

## 6.1 Threat model

The system holds three secrets — a GitHub personal access token, a Sarvam API key and a
webhook HMAC secret — and one privilege: the ability to write a review on a pull request
under the operator's own identity, which is the ability to make the operator appear to have
said something publicly. The design follows from what an attacker gains from each.

**A1, an unauthenticated caller reaching the HTTP surface.** The webhook takes a JSON body
naming a repository and a pull-request number and answers by posting a review, so such a
caller could make the bot comment on a repository of their choosing under the operator's
identity. This is the most serious threat in the model, because the damage is public and
attributed. **A2, a contributor who can open a pull request**: the diff is attacker-chosen
text, and whatever the reviewer echoes back is rendered in a trusted place. **A3, anyone who
can comment on the pull request**, who can paste the idempotency marker and suppress the
review (§6.7). **A4, a hostile model endpoint or an interceptor**: a configured endpoint
receives the diff, which may be confidential source code, and returns text the reviewer partly
trusts. **A5, the operator by accident**: a key committed to the repository or written into a
log record needs no attacker. **A6, a reader of logs, artefacts or `/health`.**

Table 6.1 — Threat model, the control for each threat, and the residual risk

| Threat | Control | Residual risk |
| --- | --- | --- |
| A1: forged webhook causes a public comment | HMAC-SHA256 verification; fail-closed posting with no secret (§6.4) | None while a secret is set; a deployment without one must opt in explicitly |
| A2: hostile diff text becomes a link or a file read | Path confinement, target validation, code-span fencing, bounded regexes (§6.6) | Attacker text is still displayed, as text |
| A3: marker suppression | None; documented limitation (§6.7) | A commenter can silence a review |
| A4: hostile endpoint or interception | Operator-configured endpoint; guarded, capped findings; keys scrubbed (§6.5) | The diff leaves the process; plaintext endpoints are not prevented |
| A5: accidental disclosure | `repr` suppression, log scrubbing, `.env` ignored, no key in any artefact | Shell history is outside the system's control |
| A6: logs and artefacts | One-line messages, no credential in any record, presence-only health | Log retention is outside the system (§6.7) |

## 6.2 Authentication and authorisation

The honest description is short, and worth stating precisely because it is easy to overclaim
in either direction: the system **has** an application-level API-key layer, and that layer is
**switched off** unless the operator turns it on. Both halves of that sentence are
load-bearing, and an earlier draft of this chapter managed to deny the first while relying on
the second.

**What is authenticated regardless of configuration.** Outbound GitHub calls carry the
operator's token as a bearer credential, and inbound webhook deliveries are authenticated by
HMAC over the raw body (§6.4). Those are the two exchanges that are authenticated whether or
not anything is configured.

**The API-key layer, and where it lives.** The scheme is implemented in `app/auth.py` and
`app/db.py`, and it is opt-in. `auth_enabled()` (`app/auth.py:87`) reads `api_auth_enabled`
(`app/config.py:91`), whose default is `False`. `require(level)` (`app/auth.py:101`) is the
FastAPI dependency factory; because the flag is read per request rather than at import time,
the dependency is always attached and returns `ANONYMOUS` (`app/auth.py:68`) — a
`UserContext` carrying no capability — when the flag is off, so an unguarded deployment
behaves exactly as it did before the layer existed. Keys are stored only as a SHA-256 hex
digest in `users.api_key_hash`, a `CHAR(64) NOT NULL UNIQUE` column of `SCHEMA_SQL`
(`app/db.py:98`), produced by `hash_api_key()` (`app/db.py:187`). `Database.authenticate()`
(`app/db.py:700`) resolves the presented `X-API-Key` through `_SELECT_USER_BY_HASH`
(`app/db.py:314`), an equality test on the digest, so the plaintext key never reaches the
database and no method returns the hash. Three roles and their capabilities are rows in
`roles`, mirrored by the constant `ROLE_PERMISSIONS` (`app/db.py:80`): `viewer` is
`(0, 0, 0)`, `reviewer` is `(1, 1, 0)`, `admin` is `(1, 1, 1)`.

Two qualifications about that resolution, stated because the temptation is to describe it as
something stronger. It is a digest lookup, not a constant-time string comparison:
`hmac.compare_digest` appears exactly once in the codebase, in `_verify_signature`
(`app/main.py:475`), and the key path does not use it. What protects the stored credential
instead is that only a digest is stored, so a leaked `users` table does not yield a usable
key, and that a deactivated user is indistinguishable from an unknown one — both return
`None` from `authenticate()`, hence the same 401.

**What the layer covers: six routes.** The matrix below is read from the `Depends(require(...))`
declaration on each route in `app/main.py`, not from intention.

Table 6.2 — The six guarded routes, the level each declares via Depends(require(level)) and the capability it requires

| Route | Method | Level | Capability | On failure |
| --- | --- | --- | --- | --- |
| `/reviews` | GET | reviewer | `can_review` | 403 |
| `/reviews/{review_id}` | GET | reviewer | `can_review` | 403 |
| `/stats` | GET | reviewer | `can_review` | 403 |
| `/users` | POST | admin | `can_admin` | 403 |
| `/users` | GET | admin | `can_admin` | 403 |
| `/users/{user_id}` | PATCH | admin | `can_admin` | 403 |

A missing, unknown or deactivated key answers 401 with `WWW-Authenticate: ApiKey`; a known
caller whose role lacks the capability answers 403; an unreachable user store answers 503
rather than reporting an outage as a bad credential (`app/auth.py:143`–`167`). Everything
else is open, and that includes the review surfaces: `/`, `/health`, `/rules`,
`/rules/{rule_id}`, `/review`, `/test-review` (GET and POST), `/webhook` and `/docs` carry no
dependency. `tests/test_api.py::test_no_endpoint_requires_a_key` deletes all three credential
variables and requires 200 from `/health`, `/test-review`, `/review` and `/webhook`, which
pins the zero-configuration demo the marking scheme asks for.

Captured live against the running application, with a seeded admin and one `viewer` user:

Listing 6.1 — The three auth checks driven live: flag off, flag on without a key, and a viewer's key
```text
API_AUTH_ENABLED unset   GET /reviews 200   GET /stats 200   GET /users 200
API_AUTH_ENABLED=true    GET /reviews 401  {"detail": "missing X-API-Key header"}
                         GET /users   200  [{"id": 1, "username": "admin", "role": "admin", ...}]
viewer key -> GET /reviews 403  {"detail": "role 'viewer' lacks the can_review permission"}
viewer key -> GET /users   403
viewer key -> GET /health  200  (unguarded)
```

**The consequence must be stated plainly.** The six guarded routes are history and user
management. The routes that spend money and speak publicly — `/review`, `/test-review` and
`/webhook` — are not covered even when the layer is on, because a demo that requires a key to
review would fail the zero-configuration requirement. So **this service must not be exposed
directly to an untrusted network.** In a real deployment it belongs behind a proxy that
terminates authentication, or behind a private network boundary. What the layer protects is the
review record and the user store, not the model budget or the operator's public voice; that is
the residual risk carried into §6.7.

One further boundary of the matrix, so it is not read as more than it is: `ROLE_LEVELS`
(`app/auth.py:80`) defines a `poster` level mapped to `can_post`, and `reviewer` carries
`can_post = 1`, but no route declares `require("poster")`. The posting path is reached through
`/webhook`, which is unguarded. The capability exists in the data model and is enforced nowhere
yet.

**The two opt-in switches that decide behaviour.** `WEBHOOK_ALLOW_UNSIGNED` (default false)
decides whether an unauthenticated delivery may cause a *post*, and is described in §6.4
because its effect is on posting rather than on reading. `REVIEW_MODE` (`auto`/`live`/`mock`)
decides whether a model may be called at all, which is a confidentiality control as much as a
behavioural one: `REVIEW_MODE=mock` guarantees no diff leaves the process.

**Authorisation of the narrower kind.** The system refuses to act on a target it cannot
validate. `owner`, `repo` and the pull-request number arrive from a webhook payload and are
untrusted; `_validate_target` (`app/github_client.py:1064`) rejects an empty value, a value
outside `[A-Za-z0-9_.-]{1,100}`, a value made only of dots or containing `..`, and any
non-positive number, before a client is constructed.
`test_posting_hardening.py::test_post_review_refuses_a_hostile_target_before_any_call` pins
that ordering, so a hostile target cannot retarget the URL or steer the token elsewhere.
Pagination is constrained the same way: `_safe_next_url` (`app/github_client.py:773`) refuses
any `Link` header pointing at a host other than the API host.

## 6.3 Database and data security

The database is embedded SQLite, created from the `SCHEMA_SQL` constant in `app/db.py`, and
that shape is a security decision rather than an omission. It holds six tables — `roles`,
`users`, `reviews`, `findings`, `pr_posts`, `benchmark_runs` — and what it stores about a
review is bounded: the mode, provider, model and target of the run, its verdict and finding
count, and the five contract fields of each finding. It stores no source code, no credentials
and no user identity at all: identity lives in the `users` table and is written only when the
API-key layer is used, and no row of `reviews` or `findings` references it. A stolen database
file therefore leaks the text of findings rather than the code they describe. There is no
separate database server, no network listener and therefore no port to expose; the file lives
inside the container filesystem and is covered by the same filesystem permissions as the
application.

Because the store is a local file rather than a server, the usual network defences have no
direct analogue, and the substitutions are worth naming. **Constraints as a defence** are
enforced at the schema boundary instead of at a table: every finding is a strict Pydantic v2
model with exactly five fields, and a sixth field, a wrong type or a missing value is a
validation error rather than a coerced value — which is what stops a model's free text from
becoming a record with attacker-controlled structure. **Least privilege** applies to the
process and the credential: the container runs as `USER 10001:10001` rather than root,
dependencies install from a local wheel cache with `--no-index` so the build cannot fetch an
unpinned package, and the documentation asks for a GitHub token that can comment on pull
requests and nothing more — although the system cannot verify the scope it is given and no
test asserts it.

**Reviews are stored, and this is the single funnel that stores them.** `_persist_review()`
(`app/main.py:512`) is called from `_build_response`, the function every review surface goes
through, and writes through `Database.store_review()` (`app/db.py:414`) in one transaction
covering the review and its findings. The `reviews` row carries `created_at`, `mode`,
`provider`, `model`, `target`, `findings_count` and `verdict`; each `findings` row carries
`file`, `line`, `severity`, `issue` and `suggested_fix` — the five contract fields. Captured
live, one `POST /review` against an empty store:

Listing 6.2 — One POST /review against an empty store, read back through the history endpoints
```text
before: reviews 0, findings 0
POST /review -> 200
after:  reviews 1, findings 2
GET /reviews/1 -> 200, 2 findings
```

The record is queryable, not write-only: `GET /reviews` lists the most recent runs newest
first (`Database.list_reviews`, `app/db.py:484`), `GET /reviews/{review_id}` returns one review
with its findings (`Database.get_review`, `app/db.py:500`), and `GET /stats` aggregates them (`Database.stats`,
`app/db.py:782`). What the record does not carry is attribution. There is no user or actor
column on `reviews`, `findings` or `pr_posts`, so no row says who asked for a review or a post:
the history answers "what was found, and when" and not "at whose request". A storage failure is
also deliberately silent to the caller — `_persist_review` logs one `WARNING` on `reviewer.db`
and returns, so a review can be answered and not remembered. Both facts are limitations and
are listed in §6.7.

## 6.4 Webhook authenticity

The webhook is the one inbound path that can cause a public action, so it is the one path with
cryptographic authentication.

GitHub signs the raw request body with the shared secret and sends
`X-Hub-Signature-256: sha256=<hex>`. `_verify_signature` (`app/main.py:467`) recomputes the
digest with `hmac.new(secret.encode("utf-8"), body, hashlib.sha256)` (`app/main.py:472`) and
compares with `hmac.compare_digest` (`app/main.py:475`), which is constant-time with respect to
the strings' content and so does not leak the expected digest through timing. A header that is
missing, does not begin with `sha256=`, or is not ASCII-decodable is rejected as a bad request
rather than raised as a server error; a mismatch returns 401 and no review is posted. The
digest covers the **raw body bytes**, read before JSON parsing — re-serialising the payload and
hashing that would break on any whitespace difference and invite a parser-differential attack
in which the bytes signed and the bytes acted on differ.

**Fail-closed by default.** Verification runs only when `GITHUB_WEBHOOK_SECRET` is configured,
which leaves the interesting case: a token is configured, so the bot *can* post, but no secret
is, so the delivery cannot be authenticated. The gate is `settings.has_webhook_secret and not
settings.webhook_allow_unsigned` in `_post_webhook` (`app/main.py:802`). The system reviews but
refuses to post, with one warning:

Listing 6.3 — The single warning a token-configured, secret-less delivery produces
```text
not posting: GITHUB_WEBHOOK_SECRET is unset, so this delivery cannot be authenticated
(set the secret, or WEBHOOK_ALLOW_UNSIGNED=1 for a local demo)
```

This is the correct default, because the alternative hands A1 the operator's public voice.
`WEBHOOK_ALLOW_UNSIGNED=1` is the local-demo escape hatch, documented in `.env.example`, in
the field description and in `HANDOFF.md`; it is not a default, and setting it is a deliberate
act. `test_audit_gaps.py::test_webhook_refuses_to_post_an_unauthenticated_delivery` pins the
refusal and `::test_webhook_posts_when_the_opt_in_is_set` pins the escape hatch, so neither can
drift into the other. Both were also driven by hand against the running application; the
refusal path with the secret set and a wrong signature supplied, then the token-set /
secret-unset path:

Listing 6.4 — Signature rejection and the fail-closed refusal, captured live
```text
bad sig: 401 X-Hub-Signature-256 does not match
rejected webhook: signature mismatch
unsigned delivery: 200 posting=null
WARNING reviewer.api | not posting: GITHUB_WEBHOOK_SECRET is unset, so this delivery cannot be
authenticated (set the secret, or WEBHOOK_ALLOW_UNSIGNED=1 for a local demo)
WEBHOOK_ALLOW_UNSIGNED=1 -> posting={"ok": false, ...} (the post is attempted and reported)
```

## 6.5 Secret handling

Secrets enter the process in one place. `app/config.py` reads them from the environment or a
`.env` file into a Pydantic settings object at start-up, and no other module reads
`os.environ` — the occurrences in `app/rules.py` are string literals inside rule definitions,
not reads. That single boundary is what makes the rest of this section possible: one object to
inspect, one place to suppress, one place to check.

**Suppression in representations.** All five secret-bearing settings fields — `sarvam_api_key`,
`github_token`, `github_webhook_secret`, `lmstudio_api_key` and `db_seed_admin_key` — are
declared `repr=False` (`app/config.py:31`, `:35`, `:54`, `:75`, `:101`), and so is the
`UserCreateRequest.api_key` body field (`app/main.py:1366`), so printing the settings object,
logging it or dropping it into a traceback cannot disclose them. Live check, with all five set:

Listing 6.5 — repr(Settings()) with all five secret fields set: no value appears
```text
repr(Settings()) -> Settings(sarvam_model='sarvam-m', github_max_inline=30, ...,
                             api_auth_enabled=False)
leaks -> []
```

`test_audit_gaps.py::test_settings_repr_hides_credentials` sets the three real credentials and
asserts none appears in `repr(Settings())`.

**Scrubbing in messages.** A provider error can echo the credential back, because SDKs often
include request headers in exception messages. Both adapters pass every outbound message
through `_scrub`, which replaces any occurrence of the configured key with `***`, and
`_present`, which relabels a reused Sarvam-worded message to the provider that actually ran and
collapses it to one line. The reason string reaching the caller and the log record is the
scrubbed one. `test_sarvam_provider.py::test_api_key_never_appears_in_outcome_reason_or_logs`
and `test_webhook_posting.py::test_posting_failure_logs_once_and_never_leaks_the_token` pin
both boundaries.

**The one-warning rule.** A degraded path logs exactly one `WARNING`, from the module that owns
the decision, and any caller that knows the same fact logs at `DEBUG`. This is a security
property as much as a usability one: a duplicated warning doubles the chance that a
credential-bearing message is written twice, and it makes alerting count one failure as two.
Four tests pin it — `test_happy_path_logs_no_warning`,
`test_each_degraded_path_logs_exactly_one_warning`, `test_demotion_logs_exactly_one_warning`
and `test_missing_token_logs_one_warning_without_the_token`.

**Presence, not value, in diagnostics.** `/health` (`app/main.py:892`, response model
`HealthResponse` at `app/main.py:322`) reports `"configured"` or `"missing"` for each credential
and never the value, as do the CLI's mode line and every notice string. The response has nine
keys — the last, `database`, reports the state of the SQLite history rather than a credential.
Observed live from `TestClient(app).get("/health")` with no credentials set:

Listing 6.6 — GET /health captured live: nine keys and no credential value
```json
{"status": "ok", "mode": "mock", "rules": 63, "categories": ["auth", "complexity",
 "config", "crypto", "deserialisation", "injection", "quality", "reliability", "secrets",
 "style"], "sarvam_key": "missing", "github_token": "missing", "webhook_secret": "missing",
 "provider": "mock", "database": "ok"}
```

**At rest.** `.env` and `.env.*` are ignored by version control, with `.env.example` the only
tracked template and every value in it blank. The image receives no secret at build time;
secrets are supplied at run time through the environment. The repository's own documentation
records the honest caveat: a key in a shell history or a `.env` on a shared machine is outside
the system's reach, and `.gitignore` protects the repository, not the workstation.

## 6.6 Injection and input validation

Five injection classes were considered, and each has a specific control.

**Path traversal on `/test-review`.** The demo endpoint reads a diff by path so an examiner can
point it at any sample, and a path is attacker-chosen input. `_confine_to_project`
(`app/main.py:415`) resolves it — relative paths against the project root, absolute paths as
given — then requires the result to be the root itself or a descendant, refusing anything else
with 403; a path that resolves inside but does not exist gets 404. Resolution before comparison
is what makes the check sound, since it collapses `..` and symlinks before the decision. Real
capture:

Listing 6.7 — Path confinement: an escape refused, a sample served, a missing path reported
```text
traversal: 403 path must stay inside the project root
inside: 200 4 findings
missing: 404 not a readable file: samples/nope.diff
```

**URL and target injection in the GitHub client.** `owner` and `repo` are interpolated into an
API URL, so `_validate_target` (`app/github_client.py:1064`) constrains them to
`[A-Za-z0-9_.-]{1,100}` and additionally rejects values made only of dots or containing `..`,
which would pass the character class and still traverse. `_safe_next_url`
(`app/github_client.py:773`) applies the same reasoning to pagination links, so a hostile
response cannot redirect the bearer token to another host.

**Markdown injection into the reviewer's own comment.** The subtlest of the five, because the
payload is rendered by GitHub as markdown in a comment attributed to the bot. A diff path such
as `` x`[click](https://evil.example)` `` would, inside a single-backtick code span, close the
span at the first backtick and leave `[click](...)` as a live link. Escaping does not fix it,
because CommonMark does not process escapes inside code spans; the fence must be longer than
the longest backtick run in the value. `_md_code` (`app/github_client.py:236`) counts that run,
fences with one more backtick, pads with a space when the value begins or ends with a backtick,
and collapses newlines first so a path cannot open a new block. Live output:

Listing 6.8 — The code-span fence growing past the longest backtick run
```text
'x`[click](https://evil.example)`' -> `` x`[click](https://evil.example)` ``
'````tick'                        -> ````` ````tick `````
```

`test_audit_gaps.py::test_a_hostile_path_cannot_break_out_of_the_code_span` and
`::test_code_span_fence_grows_with_the_longest_backtick_run` pin both the attack and the rule.

**Regular-expression denial of service.** Sixty-three patterns are matched against
attacker-chosen lines under two bounds: the patterns were reviewed for linearity, with no
nested quantifier over an unbounded group, and each line is truncated to
`_MAX_REGEX_LINE = 4000` (`app/rules.py:56`, applied before any pattern sees the text) so a
ten-megabyte minified line cannot burn CPU. The truncation is the enforced bound; the linearity
of a pattern is a property of its source and is not machine-checked.
`test_rules.py::test_regex_flood_does_not_blow_up` feeds ten lines of five thousand repeated
keywords and requires completion under five seconds; `::test_very_long_line_is_bounded_and_flagged`
feeds a hundred-thousand-character line and requires the same.

**Model output as an injection vector.** A reply is untrusted text that must become a finding.
It is parsed as JSON under a strict schema, re-validated against the five-field model, findings
whose file is not in the diff are dropped as hallucinations, line numbers outside the diff's
spans are snapped or discarded, duplicates collapsed and the list capped at fifty. A model
returning markdown, an apology or a shell command produces a validation failure and a
degradation, not a finding.

## 6.7 Known limitations, stated honestly

**No caller attribution.** Reviews and findings are stored (§6.3), but no row records who asked
for a review or a post: there is no user or actor column on `reviews`, `findings` or
`pr_posts`, so the history cannot answer "who" — only "what, and when". Closing this needs a
column and a way to populate it from the request, including the unguarded review surfaces where
there is no caller identity to record. **No retention policy** either: the compensating control
is that the `reviews` table can be purged by deleting the database file, and that every posted
comment is attributable to the token's identity and visible in the repository's history.

**The idempotency marker is public.** Every generated comment ends with
`<!-- ai-code-reviewer:<16 hex> -->`, and a re-run whose summary marker is already present is
skipped. Anyone who can comment can paste that line and suppress the next review. Closing this
needs author filtering on the comment listing or an HMAC-derived marker tied to a secret; both
change the frozen marker format and are deferred rather than improvised.

**Benchmark matching is greedy.** A one-to-one greedy assignment by largest overlap can score
lower than an optimal one, so two findings on the same line can count as one true positive and
one false positive. This affects reported numbers, not the reviewer's behaviour.

**There is no rate limiting.** Nothing throttles `/review`, `/test-review` or `/webhook`; the
only 429 handling in the codebase is the outbound response to GitHub's own rate limiter
(`GitHubRateLimitError`, `app/github_client.py:140`), which is the opposite direction. A
reachable caller can drive the rule engine as fast as the CPU allows and, with a key
configured, cause model calls at the operator's expense. Acceptable only because the service is
not meant to face an untrusted network.

**The API-key layer is off by default and does not cover the review surfaces.** With
`API_AUTH_ENABLED` unset — the default — every route answers without a credential; with it set,
the six management routes of §6.2 require one, while `/review`, `/test-review` and `/webhook`
remain open. The layer protects the review record and the user store, not the model budget or
the operator's public voice.

**The diff leaves the process when a provider is configured**: a hosted call or a local endpoint
receives the source under review, and only `REVIEW_MODE=mock` prevents it. **Token scope is not
verified**: the system asks for a token that can comment on pull requests and cannot check what
it was given.

## 6.8 Summary

The security posture is narrow and defensible rather than broad and claimed. Three secrets are
read once at a single configuration boundary, suppressed from every representation, scrubbed
from every message and reported only as present or missing. The one inbound path that can cause
a public action is authenticated by HMAC-SHA256 over the raw body [16] with a constant-time
comparison, and it fails closed: with a token configured and no secret, the delivery is reviewed
and not posted. Every attacker-influenced value that reaches a URL, a filesystem path or a
rendered comment is validated, confined or fenced, and each control has a test pinning both the
attack and the general rule behind it. Reviews are stored in `reviews` and `findings` and are
queryable through `GET /reviews`, `GET /reviews/{id}` and `GET /stats`.

The limitations in §6.7 are equally part of the posture. The application-level API-key layer
exists and is opt-in, covering six management routes and not the review surfaces; there is no
rate limiting, no caller attribution in the stored record and no protection against marker
suppression. The service is safe to run offline and behind a boundary, and is not safe to
expose. Stating that plainly is more useful to a reader than a longer list of controls that
would suggest a hardening this artefact does not have.
