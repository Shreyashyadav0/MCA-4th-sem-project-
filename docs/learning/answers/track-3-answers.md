# Track 3 — app/rules.py — answer key

Answers to the five questions at the end of `track-3-rules.md`.

1. **Cost of filtering per rule inside the line loop.** The cost is O(lines × rules) boolean
   checks instead of a precomputed rule list, which is measurable but small (63 rules × a
   few thousand lines). What would break if the filters were hoisted: `min_severity` and
   `categories` are *request-scoped* and `review_lines` is called once per file, so a
   precomputed list would have to be cached keyed on both parameters — and the moment two
   requests with different filters run concurrently (the webhook path does exactly this),
   a module-level cache would serve one request's rule list to another. The current
   placement keeps the filter a pure function of the call.

2. **Two diffs where branch density miscounts, and the direction of the error.** (a) A
   function whose body was only partly touched: the walk stops at the first added line whose
   indentation is `<= base`, so a `def` whose remaining body is unchanged counts only the
   added branches — an under-count. (b) A function containing a nested `def` at the same
   indentation: the walk stops at the inner `def` because its indent equals `base`, dropping
   every branch after it — again an under-count. Both err toward *not* reporting, which is
   the right direction for a MEDIUM heuristic: a false positive here would be noise on
   perfectly readable code.

3. **Which rule would be stronger with visibility of removed lines.** `unsafe/sql-injection`
   (and its `-concat` sibling): a query assembled across a removed line and an added line —
   the classic "replaced the parameterised call with an f-string" edit — is only fully
   visible with both sides. The anchoring problem it would create: a finding whose evidence
   is on a removed line has no added line to attach to, so GitHub would drop the inline
   comment (`file_only`), and the report would show a finding the reviewer cannot see in the
   diff. That is why the engine scans added lines only, and why the limitation is documented
   rather than worked around.

4. **`# noqa: E501` — bug in which layer.** In the design, and the argument is: the parser
   (`_suppressed_ids`) is deliberately generic — it accepts any token after `noqa:` so a new
   rule id needs no parser change. It cannot know that `E501` is a flake8 code rather than
   one of this project's rule ids, and the caller (`review_lines`) compares the token set
   against real rule ids, so an unknown id suppresses nothing. The defect is that the
   behaviour is *silent*: a reader who writes `# noqa: E501` believes they suppressed
   something. What I would change: `review_lines` logs one DEBUG line when a suppression
   names an id that is not in the registry — cheap, and it turns a silent no-op into a
   visible one without narrowing the parser.

5. **Truncation defeating an exemption, and truncation creating a false match.**
   `scan_text` cuts at 4000 characters, so: (a) an exemption that appears *after* the cut is
   never seen — e.g. a very long line whose `exempt` evidence (`os.environ`, `# noqa`, a
   `Loader=` argument) sits at column 4001: the pattern matches and the exemption cannot
   apply, producing a false positive. (b) The opposite case: a pattern whose match spans the
   cut boundary is evaluated on the truncated string, so `_SECRET_NAME_RE` can match a name
   that only looks like a credential because its second half was removed — e.g. a
   concatenated identifier cut mid-word. Both are accepted costs of the ReDoS bound; the
   bound is what keeps a 10 MB minified line from hanging the review.
