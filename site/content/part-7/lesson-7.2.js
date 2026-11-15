/* 7.2 — The _Builder two-pass design
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "7.2",
  "part": 7,
  "part_title": "The parser",
  "title": "The _Builder two-pass design",
  "order": 702,
  "duration_min": 25,
  "concept_md": "### A hunk cannot be built until it ends\n\nWhile reading a hunk's body you do not know how many lines it will hold, so you cannot decide the counts, the spans or the change kind. `_Builder` accumulates, and `finish()` decides.\n\nThat is the two passes: **collect**, then **conclude**. The first pass walks lines and appends `DiffLine` objects; the second turns the collected state into a `FileDiff`.\n\n### What the builder holds\n\n`__slots__` at **308** lists it: the two paths, the hunks, the binary flag, `explicit_change` and `has_header`. Every one of those is something a later line can change, which is exactly why it cannot live in a local variable.\n\n### Why not one pass\n\nA one-pass parser would have to decide the change kind when it saw `diff --git`, before it knew whether a `new file mode` line followed. It would have to fix the hunk counts at the `@@` line, before it had seen the body. Both decisions depend on lines that have not arrived yet.\n\n### The cost\n\nState that outlives a line is state that can be left over. `close_hunk()` exists to reset it, and the parser calls it at every boundary — a new `@@`, a new file, or the end of input.",
  "code_examples": [
    {
      "id": "7.2-ex-0",
      "lang": "python",
      "caption": "The builder's state, as declared",
      "code": "from app.parser import _Builder\n\nprint(_Builder.__slots__)\nb = _Builder()\nprint(\"paths:\", b.old_path, b.new_path, \"| has_header:\", b.has_header)",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "('old_path', 'new_path', 'hunks', 'binary', 'explicit_change', 'has_header')\npaths:   | has_header: False",
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
      "q": "Why can the change kind not be decided at the `diff --git` line?",
      "options": [
        "Because the paths are not known yet",
        "A later header line may say new file mode or rename",
        "Because the kind depends on the body",
        "Because `diff --git` carries no paths"
      ],
      "answer": 1,
      "why": "The `diff --git` line gives two paths; `new file mode`, `deleted file mode` and the rename lines arrive after it and override the guess."
    },
    {
      "q": "What does `close_hunk()` reset?",
      "options": [
        "Only the binary flag",
        "The whole builder, including both the old path and the new one",
        "The collected lines and the counters for the hunk just finished",
        "The list of finished files"
      ],
      "answer": 2,
      "why": "Each hunk starts empty; the paths and the change kind belong to the file and must survive every hunk boundary."
    },
    {
      "q": "What is the second pass in \"collect, then conclude\"?",
      "options": [
        "`finish()`, which turns the builder state into a FileDiff",
        "`parse_diff`, which splits the text into lines",
        "`close_hunk`, which empties the buffer",
        "`normalize_path`, which strips the prefix"
      ],
      "answer": 0,
      "why": "Everything the file needs is known once the last line of it has been read, so one method builds the model from the accumulated state."
    }
  ],
  "try_it": {
    "prompt": "Print the builder's slots and how many of them are set before any line is read.",
    "starter": "",
    "solution": "```python\nfrom app.parser import _Builder\n\nb = _Builder()\nprint(len(_Builder.__slots__), \"slots\")\nprint(\"set early:\", b.old_path, b.new_path, b.has_header)\n```",
    "explanation": "Six slots, three of them already meaningful — the rest are filled as the header lines arrive."
  },
  "exercise": {
    "prompt": "A file block has two hunks. How many times does `close_hunk()` run for that file, and why?",
    "hint": "Count the boundaries, including the end of the file.",
    "solution": "```text\nThree times: once at the second @@ header, once when the next file's header\narrives, and once at the end of input. The last call is what makes the final\nhunk's counts correct.\n```",
    "explanation": "The end-of-input call is the one a one-pass design cannot express, because there is no line to react to."
  },
  "common_mistakes": [
    "Assuming the builder is created once per parse; it is created per file.",
    "Deciding the change kind at `diff --git` and ignoring a later override.",
    "Forgetting the final `close_hunk()` at end of input, which loses the last hunk."
  ],
  "project_links": [
    {
      "label": "The builder and its slots",
      "path": "app/parser.py",
      "lines": "305-340"
    },
    {
      "label": "Where the hunk header is read",
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
      "label": "docs/learning/track-2-parser.md",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-2-parser.md"
    }
  ],
  "glossary_terms": [
    "builder — state that accumulates across lines",
    "slots — the fixed attribute list of a class",
    "close_hunk — finish the current hunk and reset its buffer"
  ]
});
