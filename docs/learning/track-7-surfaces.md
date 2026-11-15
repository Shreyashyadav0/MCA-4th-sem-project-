# Track 7 — app/cli.py, app/main.py, app/github_client.py (surfaces)

## Prerequisite check

This track assumes the four tracks below it. If any answer is missing, read that
track first; nothing here re-explains them.

- Which function chooses the provider, and what three fields describe what ran?
  (Track 6: `app/engine.py:318` `review()`, and `ProviderOutcome.mode`,
  `.provider`, `.model`.)
- What are the three anchor statuses, and which of them can carry an inline PR
  comment? (Track 2: `anchored` only.)
- Where do findings come from with no credentials? (Track 3/4: `app/rules.py` via
  `app/openai_compat_provider.review_with_fallback(bundle, None, ...)`.)
- What does a blank `GITHUB_TOKEN` mean? (Track 1: unset, never an error.)

```bash
grep -n "_EXIT_" app/cli.py        # the exit-code constants and every return site
grep -n "@app\." app/main.py       # every endpoint, in file order
```

## What it does

`app/cli.py` parses a flag surface (`--provider`, `--offline`, `--json`,
`--min-severity`, `--post-to-pr`, `--list-rules`), reads one file or one patch,
calls `engine.review()`, prints a report or a JSON document, and returns a process
exit code from a fixed set of three: 0 for a produced review, 1 for bad input or a
failed post, 2 for a usage error. `app/main.py` exposes the same engine over
FastAPI — `POST /review`, `GET|POST /test-review`, `POST /webhook`, `GET /rules`,
`GET /rules/{rule_id}`, `GET /health`, `GET /` — with every review response
carrying honest `mode`, `provider` and `model` fields. `app/github_client.py` is
the publishing layer both of them call: it renders findings into one inline
comment each plus a summary, and runs a posting state machine that degrades every
GitHub and transport failure into a `PostResult` instead of raising.

## Why it exists

The engine can only be trusted if its two claims survive contact with a real
caller: that it never dies for want of a credential, and that it never lies about
which provider ran. The CLI is the surface where the first claim is cheapest to
test (`echo $?` after unsetting every variable), the API is where the second claim
is load-bearing (a CI job gates on `mode`), and the webhook is where both meet the
one caller that cannot be negotiated with — GitHub, which retries a 5xx forever
and treats a non-2xx acknowledgement as a delivery failure. So this layer's job is
not "expose the engine"; it is to absorb every failure that would otherwise become
an exit code or an HTTP status the caller would misread.

## Key references

- `app/cli.py:50` — `_EXIT_OK = 0`, `_EXIT_INPUT_ERROR = 1` (`:51`),
  `_EXIT_USAGE = 2` (`:52`). Three codes, no others.
- `app/cli.py:88` — the `--provider` flag, with `choices` built from
  `engine.REQUEST_AUTO` and the three provider names, so `argparse` rejects an
  unknown name with exit 2 before any work happens.
- `app/cli.py:123` — `--post-to-pr`; `app/cli.py:309` `parse_post_target()` is the
  strict `OWNER/REPO#NUM` parser (`_POST_TO_PR_RE`, `app/cli.py:59`).
- `app/cli.py:483` — the up-front validation block: the post target is parsed and
  rejected before the file is read, and `app/cli.py:491` rejects a missing path.
- `app/cli.py:403` — `_report_posting()` returns `_EXIT_OK` when the post succeeded
  *or* was skipped as a duplicate, `_EXIT_INPUT_ERROR` otherwise. A duplicate is
  not a failure.
- `app/main.py:1135` — `@app.post(`, with the path `"/webhook"` on line 1136. The
  handler order is: signature (`app/main.py:1176`), body read (`:1171`), event filter
  (`:1186`), action filter (`:1194`), diff source, then `_publish_review`
  (`app/main.py:772`, called at `:1222` and `:1259`).
- `app/main.py:835` — `except Exception  # noqa: BLE001 - deliberate: GitHub must
  never see a 5xx`: the webhook boundary converts any posting exception into
  `posting.ok = False` and keeps the status at 200.
