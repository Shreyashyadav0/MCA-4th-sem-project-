/* 2.1 — Why schemas exist
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "2.1",
  "part": 2,
  "part_title": "Typing and data modelling",
  "title": "Why schemas exist",
  "order": 201,
  "duration_min": 15,
  "concept_md": "### A dict is not a contract\n\n```python\nfinding = {\"file\": \"app/db.py\", \"severty\": \"CRITICAL\"}\nprint(finding[\"severity\"])      # KeyError, three functions later\n```\n\nA plain dict accepts any key and any type. The mistake surfaces wherever the value is finally read — usually far from where it was built, and in a stack trace that names the reader rather than the writer.\n\nA schema moves that failure to the door. `Finding` in `app/models.py` declares five fields and `extra=\"forbid\"`, so the same mistake fails at construction:\n\n```python\nFinding(file=\"app/db.py\", severty=\"CRITICAL\")\n# ValidationError: severty  Extra inputs are not permitted\n```\n\n### Where this repository puts the door\n\nTwo places, both where untrusted data arrives: the rule engine building a finding from a matched pattern, and the provider parsing a model's JSON. Everything downstream — sorting, anchoring, posting — can then assume the shape holds.\n\n### What you get for free\n\nA schema is not only a check. From the same declaration you get a default, a JSON serialiser, an error message that names the field, and documentation that cannot drift from the code.\n\n### The cost\n\nValidation is not free: every `Finding` built in a review is checked. That is why the internal shapes in `benchmarks/` are plain frozen dataclasses — nothing untrusted reaches them. Lesson 2.10 draws that line properly.",
  "code_examples": [
    {
      "id": "2.1-ex-0",
      "lang": "python",
      "caption": "The same mistake, caught at the door instead of at use",
      "code": "from app.models import Finding\n\n# A dict accepts anything.\nloose = {\"file\": \"app/db.py\", \"severty\": \"CRITICAL\"}\nprint(\"dict key present:\", \"severity\" in loose)\n\n# A model does not.\ntry:\n    Finding(file=\"app/db.py\", severty=\"CRITICAL\")\nexcept Exception as error:\n    print(\"model refused:\", type(error).__name__)\n    print(\"problems found:\", len(error.errors()))\n    extra = [e for e in error.errors() if e[\"type\"] == \"extra_forbidden\"][0]\n    print(\"the unknown key:\", extra[\"loc\"][0])\n",
      "runnable": true,
      "run_tier": "browser",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py"
      ],
      "expected_output": "dict key present: False\nmodel refused: ValidationError\nproblems found: 5\nthe unknown key: severty"
    }
  ],
  "quiz": [
    {
      "q": "What does a plain dict give you that a BaseModel does not?",
      "options": [
        "Nothing — it accepts any key and any value",
        "So the error arrives before the value is stored",
        "A default for missing keys",
        "JSON serialisation for free"
      ],
      "answer": 0,
      "why": "A dict is a container, not a contract: the key you misspelled stays a valid key, and the failure moves to whichever line reads it."
    },
    {
      "q": "Why does this repository validate at construction rather than at use?",
      "options": [
        "So the error arrives before the value is stored",
        "Because Pydantic is faster when it validates early",
        "So the failure names the field while the code that built it is still on the stack",
        "Because Python requires it for every model field"
      ],
      "answer": 2,
      "why": "Validating at the door keeps the traceback pointing at the writer; validating at use points at a reader that is usually innocent."
    },
    {
      "q": "What does `extra=\"forbid\"` on `Finding` actually reject?",
      "options": [
        "A missing required field",
        "A string with spaces around it",
        "A value of the wrong type",
        "A field the model does not declare"
      ],
      "answer": 3,
      "why": "It rejects unknown keys — which is what stops a future model's extra output from leaking into a pull-request comment."
    }
  ],
  "try_it": {
    "prompt": "Construct a `Finding` with all five fields, then remove `issue` and read the error. Which line of the message names the missing field?",
    "starter": "from app.models import Finding\n\nf = Finding(\n    file=\"app/db.py\",\n    line=\"3\",\n    severity=\"CRITICAL\",\n    issue=\"Token literal\",\n    suggested_fix=\"Read it from the environment.\",\n)\nprint(f.severity.value, f.file, f.line)\n",
    "solution": "from app.models import Finding\n\ntry:\n    Finding(\n        file=\"app/db.py\",\n        line=\"3\",\n        severity=\"CRITICAL\",\n        suggested_fix=\"Read it from the environment.\",\n    )\nexcept Exception as error:\n    print(type(error).__name__)\n    print(str(error))\n",
    "explanation": "The message names `issue` and says `Field required`. Note it is one of several: Pydantic reports every problem it finds at once, which is why the example above counts them."
  },
  "exercise": {
    "prompt": "Name two boundaries in this repository where a Pydantic model is the gate, and say what arrives through each one.",
    "hint": "One is inside the rule engine; the other is the model provider's reply.",
    "solution": "```text\n1. app/models.py:Finding — built by the rule engine from a matched pattern, and by the\n   provider from a model's JSON. Untrusted in both cases: a rule's dict or an LLM reply.\n2. app/models.py:ReviewResult — the whole review, assembled from a list of findings and\n   the notes explaining the mode, then serialised for the API and the CLI.\n```",
    "explanation": "Both are places where data the program did not build enters it. Nothing in `benchmarks/` needs one, because nothing there is untrusted."
  },
  "common_mistakes": [
    "Validating at the end of a pipeline instead of at its door, so the traceback names the reader rather than the writer.",
    "Building a dict and passing it around because it is quicker, then discovering the typo in production.",
    "Assuming a schema checks types only — `extra=\"forbid\"` is what catches the misspelled key."
  ],
  "project_links": [
    {
      "label": "Finding — five fields, extra forbidden",
      "path": "app/models.py",
      "lines": "68-105"
    },
    {
      "label": "ReviewResult — the whole review, validated the same way",
      "path": "app/models.py",
      "lines": "151-194"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-1-models.md — the models track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-1-models.md"
    },
    {
      "label": "ADR 0001 — why strict Pydantic v2",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0001-strict-pydantic-v2.md"
    }
  ],
  "glossary_terms": [
    "schema — a declared shape that data must satisfy",
    "boundary — where data the program did not build enters it",
    "ValidationError — Pydantic's failure, carrying one entry per problem"
  ]
});
