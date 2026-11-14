# 11 Appendices

## Appendix A — Command reference

Every command below is run from the repository root. None of them requires an
environment variable, an API key or a network route except where the entry says so.
The interpreter is pinned in `.python-version`; the dependencies are installed from
`requirements.lock`, which is the resolved closure that Docker and the CI workflow
also install.

### A.1 The reviewer command line

| Command | What it does |
|---|---|
| `python reviewer.py samples/sample.diff` | Review the bundled two-file patch and print the readable report |
| `python reviewer.py <path>` | Review any source file; a path ending in `.diff` or `.patch` is treated as a patch automatically |
| `python reviewer.py <path> --diff` | Force diff mode for a file whose name has no diff suffix |
| `python reviewer.py <path> --json` | Emit the full result as JSON instead of the readable report |
| `python reviewer.py <path> --min-severity HIGH` | Drop findings below the given severity; accepts LOW, MEDIUM, HIGH, CRITICAL |
| `python reviewer.py <path> --provider auto` | Default: sarvam when its key is set, else local when the endpoint is set, else mock |
| `python reviewer.py <path> --provider local` | Force the self-hosted OpenAI-compatible endpoint |
| `python reviewer.py <path> --provider sarvam` | Force the hosted endpoint |
| `python reviewer.py <path> --provider mock` | Force the deterministic rule engine |
| `python reviewer.py <path> --offline` | Force the rule engine regardless of any configured credential |
| `python reviewer.py <path> --verbose` | Raise logging to DEBUG and show the routing decision |
| `python reviewer.py --list-rules` | Print all 63 rules, CRITICAL first, and exit |
| `python reviewer.py --version` | Print the version and exit |
| `python reviewer.py samples/sample.diff --post-to-pr OWNER/REPO#NUM` | Review and publish to a pull request; requires diff mode and a GitHub token |
| `python -m app samples/sample.diff` | Identical to `reviewer.py`; the package entry point |

Exit codes: `0` a review was produced, including every degraded run; `1` a bad input
path or an unparseable diff; `2` bad usage. A finding of any severity is not a
failure and does not change the exit code.

### A.2 The HTTP interface

| Command | What it does |
|---|---|
| `uvicorn app.main:app --port 8000` | Start the API; interactive schema at `http://localhost:8000/docs` |
| `uvicorn app.main:app --reload --port 8000` | Same, reloading on source change (this is `make run`) |
| `curl -s localhost:8000/` | Service banner: name, version, mode, rule count, endpoint list |
| `curl -s localhost:8000/health` | Liveness, active mode, rule count, categories and credential state |
| `curl -s localhost:8000/rules` | Every registered rule as a JSON array |
| `curl -s localhost:8000/rules/unsafe/sql-injection` | One rule record, including its OWASP mapping |
| `curl -s localhost:8000/test-review` | Review the bundled fixture with no credentials and no network |
| `curl -s -X POST localhost:8000/test-review -H 'Content-Type: application/json' -d '{"diff": "..."}'` | Review a diff supplied in the body through the test endpoint |
| `curl -s -X POST localhost:8000/review -H 'Content-Type: application/json' -d '{"diff": "..."}'` | The review endpoint: accepts a diff or a source file |
| `curl -s -X POST localhost:8000/webhook -H 'X-GitHub-Event: pull_request' -H 'X-Hub-Signature-256: sha256=...' -d @payload.json` | The GitHub webhook receiver |

### A.3 Development and verification

| Command | What it does |
|---|---|
| `make verify` | Build a verifier virtualenv, install the lock, run the suite, then re-run it with the network blocked |
| `make test` | `python -m pytest -q tests` |
| `make lint` | `bash -n` on the shell scripts and `compileall` on the package |
| `make run` | Start the API with reload on port 8000 |
| `make clean` | Remove `__pycache__`, `.pytest_cache` and `.venv-verify` |
| `python -m pytest -q tests` | The suite |
| `python -m pytest -q tests -rs` | The suite, naming the reason for every skip |
| `python -m pytest -q tests --durations=5` | The suite with its five slowest cases |
| `python -m pytest -q tests -k "sql"` | Follow one defect class across every layer |
| `python scripts/verify_offline.py` | Run the whole suite with outbound sockets blocked |
| `bash scripts/verify.sh` | The script `make verify` invokes |

### A.4 The benchmark harness

