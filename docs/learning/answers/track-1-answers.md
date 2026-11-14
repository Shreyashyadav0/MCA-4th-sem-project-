# Track 1 — app/models.py — answer key

Answers to the five questions at the end of `track-1-models.md`. Each names the line you
can check it against.

1. **What `LLMFinding` buys over one tolerant model.** It is the *wire* boundary: the model's
   JSON is validated against `LLMFinding` first (`app/sarvam_provider.py:72`, consumed by
   `parse_findings_payload`), and only then converted into a `Finding`. That buys three
   things a single tolerant model cannot give: a validation error names the field the model
   got wrong instead of silently coercing it; the transport shape can change (an int `line`,
   a lower-case severity) without weakening the five-field contract every surface depends on;
   and `extra="forbid"` on the wire model means a hallucinated sixth key fails at the edge
   rather than propagating. A tolerant model would move that decision into the caller, where
   it would eventually be forgotten.

2. **What ordering guarantee is missing from `sort_findings`, and what exposes it.** The key
   is `(-severity.rank, int(line_start))` with no file component, so findings of equal
   severity and equal line number in *different files* keep their input order — the sort is
   not a total order, and the rendered order can change when the diff order changes.
   Exposed by: two LOW findings on line 1 in `z.py` and `a.py`; sort them in either input
   order and the output order differs. The fix is to add `f.file` (and `f.issue` as the last
   discriminator) to the key — which is what the final audit applied at `app/models.py`
   (`sort_findings`).

3. **A verdict set in `__init__` and the path that would post a contradictory review.** If
   `verdict` were a stored field, `DiffReviewResult` could be constructed with findings that
   are all CRITICAL and `verdict="approve"`, and `app/github_client.render_summary_body`
   would print that verdict into the PR comment while `render_inline_body` posted the
   CRITICAL findings beside it. As a `computed_field` derived by `verdict_for`
   (`app/models.py`), the two cannot disagree — the verdict is a function of the findings.

4. **`"0"` accepted, `"42-39"` rejected.** `"0"` is a *syntactic* pass: the validator's job
   is only "is this a number or an ascending range" (`app/models.py`, the `line`
   validator), and it deliberately does not know which lines exist. `"42-39"` is rejected
   because a descending range is malformed under any reading — it cannot be normalised
   without guessing intent. Whether line 0 is *meaningful* is an anchoring question:
   `anchor_findings` intersects the range with the file's added lines, so `"0"` finds no
   match and the finding becomes `file_only` (or `unanchored`). Model concern: shape.
   Anchorer concern: meaning.

5. **Six keys vs five, and what adding `status` to `Finding` would break.** `as_row()` on
   `AnchoredFinding` returns the five contract fields plus `"Anchor"` — display only, never
   serialised into a finding. If `status` were a sixth field on `Finding`:
   `tests/test_rules.py::test_finding_model_stays_five_fields` fails by design; every
   `LLMFinding` payload would have to carry an anchor status the model cannot know, so the
   wire model and the contract model would diverge; `app/rules.py` would have to invent a
   status for findings that have not been anchored yet; and `github_client`'s
   `anchored → inline / file_only → summary` split would have two sources of truth. The
   anchor status belongs to the *pair* (finding, diff), which is exactly why
   `AnchoredFinding` exists.
