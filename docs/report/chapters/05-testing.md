# 5 Testing and Evaluation

## 5.1 Testing objectives and strategy

Four objectives were set. Every one of the sixty-three rules must fire on a sample, so a
pattern broken by a refactor fails the suite instead of passing unnoticed. The degraded
path must be proven rather than assumed: each provider is tested with its dependency
present and absent, and the three labelling fields (`mode`, `provider`, `model`) are
asserted so a degraded run cannot present itself as a live one. Hostile input is treated as
an ordinary input class — backticks in paths, ten-thousand-token lines, control characters,
null bytes and truncated hunk headers are normal test inputs. And the suite must run with
the network removed and produce identical counts.

Four levels are used, with a sharp boundary between them.

**Unit tests** exercise one module through its public surface with every external
dependency replaced at a single documented seam. The governing rule, from `TESTING.md` §7,
is: never touch the network, and never fake the thing being tested. Both live adapters hide
their transport behind one module-level function — `app.openai_compat_provider._build_client`
and `app.github_client._build_github_client` — and tests patch only that function, so
retries, repair attempts, guards, parsing, degradation and labelling all run for real.
Failure replies use the genuine `openai` exception classes built against an `httpx.Request`
that is never sent, so the adapter's `except` clauses meet the real hierarchy rather than a
`RuntimeError` stand-in.

**Integration tests** drive the FastAPI application through the ASGI transport with
`TestClient`, and drive the GitHub client against a scripted `httpx` response queue. They
assert on recorded calls — order, bodies, headers — because what matters in the posting
state machine is which requests were made.

**System tests** treat the CLI and the webhook endpoint as black boxes: a diff goes in, a
report or an HTTP response comes out, and the exit code is asserted. The CLI tests are the
only place where configuration, provider selection, parser, engine and renderer are
exercised through the entry point a user types.

**Regression tests** are the fifteen cases in `tests/test_audit_gaps.py`, each pinning one
defect found in the final audit and repaired, so the repair cannot be silently reverted.

### Deliberately not tested

Three exclusions are design decisions, not oversights. There is **no live model**: every
model call goes to a scripted fake, so request shape, retry budget, repair retry, guards and
degradation are proven while the quality of any model's review is not. There is **no live
GitHub**: `app/github_client.py` is tested against a fake `httpx` client, so token scopes,
real rate-limit behaviour and GitHub's acceptance of the computed anchor positions are
unverified — a genuine 422 on a real inline comment is exactly the failure this cannot
catch. There is **no live Sarvam**: a fake key returning a real 403 was reproduced once by
hand and degraded correctly, but a successful hosted review has never been produced. There
is also no browser test, so a JavaScript-level breakage in `/docs` would not fail the suite.

## 5.2 Test environment and reproduction

The environment is pinned rather than described. `.python-version` fixes the interpreter,
the two requirements files declare exact versions with `==`, and `requirements.lock` holds
the resolved closure of thirty-seven distributions, which is what continuous integration and
the container image install. Two installs of one commit therefore resolve to identical
versions. Reproduction is a single command, `make verify`, which runs `scripts/verify.sh`:
create a virtualenv, install the lock, run the suite, then run the zero-network proof.

The proof is not a container flag. `scripts/verify_offline.py` imports pytest, installs
three guards on the `socket` module in the current process, and calls
`pytest.main(["-q", "tests"])`, so the suite runs in the interpreter that carries the
guards; a subprocess would not work and a `conftest.py` fixture could be bypassed.
`socket.create_connection` is replaced by a recorder that raises, `socket.getaddrinfo`
raises for every non-loopback hostname, and `socket.socket` is subclassed so a new
`AF_INET`/`AF_INET6` socket cannot be built. `AF_UNIX` and `fileno`-wrapped sockets stay
available because asyncio builds its self-pipe from a socket pair, and neither can open a
connection. Real output, captured for this report:

```text
Network blocked: outbound connections are disabled for this run (socket.create_connection and non-loopback getaddrinfo raise; new AF_INET/AF_INET6 sockets are refused; AF_UNIX/loopback stay available for asyncio's self-pipe).
........................................................................ [ 11%]
........................................................................ [ 22%]
........................................................................ [ 33%]
...........................................................s............ [ 45%]
........................................................................ [ 56%]
........................................................................ [ 67%]
........................................................................ [ 78%]
........................................................................ [ 90%]
..............................................................           [100%]
637 passed, 1 skipped in 38.83s
```

