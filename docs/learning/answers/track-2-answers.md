# Track 2 — app/parser.py — answer key

Answers to the five questions at the end of `track-2-parser.md`.

1. **`sort_findings` inside `anchor_findings` vs its "same order" promise.** The docstring
   says the anchors come back in the same order as the findings passed in; the code sorts
   first, so the returned order is severity order, not input order. A caller that zipped
   the result back against its input list would pair each anchor with the wrong finding —
   silently, because both lists have the same length. The audit corrected the docstring
   rather than the behaviour (severity order is what every caller wants); if you need the
   original pairing, key on `(file, line, issue)` instead of position.

2. **Which real diff produces `new_count == 0`, and what containment alone would return.**
   A deletion: `@@ -3,2 +2,0 @@` removes lines 3-4 of the old file and adds nothing. With
   `new_count == 0` the containment test `new_start <= lineno < new_start + new_count`
   becomes `2 <= lineno < 2`, which is empty for every input — so `hunk_for_line` would
   return `None` for the very line the hunk sits at, and a `file_only` finding on a deleted
   file would lose its hunk header. Hence the explicit `lineno == hunk.new_start` case.

3. **Where to add the corruption check for an under-filled header.** In `parse_diff`, inside
   the hunk-body branch, before consuming a line: if the line starts with `diff --git ` (or
   is a `--- ` line followed by `+++ `) while `remaining_old` or `remaining_new` is still
   positive, the header promised more lines than the patch contains. Close the hunk and let
   the outer loop re-read the line as a header. This detects corruption without rejecting
   legal diffs because a *legal* hunk never contains a file header inside its body — a
   context line that happens to begin with `diff --git` would have a leading space, so it
   does not match. The final audit applied exactly this guard.

4. **What depends on `bundle_from_source` writing `old_path=/dev/null, change="added"`.**
   The rule engine's per-file scan does not (it only reads added lines), but
   `app/rules.py`'s file-level rules and `github_client.build_payload`'s path
   canonicalisation do: a finding on a synthetic bundle must be reported under the real path
   with no `a/`/`b/` prefix, and the payload must treat every line as added so that
   anchoring yields `anchored` rather than `file_only`. If `change` were `"modified"`, the
   GitHub client would still post, but `anchor_findings` on a synthetic bundle would compare
   against `added_line_numbers` that were built from a zero-count old side — the review of a
   whole file would silently produce no inline comments.

5. **`file_for`'s second comparison.** `DiffBundle.file_for("a/app/db.py")` normalises to
   `app/db.py` and matches on the first comparison. `file_for("app/db.py")` against a
   bundle whose `FileDiff.path` is still `a/app/db.py` (a bundle built by hand, or one whose
   header had no `b/` prefix to strip) matches only on the second. Both are kept because the
   first is the normalised path and the second is the raw one: a diff whose paths were not
   canonicalised — a plain `diff -u` with absolute paths, for instance — is still matched
   rather than silently producing `unanchored` findings.
