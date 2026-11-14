# Track 2 — parser

## Prerequisite check

Pass all four before starting:

- [ ] Track 1 done: you can state the five `Finding` fields and why `AnchoredFinding`
      wraps rather than extends.
- [ ] `python -c "import pydantic"` succeeds from the repo root (`pydantic==2.14.3`).
- [ ] `python -m pytest -q tests/test_parser.py` runs (11 tests) and you have read the
      failure messages at least once.
- [ ] You can read a unified diff by hand: identify a `@@ -a,b +c,d @@` header, count
      `+`/`-`/space body lines, and say what `\ No newline at end of file` attaches to.

## What it does

`app/parser.py` turns a raw git or plain unified diff into `DiffBundle` ->
`FileDiff` -> `Hunk` -> `DiffLine`, assigning every body line the file line number it
maps to on each side. It then places each `Finding` against those numbers with
`anchor_findings`, which assigns one of `anchored`, `file_only` or `unanchored`. It also
wraps a plain source file as a one-hunk all-added diff (`bundle_from_source`) so
diff-based rules can run on a file that has no diff.

## Why it exists

Two rejected designs are named in the module docstring (`app/parser.py:7-14`).

The first is deriving line numbers from position - counting rows from the top of the
diff, or from the top of the file. That is wrong the moment a diff is not a whole file:
a hunk headed `@@ -120,7 +120,9 @@` reports line 120 onward, and a row counter reports 1. The rejected alternative was
cheap and produces findings that point at the wrong line, which GitHub then rejects or,
worse, accepts onto unrelated code.

The second is putting the anchor on the finding. `AnchorStatus` looks like a sixth
field of `Finding`, and that is exactly why it is not one: "GitHub will drop this
comment" is a property of the publishing surface, not of what the reviewer believes
(`app/parser.py:12-14`, restated at `ARCHITECTURE.md:302`). Keeping it out means a new
provider can change how anchoring is decided without touching the five-field contract.

A third constraint shapes the whole module: it parses text, never a repository. There
is no `git` call, no checkout, no `git diff -U0` re-run - `parse_diff_file`
(`app/parser.py:472-484`) reads bytes off disk and nothing else.

## Key references

- `app/parser.py:56` — `r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))?"`, the hunk header regex that supplies both counters.
- `app/parser.py:77` — `if len(path) > 2 and path.startswith(("a/", "b/")):`, the guarded `a/`/`b/` strip in `normalize_path`.
- `app/parser.py:377` — `if line.startswith("\\"):  # "\ No newline at end of file"`, the one body line that is skipped rather than counted.
- `app/parser.py:446` — `remaining_old, remaining_new = old_count, new_count`, the counters that decide where a hunk body ends.
- `app/parser.py:516` — `hits = sorted(n for n in target.added_line_numbers if start <= n <= end)`, the anchored/file_only decision.
- `app/parser.py:566` — `new_count=len(lines),`, the synthetic hunk header `bundle_from_source` builds.
- `app/parser.py:181` — `if hunk.new_start <= lineno < hunk.new_start + hunk.new_count:`, `hunk_for_line`'s new-side containment test.
- `app/parser.py:420` — `if builder is None or builder.has_header or builder.hunks:`, the guard that stops a `diff --git` section becoming a duplicate hunk-less file.

## The three hardest ideas

### 1. Line numbers come from hunk headers, never from counting rows

`_HUNK_RE` (`app/parser.py:55-59`) captures `old_start`, `old_count`, `new_start`,
`new_count`. At `app/parser.py:445-446` the parser sets the two cursors to the starts
and the two counters to the counts; body lines then increment the cursors as they are
consumed. Nothing in the module ever computes a line number from an index.

Worked example:

```
diff --git a/app/svc.py b/app/svc.py
--- a/app/svc.py
+++ b/app/svc.py
@@ -120,3 +120,4 @@ def handler(request):
 context one
+added_a
+added_b
 context two
```

```
file      app/svc.py      change modified
hunk      @@ -120,3 +120,4 @@ def handler(request):
added     [121, 122]      spans ['121-122']
```

