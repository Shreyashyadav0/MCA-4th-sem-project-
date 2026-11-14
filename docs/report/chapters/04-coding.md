# 4. Coding

This chapter is the implementation counterpart to chapter 3: the schema as
executed DDL, the insertion path, the access model, the standards the code is
held to, its measured behaviour, its error handling, and the frozen signatures
that make up its interfaces. Code is quoted from the tree with the file named
above each block; command output is quoted as observed.

## 4.1 Development environment and repository layout

The interpreter is pinned by `.python-version` to `3.12.13`; dependencies are
pinned by `requirements.lock`, whose 37 `==` entries (`grep -c '==' requirements.lock`)
CI and the Docker image both install from, so a local pass and a CI pass install
the same versions. Nothing else is needed: an embedded database file rather than a
database server, no container, no network.

```bash
python3 --version          # Python 3.12.13
pip install -r requirements.lock
python -m pytest -q tests  # 637 passed, 1 skipped
```

The `app/` package holds fifteen modules totalling 9,250 lines; `reviewer.py`, the
thirteen-line entry point, is the only Python file outside it that a user runs.

`make test` runs the suite, `make lint` runs `bash -n` over the shell scripts and
`python -m compileall` over `app/`, and `make verify` builds a throwaway
virtualenv, installs the lock, runs the suite and then re-runs it with sockets
blocked (`scripts/verify_offline.py`) as a zero-network proof. `make run` starts
`uvicorn app.main:app --reload --port 8000`.

```text
.
├── reviewer.py                 # 13-line entry point: python reviewer.py <path>
├── app/                        # 15 modules, 9,250 lines (wc -l app/*.py)
│   ├── __init__.py  __main__.py
│   ├── config.py               # the only reader of os.environ
│   ├── models.py               # Finding, AnchoredFinding, ReviewResult
│   ├── parser.py               # diff parsing + anchoring
│   ├── rules.py                # the 63 deterministic rules
│   ├── mock_provider.py        # the offline paths
│   ├── sarvam_provider.py      # live layer + reusable guards
│   ├── openai_compat_provider.py   # the single transport
│   ├── engine.py               # provider selection + review()
│   ├── github_client.py        # PR posting
│   ├── db.py                   # SCHEMA_SQL + the persistence layer
│   ├── auth.py                 # roles, as a FastAPI dependency
│   ├── cli.py  main.py         # the two front ends
├── benchmarks/                 # loader, matching, metrics, runner, report
├── samples/sample.diff         # the fixture every surface defaults to
├── scripts/                    # verify.sh, verify_offline.py, learning_progress.py
├── tests/                      # 15 files, 638 collected cases (565 + 73 benchmark)
├── docs/decisions/             # seven decision records
└── requirements.lock  Makefile  Dockerfile  docker-compose.yml
```

## 4.2 Database creation

The schema is created from one constant, `SCHEMA_SQL` in `app/db.py` [7], so the DDL that
runs and the DDL in this report cannot drift. `Database.init_schema()` executes it with
`executescript`, and every connection sets `PRAGMA foreign_keys = ON` so the referential
actions below actually fire. The block below is that string character for character —
comparing it with `python -c "from app.db import SCHEMA_SQL; print(SCHEMA_SQL)"`
returns an empty diff — and Appendix B carries the same six tables, three indexes and
four `CHECK` constraints.

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

The statement is idempotent (`CREATE TABLE IF NOT EXISTS`), so starting the service
twice creates the schema once and leaves existing rows untouched.

## 4.3 Data collection and insertion

Data enters the database from exactly one place: the result objects the engine
already produces. A review is collected as `ProviderOutcome` (mode, provider,
model, findings, reason, latency), turned into `DiffReviewResult`, and — where
posting is attempted — into `PostResult`. Nothing is re-derived for storage, and
nothing is parsed back out of a log line.

Insertion is two parameterised statements in one transaction, and the second is
an `executemany` over the findings:

```python
db.execute(
    "INSERT INTO reviews (mode, provider, model, target, findings_count, verdict)"
    " VALUES (?, ?, ?, ?, ?, ?)",
    (result.mode, outcome.provider, outcome.model, result.target,
     len(result.findings), result.verdict),
)
review_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
db.executemany(
    "INSERT INTO findings (review_id, file, line, severity, issue, suggested_fix)"
    " VALUES (?, ?, ?, ?, ?, ?)",
    [(review_id, f.file, f.line, f.severity.value, f.issue, f.suggested_fix)
     for f in result.findings],
)
```