The counts match the unguarded run in §5.5. That identity, not the green colour, is the
proof.

## 5.3 Unit test cases

Twenty representative unit cases, quoted by their real identifiers; all passed in §5.5.

| ID | Module | Test case | Input | Expected | Result |
| --- | --- | --- | --- | --- | --- |
| UT-01 | `parser` | `test_parser.py::test_added_line_numbers_come_from_hunk_header` | Hunk header declaring `+1,8` | Added lines derived from header counters, not patch position | Pass |
| UT-02 | `parser` | `test_parser.py::test_anchor_statuses` | Changed line, unchanged line, absent file | `anchored`, `file_only`, `unanchored` | Pass |
| UT-03 | `parser` | `test_audit_gaps.py::test_truncated_hunk_does_not_swallow_the_next_file` | Header promising nine lines, patch holding one, then a second file | Two files; added lines `{2}` each | Pass |
| UT-04 | `rules` | `test_rules.py::test_each_rule_fires` | One sample per rule id, 63 ids | Named rule id among those fired | Pass |
| UT-05 | `rules` | `test_rules.py::test_bare_noqa_suppresses_the_line` | Credential literal with `# noqa` | No findings | Pass |
| UT-06 | `rules` | `test_rules.py::test_targeted_noqa_suppresses_one_rule` | Same line, `# noqa: <one id>` | That rule suppressed, others fire | Pass |
| UT-07 | `rules` | `test_rules.py::test_malicious_payloads_are_caught` | Labelled attack lines | Expected rule id fires | Pass |
| UT-08 | `rules` | `test_rules.py::test_benign_lines_do_not_fire` | Ordinary source lines | Empty finding list | Pass |
| UT-09 | `rules` | `test_rules.py::test_regex_flood_does_not_blow_up` | Ten lines of 5000 `if ` plus 5000 `select ` | Under five seconds, no exception | Pass |
| UT-10 | `rules` | `test_rules.py::test_findings_only_on_added_lines` | Defects on context and removed lines | No finding on an unadded line | Pass |
| UT-11 | `rules` | `test_rules.py::test_engine_is_deterministic` | Same diff twice | Byte-identical findings | Pass |
| UT-12 | `models` | `test_audit_gaps.py::test_sort_findings_is_a_total_order_across_files` | Equal severity in `z.py`, `a.py`, `m.py`, then reversed | `a.py`, `m.py`, `z.py` both times | Pass |
| UT-13 | `github_client` | `test_github_client.py::test_fingerprint_is_stable_across_calls` | One finding, fingerprinted twice | Same sixteen-hex digest | Pass |
| UT-14 | `github_client` | `test_github_client.py::test_build_payload_respects_inline_cap` | Four anchored findings, `max_inline=1` | One inline, three dropped, summary states both counts | Pass |
| UT-15 | `github_client` | `test_github_client.py::test_render_inline_body_marker_appears_exactly_once` | One rendered body | Marker line once, at the end | Pass |
| UT-16 | `github_client` | `test_audit_gaps.py::test_a_hostile_path_cannot_break_out_of_the_code_span` | File `` x`[click](https://evil.example)` `` | Head fenced with double backticks | Pass |
| UT-17 | `openai_compat_provider` | `test_openai_compat_provider.py::test_prose_then_valid_json_repairs_without_response_format` | Prose reply, then valid JSON | Two calls; second omits `response_format` | Pass |
| UT-18 | `sarvam_provider` | `test_sarvam_provider.py::test_api_key_never_appears_in_outcome_reason_or_logs` | Key echoed in a failure message | Key absent from reason and logs | Pass |
| UT-19 | `config` | `test_audit_gaps.py::test_settings_repr_hides_credentials` | Three credentials in the environment | None appears in `repr(Settings())` | Pass |
| UT-20 | `github_client` | `test_posting_hardening.py::test_safe_next_url_refuses_offsite_links` | Pagination link to a foreign host | Link refused; token cannot be redirected | Pass |

Two properties matter here. The rule cases are parametrised — `tests/test_rules.py` has
thirty-four functions collecting one hundred and eighty-seven cases — so the collected
count is what ran and a `grep -c "def test_"` undercounts by the parametrisation factor.
And the negative cases carry as much weight as the positive ones: UT-08 and UT-10 stop the
engine from being a machine that reports everything, and UT-05 and UT-06 pin suppression
semantics a refactor could easily invert.