| Command | What it does |
|---|---|
| `python -m benchmarks.eval` | Run all three modes over the default dataset and write the artefacts |
| `python -m benchmarks.eval --modes rules` | Run one mode only |
| `python -m benchmarks.eval --modes rules local merged --dataset benchmarks/golden --out benchmarks/out` | The full invocation |
| `python -m benchmarks.eval --quiet` | Suppress stdout; artefacts are still written |
| `python -m benchmarks.collect_candidates --dataset benchmarks/golden` | Create empty label templates for new samples |
| `python -m benchmarks.label_helper --dataset benchmarks/golden` | Prompt a human to write the labels |

Artefacts written to the output directory: `metrics.csv`, `summary.json`,
`summary.md`, `chart.png`. They are generated and not checked in.

### A.5 Container and CI

| Command | What it does |
|---|---|
| `docker build -t ai-code-reviewer .` | Build the two-stage image (never built in the development environment; see section 8.6) |
| `docker compose up` | Run the service from the compose file |
| `docker compose config` | Validate the compose file without starting anything |

---

## Appendix B — Database definition

The complete DDL, quoted from `SCHEMA_SQL` in `app/db.py`. Applying this script to an
empty SQLite file reproduces the database the service uses; `tests/test_db.py` asserts
that each constraint below rejects bad data.

```sql
-- roles: the three permission bundles the system recognises.
CREATE TABLE IF NOT EXISTS roles (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE CHECK (name IN ('admin', 'reviewer', 'viewer')),
    can_review  INTEGER NOT NULL DEFAULT 0,
    can_post    INTEGER NOT NULL DEFAULT 0,
    can_admin   INTEGER NOT NULL DEFAULT 0
);

-- users: one row per API key holder. Only the SHA-256 of the key is stored.
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT    NOT NULL UNIQUE,
    email         TEXT    NOT NULL UNIQUE,
    api_key_hash  CHAR(64) NOT NULL UNIQUE,
    role_id       INTEGER NOT NULL REFERENCES roles(id),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL
);

-- reviews: one row per completed review, whatever surface produced it.
CREATE TABLE IF NOT EXISTS reviews (
    id              INTEGER PRIMARY KEY,
    created_at      TEXT    NOT NULL,
    mode            TEXT    NOT NULL CHECK (mode IN ('live', 'mock')),
    provider        TEXT    NOT NULL,
    model           TEXT    NOT NULL,
    target          TEXT    NOT NULL,
    findings_count  INTEGER NOT NULL DEFAULT 0,
    verdict         TEXT    NOT NULL CHECK (verdict IN ('block', 'approve with comments', 'approve'))
);

-- findings: the five contract fields, attached to their review.
CREATE TABLE IF NOT EXISTS findings (
    id             INTEGER PRIMARY KEY,
    review_id      INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    file           TEXT    NOT NULL,
    line           TEXT    NOT NULL,
    severity       TEXT    NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    issue          TEXT    NOT NULL,
    suggested_fix  TEXT    NOT NULL
);

-- pr_posts: one row per attempt to publish a review to a pull request.
CREATE TABLE IF NOT EXISTS pr_posts (
    id               INTEGER PRIMARY KEY,
    review_id        INTEGER REFERENCES reviews(id) ON DELETE SET NULL,
    owner            TEXT    NOT NULL,
    repo             TEXT    NOT NULL,
    pr_number        INTEGER NOT NULL,
    ok               INTEGER NOT NULL,
    inline_posted    INTEGER NOT NULL DEFAULT 0,
    inline_demoted   INTEGER NOT NULL DEFAULT 0,
    summary_posted   INTEGER NOT NULL DEFAULT 0,
    skipped_dup      INTEGER NOT NULL DEFAULT 0,
    error            TEXT,
    created_at       TEXT    NOT NULL
);

-- benchmark_runs: one row per benchmark run, with its metrics.
CREATE TABLE IF NOT EXISTS benchmark_runs (
    id            INTEGER PRIMARY KEY,
    created_at    TEXT NOT NULL,
    mode          TEXT NOT NULL,
    dataset       TEXT NOT NULL,
    precision     REAL,
    recall        REAL,
    f1            REAL,
    fpr           REAL,
    tp            INTEGER,
    fp            INTEGER,
    fn            INTEGER,
    tn            INTEGER,
    latency_p50   REAL,
    latency_p95   REAL
);

CREATE INDEX IF NOT EXISTS idx_findings_review_id ON findings (review_id);
CREATE INDEX IF NOT EXISTS idx_pr_posts_pr_number ON pr_posts (pr_number);
CREATE INDEX IF NOT EXISTS idx_reviews_created_at ON reviews (created_at);
```

