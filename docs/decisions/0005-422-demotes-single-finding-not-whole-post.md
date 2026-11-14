# 0005 — A 422 demotes one finding to the summary, never the whole post

## Status

Accepted — 2026-11-14

## Context

GitHub's review API rejects an inline comment anchored to a line that is not part of
the diff with HTTP 422. The anchor is computed from a parsed diff and a canonicalised
path, so the 422 should be rare — but "rare" is not "never": GitHub's own diff
representation can differ from ours after a force-push, a rename, or a path spelled
two ways.

The unit of failure matters. A review is one API call carrying up to
`GITHUB_MAX_INLINE` (default 30) inline comments plus a summary. If a 422 on any one
of them failed the whole request, a single unplaceable line — usually the least
interesting finding in the set — would cost the author every other comment, including
the CRITICAL ones.

## Decision

`post_review` treats a 422 on the bulk review as "retry per comment, demote the
offenders" (`app/github_client.py`). `_raise_for_status`
(`app/github_client.py:691`) deliberately does not raise on 422: "it means 'this
inline position is not part of the diff', which the caller handles by demoting one
comment."

- On 422 the bulk review is retried one comment at a time, each as a one-comment
  payload from `_single_review_payload` (`app/github_client.py:940`), whose review
  body is empty so the summary is not repeated per comment.
- A success counts as posted; a refusal appends that comment to `demoted` and the
  loop continues (`app/github_client.py:1213`): "A 422 (or any other refusal) means
  'this position is not in the diff': demote that one comment, keep the rest."
- The summary is then rebuilt with `dropped=tuple(payload.dropped) + tuple(demoted)`
  (`app/github_client.py:1226`), so every demoted finding still reaches the author.
- The post still returns `ok=True`, with one WARNING naming the count
  (`app/github_client.py:1254`) and `inline_demoted` set on `PostResult`.
- Credential, 404 and 5xx failures still fail the whole post — only a 422 is a
  per-comment verdict.

## Consequences

Positive: one bad anchor costs one inline comment, not the review. The demoted finding
is not lost — it moves to the summary, so the author sees everything. The outcome is
observable: `PostResult.inline_demoted`, the CLI's `demoted : N moved to the summary`
line, and the single WARNING. Covered by
`tests/test_github_client.py:701` (only the rejected comment demotes),
`:733` (all comments demote), `:985` (exactly one warning) and
`tests/test_webhook_posting.py:518` (summary still posted).

Negative: the fallback costs a per-comment retry loop — up to 30 extra API calls in
the worst case, each with its own 429 handling — and it needs the one-extra-call
payload builder plus the summary rebuild. That is meaningfully more code than a
single `return PostResult(False, ...)`, and it is the kind of branch that only a
mocked test exercises, because a real 422 is hard to provoke on purpose.

## Alternatives considered

**Fail the whole post on 422 and report the error.** Simplest, and it throws away
every other finding because of one bad line. Rejected.

**Pre-filter aggressively so a 422 cannot happen.** Already done at build time
(`build_payload` sends `file_only` and `unanchored` findings straight to the summary),
but it cannot cover GitHub's view of the diff diverging from ours. Rejected as
insufficient, not as wrong.

**Demote everything on the first 422 and skip the retries.** Cheaper, but it converts
one bad anchor into zero inline comments on a PR that could have had twenty-nine.
Rejected.