## 5.4 Integration and system test cases

| ID | Level | Test case | Input | Expected | Result |
| --- | --- | --- | --- | --- | --- |
| IT-01 | Integration | `test_api.py::test_review_a_diff` | `POST /review` with a diff | 200; findings carry the five contract fields | Pass |
| IT-03 | Integration | `test_api.py::test_no_endpoint_requires_a_key` | Default configuration (`API_AUTH_ENABLED` unset), all three credentials deleted | `/health`, `/test-review`, `/review`, `/webhook` answer 200 with no credential | Pass |
| IT-04 | Integration | `test_webhook_posting.py::test_duplicate_delivery_is_skipped_without_any_post` | Marker already on the pull request | No review POST; `skipped_dup` true; 200 | Pass |
| IT-05 | Integration | `test_webhook_posting.py::test_422_demotes_a_comment_and_still_posts_the_summary` | Bulk review refused with 422 | Per-comment retry, offender demoted, summary posted | Pass |
| IT-06 | Integration | `test_github_client.py::test_post_review_429_is_retried_once_honouring_retry_after` | 429 with `Retry-After` | One retry after the recorded wait, then success | Pass |
| IT-07 | Integration | `test_github_client.py::test_post_review_429_twice_degrades_to_summary_only` | Two consecutive 429s | No further retry; summary alone attempted | Pass |
| IT-08 | Integration | `test_github_client.py::test_post_review_auth_failure_posts_no_summary` | 401 on the review request | Post fails, no summary, typed auth error | Pass |
| IT-10 | Integration | `test_openai_compat_provider.py::test_auto_with_both_configured_sarvam_wins_over_local` | Sarvam key and local URL both set | Sarvam selected, model `sarvam-m` | Pass |
| IT-11 | Integration | `test_openai_compat_provider.py::test_forced_local_without_the_url_degrades_to_mock_naming_lmstudio_base_url` | `provider=local`, no base URL | Rule engine runs; reason names `LMSTUDIO_BASE_URL` | Pass |
| ST-01 | System | `test_cli.py::test_missing_path_exits_2` | `reviewer.py` with no argument | Exit 2, `error: a path is required unless --list-rules is used` | Pass |
| ST-02 | System | `test_cli.py::test_posting_auth_failure_exits_1` | Post with rejected credentials | Exit 1, not 0 | Pass |
| ST-03 | System | `test_cli.py::test_json_stdout_stays_pure_with_posting` | `--json` with `--post-to-pr` | One JSON document on stdout; narration on stderr | Pass |

The webhook cases assert the *sequence* of calls, not only the outcome, because the defect
they guard against is a call that should never have been made. The exit-code cases treat
the process boundary as part of the contract: 0 for success and for a duplicate delivery,
1 for an input or upstream error, 2 for a usage error — and a *posting* failure is 1 while
a *degraded review* is 0, because a degraded review is a correct answer rather than a
failed command. Both branches were run by hand as well as through the suite: `reviewer.py`
with no argument exits 2 with `error: a path is required unless --list-rules is used`, and
`reviewer.py samples/sample.diff --post-to-pr bad-format` exits 2 with `error: --post-to-pr
expects OWNER/REPO#NUM`. A path that does not exist is a different branch: `reviewer.py
/no/such/file.diff` exits **1** with `error: no such file: /no/such/file.diff`, because a
missing input is an input error and not a usage error. The suite pins the usage-error branch
(ST-01); the missing-file branch was verified by hand while preparing this chapter and has
no case of its own.

IT-03 fixes the default posture described in Chapter 6: with `API_AUTH_ENABLED` unset, no
endpoint requires a credential. That is a claim about the default configuration, not about
the software, and the difference is asserted rather than glossed.
`test_auth.py::test_guarded_endpoints_need_a_key_only_when_auth_is_on` walks the same six
routes twice — open while the flag is off, and answering 401 with `missing X-API-Key header`
once `API_AUTH_ENABLED=1`, with 403 reserved for a known caller whose role is too weak. The
six are `GET /reviews`, `GET /reviews/{id}`, `GET /stats`, `POST /users`, `GET /users` and
`PATCH /users/{id}`. `/health`, `/test-review`, `/review` and `/webhook` stay open in both
configurations, which is what `test_the_review_surfaces_stay_open_even_when_auth_is_on`
asserts. `test_posting_failure_still_returns_200_with_the_review` and
`test_transport_error_still_returns_200_with_the_review` further establish that any posting
failure, typed or unexpected, leaves the status at 200 and reports itself in the additive
`posting` field, because GitHub retries a 5xx delivery indefinitely over a defect that will
not resolve itself.