### B.1 Tables, keys and constraints

| Table | Purpose | Rows created by |
| --- | --- | --- |
| `roles` | The three permission bundles the system recognises | `app/db.py` |
| `users` | One row per API-key holder; only the SHA-256 of the key is stored | `app/db.py` |
| `reviews` | One row per completed review, whatever surface produced it | `app/db.py` |
| `findings` | The five contract fields, attached to their review | `app/db.py` |
| `pr_posts` | One row per attempt to publish a review to a pull request | `app/db.py` |
| `benchmark_runs` | One row per benchmark run, with its metrics | `app/db.py` |

Six tables, three indexes (`idx_findings_review_id`, `idx_pr_posts_pr_number`,
`idx_reviews_created_at`) and four `CHECK` constraints. Referential actions:
`findings.review_id` cascades on delete, `pr_posts.review_id` is set to NULL on delete,
and `users.role_id` is a plain reference that refuses to delete a role still in use.

## Appendix C — Configuration and environment variables

Configuration is read once, at process start, in one module. A missing value is data
rather than an error: the absence of a credential selects a mode, and nothing else in
the codebase reads the environment.

The table is exhaustive: `Settings` in `app/config.py` declares exactly these fifteen
fields, and no other module reads the environment (`grep -rn "os.environ\|getenv"
app/` finds only the docstring in `app/config.py` and pattern strings inside
`app/rules.py`, never a read). `python -c "from app.config import Settings;
print(len(Settings.model_fields))"` prints `15`.

| Variable | Default | Effect |
|---|---|---|
| `SARVAM_API_KEY` | unset | When non-blank, selects the hosted provider and wins over the local endpoint |
| `SARVAM_MODEL` | `sarvam-m` | Model identifier sent to the hosted endpoint |
| `LMSTUDIO_BASE_URL` | unset | When non-blank, selects the self-hosted OpenAI-compatible provider; the `/v1` suffix is required |
| `LMSTUDIO_MODEL` | `qwen2.5-coder-7b-instruct` | Model identifier sent to the local endpoint; must match an id reported by that endpoint |
| `LMSTUDIO_API_KEY` | `lm-studio` | Bearer key for the local endpoint; the server ignores it but the client library requires a non-empty string |
| `LMSTUDIO_TIMEOUT` | `120` seconds | Per-request timeout for the local endpoint, which is slow on first load |
| `REQUEST_TIMEOUT_S` | `20` seconds | Per-request timeout for the hosted endpoint |
| `DATABASE_PATH` | `data/reviewer.db` | Where the SQLite file lives; a blank value disables persistence |
| `API_AUTH_ENABLED` | `0` | Require `X-API-Key` on the stored-review, stats and user routes |
| `DB_SEED_ADMIN_KEY` | *(unset)* | Seeds one admin user with this key on first start |
| `GITHUB_TOKEN` | unset | Personal access token used to read a pull request and post comments |
| `GITHUB_MAX_INLINE` | `30` | Maximum inline comments per review, between 1 and 100; the remainder moves into the summary |
| `GITHUB_WEBHOOK_SECRET` | unset | When set, every delivery's `X-Hub-Signature-256` is verified |
| `WEBHOOK_ALLOW_UNSIGNED` | `false` | Local-demo escape hatch: allows posting from an unsigned delivery; fails closed when unset |
| `REVIEW_MODE` | `auto` | `auto` selects by credential presence, `live` prefers the model, `mock` forces the rule engine |

Precedence, in order of strength: the `--offline` flag, then an explicit
`--provider` value or the API's `provider` field, then `REVIEW_MODE`, then credential
presence with `sarvam > local > mock`. A forced provider whose configuration is
missing degrades to the rule engine with a reason naming the missing variable; it
does not fail. The `.env` file is read if present, and `.env.example` lists every
variable with its default and its purpose.

---

## Appendix D — The 63 rule identifiers

