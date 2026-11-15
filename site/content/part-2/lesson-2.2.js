/* 2.2 — BaseModel, fields and coercion
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "2.2",
  "part": 2,
  "part_title": "Typing and data modelling",
  "title": "BaseModel, fields and coercion",
  "order": 202,
  "duration_min": 25,
  "concept_md": "### A field is a name, a type and a default\n\n```python\nclass Note(BaseModel):\n    text: str                  # required\n    tag: str = \"general\"       # optional, with a default\n```\n\nRequired means required: omit `text` and construction fails. A default makes the field optional, and the default is evaluated per instance, so a `list` default is safe here in a way it is not in a plain function signature.\n\n### Coercion is real, and it has limits\n\nPydantic converts a value when the conversion is unambiguous. `\"1\"` becomes `1` for an `int` field; `\"abc\"` does not, and raises. `\"3.0\"` becomes `3`. `None` never becomes `0`.\n\nThat leniency is why the repository types `Finding.line` as `str` rather than `int`: a line can be `\"42\"` or the range `\"42-45\"`, and coercion to an int would quietly destroy the second.\n\n### Dumping back out\n\n`model_dump()` returns a dict; `model_dump(mode=\"json\")` returns JSON-safe primitives; `model_dump_json()` returns a string. The difference matters at the HTTP layer, where a `Severity` enum has to become `\"CRITICAL\"` rather than `<Severity.CRITICAL: 'CRITICAL'>`.\n\n### Defaults that build themselves\n\n`Field(default_factory=list)` is the safe spelling for a mutable default. `ReviewResult.findings` uses it, so two results never share one list — the same trap as the mutable default argument, closed by the framework.",
  "code_examples": [
    {
      "id": "2.2-ex-0",
      "lang": "python",
      "caption": "Required, defaulted, coerced and refused",
      "code": "from pydantic import BaseModel\n\n\nclass Note(BaseModel):\n    text: str\n    tag: str = \"general\"\n    priority: int = 0\n\n\nprint(Note(text=\"a\").tag)\ncoerced = Note(text=\"b\", priority=\"2\")\nprint(coerced.priority, type(coerced.priority).__name__)\n\ntry:\n    Note(text=\"c\", priority=\"high\")\nexcept Exception as error:\n    entry = error.errors()[0]\n    print(\"refused:\", entry[\"loc\"][0], entry[\"type\"])\n\ntry:\n    Note(tag=\"x\")\nexcept Exception as error:\n    entry = error.errors()[0]\n    print(\"missing:\", entry[\"loc\"][0], entry[\"type\"])\n",
      "runnable": true,
      "run_tier": "browser",
      "packages": [
        "pydantic"
      ],
      "expected_output": "general\n2 int\nrefused: priority int_parsing\nmissing: text missing"
    }
  ],
  "quiz": [
    {
      "q": "`priority: int = 0` — what does the `= 0` change?",
      "options": [
        "It makes the field required",
        "It restricts the field to positive numbers",
        "It gives the field a default, so it may be omitted",
        "It makes the field read-only"
      ],
      "answer": 2,
      "why": "A default is what turns a required field into an optional one; a constraint on the value needs `Field(ge=...)`, which is lesson 2.3."
    },
    {
      "q": "`Note(priority=\"2\")` on an `int` field — what happens?",
      "options": [
        "It is coerced to 2, because the string is unambiguously numeric",
        "It stays the string \"2\" and fails on the next comparison",
        "It silently becomes 0, the field's default value",
        "It is coerced to 2, because the string is unambiguously an integer"
      ],
      "answer": 3,
      "why": "Pydantic coerces where the conversion is unambiguous; `\"2\"` is, `\"high\"` is not, which is the line between leniency and guessing."
    },
    {
      "q": "Why is `Finding.line` typed `str` rather than `int`?",
      "options": [
        "Because Pydantic cannot do ints",
        "Because a line may be a range like \"42-45\"",
        "Because the database stores strings",
        "To make sorting faster"
      ],
      "answer": 1,
      "why": "Coercion to int would destroy `\"42-45\"` or refuse it, and the contract allows both forms — so the type has to allow both too."
    }
  ],
  "try_it": {
    "prompt": "Add `note: str | None = None` to `Note` and construct one with and without it. Then call `model_dump()` on both.",
    "starter": "from pydantic import BaseModel\n\n\nclass Note(BaseModel):\n    text: str\n    tag: str = \"general\"\n\n\nprint(Note(text=\"a\").model_dump())\n",
    "solution": "from pydantic import BaseModel\n\n\nclass Note(BaseModel):\n    text: str\n    tag: str = \"general\"\n    note: str | None = None\n\n\nprint(Note(text=\"a\").model_dump())\nprint(Note(text=\"b\", note=\"careful\").model_dump())\n",
    "explanation": "Both dump successfully; the first has `note: None`. `X | None = None` is the idiom for \"may be absent\", and it is the same spelling the repository uses for `min_severity`."
  },
  "exercise": {
    "prompt": "Construct a `Finding` with `line=\"42-45\"` and one with `line=\"45-42\"`. Which one raises, and what does the message say?",
    "hint": "The validator on `line` checks the regex first, then the ordering.",
    "solution": "from app.models import Finding\n\n\nok = Finding(file=\"a.py\", line=\"42-45\", severity=\"LOW\", issue=\"x\", suggested_fix=\"y\")\nprint(\"accepted:\", ok.line)\n\ntry:\n    Finding(file=\"a.py\", line=\"45-42\", severity=\"LOW\", issue=\"x\", suggested_fix=\"y\")\nexcept Exception as error:\n    print(\"refused:\", str(error).splitlines()[2].strip())\n",
    "explanation": "`42-45` is accepted; `45-42` fails with \"line range must ascend\" — a rule the type alone cannot express, which is why lesson 2.5 exists."
  },
  "common_mistakes": [
    "Using a mutable default (`items: list = []`) where `Field(default_factory=list)` is meant — the same trap as a mutable function default.",
    "Typing a field `int` because the value is usually numeric, when the contract also allows a range.",
    "Comparing `model_dump()` output to JSON: enums stay enum objects until `mode=\"json\"`."
  ],
  "project_links": [
    {
      "label": "Field declarations, defaults and factories",
      "path": "app/models.py",
      "lines": "68-105"
    },
    {
      "label": "default_factory on a list field",
      "path": "app/models.py",
      "lines": "155-165"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-1-models.md — the models track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-1-models.md"
    }
  ],
  "glossary_terms": [
    "coercion — converting a value to the declared type when the conversion is unambiguous",
    "default_factory — a callable that builds a fresh default per instance",
    "model_dump — a dict of the model's fields"
  ]
});