## 5.5 Test execution report

All figures were produced on the checked-in tree, on Python 3.12.13, while preparing this
report.

```text
$ python -m pytest -q tests
........................................................................ [ 11%]
........................................................................ [ 22%]
........................................................................ [ 33%]
...........................................................s............ [ 45%]
........................................................................ [ 56%]
........................................................................ [ 67%]
........................................................................ [ 78%]
........................................................................ [ 90%]
..............................................................           [100%]
637 passed, 1 skipped in 29.27s

$ python -m pytest -q tests --collect-only | tail -3
tests/test_webhook_posting.py::test_clean_diff_posts_nothing_at_all

638 tests collected in 8.09s
```

The suite collects 638 cases and executes 637; all pass, one is skipped. Elapsed time
varies between runs on the same machine — 21.12 s, 23.02 s, 29.27 s, 32.60 s and 35.18 s
were observed here, and 38.83 s with the sockets guarded — because it is a wall-clock
measurement, and the machine used for this chapter is slower than the one that produced an
earlier draft. The counts do not vary.

| Test file | Cases | Covers |
| --- | --- | --- |
| `test_parser.py` | 11 | Diff parsing, anchoring |
| `test_rules.py` | 187 | The 63 rules, suppression, bounds |
| `test_openai_compat_provider.py` | 51 | The adapter, retry budget, guards |
| `test_sarvam_provider.py` | 87 | The legacy SDK path and shared guards |
| `test_github_client.py` | 54 | Fingerprint, payload, posting state machine |
| `test_posting_hardening.py` | 32 | Pagination, SSRF guard, retry parsing, hostile target |
| `test_webhook_posting.py` | 27 | Webhook to posting end to end |
| `test_api.py` | 47 | Every endpoint, OpenAPI schema |
| `test_cli.py` | 14 | Flags, exit codes, JSON purity |
| `test_audit_gaps.py` | 15 | Regression tests for the audit fixes |
| `test_db.py` | 27 | Schema, constraints, persistence, hashing |
| `test_auth.py` | 13 | API keys, roles, 401/403 |
| `test_matching.py` | 35 | Greedy matching and equivalence |
| `test_metrics.py` | 20 | Precision, recall, latency |
| `test_runner_mock.py` | 18 | Benchmark modes and artefacts |
| **Total** | **638** | 637 execute and pass; 1 skips by design |

Five hundred and sixty-five cases exercise the application and seventy-three the benchmark
harness. The split is read off the table itself: its last three rows — `test_matching.py`
(35), `test_metrics.py` (20) and `test_runner_mock.py` (18) — are the benchmark layer, and
the other twelve files are the application, 638 − 73 = 565. The split is lopsided in a way
that reflects risk, since nearly a third of the suite covers the rule engine, the component
that runs on every request and whose output the user reads as fact. Two documentation
drifts were found while producing this table, all in the supporting documents rather than in
the suite: `TESTING.md` §1 describes twelve files and no benchmark tests, whereas the tree has
fifteen files and seventy-three benchmark cases, and one older table sums to 510 against a
stated total of 596. The measured counts above are authoritative: 638 collected, 637 passing,
one skipped by design.

### The single skipped test

```text
$ python -m pytest -q tests -rs
........................................................................ [ 11%]
........................................................................ [ 22%]
........................................................................ [ 33%]
...........................................................s............ [ 45%]
........................................................................ [ 56%]
........................................................................ [ 67%]
........................................................................ [ 78%]
........................................................................ [ 90%]
..............................................................           [100%]
=========================== short test summary info ============================
SKIPPED [1] tests/test_openai_compat_provider.py:1062: needs a live LM Studio server
637 passed, 1 skipped in 23.02s
```