Produced by `python reviewer.py --list-rules`, which prints one line per rule in
severity order, CRITICAL first, and ends with the count. The table below is that
output with the OWASP mapping and the human-readable title added from the registry,
row for row and in the order the command emits it — severity first (CRITICAL,
HIGH, MEDIUM, LOW), then category, then rule id. The distribution is 17 CRITICAL, 23 HIGH, 16
MEDIUM and 7 LOW, across ten categories: secrets 15, injection 14, config 7, crypto 6,
quality 5, deserialisation 4, style 4, auth 3, complexity 3, reliability 2. Mapping
to the OWASP Top Ten is not uniform — twenty rules fall under cryptographic failures
and eleven under injection, while the vulnerable-and-outdated-components category has
no rule, because a line-oriented pattern cannot establish a dependency version.

| # | Rule id | Category | Severity | OWASP 2021 | Title |
|---|---|---|---|---|---|
| 1 | `auth/verify-false-jwt` | auth | CRITICAL | A07:2021-Identification and Authentication Failures | JWT signature verification disabled |
| 2 | `secret/aws-access-key` | secrets | CRITICAL | A02:2021-Cryptographic Failures | AWS access key id |
| 3 | `secret/aws-secret-key` | secrets | CRITICAL | A02:2021-Cryptographic Failures | AWS secret access key |
| 4 | `secret/github-token` | secrets | CRITICAL | A02:2021-Cryptographic Failures | GitHub token |
| 5 | `secret/gitlab-token` | secrets | CRITICAL | A02:2021-Cryptographic Failures | GitLab token |
| 6 | `secret/google-api-key` | secrets | CRITICAL | A02:2021-Cryptographic Failures | Google API key |
| 7 | `secret/hardcoded-credential` | secrets | CRITICAL | A02:2021-Cryptographic Failures | Hardcoded credential |
| 8 | `secret/openai-key` | secrets | CRITICAL | A02:2021-Cryptographic Failures | OpenAI-style secret key |
| 9 | `secret/private-key-block` | secrets | CRITICAL | A02:2021-Cryptographic Failures | Private key block |
| 10 | `secret/slack-token` | secrets | CRITICAL | A02:2021-Cryptographic Failures | Slack token |
| 11 | `secret/stripe-key` | secrets | CRITICAL | A02:2021-Cryptographic Failures | Stripe secret key |
| 12 | `unsafe/command-injection` | injection | CRITICAL | A03:2021-Injection | Command injection |
| 13 | `unsafe/eval-exec` | injection | CRITICAL | A03:2021-Injection | Dynamic code execution |
| 14 | `unsafe/sql-injection` | injection | CRITICAL | A03:2021-Injection | SQL injection |
| 15 | `unsafe/sql-injection-concat` | injection | CRITICAL | A03:2021-Injection | SQL injection by concatenation |
| 16 | `unsafe/template-injection` | injection | CRITICAL | A03:2021-Injection | Server-side template injection |
| 17 | `unsafe/yaml-unsafe-load` | deserialisation | CRITICAL | A08:2021-Software and Data Integrity Failures | YAML unsafe_load |
| 18 | `auth/assert-as-check` | auth | HIGH | A01:2021-Broken Access Control | assert used for authorisation |
| 19 | `config/cors-credentials-wildcard` | config | HIGH | A05:2021-Security Misconfiguration | Wildcard CORS with credentials |
| 20 | `config/debug-enabled` | config | HIGH | A05:2021-Security Misconfiguration | Debug mode enabled |
| 21 | `crypto/ecb-mode` | crypto | HIGH | A02:2021-Cryptographic Failures | ECB block mode |
| 22 | `crypto/insecure-random` | crypto | HIGH | A02:2021-Cryptographic Failures | Non-cryptographic randomness for a secret |
| 23 | `reliability/http-no-timeout` | reliability | HIGH | A04:2021-Insecure Design | Network call without timeout |
| 24 | `secret/basic-auth-url` | secrets | HIGH | A02:2021-Cryptographic Failures | Credentials in URL |
| 25 | `secret/bearer-literal` | secrets | HIGH | A02:2021-Cryptographic Failures | Bearer token literal |
| 26 | `secret/connection-string-password` | secrets | HIGH | A02:2021-Cryptographic Failures | Password in connection string |
| 27 | `secret/jwt-literal` | secrets | HIGH | A07:2021-Identification and Authentication Failures | JWT literal |
| 28 | `security/tls-verify-disabled` | crypto | HIGH | A02:2021-Cryptographic Failures | TLS verification disabled |
| 29 | `security/unverified-ssl-context` | crypto | HIGH | A02:2021-Cryptographic Failures | Unverified SSL context |
| 30 | `unsafe/compile-input` | injection | HIGH | A03:2021-Injection | Dynamic compilation |
| 31 | `unsafe/ldap-injection` | injection | HIGH | A03:2021-Injection | LDAP injection |
| 32 | `unsafe/nosql-injection` | injection | HIGH | A03:2021-Injection | NoSQL operator injection |
| 33 | `unsafe/os-system` | injection | HIGH | A03:2021-Injection | os.system call |
| 34 | `unsafe/path-traversal` | injection | HIGH | A01:2021-Broken Access Control | Path traversal |
| 35 | `unsafe/pickle-load` | deserialisation | HIGH | A08:2021-Software and Data Integrity Failures | Unsafe deserialisation (pickle) |
| 36 | `unsafe/raw-sql` | injection | HIGH | A03:2021-Injection | Raw SQL execution |
| 37 | `unsafe/shell-true` | injection | HIGH | A03:2021-Injection | Shell injection risk |
| 38 | `unsafe/ssrf` | injection | HIGH | A10:2021-Server-Side Request Forgery | Server-side request forgery |
| 39 | `unsafe/xxe` | deserialisation | HIGH | A08:2021-Software and Data Integrity Failures | XML external entity expansion |
| 40 | `unsafe/yaml-load` | deserialisation | HIGH | A08:2021-Software and Data Integrity Failures | Unsafe YAML load |
| 41 | `auth/timing-unsafe-compare` | auth | MEDIUM | A07:2021-Identification and Authentication Failures | Non-constant-time secret comparison |
| 42 | `complexity/branch-density` | complexity | MEDIUM | A04:2021-Insecure Design | Branch-heavy function |
| 43 | `complexity/deep-nesting` | complexity | MEDIUM | A04:2021-Insecure Design | Deeply nested block |
| 44 | `complexity/too-many-params` | complexity | MEDIUM | A04:2021-Insecure Design | Too many parameters |
| 45 | `config/allowed-hosts-wildcard` | config | MEDIUM | A05:2021-Security Misconfiguration | Wildcard allowed hosts |
| 46 | `config/cors-wildcard` | config | MEDIUM | A05:2021-Security Misconfiguration | Wildcard CORS origin |
| 47 | `config/csrf-disabled` | config | MEDIUM | A05:2021-Security Misconfiguration | CSRF protection disabled |
| 48 | `config/world-writable-permissions` | config | MEDIUM | A05:2021-Security Misconfiguration | World-writable permissions |
| 49 | `crypto/static-iv` | crypto | MEDIUM | A02:2021-Cryptographic Failures | Static IV or nonce |
| 50 | `crypto/weak-hash` | crypto | MEDIUM | A02:2021-Cryptographic Failures | Weak hash algorithm |
| 51 | `quality/bare-except` | quality | MEDIUM | A09:2021-Security Logging and Monitoring Failures | Bare except |
| 52 | `quality/except-pass` | quality | MEDIUM | A09:2021-Security Logging and Monitoring Failures | Swallowed exception |
| 53 | `quality/missing-type-hints` | quality | MEDIUM | A04:2021-Insecure Design | Missing type hints |
| 54 | `quality/mutable-default-arg` | quality | MEDIUM | A04:2021-Insecure Design | Mutable default argument |
| 55 | `secret/high-entropy-string` | secrets | MEDIUM | A02:2021-Cryptographic Failures | High-entropy string (possible secret) |
| 56 | `unsafe/open-redirect` | injection | MEDIUM | A01:2021-Broken Access Control | Open redirect |
| 57 | `config/bind-all-interfaces` | config | LOW | A05:2021-Security Misconfiguration | Service bound to all interfaces |
| 58 | `quality/open-without-context-manager` | quality | LOW | A04:2021-Insecure Design | File opened without a context manager |
| 59 | `reliability/subprocess-no-check` | reliability | LOW | A04:2021-Insecure Design | Subprocess without check |
| 60 | `style/long-line` | style | LOW | A04:2021-Insecure Design | Overlong line |
| 61 | `style/print-statement` | style | LOW | A09:2021-Security Logging and Monitoring Failures | print() in library code |
| 62 | `style/todo-comment` | style | LOW | A04:2021-Insecure Design | Unresolved TODO |
| 63 | `style/wildcard-import` | style | LOW | A04:2021-Insecure Design | Wildcard import |