Every value is bound, never interpolated: the same rule the reviewer enforces on
other people's code (`unsafe/sql-injection`) applies to its own storage layer.

**Worked example.** Reviewing `samples/sample.diff` in mock mode produces one
`reviews` row and four `findings` rows. The review row:

| Column | Value |
|---|---|
| `id` | 1 |
| `mode` | `mock` |
| `provider` | `mock` |
| `model` | `local-rules` |
| `target` | `samples/sample.diff` |
| `findings_count` | 4 |
| `verdict` | `block` |

and the four finding rows, abbreviated in the `issue` and `suggested_fix`
columns only:

| `id` | `file` | `line` | `severity` | `issue` (rule) | `suggested_fix` |
|---|---|---|---|---|---|
| 1 | `app/db.py` | `3` | `CRITICAL` | GitHub token literal committed (secret/github-token) | Revoke the token, read it at runtime |
| 2 | `app/db.py` | `3` | `CRITICAL` | Literal credential in `API_TOKEN` (secret/hardcoded-credential) | `API_TOKEN = os.environ["API_TOKEN"]` |
| 3 | `app/db.py` | `7` | `CRITICAL` | SQL built by string interpolation (unsafe/sql-injection) | `db.execute("... WHERE id = ?", (uid,))` |
| 4 | `app/report.py` | `1` | `MEDIUM` | Public function without full annotations (quality/missing-type-hints) | `def render(value: str) -> str:` |

Rows 1 and 2 share a file and a line and are still two rows, because they are two
distinct rules with distinct fixes: deduplication is on
`(file, line, rule)`, not on position. A posting attempt for the same review adds
one `pr_posts` row whose counters are copied from `PostResult` field for field by
`Database.store_pr_post`, so the table can be read without re-deriving anything.
For the fixture the mapping is arithmetically checkable: `anchor_findings` anchors
all four findings and `build_payload` returns four inline comments
(`len(payload.inline_comments) == 4`, `max_inline` is 30), so a clean post of this
review records `ok=1, inline_posted=4, inline_demoted=0, summary_posted=1,
skipped_dup=0, error=''`. The repository it is posted to is whatever `owner` and
`repo` the caller supplied; the counters do not depend on it.

## 4.4 Access rights for different users

Three roles, and one source of truth for what each may do. `ROLE_PERMISSIONS` in
`app/db.py` is that source; `seed_defaults` writes it into the `roles` table, so
the rows in the database and the tuple in the code cannot disagree:

```python
# app/db.py
ROLE_PERMISSIONS: dict[str, tuple[int, int, int]] = {
    "viewer": (0, 0, 0),
    "reviewer": (1, 1, 0),
    "admin": (1, 1, 1),
}
```

The tuple is `(can_review, can_post, can_admin)`. Two of the three capabilities
are enforced by HTTP routes through `Depends(require(...))` in `app/auth.py`:
`require("reviewer")` checks `can_review`, `require("admin")` checks `can_admin`.
`can_post` is stored, returned on the request context and asserted by
`tests/test_db.py`, but no route in `app/main.py` consults it — publishing to a
pull request happens either in the CLI (`--post-to-pr`, under the operator's own
GitHub token) or at the `/webhook` boundary, which is authenticated by an HMAC
signature rather than by a role.

`API_AUTH_ENABLED` defaults to false, so an unconfigured deployment answers
without a key and the request context is `ANONYMOUS`, which carries no capability
at all. Table 4.1 therefore describes what happens with the flag **on**.

**Table 4.1 — Access-rights matrix, as measured with `API_AUTH_ENABLED=1`**