- `app/github_client.py:1115` — the duplicate check: the payload's summary
  fingerprint is looked for among the PR's existing markers, and the whole post is
  skipped when it is already there.
- `app/github_client.py:1135` — the single 429 retry on the inline review;
  `app/github_client.py:1168` — `elif status == 422:`, the per-comment retry whose
  repeat 422s demote that one comment into the summary instead of failing the post.

## The three hardest ideas

### (a) A posting failure must never change the HTTP status

GitHub treats any 5xx from a webhook endpoint as a delivery failure and retries
the same delivery — with backoff, and then it shows the operator a red mark on the
repository. A review we could not *attach* is not a bad request and not a server
error: the review itself succeeded, and only the publish step failed. So the
locked decision is that `_publish_review` reports the failure inside the response
body (`posting.ok = False`, `posting.error`) and the status stays 200.

This is a deliberate split between *what the request asked for* (a review of this
pull request — delivered) and *what the side effect did* (post it — failed, and
will fail again identically on a retry, so retrying is pointless). Malformed input
is still reported as malformed: an unparseable `diff` is 422 and a bad
`X-Hub-Signature-256` is 401, because those are genuinely the caller's fault.

Worked mini-example (executed against this tree with `GITHUB_TOKEN` and
`GITHUB_WEBHOOK_SECRET` set, `_build_github_client` patched to return 500 on every
call):

```
bad sig:            401  X-Hub-Signature-256 does not match
good sig + 5xx:     200  {'ok': False, 'inline_posted': 0, 'inline_demoted': 0,
                          'summary_posted': False, 'skipped_dup': False,
                          'error': 'GitHub is unavailable (HTTP 500)'}
bad diff (/review): 422  cannot parse diff: no file headers found; ...
```

Read the middle line carefully: the engine still produced a review (that is what
the request asked for), GitHub was down for the post, and the caller is told both
facts in one 200. The same rule holds on the CLI, where the exit code is 1 — a
shell script wants to know the post failed, and there is no retry loop to protect.

### (b) The idempotency marker hashes the findings, not the commit

Every body the poster writes ends with `<!-- ai-code-reviewer:<16 hex> -->`. The
fingerprint behind it is SHA-256 over exactly four identity fields — `file`,
`line`, `severity`, and the whitespace-normalised `issue` — joined by `\x1f`
(`app/github_client.py:236`). The suggested fix is excluded, and so is the commit
SHA.

Hashing the findings rather than the commit is what makes the check useful on a
real pull request. A PR receives many `synchronize` events; a push that only
touches a README re-runs the review and yields the same findings, and re-posting
them would spam the PR with duplicates. Hashing the head SHA would make every push
look new, which is exactly the behaviour the marker exists to prevent. The
trade-off is stated in the module docstring and is deliberate: an identical
re-review of a later push is treated as a duplicate, so a finding that survived a
push is not re-announced.

Worked mini-example (executed; the two findings differ only in
`suggested_fix`):

```python
f = Finding(file="app/db.py", line="3", severity=Severity.CRITICAL,
            issue="SQL built by f-string", suggested_fix="use a parameter")
g = f.model_copy(update={"suggested_fix": "something else entirely"})
print(fingerprint(f), fingerprint(g), fingerprint(f) == fingerprint(g))
```

```
6904ba9e1e54cb2e 6904ba9e1e54cb2e True
<!-- ai-code-reviewer:6904ba9e1e54cb2e -->
```

The summary marker goes one level up: `_summary_fingerprint`
(`app/github_client.py:429`) hashes the sorted fingerprints of *every* comment in
the payload, inline and demoted, so one changed finding produces a new marker and
a whole-post duplicate is detected in a single listing call.

### (c) The CLI validates `--post-to-pr` before doing any review work

`run()` parses the post target at `app/cli.py:483`, before `read_source`
(`:496`), before `Settings()` (`:502`) and before `engine.review()` (`:516`). A
malformed value returns exit 2 with one line on stderr and nothing else happens.

