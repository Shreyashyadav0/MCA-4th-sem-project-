/* 2.7 — Literal and Enum for closed sets
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "2.7",
  "part": 2,
  "part_title": "Typing and data modelling",
  "title": "Literal and Enum for closed sets",
  "order": 207,
  "duration_min": 20,
  "concept_md": "### Three ways to say \"one of these\"\n\n```python\nseverity: str                                  # anything at all\nseverity: Literal[\"LOW\", \"MEDIUM\"]             # one of these two strings\nseverity: Severity                             # an enum member, with behaviour\n```\n\n`Severity` in `app/models.py` is a `str`-valued Enum: `Severity.CRITICAL == \"CRITICAL\"` is true, so it serialises as a plain string and still carries `.value`, `.rank` and a fixed order. That is why the repository sorts by `severity.rank` rather than by name.\n\n### When Literal is the better tool\n\nA `Literal` is lighter: no import of an enum class, no `.value` at the call site, and the values are visible where the field is declared. `app/main.py` types its provider field as `Literal[\"auto\", \"local\", \"sarvam\", \"mock\"]` — four strings, one of which (`auto`) asks the engine to choose. There is no behaviour attached, so an enum would buy nothing.\n\n### When the Enum wins\n\nAs soon as you need behaviour or ordering, the enum wins. `Severity.rank` is what makes \"CRITICAL first\" a sort key rather than a lookup table. And `Severity(\"LOW\")` raises on a bad value, which is a validation the Literal also gives but without the member to hold a rank.\n\n### Reading it in a diff\n\n`Literal[...]` inline is one line and obvious. An enum moves the set to another file, which is better when ten modules need it and worse when one does.",
  "code_examples": [
    {
      "id": "2.7-ex-0",
      "lang": "python",
      "caption": "The enum the repository uses, and a Literal that needs no behaviour",
      "code": "from typing import Literal, get_args\n\nfrom app.models import Severity\n\nprint(\"enum values:\", [member.value for member in Severity])\nprint(\"rank of CRITICAL:\", Severity.CRITICAL.rank)\nprint(\"is a str:\", Severity.CRITICAL == \"CRITICAL\")\n\nMode = Literal[\"auto\", \"local\", \"sarvam\", \"mock\"]\nprint(\"literal:\", get_args(Mode))\nprint(\"a bad value:\", end=\" \")\ntry:\n    Severity(\"SEVERE\")\nexcept ValueError as error:\n    print(type(error).__name__)\n",
      "runnable": true,
      "run_tier": "browser",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py"
      ],
      "expected_output": "enum values: ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']\nrank of CRITICAL: 3\nis a str: True\nliteral: ('auto', 'local', 'sarvam', 'mock')\na bad value: ValueError"
    }
  ],
  "quiz": [
    {
      "q": "Why does the repository sort by `severity.rank` instead of the string?",
      "options": [
        "Strings cannot be sorted",
        "Because rank encodes the order CRITICAL > HIGH > MEDIUM > LOW",
        "Because rank is faster",
        "Because severity is not a string"
      ],
      "answer": 1,
      "why": "Alphabetical order would put CRITICAL before LOW by accident of spelling; rank states the intended order explicitly."
    },
    {
      "q": "When is a `Literal` better than an `Enum`?",
      "options": [
        "When the set needs behaviour or ordering",
        "When the set is a few strings and nothing else is attached",
        "When the values are integers",
        "Never"
      ],
      "answer": 1,
      "why": "`Literal[\"auto\", \"local\", \"sarvam\", \"mock\"]` carries no behaviour, so an enum class would be a file for nothing."
    },
    {
      "q": "`Severity.CRITICAL == \"CRITICAL\"` is True because…",
      "options": [
        "Pydantic converts it at comparison time",
        "`Severity` is a `str`-valued Enum",
        "The enum overrides `__eq__`",
        "It is actually False"
      ],
      "answer": 1,
      "why": "A str-valued Enum member *is* a string, which is why it serialises as one and compares equal to one."
    }
  ],
  "try_it": {
    "prompt": "Rewrite a provider field as `Literal[\"mock\", \"local\"]`, then pass `\"sarvam\"` and read the error.",
    "starter": "from typing import Literal\n\nfrom pydantic import BaseModel\n\n\nclass Request(BaseModel):\n    provider: Literal[\"mock\", \"local\"] = \"mock\"\n\n\nprint(Request().provider)\n",
    "solution": "from typing import Literal\n\nfrom pydantic import BaseModel\n\n\nclass Request(BaseModel):\n    provider: Literal[\"mock\", \"local\"] = \"mock\"\n\n\nprint(Request().provider)\ntry:\n    Request(provider=\"sarvam\")\nexcept Exception as error:\n    print(\"refused:\", error.errors()[0][\"type\"])\n",
    "explanation": "It prints `mock` then `refused: literal_error` — the closed set is enforced at parse time, not at the call site that eventually fails."
  },
  "exercise": {
    "prompt": "Rewrite one real field's annotation using `Literal`. Pick `ReviewResult.mode` (currently `str` plus a validator) and show what changes.",
    "hint": "With a Literal you can drop the validator — the type now carries the rule.",
    "solution": "from typing import Literal\n\nfrom pydantic import BaseModel\n\n\nclass Result(BaseModel):\n    mode: Literal[\"live\", \"mock\"]\n\n\nprint(Result(mode=\"mock\").mode)\ntry:\n    Result(mode=\"offline\")\nexcept Exception as error:\n    print(\"refused:\", error.errors()[0][\"type\"])\n",
    "explanation": "The `_check_mode` validator becomes unnecessary: `literal_error` replaces it, and the rule is visible in the annotation. The repository keeps `str` there because the validator's message is the one its tests assert."
  },
  "common_mistakes": [
    "Using a bare `str` for a closed set, then validating it in a function nobody calls on the new path.",
    "Reaching for an Enum when the set is four strings with no behaviour — one more file, no gain.",
    "Comparing an Enum member to a string with `is` instead of `==`; `is` is an identity test and will be False."
  ],
  "project_links": [
    {
      "label": "Severity: the str-valued Enum with a rank",
      "path": "app/models.py",
      "lines": "46-60"
    },
    {
      "label": "The provider field typed as a Literal",
      "path": "app/main.py",
      "lines": "188-195"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-5-providers.md — the providers track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-5-providers.md"
    },
    {
      "label": "ADR 0003 — one provider-agnostic transport",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0003-provider-agnostic-openai-compat.md"
    }
  ],
  "glossary_terms": [
    "Literal — a type restricted to specific values",
    "Enum — a named set of members, optionally with behaviour",
    "rank — the integer order a severity sorts by"
  ]
});