| Operation | Guard in code | `viewer` (0,0,0) | `reviewer` (1,1,0) | `admin` (1,1,1) |
|---|---|---|---|---|
| `GET /`, `GET /health` — banner and liveness | none | 200 | 200 | 200 |
| `GET /rules`, `GET /rules/{id}` — the rule registry | none | 200 | 200 | 200 |
| `POST /review` — review a supplied diff or file | none | 200 | 200 | 200 |
| `GET /test-review`, `POST /test-review` — demo on the fixture | none | 200 | 200 | 200 |
| `POST /webhook` — GitHub event receiver | HMAC signature, not a role | — | — | — |
| `GET /reviews`, `GET /reviews/{id}` — stored reviews | `require("reviewer")` | 403 | 200 | 200 |
| `GET /stats` — aggregate counts | `require("reviewer")` | 403 | 200 | 200 |
| `POST /users` — create a user and issue a key | `require("admin")` | 403 | 403 | 201 |
| `GET /users` — list users and roles | `require("admin")` | 403 | 403 | 200 |
| `PATCH /users/{id}` — activate or deactivate a user | `require("admin")` | 403 | 403 | 200 |
| CLI `reviewer.py <path>`, `--post-to-pr OWNER/REPO#N` | operator's token, not a role | — | — | — |

Every cell in the table is a status code an HTTP call actually returned: all
eight unguarded route registrations and all six guarded ones were called through
`TestClient` with one user per role, and a request with no key at all answers 200
on the unguarded routes and 401 on the guarded ones. The `—` cells are the two
surfaces a role does not govern: the webhook is authenticated by signature (401
when the signature is wrong, 200 when it is right, whatever the role), and the CLI
runs as whoever started it, with posting gated by the presence of `GITHUB_TOKEN`
and the token's own scopes.

Three consequences are worth stating plainly, because the code and a naive
reading of "three roles" diverge here.

*A `viewer` is identified but unprivileged.* The tuple is `(0, 0, 0)`, so a
viewer authenticates successfully and is then refused by every guarded route:
`GET /reviews` answers 403, not 200. The role exists as the
identified-but-untrusted level — `require("viewer")` is an accepted argument to
the dependency factory — but no route in `app/main.py` currently asks for it, so a
viewer's usable surface is exactly the unguarded ones: the banner, the health
check, the rule registry and the review endpoints.

*The rule registry and the review endpoints are open, not read-protected.* They
carry no `Depends(...)`, so they answer to an anonymous caller even with
`API_AUTH_ENABLED=1`. That is a deliberate trade for a demo that must respond with
zero configuration, and it is the honest reading of the table: the rule set is
public policy and a review is stateless computation. What is protected is the
*history* — the stored reviews, findings, statistics and the user table.

*`can_post` is defined but not enforced.* It is the one capability in the tuple
with no HTTP enforcement point, which is why no row above reads it.

**Operations the system does not have.** Two rights that a fuller design would
carry are absent from this build, and are therefore absent from the matrix rather
than listed as rows:

- *Deleting a review.* `app/main.py` declares no `DELETE` handler and `Database`
  exposes no `delete_review`; the cascade from `reviews` to `findings` fires only
  when a row is removed by hand in `sqlite3`. A review, once stored, is evidence
  and is not deleted through any interface this system offers.
- *Rotating an API key.* Only the SHA-256 of a key is stored and `Database` has no
  rotation method: a key is fixed at `POST /users`, and changing it means
  deactivating the user with `PATCH /users/{id}` and creating a replacement.

Neither is a row in Table 4.1. A matrix of rights over operations that do not
exist would be fiction, and the two are recorded here as gaps instead.

## 4.5 Coding standards

**Type hints everywhere.** Every one of the 244 functions in `app/` is
annotated — an AST pass over the package finds no parameter (ignoring `self` and
`cls`) and no return type without an annotation — and 14 of the 15 modules begin
with `from __future__ import annotations` (the exception is the three-line
`app/__init__.py`), so annotations are strings at runtime and a forward reference
costs nothing:

```python
# app/engine.py
def review(
    bundle: DiffBundle,
    settings: Settings,
    *,
    provider: str = REQUEST_AUTO,
    force_offline: bool = False,
    min_severity: Severity | None = None,
    categories: Iterable[RuleCategory] | None = None,
) -> ProviderOutcome:
```

**Docstrings state the contract, not the code.** Google-style sections — a
one-line summary, then `Args:`, `Returns:` and `Raises:` where each is real.
`select_provider` documents that it never raises for a missing credential and
does raise `ValueError` for an unknown provider name; the reader learns the
error model from the docstring before reading a line of the body.