---

## Appendix E — Sample API requests and responses

All responses below were produced by the shipped application on the submitted tree,
with no environment variable set. Fields that are wall-clock measurements vary
between runs and are marked as such rather than presented as constants.

### E.1 Service banner

```http
GET /
```

```json
{
  "name": "Autonomous AI Code Reviewer & PR Assistant",
  "version": "0.1.0",
  "mode": "mock",
  "rules": 63,
  "endpoints": ["/health", "/rules", "/review", "/test-review", "/webhook", "/docs"],
  "docs": "/docs"
}
```

### E.2 Liveness and credential state

```http
GET /health
```

```json
{
  "status": "ok",
  "mode": "mock",
  "rules": 63,
  "categories": ["auth", "complexity", "config", "crypto", "deserialisation",
                 "injection", "quality", "reliability", "secrets", "style"],
  "sarvam_key": "missing",
  "github_token": "missing",
  "webhook_secret": "missing",
  "provider": "mock"
}
```

The three credential fields report what the process can actually see. They are the
first thing to read when a run chose a mode the operator did not expect.

### E.3 One rule record

```http
GET /rules/unsafe/sql-injection
```

```json
{
  "id": "unsafe/sql-injection",
  "title": "SQL injection",
  "category": "injection",
  "owasp": "A03:2021-Injection",
  "severity": "CRITICAL"
}
```