The test is
`tests/test_openai_compat_provider.py::test_live_smoke_review_against_a_real_endpoint`,
guarded by `@pytest.mark.skipif(not LIVE_BASE_URL, ...)` reading `LMSTUDIO_BASE_URL`.
Skipping is correct. It cannot pass in continuous integration, and a suite that goes red
for an environmental reason trains people to ignore red. It would not prove what its name
suggests: it asserts that a run completes and accepts a mode of either `live` or `mock`,
because a configured but silent endpoint is a legitimate degradation — a wiring check, not
a quality check. Everything it would exercise is covered by the other fifty tests in the
same file against a scripted fake. And it is opt-in through one variable, though that path
has never been exercised here, because no endpoint has ever been available. The honest
reading: 637 tests prove the offline behaviour of every layer, and one is a live wiring
check that CI must not run.

### Slowest tests

```text
$ python -m pytest -q tests --durations=5
........................................................................ [ 11%]
........................................................................ [ 22%]
........................................................................ [ 33%]
...........................................................s............ [ 45%]
........................................................................ [ 56%]
........................................................................ [ 67%]
........................................................................ [ 78%]
........................................................................ [ 90%]
..............................................................           [100%]
============================= slowest 5 durations ==============================
0.41s call     tests/test_auth.py::test_a_review_is_stored_and_readable
0.40s call     tests/test_auth.py::test_guarded_endpoints_need_a_key_only_when_auth_is_on
0.34s call     tests/test_auth.py::test_a_bad_key_is_401_and_a_weak_role_is_403
0.29s call     tests/test_auth.py::test_users_lifecycle_from_the_seed_admin
0.27s call     tests/test_auth.py::test_health_reports_the_database_state
637 passed, 1 skipped in 22.76s
```

The profile is itself a finding, and a different one from the profile an earlier draft of
this chapter recorded. The five slowest cases are all in `tests/test_auth.py`, which builds
a temporary SQLite database per test and drives the guarded routes through it, so the cost
is database setup and the SQLAlchemy layer rather than anything the review code does; no
case reaches a second. The hundredths and the order inside the top five move between runs —
`test_guarded_endpoints_need_a_key_only_when_auth_is_on` came first at 0.47 s in one run and
second at 0.40 s in the run quoted above — so what repeats is the set of five cases and the
sub-second ceiling, not the ranking. What also does not move: no test sleeps and no test
waits on a socket. That is the practical consequence of the seam discipline, since retry waits cost
milliseconds because `time.sleep` is patched at the module and the recorded waits are
asserted instead of endured.

## 5.6 Defect log

| ID | Description | Severity | Root cause | Fix | Regression test |
| --- | --- | --- | --- | --- | --- |
| DL-01 | A `diff --git` line followed by a plain `---`/`+++` pair produced a phantom hunk-less duplicate file, inflating the changed-file count. | High | The header branch always opened a new builder, ignoring the one already open. | Reuse the open builder when it has neither header nor hunks. | `test_audit_gaps.py::test_truncated_hunk_does_not_swallow_the_next_file` |
| DL-02 | A truncated hunk swallowed the next file, misattributing its findings. | High | The hunk loop trusted the header's counts and consumed the next `diff --git` line. | A new file header closes the open hunk first. | `test_audit_gaps.py::test_truncated_hunk_does_not_swallow_the_next_file` |
| DL-03 | One degraded posting event logged two `WARNING` records, so alerting counted a single failure twice. | Medium | Both the webhook handler and `post_review` logged the same failure at `WARNING`. | `post_review` owns the single `WARNING`; the handler logs `DEBUG` and reports in `posting`. | `test_webhook_posting.py::test_posting_failure_logs_once_and_never_leaks_the_token` |
| DL-04 | A backtick in a diff path broke out of the code span, letting attacker-chosen text render as a live markdown link in the bot's own comment. | High | The path was interpolated into a single-backtick span; escapes do not work inside code spans. | `_md_code` fences with one more backtick than the longest run in the value. | `test_audit_gaps.py::test_a_hostile_path_cannot_break_out_of_the_code_span` |
| DL-05 | Finding order was not total: equal severity and line in different files returned in input order. | Medium | The sort key was `(severity, line)` with no file component and no tie-break. | `sort_findings` orders by severity, line, file, then issue text. | `test_audit_gaps.py::test_sort_findings_is_a_total_order_across_files` |
| DL-06 | When the diff could not be fetched, the webhook reviewed the bundled fixture and posted those findings to the real pull request. | Critical | The degrade-to-fixture path was shared between showing and publishing; the posting branch never checked the source. | A fixture-sourced review is never posted; the notice says so and `posting` stays `None`. | `test_audit_gaps.py::test_webhook_never_publishes_fixture_content` |
| DL-07 | A single 422 on any inline comment failed the whole review, so one unplaceable line cost the author every other comment. | High | The review was posted as one bulk request and any refusal failed the post. | On 422, retry per comment, demote the offender into the summary, still succeed, warn once. | `test_github_client.py::test_post_review_422_demotes_only_the_rejected_comment` |
| DL-08 | Three artefacts disagree on the interpreter: `.python-version` pins 3.12.13, `verify.sh` prefers `python3.10`, the container comment tracks 3.10. | Medium | The pin was raised in one place in Phase 6 and its two consumers were not updated. | Not repaired; the script warns on fallback and `docs/REPRODUCIBILITY.md` §3 records it. | None; configuration drift found by inspection. |