**No broad except.** Across `app/` there are 75 `except` clauses, none of them
bare, and six are `except Exception` — each carrying `# noqa: BLE001` and a reason
on the same line: a broken SDK import that must degrade rather than crash
(`sarvam_provider.py`), a `close()` in a `finally` that must not mask the real
outcome (`github_client.py`), two storage calls whose failure must not change the
response — one for the review, one for the posting outcome (`main.py`), the health
check, which must answer even when the store is broken (`main.py`), and the
webhook boundary, where GitHub must never see a 5xx (`main.py`). Everything else
names its type —
`SarvamUnavailableError`, `GitHubRateLimitError`, `ValidationError`,
`DiffParseError`, `ReviewInputError`, `OSError`, `ValueError`, `ImportError`.

**One WARNING per event.** Logging is part of the standard, not an afterthought:
a degraded run logs one WARNING at the point the decision was made, and every
other site that knows the same fact logs at DEBUG. The rule exists because two
log lines for one event train operators to ignore both.

**Naming.** Modules are nouns (`engine`, `parser`, `rules`); functions are verbs
(`parse_diff`, `anchor_findings`, `build_payload`); booleans read as assertions
(`provider_available`, `github_available`, `has_webhook_secret`); module-private
helpers are underscore-prefixed (`_mock_outcome`, `_scrub`, `_raise_for_status`);
and 13 of the 15 modules declare `__all__` — all but the three-line
`app/__init__.py` and the eight-line `app/__main__.py` — so each public surface is
stated rather than inferred. Constants that are part of a contract are module-level and upper-case
(`PROVIDERS`, `RULE_COUNT`, `COMMENT_MARKER_PREFIX`).

**Immutability by default.** Domain values are frozen — Pydantic models with
`frozen=True`, dataclasses with `frozen=True, slots=True` — and mutation happens
by `model_copy(update=...)` or `dataclasses.replace`, which returns a new value.

There is no formatter or linter pinned in this tree; `make lint` runs `bash -n`
and `compileall`. The standards above are held by review, by the tests that
assert them (frozen dataclasses, field order, `__all__` contents) and by the
decision records in `docs/decisions/`.

## 4.6 Code efficiency

**The ReDoS bound.** Every rule pattern is linear — no nested quantifiers — and
each line is truncated before any regex sees it:

```python
# app/rules.py
_MAX_REGEX_LINE = 4000

    @property
    def scan_text(self) -> str:
        """The line, truncated to the regex budget."""
        if len(self.text) <= _MAX_REGEX_LINE:
            return self.text
        return self.text[:_MAX_REGEX_LINE]
```

A 10 MB minified line therefore costs 4,000 characters of regex work, not 10 MB.
The suite pins the property twice: `test_very_long_line_is_bounded_and_flagged`
asserts a 100,000-character line is scanned in under 2 s, and
`test_regex_flood_does_not_blow_up` asserts that 10 lines of
`"if " * 5000 + "select " * 5000` finish in under 5 s.

**Single-pass parsing.** `parse_diff` walks the diff once with a line index and
hunk counters (`remaining_old`, `remaining_new`) that decide when a hunk ends, so
each line is visited exactly once and no hunk is re-scanned. Line numbers come
from the header counters rather than from counting rows, which also means the
parser never needs a second pass to number what it read. The whole diff is held
in memory as a string; that is a deliberate trade, bounded by the CLI's 2 MB
input cap and by the fact that a pull-request diff is small.

**Deduplication and filtering happen before construction.** `review_lines`
filters on severity floor and category before calling `rule.check`, skips
suppressed lines before the rule loop, and holds a `seen` set on
`(path, lineno, rule.id)` so a duplicate never becomes a `Finding` object at all.
Cheap checks come first: a rule that is below the severity floor costs one
integer comparison.

**Measured.** The suite, as run for this chapter:

```text
$ python -m pytest -q tests --durations=5
============================= slowest 5 durations ==============================
1.01s call     tests/test_auth.py::test_guarded_endpoints_need_a_key_only_when_auth_is_on
0.82s call     tests/test_auth.py::test_a_bad_key_is_401_and_a_weak_role_is_403
0.81s call     tests/test_auth.py::test_a_review_is_stored_and_readable
0.72s call     tests/test_auth.py::test_users_lifecycle_from_the_seed_admin
0.51s call     tests/test_auth.py::test_patch_rejects_a_missing_user_and_a_bad_body
637 passed, 1 skipped in 40.64s
```