Two reasons, both about the meaning of the exit codes. First, a malformed flag is
a *usage* error (2), not an *input* error (1), and a user who mistypes a repository
must not have to wait for a model call — or pay for one — to learn that. Second,
the two errors must stay distinguishable: if the parse happened after the review,
the process would already have produced output and, on the live path, already have
spent a network round trip; the exit code would then be reporting a failure that
occurred after success, which is the ambiguity the three-code scheme exists to
avoid.

Worked mini-example (executed; no credentials exported):

```
[--post-to-pr bad-format samples/sample.diff]   exit=2  error: --post-to-pr expects OWNER/REPO#NUM
[]                                              exit=2  error: a path is required unless --list-rules is used
[--post-to-pr o/r#1 app/config.py]              exit=1  error: --post-to-pr needs a diff review; ...
[--post-to-pr o/r#1 samples/sample.diff]        exit=1  WARNING reviewer.github: GITHUB_TOKEN not configured; ...
[samples/sample.diff]                           exit=0  (mock review printed)
```

Note the two middle rows: a *well-formed* target pointed at a source file is exit 1,
not 2, because the flag was valid and the input was not. `--post-to-pr` requires
diff mode; there are no anchors to attach to in a single file, so the run stops
before reviewing with a message that says exactly that (`app/cli.py:507`).

## Rebuild exercise

Rebuild the three surfaces against the engine without reading the originals, then
compare.

1. **CLI.** `build_parser()` with `path` (optional), `--diff`, `--provider`
   (`auto|local|sarvam|mock`), `--offline`, `--json`, `--verbose`,
   `--min-severity`, `--post-to-pr OWNER/REPO#NUM`, `--list-rules`, `--version`.
   `run()` returns 0/1/2 per the table below. `--json` must keep stdout a single
   JSON document, which is why the posting report moves to stderr
   (`app/cli.py:328`).
2. **API.** FastAPI app with the seven endpoints, one funnel
   (`_build_response`, `app/main.py:459`) that parses once and returns
   `ReviewResponse` with `source`, `notice`, `review`, `comment`, `stats`,
   `provider`, `model`, `posting`. `POST /review` returns 422 for a diff that does
   not parse; `POST /webhook` verifies HMAC when a secret is configured, filters
   events and actions, and never returns 5xx for a posting failure.
3. **Posting.** Pure renderers (`fingerprint`, `render_inline_body`,
   `render_summary_body`, `build_payload`) plus `post_review`, which converts
   every failure into `PostResult` and never raises.

| Situation | CLI | API |
|---|---|---|
| review produced, no post | 0 | 200 |
| bad `--post-to-pr` shape / unknown `--provider` | 2 | 422 (body) / 400 by FastAPI |
| missing file, unparseable diff | 1 | 422 |
| post failed (401/403/404/429/5xx/transport) | 1 | 200 with `posting.ok = false` |
| post skipped as duplicate | 0 | 200 with `posting.skipped_dup = true` |

Acceptance checks (all offline, no credentials):

```bash
python reviewer.py samples/sample.diff; echo $?                       # 0
python reviewer.py nope.diff; echo $?                                 # 1
python reviewer.py --post-to-pr bad samples/sample.diff; echo $?       # 2
python -m pytest -q tests/test_cli.py tests/test_api.py \
  tests/test_github_client.py tests/test_posting_hardening.py \
  tests/test_webhook_posting.py
```

## Self-test questions

1. `python reviewer.py --post-to-pr o/r#1 samples/sample.diff` exits 1 with a
   `GITHUB_TOKEN not configured` warning. Which line decides that exit code, and
   why is it 1 rather than 2 or 0?
2. A webhook delivery arrives with a valid signature while `api.github.com` is
   returning 500. Give the status code the handler returns, the field that reports
   the failure, and the reason a retry would not help.
3. Two findings differ only in `suggested_fix`. Explain, with reference to
   `fingerprint()` and `_summary_fingerprint()`, whether the second one is treated
   as a duplicate of the first, and what the consequence is on a later push.
4. The inline review POST returns 422 on a PR with five comments. Describe what
   `post_review` does next, what the caller sees in `PostResult`, and why the post
   is not failed outright.
5. `GET /health` and `POST /review` can disagree about the provider (one says
   `mock`, the other `sarvam`) without either being wrong. Explain when that
   happens and which field of each response you would read to prove it.
