/* 5.6 — Binary files carry no hunks
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "5.6",
  "part": 5,
  "part_title": "Unified diffs",
  "title": "Binary files carry no hunks",
  "order": 506,
  "duration_min": 15,
  "concept_md": "### Not everything is text\n\nA diff of a PNG or a compiled artefact cannot show lines, because there are none to show. Git writes:\n\n```text\ndiff --git a/logo.png b/logo.png\nindex 3b18e51..a1b2c3d 100644\nBinary files a/logo.png and b/logo.png differ\n```\n\nNo `---`, no `+++`, no `@@`, no body. A parser that assumes every file block contains a hunk will either crash or, worse, silently attach the next file's hunks to this one.\n\n### The flag exists so downstream can skip honestly\n\n`FileDiff` and `FileSummary` both carry `binary: bool = False`, and the summary copies it through. That single boolean is what lets the reviewer say \"this file changed and I did not look inside it\" — which is a true statement — instead of \"this file has no findings\", which would be a false one.\n\n### Why this is a lesson about honesty\n\nAn empty finding list has two very different meanings: nothing was wrong, or nothing was examined. The `binary` flag is how the tool keeps those apart. A review that cannot tell them apart will eventually claim a clean result for a file it never read.\n\n### What the sample does not contain\n\n`samples/sample.diff` has no binary file, so this lesson quotes the declarations rather than a capture — and says so, rather than inventing a diff that is not in the repository.",
  "code_examples": [
    {
      "id": "5.6-ex-0",
      "lang": "console",
      "caption": "Every place the parser touches the flag",
      "code": "grep -n 'binary' app/parser.py",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "161:    binary: bool = False\n203:    binary: bool = False\n242:                binary=file.binary,\n308:    __slots__ = (\"old_path\", \"new_path\", \"hunks\", \"binary\", \"explicit_change\", \"has_header\")\n314:        self.binary = False\n339:            binary=self.binary,\n489:            elif line.startswith((\"Binary files\", \"GIT binary patch\")):\n490:                builder.binary = True",
      "why_not": "the browser runner has Python but no shell, so head/sed/grep cannot run there; the command needs a checkout on disk."
    }
  ],
  "quiz": [
    {
      "q": "What does a binary file's block contain instead of hunks?",
      "options": [
        "A `Binary files … differ` line, no body",
        "A hunk with one placeholder line",
        "The file's bytes, base64 encoded",
        "A `@@` header carrying zero counts, which marks a deletion"
      ],
      "answer": 0,
      "why": "There is nothing textual to hunk, so git states the fact in one line and stops. A parser that expects a hunk here is the bug this flag prevents."
    },
    {
      "q": "Why does `binary` matter to a review's honesty?",
      "options": [
        "Because it changes the file's change kind to modified",
        "Because it makes the JSON payload smaller",
        "Because binary files are usually unsafe",
        "Because clean and unexamined must differ"
      ],
      "answer": 3,
      "why": "An empty list is ambiguous on its own; the flag records that the file was skipped deliberately rather than cleared."
    },
    {
      "q": "`FileSummary` copies `binary=file.binary`. Why copy rather than recompute?",
      "options": [
        "Because recomputing it on every read would be slow",
        "Because one fact must have one source",
        "Because FileDiff has no binary field",
        "Because the summary is built elsewhere"
      ],
      "answer": 1,
      "why": "Two places deciding the same fact is how they drift apart; copying keeps one source of truth."
    }
  ],
  "try_it": {
    "prompt": "Check whether the sample diff contains a binary file at all.",
    "starter": "",
    "solution": "```console\n$ grep -c '^Binary files' samples/sample.diff\n0\n```",
    "explanation": "Zero — the sample is text only. That is why this lesson quotes declarations instead of a capture."
  },
  "exercise": {
    "prompt": "`FileSummary` drops the `binary` field and a review reports an empty finding list for a PNG. What has the reader been told, and what is actually true?",
    "hint": "Think about where the next file's header would land.",
    "solution": "```text\nTold: nothing was found in that file.\nTrue: nothing was looked at — the flag that would have said so is gone, and an\nempty list is indistinguishable from a clean one.\n```",
    "explanation": "The failure is silent in both directions, which is why the flag is a data-model decision rather than a parsing detail."
  },
  "common_mistakes": [
    "Reporting a binary file as unchanged because it has no findings.",
    "Re-deriving the binary flag in the summary instead of copying it.",
    "Assuming every file block has at least one hunk."
  ],
  "project_links": [
    {
      "label": "The flag on FileDiff, and on FileSummary",
      "path": "app/parser.py",
      "lines": "152-203"
    },
    {
      "label": "Where the summary copies it",
      "path": "app/parser.py",
      "lines": "234-245"
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
    "binary file — content git will not diff line by line",
    "binary flag — the boolean set when git prints `Binary files … differ`",
    "skip — deliberately not examining a file, and recording that fact"
  ]
});