No case takes more than about a second and most finish in milliseconds; the
slowest are the access-control tests, which stand up a temporary SQLite file and
drive the guarded routes through `TestClient`. The 40-second total is dominated by import and
collection time rather than by any test — `python -m pytest -q tests
--collect-only` alone takes about 23 s on this machine, because every test module
imports the application package. Nothing in the suite touches the network.

End-to-end, the API reports its own engine time: the `stats` block of the
`POST /review` response for the four-finding review of `samples/sample.diff`
carries `"duration_ms": 23.646`. The digits move between runs on a shared machine;
the field is the point, not the value.

Throughput was measured with a harness that builds one synthetic hunk whose every
added line trips the SQL-injection rule, then times `parse_diff` and
`review_diff` (all 63 rules) separately:

```text
1000 added lines -> parse   14.6 ms, rules   576.5 ms, 1000 findings
4000 added lines -> parse   55.2 ms, rules  2071.6 ms, 4000 findings
one 5 MB line    ->        211.7 ms,   1 finding
```

Read the shape rather than the digits, which move between runs on a shared
machine: cost is linear in added lines at roughly 0.4–0.6 ms per line for all 63
rules — repeating a single case moved it by about a third — and a single
pathological 5 MB line costs about 0.2 s, because of the 4,000-character
truncation, not the seconds a backtracking regex would need.

## 4.7 Error handling and validation

**A configuration failure is a value.** The routing function catches its own
programming-error case so a bad query parameter cannot 500 a request:

```python
# app/engine.py
    try:
        selection = select_provider(settings, requested=provider)
    except ValueError:
        # Defensive: only reachable if a caller bypasses the CLI/API validation.
        # A request must still get a review, so fall back to the rule engine.
        selection = _mock_selection(
            f"unknown provider {provider!r}; local rule engine used"
        )
```

**A degradation is one warning, with an honest label.**

```python
# app/openai_compat_provider.py
    logger.warning("%s review degraded to the local rule engine: %s", provider_label, reason)
```

**An HTTP status becomes a typed exception — except the one that must not.**

```python
# app/github_client.py
def _raise_for_status(response: httpx.Response) -> None:
    """Translate a failure status into a typed exception.

    A 422 is deliberately *not* raised: it means "this inline position is not
    part of the diff", which the caller handles by demoting one comment.
    """
    status = response.status_code
    if 200 <= status < 300:
        return
    if status in (401, 403):
        raise GitHubAuthError(f"GitHub rejected the credentials (HTTP {status})")
    if status == 404:
        raise GitHubNotFoundError("GitHub could not find the repository or pull request (HTTP 404)")
    if status == 429:
        raise GitHubRateLimitError(
            "GitHub rate limited the request (HTTP 429)",
            retry_after=_retry_after(response),
        )
    if status >= 500:
        raise GitHubUnavailableError(f"GitHub is unavailable (HTTP {status})")
    raise GitHubError(f"GitHub returned an unexpected status (HTTP {status})")
```

**Validation happens before work, not after it.** Untrusted repository names are
rejected before any client is built:

```python
# app/github_client.py
    for label, value in (("owner", owner), ("repo", repo)):
        if not isinstance(value, str) or not value:
            return f"{label} is empty"
        if not _SAFE_OWNER_RE.fullmatch(value):
            return f"{label} contains characters GitHub does not allow"
        if set(value) <= {"."} or ".." in value:
            # "." / ".." / "a..b" pass the character class but resolve as path
            # traversal, which would retarget the request URL.
            return f"{label} is not a valid GitHub name"
```

and file reads check existence, file-ness, size and encoding before returning
text:

```python
# app/cli.py
    if not path.exists():
        raise ReviewInputError(f"no such file: {path}")
    if not path.is_file():
        raise ReviewInputError(f"not a regular file: {path}")
    size = path.stat().st_size
    if size > _MAX_BYTES:
        raise ReviewInputError(f"file is {size} bytes; limit is {_MAX_BYTES}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ReviewInputError(f"file is not valid UTF-8 text: {path}") from exc
```

Request bodies are validated by the model, not by hand:

```python
# app/main.py
    @field_validator("code")
    @classmethod
    def _no_null_bytes(cls, value: str | None) -> str | None:
        """Reject NUL bytes: they are never valid source and confuse every tool downstream."""
        if value is not None and "\x00" in value:
            raise ValueError("code contains NUL bytes")
        return value
```

