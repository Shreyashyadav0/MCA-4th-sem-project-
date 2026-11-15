/* 2.4 — ConfigDict: extra='forbid' and frozen=True
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "2.4",
  "part": 2,
  "part_title": "Typing and data modelling",
  "title": "ConfigDict: extra='forbid' and frozen=True",
  "order": 204,
  "duration_min": 20,
  "concept_md": "### One line that changes what the model accepts\n\n```python\nmodel_config = ConfigDict(extra=\"forbid\", frozen=True, str_strip_whitespace=True)\n```\n\nThat is `Finding`'s configuration, quoted from `app/models.py`. Three settings, three effects.\n\n**`extra=\"forbid\"`** turns an unknown key into an error. The alternative, `ignore`, silently drops it — and a model's stray `confidence` field would then vanish without anyone noticing. Forbidding is what makes model output safe to parse: a shape you did not expect is a failure, not a shrug.\n\n**`frozen=True`** makes an instance immutable, and hashable when every field is hashable. A frozen finding can be a set member or a dict key, and cannot be mutated by a caller who received it.\n\n**`str_strip_whitespace=True`** trims surrounding spaces on every string field before validation. `\"  app/db.py  \"` becomes `\"app/db.py\"`, so a constraint on length is not fooled by padding.\n\n### What frozen costs you, and the trap in the obvious fix\n\nYou cannot fix a field in place, so you build a variant. The obvious method has a sharp edge: `model_copy(update={...})` applies the update **without validating it**, so an update with the string `\"LOW\"` leaves a `str` where a `Severity` belongs, and nothing complains until something reads `.value`.\n\nThe safe variant re-validates:\n\n```python\nupdated = Finding.model_validate({**finding.model_dump(), \"severity\": \"LOW\"})\n```\n\nThat is a real difference, not a stylistic one, and the example below shows both.\n\n### Why a webhook handler cares\n\nA handler receives JSON from outside, builds a model, and passes it on. Forbidding unknown keys means the payload cannot smuggle extra state past the handler, and freezing means nothing downstream can quietly rewrite it.",
  "code_examples": [
    {
      "id": "2.4-ex-0",
      "lang": "python",
      "caption": "The three settings, and model_copy instead of mutation",
      "code": "from app.models import Finding\n\nfinding = Finding(\n    file=\"  app/db.py  \",\n    line=\"3\",\n    severity=\"CRITICAL\",\n    issue=\"Token literal\",\n    suggested_fix=\"Read it from the environment.\",\n)\nprint(\"stripped:\", repr(finding.file))\n\ntry:\n    finding.severity = \"LOW\"\nexcept Exception as error:\n    print(\"frozen:\", type(error).__name__)\n\nloose = finding.model_copy(update={\"severity\": \"LOW\"})\nprint(\"model_copy leaves a:\", type(loose.severity).__name__)\n\nsafe = Finding.model_validate({**finding.model_dump(), \"severity\": \"LOW\"})\nprint(\"revalidated:\", safe.severity.value, \"| original:\", finding.severity.value)\n",
      "runnable": true,
      "run_tier": "browser",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py"
      ],
      "expected_output": "stripped: 'app/db.py'\nfrozen: ValidationError\nmodel_copy leaves a: str\nrevalidated: LOW | original: CRITICAL"
    }
  ],
  "quiz": [
    {
      "q": "What does `extra=\"forbid\"` protect you from?",
      "options": [
        "A missing field",
        "An unknown key arriving in the payload",
        "A value of the wrong type",
        "A slow validator"
      ],
      "answer": 1,
      "why": "With `ignore`, an unexpected key disappears silently; forbidding turns it into a failure you can see and fix."
    },
    {
      "q": "A frozen model cannot be changed. How do you produce a valid variant?",
      "options": [
        "`copy.deepcopy` and then assign to the field",
        "`model_copy(update={...})` and nothing else",
        "`model_validate({**model.model_dump(), ...})`, so the change is checked",
        "Unfreeze the config for that one field"
      ],
      "answer": 2,
      "why": "`model_copy(update=...)` skips validation, so it can build an instance whose field is the wrong type; re-validating is what keeps the invariant true."
    },
    {
      "q": "What does `str_strip_whitespace=True` change?",
      "options": [
        "It removes all spaces inside strings",
        "It trims leading and trailing spaces before validation",
        "It converts strings to lowercase",
        "It makes strings optional"
      ],
      "answer": 1,
      "why": "Trimming happens before validation, so `min_length=1` cannot be satisfied by a string of spaces."
    }
  ],
  "try_it": {
    "prompt": "Try `Finding(..., confidence=0.9)` and read the error. Then try `model_copy(update={\"line\": \"7\"})` on a valid finding.",
    "starter": "from app.models import Finding\n\nf = Finding(file=\"a.py\", line=\"3\", severity=\"LOW\", issue=\"x\", suggested_fix=\"y\")\nprint(f.model_copy(update={\"line\": \"7\"}).line)\n",
    "solution": "from app.models import Finding\n\nf = Finding(file=\"a.py\", line=\"3\", severity=\"LOW\", issue=\"x\", suggested_fix=\"y\")\nprint(f.model_copy(update={\"line\": \"7\"}).line)\ntry:\n    Finding(file=\"a.py\", line=\"3\", severity=\"LOW\", issue=\"x\", suggested_fix=\"y\", confidence=0.9)\nexcept Exception as error:\n    print(\"refused:\", error.errors()[0][\"type\"], error.errors()[0][\"loc\"])\n",
    "explanation": "The copy prints `7`; the extra key fails with `extra_forbidden` at `('confidence',)`. Careful with the copy: `model_copy(update=...)` does not validate, so `update={\"line\": \"not-a-line\"}` would slip through."
  },
  "exercise": {
    "prompt": "Explain how you build a variant of a frozen model instead of mutating it, and why the framework re-validates the change.",
    "hint": "The method is `model_copy(update=...)`; the re-validation is what keeps the invariant true.",
    "solution": "```text\nmodel_copy(update={...}) returns a new instance with those fields replaced and leaves the\noriginal untouched — but it does NOT validate the update, so a field can end up the wrong\ntype (a str where a Severity belongs) with no error at the time.\nThe safe pattern is model_validate({**model.model_dump(), ...}), which runs the same\nvalidators a fresh construction would, so the variant cannot be invalid.\n```",
    "explanation": "Immutability without a validated copy just moves the bug one method call later — which is why the safe pattern re-validates rather than patching fields."
  },
  "common_mistakes": [
    "Using `extra=\"ignore\"` and wondering why a model's extra field never reaches the log.",
    "Mutating a frozen model and catching the error as if it were a bug — it is the feature.",
    "Assuming `model_copy(update=...)` validates: it does not, and a mistyped field survives until something reads it."
  ],
  "project_links": [
    {
      "label": "The model_config line, quoted above",
      "path": "app/models.py",
      "lines": "68-75"
    },
    {
      "label": "A second model with a different config",
      "path": "app/models.py",
      "lines": "151-160"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-1-models.md — the models track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-1-models.md"
    },
    {
      "label": "ADR 0001 — strict Pydantic v2",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0001-strict-pydantic-v2.md"
    }
  ],
  "glossary_terms": [
    "ConfigDict — per-model configuration",
    "frozen — immutable, and hashable when its fields are",
    "model_copy — build a new instance with fields replaced"
  ]
});
