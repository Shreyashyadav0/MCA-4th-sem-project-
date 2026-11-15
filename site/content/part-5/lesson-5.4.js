/* 5.4 — added, modified, deleted, renamed
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "5.4",
  "part": 5,
  "part_title": "Unified diffs",
  "title": "added, modified, deleted, renamed",
  "order": 504,
  "duration_min": 20,
  "concept_md": "### Four kinds, decided from the header\n\nEvery file in a diff gets exactly one change kind, decided from the header lines alone:\n\n```python\nChangeKind = Literal[\"added\", \"modified\", \"deleted\", \"renamed\"]\n```\n\n- **added** — the old side is `/dev/null`, or the header says `new file mode`.\n- **deleted** — the new side is `/dev/null`.\n- **renamed** — `diff --git a/old b/new` where the two paths differ, and git adds `rename from` / `rename to`.\n- **modified** — everything else, including a file whose content changed and whose path did not.\n\n### Why the kind is not inferred from the content\n\nA rename has no content hunk at all when the file is unchanged — the header says the path moved and nothing follows. A parser that waited for hunks to decide the kind would classify that as nothing. The header is the only place the answer exists, which is why `_Builder` carries an `explicit_change` slot: a header line sets it and the body never overrides it. When no header line set it, `_Builder.finish()` infers the kind from the paths collected so far.\n\n### The rename branch\n\nWhen the two paths in `diff --git a/x b/y` differ, the builder records `change = \"renamed\"` and keeps both paths, so a reviewer can say \"moved from here to there\" rather than \"deleted and added\", which would be two misleading findings.\n\n### What the sample shows\n\n`samples/sample.diff` exercises two of the four: `app/db.py` is `modified` and `app/report.py` is `added`. The other two kinds are implemented and not in this sample: `deleted` has a test, `renamed` is implemented but no test constructs one — which is worth knowing before you claim a parser handles everything.",
  "code_examples": [
    {
      "id": "5.4-ex-0",
      "lang": "python",
      "caption": "The kind each file gets, and how many hunks it carries",
      "code": "from app.parser import parse_diff\n\nwith open(\"samples/sample.diff\", encoding=\"utf-8\") as handle:\n    bundle = parse_diff(handle.read())\n\nfor file in bundle.files:\n    print(file.path, \"->\", file.change, \"with\", len(file.hunks), \"hunk(s)\")",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "app/db.py -> modified with 1 hunk(s)\napp/report.py -> added with 1 hunk(s)",
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
      "q": "A renamed file with no content change arrives in a diff. How many hunks does it carry?",
      "options": [
        "One, containing the old path only",
        "None — the header carries the change",
        "One, containing the new path only",
        "Two, one for each side of the move: old path and new path"
      ],
      "answer": 1,
      "why": "A pure rename changes no content, so there is nothing to hunk; the `rename from` / `rename to` lines are the entire record."
    },
    {
      "q": "Why can the change kind not be inferred from the hunks?",
      "options": [
        "Because `added` and `modified` look identical in the body",
        "Because hunks are parsed after the file list is built",
        "Because a pure rename has no hunks to infer from",
        "Because the kind is only cosmetic"
      ],
      "answer": 2,
      "why": "The zero-hunk case is the proof: with nothing in the body, the header is the only evidence of what happened."
    },
    {
      "q": "`app/report.py` is reported as `added`. What in the diff proves it?",
      "options": [
        "`--- /dev/null` plus `new file mode`",
        "The absence of `-` lines in its hunk",
        "The `index 0000000..4064cb7` line",
        "The `+++ b/app/report.py` line"
      ],
      "answer": 0,
      "why": "Either signal alone is suggestive; together they say the old side never existed. `index 0000000` is a consequence, not the rule."
    }
  ],
  "try_it": {
    "prompt": "Ask the parser for the change kind of each file and the count of hunks each one has.",
    "starter": "",
    "solution": "```console\n$ python -c \"from pathlib import Path; from app.parser import parse_diff; b = parse_diff(Path('samples/sample.diff').read_text()); print([(f.path, f.change, len(f.hunks)) for f in b.files])\"\n[('app/db.py', 'modified', 1), ('app/report.py', 'added', 1)]\n```",
    "explanation": "Both files here have exactly one hunk; the interesting zero-hunk case is a pure rename, which this sample does not contain."
  },
  "exercise": {
    "prompt": "Write a minimal diff for a file that was deleted, and say which header line makes the parser call it `deleted`.",
    "hint": "It is the mirror of the added case.",
    "solution": "```text\ndiff --git a/app/old.py b/app/old.py\ndeleted file mode 100644\n--- a/app/old.py\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-print(1)\n-print(2)\n\nThe `+++ /dev/null` line: the new side does not exist. The hunk's `+0,0` agrees —\nzero lines on the new side — but the header is what the parser reads.\n```",
    "explanation": "Added and deleted are the same test on opposite sides: `/dev/null` on the old side means added, on the new side means deleted."
  },
  "common_mistakes": [
    "Classifying a rename as delete-plus-add, which reports two changes where one happened.",
    "Inferring the kind from whether the body has `-` lines; an empty new file also has none.",
    "Assuming every file in a diff has a hunk — a pure rename has none."
  ],
  "project_links": [
    {
      "label": "The four change kinds",
      "path": "app/parser.py",
      "lines": "57"
    },
    {
      "label": "The builder and its explicit_change slot",
      "path": "app/parser.py",
      "lines": "305-340"
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
    "change kind — added, modified, deleted or renamed",
    "rename from / rename to — the header lines naming both paths",
    "explicit_change — the builder slot the header sets and the body cannot override"
  ]
});