The added lines are 121 and 122, because the new-side cursor started at 120 and the
context line consumed 120. A row counter would have said 2 and 3. This property is
asserted directly at `tests/test_parser.py:40`
(`test_added_line_numbers_come_from_hunk_header`) and again for a plain diff without a
git header at `tests/test_parser.py:49`, where `@@ -10,3 +10,4 @@` must yield
`{11, 12}`.

`Hunk.header` (`app/parser.py:128-134`) reconstructs the header from the counters, which
is what `AnchoredFinding.hunk_header` shows a reviewer. It always prints both counts, so
a diff written as `@@ -1 +1 @@` comes back as `@@ -1,1 +1,1 @@` - semantically identical,
not textually identical.

### 2. A hunk body ends when both counters hit zero

The parser has two states. Inside a body, it consumes lines without inspecting them for
meaning (`app/parser.py:376`): `+` is an added line and decrements `remaining_new`,
`-` is a removed line and decrements `remaining_old`, anything else is context and
decrements both. The body ends only when both counters reach zero; the next iteration
falls through to `close_hunk()` (`app/parser.py:400`) and the header-matching branches.

Why counters and not line prefixes? Because a body line can look exactly like a header.
This is a real diff body, parsed by the real module:

```
@@ -1,2 +1,2 @@
--- keep this comment
+++ add this comment
```

```
removed  '-- keep this comment'    old 1
added    '++ add this comment'     new 1
```

Both lines begin with `--- ` / `+++ ` after git's own prefix. A parser that ended the
hunk on a `--- `/`+++ ` pair would treat them as a file header and corrupt the file
list. The counters make the body unambiguous, and the `\ No newline at end of file`
marker (`app/parser.py:377`) is skipped so it cannot be mistaken for a context line.

The cost of trusting the counters is that a wrong header is silently obeyed. Take a
hunk whose header claims 3+3 but whose body carries one removed and one added line,
followed by a second file:

```
@@ -1,3 +1,3 @@
--- one
+++ one
diff --git a/y.py b/y.py
--- a/y.py
+++ b/y.py
@@ -1 +1 @@
-old
+new
```

```
file x.py modified
  hunk @@ -1,3 +1,3 @@
    removed  '-- one'                     1    None
    added    '++ one'                     None 1
    context  'diff --git a/y.py b/y.py'   2    2
    removed  '-- a/y.py'                  3    None
    added    '++ b/y.py'                  None 3
  hunk @@ -1,1 +1,1 @@
    removed  'old'  1  None
    added    'new'  None 1
```

