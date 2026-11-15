/* 5.5 — New files, deleted files, and /dev/null
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "5.5",
  "part": 5,
  "part_title": "Unified diffs",
  "title": "New files, deleted files, and /dev/null",
  "order": 505,
  "duration_min": 20,
  "concept_md": "### The empty side\n\nA new file has no old version, and a deleted file has no new one. The format says so by pointing that side at `/dev/null`:\n\n```text\n--- /dev/null\n+++ b/app/report.py\n```\n\nRead the two header lines as \"old side: nothing, new side: this path\". Flip them and you have a deletion.\n\n### Two signals, one answer\n\nGit also writes `new file mode 100644` above the `---` line, and `deleted file mode` for the other direction. The parser accepts either signal, because a hand-written patch may carry only one.\n\n### normalize_path\n\nThe paths in a diff carry git's `a/` and `b/` prefixes. A finding has to name `app/report.py`, not `b/app/report.py`, so the prefix is stripped:\n\n```python\ndef normalize_path(raw: str) -> str:\n    path = raw.strip()\n    if len(path) >= 2 and path.startswith('\"') and path.endswith('\"'):\n        path = path[1:-1]\n    if path.startswith(\"./\"):\n        path = path[2:]\n    if len(path) > 2 and path.startswith((\"a/\", \"b/\")):\n        path = path[2:]\n    return path\n```\n\nThree details matter. Quotes are stripped because git quotes paths containing spaces. The `./` case is handled separately. And the strip happens once because it is a single `if`, not a loop — which is what the docstring means by \"at most once\". The `len(path) > 2` guard does something different: it stops the degenerate path `a/` from collapsing to an empty string.\n\n### What the sample shows\n\nThe second file in `samples/sample.diff` is exactly this case: `--- /dev/null`, `new file mode`, five added lines, and a path the parser normalises to `app/report.py`.",
  "code_examples": [
    {
      "id": "5.5-ex-0",
      "lang": "console",
      "caption": "The new-file block, from /dev/null",
      "code": "sed -n '15,20p' samples/sample.diff",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "diff --git a/app/report.py b/app/report.py\nnew file mode 100644\nindex 0000000..4064cb7\n--- /dev/null\n+++ b/app/report.py\n@@ -0,0 +1,5 @@",
      "why_not": "the browser runner has Python but no shell, so head/sed/grep cannot run there; the command needs a checkout on disk."
    }
  ],
  "quiz": [
    {
      "q": "Which header line marks a file as deleted?",
      "options": [
        "`deleted file mode 100644` alone",
        "`--- /dev/null` — the old side does not exist",
        "`+++ /dev/null` — the new side does not exist",
        "The absence of any `+` lines"
      ],
      "answer": 2,
      "why": "The old side exists and the new side does not, so it is the `+++` line that points at /dev/null. The mode line corroborates but is not required."
    },
    {
      "q": "What does the `len(path) > 2` guard actually prevent?",
      "options": [
        "A bare `a/` collapsing to an empty string",
        "The prefix being stripped twice",
        "Quoted paths losing their quotes",
        "Windows-style paths being mangled"
      ],
      "answer": 0,
      "why": "`normalize_path('a/')` returns `a/` because of the guard. Stripping twice cannot happen anyway: the strip is one `if`, not a loop."
    },
    {
      "q": "A finding must name `app/report.py`. What does the diff call it?",
      "options": [
        "`new file mode 100644` in the header",
        "`app/report.py`, exactly as written",
        "`/dev/null`, the empty side of the diff",
        "`b/app/report.py`, which is normalised"
      ],
      "answer": 3,
      "why": "The `b/` prefix is git's, not the repository's; `normalize_path` removes it so the finding matches a real path."
    }
  ],
  "try_it": {
    "prompt": "Print the normalised path of each file in the sample.",
    "starter": "",
    "solution": "```console\n$ python -c \"from pathlib import Path; from app.parser import parse_diff; print([f.path for f in parse_diff(Path('samples/sample.diff').read_text()).files])\"\n['app/db.py', 'app/report.py']\n```",
    "explanation": "No `a/`, no `b/`, no quotes — the paths match the repository, which is what makes a finding linkable."
  },
  "exercise": {
    "prompt": "`normalize_path` is given `\"a/app/config.py\"` (quoted, with the prefix). What does it return, and which line does the work?",
    "hint": "Quotes come off first, then the prefix.",
    "solution": "```text\nReturns app/config.py.\n\nLine 80-81 strips the quotes; line 84-85 strips the `a/`. The strip runs once because it is a single `if`; the guard is there for the\ndegenerate `a/` case, which would otherwise become empty.\n```",
    "explanation": "The function is four small rules in a fixed order; the order is the design, since quoting and prefixing can appear together."
  },
  "common_mistakes": [
    "Stripping the prefix twice, turning `app/config.py` into `pp/config.py`.",
    "Treating `/dev/null` as a filename and reporting a finding against it.",
    "Forgetting that git quotes paths containing spaces, so the quotes survive into the path."
  ],
  "project_links": [
    {
      "label": "normalize_path and its three rules",
      "path": "app/parser.py",
      "lines": "73-88"
    },
    {
      "label": "The added-file block in the sample",
      "path": "samples/sample.diff",
      "lines": "15-25"
    }
  ],
  "learn_more": [
    {
      "label": "app/parser.py — the parser",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/parser.py"
    },
    {
      "label": "samples/sample.diff — the sample under review",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/samples/sample.diff"
    }
  ],
  "glossary_terms": [
    "prefix — the a/ or b/ git writes on each side",
    "normalise — reduce a diff path to a repository path"
  ]
});