The two highest-severity defects (DL-04, DL-06) both concern output that leaves the system
— a comment rendered on someone else's pull request — and neither is reachable by testing
components in isolation; they were found by asking what an attacker or an outage could make
the system *say*. DL-08 is listed although unrepaired, because a defect log containing only
fixed defects is a record of success rather than a record of the work.

## 5.7 Debugging approach and tools

Four choices make the suite debuggable without a debugger. **Assertion on recorded
calls**: both HTTP doubles keep the requests they were given, so a failure prints what the
code asked for, not merely that the answer was wrong. **One seam per dependency**,
findable with `grep -n "^def _build" app/<module>.py`, so a test never patches an import
site and silently stops covering client construction. **`-x -l` as the default failure
mode**, because on a twenty-second suite there is no reason to read a hundred failures at
once. **Keyword selection**: `-k "sql"` selects fifteen cases — the fourteen parametrised
SQL and NoSQL rule cases plus `test_db.py::test_the_database_is_a_real_sqlite_file` — which
is the cheapest way to follow one rule family from the pattern that fires to the row it is
persisted in.

Beyond pytest, two tools carried the work. `scripts/verify_offline.py` answers "is this
test secretly using the network", failing at the attempt rather than at the assertion.
`--durations=5` is the first command when the suite creeps, and its current profile is the
baseline to compare against. For the benchmark harness the artefacts are the debugger:
`metrics.csv` carries per-category tallies beside the aggregate, so a surprising precision
figure is traceable to the category that produced it.

## 5.8 Limitations of the testing effort

The suite proves plumbing, not judgement. Every model call is scripted and every GitHub
response replayed: what is proven is that the right request is sent and the right reply
handled, not that a real model produces useful findings or that GitHub accepts the computed
positions. The most likely production failure — a 422 on a real inline comment because
GitHub's view of the diff differs from ours — is simulated, not observed.

There is no performance or resource assertion: `--durations=5` reports what happened and
nothing fails when it gets worse, so a change that doubled review time would pass. No
line-coverage figure is quoted in this report, because none was produced; a coverage
percentage would measure the wrong thing while creating the impression of a measured one.
The benchmark layer's numbers are a smoke test over two format examples, excluded from
every published metric. Two documentation drifts remain in the tree and are recorded rather
than tidied. Finally, the zero-network proof is a proof about this interpreter: a test that
shelled out to a subprocess could in principle reach the network from the child. No test
does so, and the guarantee is stated for what it is.

## 5.9 Summary

The suite comprises 638 collected cases across fifteen files, of which 637 execute and
pass and one is skipped by design; 565 cover the application and 73 the benchmark harness.
It runs in twenty-one to thirty-nine seconds on the machine used here, with no case above
a second, and produces identical
counts with outbound sockets disabled in the same interpreter.

The strategy behind those numbers is a sharp boundary: one patched seam per dependency,
real exception classes rather than stand-ins, assertion on recorded calls, and hostile input
as an ordinary input class. What the suite proves is that every layer behaves correctly with
no credential and no network, that every rule fires, that every degraded path degrades
observably, and that a defect once found stays fixed. What it does not prove is the quality
of any model's review, GitHub's acceptance of any real comment, or behaviour under load.
Those exclusions are stated in §5.1 and repeated in §5.8, because a green suite read as a
stronger claim than it is becomes a liability rather than an asset.