The counters were still hungry, so the next file's `diff --git` line was eaten as
context, and `y.py`'s two header lines became a removed line and an added line inside
`x.py`. No exception is raised. That is the trade: a well-formed diff parses exactly,
and a malformed one produces wrong data rather than an error. `DiffParseError` is
reserved for input that is not a diff at all (`app/parser.py:465-468`: "no file headers
found"), and for empty input (`app/parser.py:334-335`).

### 3. Anchoring is kept outside the five-field contract

`anchor_findings` (`app/parser.py:487-541`) returns one `AnchoredFinding` per input
finding, in severity order. Three statuses, decided in this order:

| Condition | Status | Detail text produced |
|---|---|---|
| `bundle.file_for(...)` returns nothing | `unanchored` | `"<file> is not part of this diff"` |
| file found, range touches an added line | `anchored` | `"added line: 121"` or `"2 added lines in range: 121-122"` |
| file found, range touches no added line | `file_only` | `"... is in the diff but line 130 was not changed; GitHub would drop this inline comment"` |

Worked example, real output for four findings against the diff in idea 1:

```
b/app/svc.py  120-122  CRITICAL  anchored    | @@ -120,3 +120,4 @@ def handler(request): | 2 added lines in range: 121-122
app/svc.py    121      HIGH      anchored    | @@ -120,3 +120,4 @@ def handler(request): | added line: 121
app/other.py  1        MEDIUM    unanchored  | None | app/other.py is not part of this diff
app/svc.py    130      LOW       file_only   | None | app/svc.py is in the diff but line 130 was not changed; ...
```

Three things are worth noticing in that output. The `b/app/svc.py` finding is found
because `DiffBundle.file_for` (`app/parser.py:219-225`) normalises the lookup key before
comparing. The `file_only` case carries `hunk_header: None` here only because line 130
falls outside the hunk; when the line is inside a hunk but not added, the header is
attached. And the findings come back reordered: the input list is re-sorted by
`sort_findings` at `app/parser.py:503`, so the output order is severity order, not
input order - which is why `DiffReviewResult.sorted_anchors` (`app/parser.py:260-267`)
has to rebuild the correspondence by `id()`.

The contract stays intact: `AnchoredFinding` has four fields (`finding`, `status`,
`hunk_header`, `detail`) and `Finding` still has five. `status` is a fact about the
diff, and the diff is a property of the review, not of the review's claim. That is what
lets the same anchoring code serve the rule engine (which only ever reports added
lines, so everything it emits is `anchored`) and a live provider (which can name any
line at all).

## Rebuild exercise

Time: 1-3 hours. Fresh file: `track2_parser.py`, outside `app/` (for example
`/tmp/track2/track2_parser.py`). Do not modify `app/parser.py`, and do not read it while
writing your version - use the descriptions above and the tests as the specification.

Build:

1. `normalize_path(raw)` - strip surrounding quotes, a leading `./`, then at most one
   `a/` or `b/` prefix, and never mangle `app/config.py` into `pp/config.py`.
2. `Hunk`, `DiffLine`, `FileDiff`, `DiffBundle` as Pydantic models with `extra="forbid"`;
   `FileDiff.added_line_numbers` (a set), `added_spans` (compressed ranges), and
   `hunk_for_line(lineno)` on the new side.
3. `parse_diff(raw, *, source)` as a single-pass state machine: counters from the hunk
   header, `+`/`-`/space classification, `\ No newline` skipped, `diff --git` and
   `--- `/`+++ ` file headers, `new file mode` / `deleted file mode` / `rename` /
   `Binary files` flags, `DiffParseError` on empty input or no headers.
4. `bundle_from_source(path, source)` - one file, one hunk, `old_start=0`,
   `old_count=0`, `new_start=1`, every line `added`.
5. `anchor_findings(bundle, findings)` - the three statuses and their detail strings.

Test it against the real behaviour, in this order:

- `python -m pytest -q tests/test_parser.py` must pass against the real `app/parser.py`;
  then run your module's functions through the same assertions (import it by path) and
  require identical results.
- `samples/sample.diff` must yield paths `["app/db.py", "app/report.py"]`, changes
  `["modified", "added"]`, and `added_spans == ["3-4", "7-8"]` for `app/db.py`.
- `@@ -10,3 +10,4 @@` on the plain diff in `tests/test_parser.py` must yield
  `added_line_numbers == {11, 12}`.
- The under-filled-header diff from idea 2 must reproduce the same five body lines,
  including the swallowed `diff --git` line. If your parser raises instead, you have
  invented a stricter contract than the code has.
- `normalize_path('a/')` must return `'a/'` (the `len(path) > 2` guard), and
  `normalize_path('app/config.py')` must return it unchanged.

## Self-test questions

1. `anchor_findings` sorts its input with `sort_findings` before iterating. What does
   that do to the "same order" promise in its own docstring, and what would break in a
   caller that zipped the result back against the input list?
2. `FileDiff.hunk_for_line` special-cases `hunk.new_count == 0` by comparing
   `lineno == hunk.new_start`. Which real diff produces such a hunk, and what would the
   containment test alone have returned for it?
3. In the under-filled-header example, no exception is raised and file `y.py` is lost.
   Where would you add a check, and what would you compare to detect the corruption
   without rejecting legal diffs?
4. `bundle_from_source` writes `old_path=_DEV_NULL` and `change="added"`. Which
   downstream rule-engine behaviour depends on that choice rather than on the hunk
   contents?
5. `DiffBundle.file_for` tries `file.path == key` and then `file.path == path`. Give an
   input where the second comparison matches and the first does not, and say why both
   are kept.
