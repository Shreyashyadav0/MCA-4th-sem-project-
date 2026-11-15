/* 5.1 — The shape of a unified diff
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "5.1",
  "part": 5,
  "part_title": "Unified diffs",
  "title": "The shape of a unified diff",
  "order": 501,
  "duration_min": 15,
  "concept_md": "### A diff is a description of changes\n\nA diff is not the file. It is the smallest set of instructions that turns the old file into the new one — which is why a diff of a 2000-line file can be four lines long.\n\nEvery line in a diff starts with one character that says what it is:\n\n- `+` — this line was **added**.\n- `-` — this line was **removed**.\n- a space — this line is **context**: unchanged, present in both versions.\n- `\\` — a marker with no newline at end of file, not content.\n\n### The header block\n\nBefore any changed line, each file gets a header:\n\n```text\ndiff --git a/app/db.py b/app/db.py\nindex 3926f43..f17d112 100644\n--- a/app/db.py\n+++ b/app/db.py\n```\n\n`diff --git` names the file twice, once per side. `index` carries the two blob hashes. `---` and `+++` are the old and new paths — and they are the lines the parser actually trusts when deciding what file it is looking at.\n\n### Why the `a/` and `b/` prefixes exist\n\nGit writes `a/` for the old side and `b/` for the new so that a file literally named `a/thing` cannot be confused with the prefix. The parser strips exactly one prefix, which is lesson 5.5's subject.\n\n### Reading a real one\n\n`samples/sample.diff` is 25 lines and describes two files. The first is modified: a token is added, a `return None` is replaced by two statements. The second is new: five lines that did not exist. Nothing in it tells you what the rest of `app/db.py` contains — a diff never shows what it does not change.",
  "code_examples": [
    {
      "id": "5.1-ex-0",
      "lang": "console",
      "caption": "The first twenty lines of the sample diff",
      "code": "head -20 samples/sample.diff",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "diff --git a/app/db.py b/app/db.py\nindex 3926f43..f17d112 100644\n--- a/app/db.py\n+++ b/app/db.py\n@@ -1,5 +1,8 @@\n import sqlite3\n \n+API_TOKEN = \"ghp_exampleTokenValue1234567890\"\n+\n \n def get_user(uid):\n-    return None\n+    query = f\"SELECT * FROM users WHERE id = {uid}\"\n+    return sqlite3.connect(\"app.db\").execute(query).fetchone()\ndiff --git a/app/report.py b/app/report.py\nnew file mode 100644\nindex 0000000..4064cb7\n--- /dev/null\n+++ b/app/report.py\n@@ -0,0 +1,5 @@",
      "why_not": "the browser runner has Python but no shell, so head/sed/grep cannot run there; the command needs a checkout on disk."
    }
  ],
  "quiz": [
    {
      "q": "What does a line beginning with a single space mean in a diff?",
      "options": [
        "It was added to the new file",
        "It was removed from the old file, so only the new file has it",
        "It is unchanged, in both versions",
        "It marks the end of one hunk"
      ],
      "answer": 2,
      "why": "The leading character is the type: `+` added, `-` removed, space context. A blank-looking line in a diff is usually a context line holding one space."
    },
    {
      "q": "Why does a diff of a huge file sometimes fit in four lines?",
      "options": [
        "Because a diff carries only the changes",
        "Because git truncates any very long file",
        "Because unchanged lines are compressed away",
        "Because the index line stands in for content"
      ],
      "answer": 0,
      "why": "The format describes a transformation, so its size tracks the change, not the file. That is what makes reviewing a diff cheaper than reviewing a file."
    },
    {
      "q": "What is the `index 3926f43..f17d112` line for?",
      "options": [
        "It is the commit hash of the whole change",
        "It numbers the files inside the diff",
        "It sets the file mode to one hundred six",
        "It lists the two blob hashes, old and new"
      ],
      "answer": 3,
      "why": "The two hashes identify the blobs on each side; the mode appears separately as `100644`. Neither is a commit hash."
    }
  ],
  "try_it": {
    "prompt": "Count the added, removed and context lines in the first file's hunk of `samples/sample.diff`.",
    "starter": "",
    "solution": "```console\n$ sed -n '6,14p' samples/sample.diff | cut -c1 | sort | uniq -c\n      4  \n      4 +\n      1 -\n```",
    "explanation": "Four added, one removed, four context. The counts agree with the hunk header `@@ -1,5 +1,8 @@`: four context plus one removed is the old count of five, four context plus four added is the new count of eight."
  },
  "exercise": {
    "prompt": "The second file in the sample has no `-` lines at all. What does that tell you about it, and which header line proves it?",
    "hint": "Compare the `---` line of the first file with the second.",
    "solution": "```text\nIt is a new file: nothing was removed because nothing existed before.\nThe proof is `--- /dev/null` on line 18, together with `new file mode 100644` on\nline 16. A diff against /dev/null is a diff against nothing.\n```",
    "explanation": "`--- /dev/null` is the format's way of saying the old side does not exist; lesson 5.5 turns that into the `added` change kind."
  },
  "common_mistakes": [
    "Reading the `---`/`+++` lines as changes — they are header lines, not content.",
    "Forgetting the leading space is part of the line; stripping it shifts every column by one.",
    "Assuming a diff contains the whole file, then looking for a function it never touches."
  ],
  "project_links": [
    {
      "label": "The sample diff, 25 lines and two files",
      "path": "samples/sample.diff",
      "lines": "1-25"
    },
    {
      "label": "The regex that recognises the `diff --git` header",
      "path": "app/parser.py",
      "lines": "61"
    }
  ],
  "learn_more": [
    {
      "label": "samples/sample.diff",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/samples/sample.diff"
    },
    {
      "label": "app/parser.py — the whole parser",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/parser.py"
    }
  ],
  "glossary_terms": [
    "hunk — one block of changes with its own header",
    "context line — an unchanged line kept so the change has a position",
    "blob hash — git's identifier for one version of a file's content",
    "/dev/null — the empty side of an added or deleted file"
  ]
});