and the demo's file-reading endpoint confines every resolved path to the project
root, answering 403 outside it and 404 when missing. The result is that every
rejection has a defined status: 422 for unusable input, 401 for a bad webhook
signature, 403 for an escaping path, 404 for an unknown rule, and 200 with
`posting.error` for anything that went wrong at GitHub.

## 4.8 Parameter passing and interfaces

The signatures below are the frozen interface: what the tests patch and the
front ends call.

```python
# app/engine.py
def select_provider(settings: Settings, *, requested: str = "auto") -> ProviderSelection
def review(bundle: DiffBundle, settings: Settings, *, provider: str = REQUEST_AUTO,
           force_offline: bool = False, min_severity: Severity | None = None,
           categories: Iterable[RuleCategory] | None = None) -> ProviderOutcome

# app/openai_compat_provider.py
def review_with_fallback(bundle: DiffBundle, config: OpenAICompatConfig | None, *,
                         min_severity: Severity | None = None,
                         categories: Iterable[RuleCategory] | None = None) -> ProviderOutcome

# app/parser.py
def parse_diff(raw: str, *, source: str = "<diff>") -> DiffBundle
def parse_diff_file(path: Path) -> DiffBundle
def anchor_findings(bundle: DiffBundle, findings: Iterable[Finding]) -> list[AnchoredFinding]

# app/rules.py
def review_diff(bundle: DiffBundle, *, min_severity: Severity | None = None,
                categories: Iterable[RuleCategory] | None = None) -> list[Finding]

# app/github_client.py
def fingerprint(finding: Finding) -> str
def build_payload(findings: Sequence[AnchoredFinding], diff_files: Sequence[FileDiff],
                  *, max_inline: int = 30) -> ReviewPayload
def post_review(owner: str, repo: str, pr_number: int, payload: ReviewPayload, *,
                token: str | None = None, commit_id: str | None = None) -> PostResult
```

Four conventions are visible in that list and are applied consistently.

*Positional for the subject, keyword-only for the options.* The thing being
operated on — the bundle, the finding, the payload — is positional; every
modifier after it is behind a bare `*`. `review(bundle, settings,
min_severity=...)` cannot be mis-called by argument order, and adding an option
later never breaks an existing call.

*`Iterable` in, `list` out.* Inputs that are only traversed are typed
`Iterable` (`findings`, `categories`), so a caller can pass a tuple, a generator
or a set; outputs are concrete `list`s, so the caller can index and re-iterate
without a second conversion.

*No mutable defaults.* Defaults are `None`, `"auto"`, `30`, `""` — never `[]` or
`{}`. `categories: Iterable[...] | None = None` means "no filter", which is
distinguishable from "an empty filter", and the function decides.

*Structured returns, never tuples.* `ProviderSelection`, `ProviderOutcome`,
`ReviewPayload` and `PostResult` are frozen dataclasses or models with named
fields, so a caller reads `result.inline_demoted` rather than `result[2]`, and
`PostResult` is comparable by value in a test.

Interfaces between layers are values rather than callbacks: the engine never
receives a client, the adapter never receives a renderer, and the CLI never
receives an HTTP session. That is what lets all 638 collected cases — 565 covering the
application and 73 the benchmark harness — run with the network blocked.

## 4.9 Summary

The implementation is small enough to read and constrained enough to trust: 15
modules totalling 9,250 lines, six tables, three roles, 63 rules, 638 collected
test cases. The schema
is executed DDL rather than prose, with `CHECK`, `UNIQUE` and foreign keys whose
delete behaviour is chosen per relationship — cascade for findings, set-null for
posting records, restrict for roles. Insertion is two bound statements in one
transaction, fed from the result objects the engine already produced, so storage
adds no second representation of a finding. Access is three roles, a tuple of
three capabilities, and a matrix measured against the running app rather than
asserted: two of those capabilities gate the six guarded routes, and the third is
stored but unenforced. The standards that matter are the ones
a test can see: complete annotations, no bare except, one warning
per degraded event, frozen values. Efficiency is bounded by construction — 4,000
characters of regex per line, a single parse pass, deduplication before object
construction — and measured: roughly 0.4–0.6 ms per added line for all 63 rules,
and about 0.2 s for a single pathological 5 MB line. Chapter 5 covers the
test strategy in full; chapter 6 the threats and the residual risks.