### E.4 The fixture review

```http
GET /test-review
```

Response body, abridged to the fields that matter (`duration_ms` varies per call):

```json
{
  "stats": {
    "files": 2,
    "findings": 4,
    "critical": 3,
    "high": 0,
    "medium": 1,
    "low": 0,
    "verdict": "block",
    "rules_evaluated": 63,
    "duration_ms": 7.445
  },
  "provider": "mock",
  "model": "local-rules",
  "notice": "sample fixture: sample.diff"
}
```

The review itself is nested under `review`, so a query for `.mode` at the top level
returns null while `.review.mode` returns `"mock"`.

### E.5 A review submitted in the body

```http
POST /review
Content-Type: application/json

{"diff": "<contents of samples/sample.diff>", "min_severity": "HIGH"}
```

```json
{
  "source": "inline_diff",
  "notice": "diff supplied in the request body",
  "review": {
    "mode": "mock",
    "target": "<request body>",
    "files": [
      {"path": "app/db.py", "change": "modified", "added_spans": ["3-4", "7-8"],
       "added_line_count": 4, "hunk_count": 1, "binary": false},
      {"path": "app/report.py", "change": "added", "added_spans": ["1-5"],
       "added_line_count": 5, "hunk_count": 1, "binary": false}
    ],
    "findings": [
      {"file": "app/db.py", "line": "3", "severity": "CRITICAL",
       "issue": "A GitHub token literal is committed here, granting every scope the token holds to anyone who reads the repository. (rule: secret/github-token)",
       "suggested_fix": "Revoke the token, then read it at runtime: `token = os.environ[\"GITHUB_TOKEN\"]`."}
    ]
  },
  "stats": {"files": 2, "findings": 3, "critical": 3, "high": 0, "medium": 0,
            "low": 0, "verdict": "block", "rules_evaluated": 63, "duration_ms": 5.657},
  "provider": "mock",
  "model": "local-rules",
  "posting": null
}
```

`posting` is null because nothing was published: no token was configured. The
response also carries a `comment` field holding the exact markdown a pull-request
comment would contain, beginning:

```markdown
## Autonomous AI Code Review

**Mode:** `mock` · **Files:** 2 · **Findings:** 3 (CRITICAL 3, HIGH 0, MEDIUM 0, LOW 0)

| File | Change | Added lines |
|---|---|---|
| `app/db.py` | modified | 3-4, 7-8 |
| `app/report.py` | added | 1-5 |
```

### E.6 A source file instead of a diff

```http
POST /review
Content-Type: application/json

