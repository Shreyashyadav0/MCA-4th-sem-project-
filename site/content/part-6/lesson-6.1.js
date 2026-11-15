/* 6.1 — Why five fields and no more
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "6.1",
  "part": 6,
  "part_title": "The five-field contract",
  "title": "Why five fields and no more",
  "order": 601,
  "duration_min": 15,
  "concept_md": "### One shape for every finding\n\nWhatever produced a finding — a regex rule, a model call, a pasted snippet — it leaves the tool as the same five fields:\n\n```text\nfile, line, severity, issue, suggested_fix\n```\n\nThat is the whole contract. A sixth field would have to be understood by every consumer: the CLI table, the Markdown comment, the JSON body, the GitHub inline comment. Five is the number that all of them can render without a translation step.\n\n### Why not fewer\n\nDrop `severity` and a reviewer cannot triage. Drop `line` and a finding cannot be anchored to a diff. Drop `suggested_fix` and the comment is a complaint rather than a change. Each field earns its place by being read by something downstream.\n\n### The model enforces it\n\n```python\nclass Finding(BaseModel):\n    model_config = ConfigDict(extra=\"forbid\", frozen=True, str_strip_whitespace=True)\n```\n\n`extra=\"forbid\"` means a sixth key is an error, not a silently dropped extra. `frozen=True` means a finding cannot be edited after it is created — a review is a record, and a record that can change is not one.\n\n### What the five fields are not\n\nThey are not the whole finding. `AnchoredFinding` wraps one and adds the anchoring status; `ReviewResult` collects many. The contract is the atom, not the container.",
  "code_examples": [
    {
      "id": "6.1-ex-0",
      "lang": "python",
      "caption": "One finding, and the five keys it exposes",
      "code": "from app.models import Finding\n\nfinding = Finding(file=\"app/db.py\", line=\"3\", severity=\"CRITICAL\",\n                  issue=\"A token is hardcoded in the source.\",\n                  suggested_fix=\"Read it from the environment instead.\")\nprint(list(finding.as_row()))\nprint(finding.as_row()[\"Severity\"])",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "['File', 'Line', 'Severity', 'Issue', 'Suggested Fix']\nCRITICAL",
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
      "q": "What does `extra=\"forbid\"` do to a sixth field?",
      "options": [
        "It does nothing until the model is serialised",
        "It stores the key but hides it from the output",
        "It renames the key to a known field",
        "It raises instead of silently dropping the key"
      ],
      "answer": 3,
      "why": "The config turns an undeclared key into a validation error, which is why a wider finding cannot leak through a consumer that only knows five fields."
    },
    {
      "q": "Why is `frozen=True` on `Finding`?",
      "options": [
        "It makes the model faster to construct",
        "A finding is a record, and a record that can change is not one",
        "It allows the model to be hashed",
        "It prevents the fields from being validated"
      ],
      "answer": 1,
      "why": "Frozen blocks attribute assignment after construction, so what the rule engine produced is what the comment says. It is not about hashing — a dict field would still make it unhashable."
    },
    {
      "q": "Which field makes a finding anchorable to a diff?",
      "options": [
        "`suggested_fix`, which is the replacement",
        "`issue`, which names the problem",
        "`line`, which is what the anchorer compares against changed spans",
        "`severity`, which orders the output"
      ],
      "answer": 2,
      "why": "Anchoring asks whether the finding's line sits in an added span; without `line` the best a review could do is name the file."
    }
  ],
  "try_it": {
    "prompt": "Build a finding and print its row as a dictionary, then change one field and watch it fail.",
    "starter": "",
    "solution": "```python\nfrom app.models import Finding\n\nfinding = Finding(file=\"app/db.py\", line=\"3\", severity=\"HIGH\",\n                  issue=\"A token is hardcoded.\", suggested_fix=\"Use os.environ.\")\nprint(finding.as_row())\nfinding.severity = \"LOW\"   # FrozenInstanceError\n```",
    "explanation": "The row prints in contract order; the assignment raises because the model is frozen. Both behaviours come from `model_config`, one line."
  },
  "exercise": {
    "prompt": "Construct a `Finding` with a sixth key `confidence=0.9` and say what happens, then remove `suggested_fix` and say what happens.",
    "hint": "One is an unknown key; the other is a required field.",
    "solution": "```text\nconfidence=0.9  -> ValidationError, type \"extra_forbidden\", loc (\"confidence\",)\nsuggested_fix   -> ValidationError, type \"missing\", loc (\"suggested_fix\",)\n\nBoth are raised at construction, before anything downstream sees the object.\n```",
    "explanation": "The two failure types are different and both name the field, which is what makes the boundary debuggable from the error alone."
  },
  "common_mistakes": [
    "Adding a sixth field to carry extra detail, which breaks every consumer that knows five.",
    "Editing a finding after construction to fix its severity; the model is frozen.",
    "Assuming `frozen=True` makes a finding hashable — a dict-valued field still blocks it."
  ],
  "project_links": [
    {
      "label": "The Finding model and its config",
      "path": "app/models.py",
      "lines": "68-106"
    },
    {
      "label": "The five-field row",
      "path": "app/models.py",
      "lines": "97-106"
    }
  ],
  "learn_more": [
    {
      "label": "app/models.py — the models",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/models.py"
    },
    {
      "label": "docs/decisions/0001-five-field-finding.md",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0001-five-field-finding.md"
    }
  ],
  "glossary_terms": [
    "contract — the five fields every consumer can render",
    "frozen — a model that cannot be edited after construction",
    "extra=forbid — an undeclared key is an error"
  ]
});
