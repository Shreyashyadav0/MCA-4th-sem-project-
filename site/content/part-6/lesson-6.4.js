/* 6.4 — issue and suggested_fix: one sentence each
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "6.4",
  "part": 6,
  "part_title": "The five-field contract",
  "title": "issue and suggested_fix: one sentence each",
  "order": 604,
  "duration_min": 20,
  "concept_md": "### Two sentences, two jobs\n\n`issue` says what is wrong and why it bites. `suggested_fix` says what to do instead. They are separate fields because they are read by different readers: the issue by a human deciding whether to care, the fix by a human deciding whether to accept.\n\n### Brevity is enforced by the shape, not by a style guide\n\nBoth fields carry `min_length=1`, so neither may be empty. Neither has a maximum, and the discipline is social: a comment that runs to a paragraph will not be read in a pull request, and an inline comment has about 120 characters of comfortable width.\n\nThe rule the repository follows is one sentence each. \"A token is hardcoded in the source\" is an issue. \"Read it from the environment instead\" is a fix. Neither repeats the other.\n\n### Why not merge them\n\nA merged field would force every consumer to guess where the diagnosis ends and the remedy begins. The Markdown renderer puts them in different table columns; the GitHub client posts the fix as a suggestion block. Two fields, two destinations.\n\n### The trap\n\nThe tempting failure is to put the code in `issue` and the prose in `suggested_fix`. The reader then has to rewrite it before acting — which is the work the tool exists to save.",
  "code_examples": [
    {
      "id": "6.4-ex-0",
      "lang": "python",
      "caption": "The two fields, and what an empty one does",
      "code": "from app.models import Finding\n\nf = Finding(file=\"app/db.py\", line=\"3\", severity=\"HIGH\",\n            issue=\"A token is hardcoded in the source.\",\n            suggested_fix=\"Read it from os.environ at startup.\")\nprint(\"issue:\", f.issue)\nprint(\"fix  :\", f.suggested_fix)\n\ntry:\n    Finding(file=\"a.py\", line=\"1\", severity=\"LOW\", issue=\"\", suggested_fix=\"x\")\nexcept Exception as exc:\n    print(\"empty issue ->\", exc.errors()[0][\"type\"])",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "issue: A token is hardcoded in the source.\nfix  : Read it from os.environ at startup.\nempty issue -> string_too_short",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py"
      ]
    }
  ],
  "quiz": [
    {
      "q": "What does `issue` answer that `suggested_fix` does not?",
      "options": [
        "What is wrong and why it bites",
        "Which file the problem is in",
        "How severe the problem is",
        "What the replacement code should be"
      ],
      "answer": 0,
      "why": "The issue is the diagnosis; the fix is the remedy. The file, line and severity live in their own fields."
    },
    {
      "q": "Why does the model forbid an empty `issue`?",
      "options": [
        "Because Pydantic requires a minimum of two fields per model",
        "Because JSON cannot store empty strings",
        "Because the column would render as null",
        "A finding with no diagnosis cannot be acted on or triaged"
      ],
      "answer": 3,
      "why": "`min_length=1` stops the empty case at the boundary, where it is cheap to catch, rather than at a reviewer who has to ask what it meant."
    },
    {
      "q": "What goes wrong when the code is put in `issue`?",
      "options": [
        "The field fails validation",
        "The reader must rewrite it before acting",
        "The severity is downgraded",
        "The finding can no longer be anchored to a line in the diff"
      ],
      "answer": 1,
      "why": "The fix field is what a consumer renders as a suggestion; a diagnosis full of code has to be translated back into a change by hand."
    }
  ],
  "try_it": {
    "prompt": "Print the row for a finding whose issue is one sentence and whose fix is the replacement line.",
    "starter": "",
    "solution": "```python\nfrom app.models import Finding\n\nf = Finding(file=\"app/db.py\", line=\"7\", severity=\"CRITICAL\",\n            issue=\"The query is built by string interpolation.\",\n            suggested_fix=\"Pass uid as a parameter: execute(sql, (uid,)).\")\nprint(f.as_row())\n```",
    "explanation": "The row puts both sentences in their own columns, which is the shape every renderer expects."
  },
  "exercise": {
    "prompt": "Rewrite this as two fields: \"line 7 has SQL injection, use parameters\".",
    "hint": "One half is the diagnosis, the other the change.",
    "solution": "```text\nissue         \"The query is built by interpolating uid into the SQL string.\"\nsuggested_fix \"Pass uid as a parameter: execute(sql, (uid,)).\"\n\nThe original sentence mixes both and names the line, which is already its own field.\n```",
    "explanation": "Splitting the sentence is the exercise: what is wrong, and what to write instead, with the position left to `line`."
  },
  "common_mistakes": [
    "Leaving `suggested_fix` as \"fix this\", which saves the reader no work.",
    "Repeating the file and line inside `issue`, which duplicates fields that already exist.",
    "Writing a paragraph in `issue`; an inline comment will be truncated in the UI."
  ],
  "project_links": [
    {
      "label": "The issue and fix fields",
      "path": "app/models.py",
      "lines": "68-83"
    },
    {
      "label": "Where the row puts them",
      "path": "app/models.py",
      "lines": "97-105"
    }
  ],
  "learn_more": [
    {
      "label": "app/models.py — the models",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/models.py"
    },
    {
      "label": "docs/decisions/0001-five-field-finding.md",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0001-strict-pydantic-v2.md"
    }
  ],
  "glossary_terms": [
    "issue — the diagnosis, in one sentence",
    "suggested_fix — the concrete change to make",
    "suggestion block — the GitHub form that renders a fix as code"
  ]
});