{"code": "import os\nAPI_KEY = 'AKIAIOSFODNN7EXAMPLE0'\n", "filename": "app/x.py"}
```

Returns source `raw_code` with a notice that the file was reviewed as an all-added
file, one changed-file entry for `app/x.py` with the span `1-2`, and one CRITICAL
finding on line 2 attributed to `secret/hardcoded-credential`.

### E.7 A rejected request

```http
POST /review
Content-Type: application/json

{"diff": "not a diff", "bogus": 1}
```

```json
{
  "detail": [
    {
      "type": "extra_forbidden",
      "loc": ["body", "bogus"],
      "msg": "Extra inputs are not permitted",
      "input": 1
    }
  ]
}
```

Status 422. This is the five-field contract and the request schema being enforced at
the boundary: an unknown field is refused rather than ignored.

### E.8 Webhook signature rejection and acceptance

```http
POST /webhook
X-GitHub-Event: pull_request
X-Hub-Signature-256: sha256=deadbeef

{"action": "closed"}
```

```json
{"detail": "X-Hub-Signature-256 does not match"}
```

Status 401, with a warning logged naming a signature mismatch. The same body with a
correct HMAC-SHA256 digest of the configured secret is accepted:

```json
{"status": "ignored", "event": "pull_request", "detail": "action 'closed' is not reviewed"}
```

Status 200. An event that is not a pull request is answered the same way:

```json
{"status": "ignored", "event": "ping", "detail": "only pull_request events are reviewed"}
```

---

## Appendix F — Screenshots and captured figures

The following figures are to be captured from the running system at submission time
and inserted at the markers below. Each caption states what the figure must show, so
that a captured image can be checked against the claim it supports. Screenshots of a
terminal must include the command line, not only its output.

`[SCREENSHOT PLACEHOLDER: Figure F.1 — Terminal capture of "python reviewer.py samples/sample.diff" showing the mode, provider and model header, all four findings with their rule identifiers and anchor lines, and the final verdict line. Caption: "Deterministic review of the bundled two-file patch, with no credentials configured."]`

`[SCREENSHOT PLACEHOLDER: Figure F.2 — Terminal capture of "python reviewer.py --list-rules" showing the first ten lines and the final count line. Caption: "The rule registry, printed in severity order."]`

`[SCREENSHOT PLACEHOLDER: Figure F.3 — Terminal capture of "python reviewer.py samples/sample.diff --json | jq '.mode, .verdict'" showing the two quoted strings. Caption: "The same review as machine-readable output."]`

`[SCREENSHOT PLACEHOLDER: Figure F.4 — Browser capture of the Swagger UI at http://localhost:8000/docs, with the review endpoint expanded. Caption: "The self-documenting HTTP surface."]`

`[SCREENSHOT PLACEHOLDER: Figure F.5 — Terminal capture of "curl -s localhost:8000/health | jq" showing the credential state fields. Caption: "What the running process can see."]`

`[SCREENSHOT PLACEHOLDER: Figure F.6 — Terminal capture of the full test run showing the pass, skip and elapsed-time line, preceded by the command. Caption: "The offline suite."]`

`[SCREENSHOT PLACEHOLDER: Figure F.7 — Terminal capture of "python scripts/verify_offline.py" showing the network-blocked banner and the same pass and skip counts. Caption: "The same suite with outbound connections blocked."]`

`[SCREENSHOT PLACEHOLDER: Figure F.8 — Terminal capture of a degraded run: LMSTUDIO_BASE_URL set to a port with nothing listening, showing one warning and mode falling back to mock with exit code 0. Caption: "A provider failure costs a warning, not a run."]`

`[SCREENSHOT PLACEHOLDER: Figure F.9 — Terminal capture of "python -m benchmarks.eval" showing the per-mode table and its own note that the samples are format examples. Caption: "The harness, and its own statement of what the numbers are worth."]`

`[SCREENSHOT PLACEHOLDER: Figure F.10 — A pull-request view on github.com showing one inline comment and the summary comment, once posting has been verified against a real repository. Caption: "A published review: inline findings plus one summary." This figure cannot be captured until posting has been exercised against GitHub; until then the claim it illustrates remains unverified (section 8.6).]`

`[SCREENSHOT PLACEHOLDER: Figure F.11 — The four planning charts from the proposal package: the level-0 data flow diagram, the entity-relationship diagram, the PERT network and the Gantt chart, reproduced at report size. Caption: "Project analysis and schedule."]`
