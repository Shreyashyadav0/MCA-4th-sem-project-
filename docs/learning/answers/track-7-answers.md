# Track 7 — app/cli.py, app/main.py, app/github_client.py answer key

**1. `python reviewer.py --post-to-pr o/r#1 samples/sample.diff` exits 1 with a
`GITHUB_TOKEN not configured` warning. Which line decides that, and why 1?**

`_report_posting` returns `_EXIT_INPUT_ERROR` when the `PostResult` is neither `ok`
nor `skipped_dup`, and a missing token produces exactly that result from
`post_review`. It is 1 rather than 2 because the flag was well formed and the input
was valid — the *side effect* failed — and it is not 0 because a script that asked
for a post must be able to see that no post happened.
Check: `app/cli.py:403`.

**2. A webhook delivery arrives with a valid signature while `api.github.com`
returns 500. What status comes back, and why is a retry pointless?**

HTTP 200, with `posting.ok = false` and `posting.error` set to `GitHub is
unavailable (HTTP 500)`; the handler catches the posting exception at the webhook
boundary and never lets it become a 5xx. A retry would re-run the same review
against the same outage and fail identically, and because GitHub retries a 5xx
delivery indefinitely, answering 5xx would turn an upstream outage into a delivery
loop against our own endpoint.
Check: `app/main.py:651`.

**3. Two findings differ only in `suggested_fix`. Is the second a duplicate?**

Yes. `fingerprint` hashes only file, line, severity and the normalised issue, so the
two findings share a fingerprint; `_summary_fingerprint` hashes the sorted set of
those fingerprints, so the payload marker is unchanged too. On a later push whose
review yields the same findings, the marker is already on the PR and the whole post
is skipped with `skipped_dup = True` — a deliberate trade, stated in the module
docstring, that avoids re-announcing surviving findings on every push.
Check: `app/github_client.py:249`, `app/github_client.py:444`.

**4. The inline review POST returns 422 on a PR with five comments. What happens
next?**

`post_review` re-posts each comment as its own single-comment review, keeping the
ones GitHub accepts and demoting each one that 422s again into the summary; the
summary is then rebuilt so the demoted findings appear in it. The caller sees
`ok=True` with `inline_demoted` counting the demotions, because a comment that
cannot be attached is not a failed review — the finding is still delivered, just in
the summary body.
Check: `app/github_client.py:1168`, `app/github_client.py:1223`.

**5. `GET /health` and `POST /review` can disagree about the provider without
either being wrong. When, and which field proves it?**

`/health` reports what the *next* review would select from the current
configuration, while each review response reports the provider that actually ran, so
a configured-but-failing live endpoint gives `provider: sarvam` from `/health` and
`provider: mock` plus `mode: mock` from the review that degraded. Read
`HealthResponse.provider` against `ReviewResponse.provider` (and `review.mode`) to
see the difference; the per-response labels come straight from
`ProviderOutcome`, so neither surface is guessing.
Check: `app/main.py:706`, `app/main.py:539`.
