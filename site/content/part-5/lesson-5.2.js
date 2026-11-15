/* 5.2 — Hunk headers: @@ -a,b +c,d @@
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "5.2",
  "part": 5,
  "part_title": "Unified diffs",
  "title": "Hunk headers: @@ -a,b +c,d @@",
  "order": 502,
  "duration_min": 20,
  "concept_md": "### Four numbers in one line\n\nA hunk begins with a header that says where the block sits on each side:\n\n```text\n@@ -1,5 +1,8 @@\n```\n\nRead it as **old file, line 1, 5 lines** and **new file, line 1, 8 lines**. The minus side is the old file, the plus side the new one. The difference between the counts is the net change: five lines became eight, so three were added.\n\n### The omitted count\n\nThe comma part is optional, and when it is missing the count is **1**, not zero:\n\n```text\n@@ -1 +1 @@\n```\n\nThat is one line replaced by one line. The parser expresses this directly — `int(hunk_match.group(\"old_count\") or 1)` — so the `or 1` is the whole rule.\n\n### The regex that reads it\n\n```python\n_HUNK_RE = re.compile(\n    r\"^@@ -(?P<old_start>\\d+)(?:,(?P<old_count>\\d+))?\"\n    r\" \\+(?P<new_start>\\d+)(?:,(?P<new_count>\\d+))?\"\n    r\" @@[ ]?(?P<section>.*)$\"\n)\n```\n\nEvery counter is a named group, and each count sits in a non-capturing optional group — `(?:,(?P<old_count>\\d+))?` — The grammar only makes the count optional; the default of one comes from `or 1` when the group is absent.\n\n### The trailing section\n\n`@@ -1,5 +1,8 @@ def get_user(uid):` may carry the enclosing function after the second `@@`. It is a hint for humans; the parser stores it and never depends on it.",
  "code_examples": [
    {
      "id": "5.2-ex-0",
      "lang": "python",
      "caption": "A one-line hunk: every counter is 1",
      "code": "from app.parser import parse_diff\n\nhunk = parse_diff(\n    \"diff --git a/x.py b/x.py\\n\"\n    \"--- a/x.py\\n\"\n    \"+++ b/x.py\\n\"\n    \"@@ -1 +1 @@\\n\"\n    \"-a\\n\"\n    \"+b\\n\"\n).files[0].hunks[0]\nprint(\"old_start=%d old_count=%d new_start=%d new_count=%d\"\n      % (hunk.old_start, hunk.old_count, hunk.new_start, hunk.new_count))",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "old_start=1 old_count=1 new_start=1 new_count=1",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py",
        "app/parser.py",
        "samples/sample.diff"
      ]
    }
  ],
  "quiz": [
    {
      "q": "In `@@ -10,7 +10,9 @@`, what is the net change to the file?",
      "options": [
        "Two lines more on the new side",
        "Seven lines replaced by nine",
        "No change, since both start at 10",
        "Nine lines replaced by seven"
      ],
      "answer": 0,
      "why": "The counts are the size of each side of the block: 7 lines became 9, so the file grew by two. How many were added and how many removed depends on the body, not the header."
    },
    {
      "q": "What does `@@ -1 +1 @@` mean?",
      "options": [
        "Line 1 was added and line 1 was deleted",
        "The hunk is empty and can be skipped",
        "The counts are missing, so it is invalid, and the parser refuses it",
        "One line of the old became one of the new"
      ],
      "answer": 3,
      "why": "An absent count means 1, so both sides hold a single line; a `-` and a `+` between them make it a replacement."
    },
    {
      "q": "Why does the parser read the count as `group(...) or 1`?",
      "options": [
        "Because the regex always captures an empty string",
        "Because a missing count means one line, not zero",
        "Because counts above one are rare",
        "Because zero is not a valid integer"
      ],
      "answer": 1,
      "why": "`None or 1` is 1: the optional group is absent in the short form, and the short form means a single line."
    }
  ],
  "try_it": {
    "prompt": "Write a one-hunk diff with `@@ -1 +1 @@` and print the parsed counts.",
    "starter": "",
    "solution": "```console\n$ python -c \"from app.parser import parse_diff; h = parse_diff('diff --git a/x.py b/x.py\\n--- a/x.py\\n+++ b/x.py\\n@@ -1 +1 @@\\n-a\\n+b\\n').files[0].hunks[0]; print(h.old_count, h.new_count)\"\n1 1\n```",
    "explanation": "Two integers, both 1, produced from a header that contains no counts at all."
  },
  "exercise": {
    "prompt": "A hunk header reads `@@ -40,6 +40,6 @@`. What can you say about the change without seeing the body, and what can you not say?",
    "hint": "The two counts are the sizes of each side, not the number of changes.",
    "solution": "```text\nYou can say: six lines on each side, so the block is the same size —\nremovals and additions are equal in number.\n\nYou cannot say how many lines were added: one added and one removed is a\nreplacement, and the counts are identical either way. The body decides.\n```",
    "explanation": "Equal counts bound the answer to added equals removed, but the body is still needed to know the number — the same reason the parser builds added lines from `+` lines rather than from the header."
  },
  "common_mistakes": [
    "Reading `@@ -1 +1 @@` as a zero-count hunk, which drops the only line.",
    "Treating the two numbers as start and end rather than start and count.",
    "Assuming the function name after `@@` is significant to the parse; it is stored, not used."
  ],
  "project_links": [
    {
      "label": "The hunk-header regex, verbatim",
      "path": "app/parser.py",
      "lines": "62-66"
    },
    {
      "label": "Where the counts are read, with the `or 1` rule",
      "path": "app/parser.py",
      "lines": "460-479"
    }
  ],
  "learn_more": [
    {
      "label": "app/parser.py — the parser",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/parser.py"
    },
    {
      "label": "docs/learning/track-2-parser.md — the parser track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-2-parser.md"
    }
  ],
  "glossary_terms": [
    "hunk header — the `@@` line giving position and size on each side",
    "count — how many lines the block covers, defaulting to one",
    "section — the optional text after the second `@@`"
  ]
});
