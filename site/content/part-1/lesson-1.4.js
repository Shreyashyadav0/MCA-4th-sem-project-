/* 1.4 — Classes, dataclasses and @property
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "1.4",
  "part": 1,
  "part_title": "Python fundamentals",
  "title": "Classes, dataclasses and @property",
  "order": 104,
  "duration_min": 25,
  "concept_md": "### Three ways to hold data, and when each is right\n\nA plain **class** when the object has behaviour and invariants. A **dataclass** when it is mostly data: `@dataclass` writes `__init__`, `__repr__` and `__eq__` for you, and `frozen=True` makes instances immutable and hashable. A **Pydantic `BaseModel`** when the data crosses a boundary and must be validated — a stray key from a model should fail loudly, not leak into a pull-request comment.\n\nThis repository uses all three, and the choice is deliberate:\n\n- `Finding` is a `BaseModel` with `extra=\"forbid\"` — it validates what a rule or a model hands it.\n- `MatchResult` in `benchmarks/matching.py` is a `@dataclass(frozen=True)` — internal, trusted, and cheap.\n- `Point` below is the smallest useful example of the second kind.\n\n### `@property` is a method that reads like an attribute\n\n```python\n@property\ndef magnitude(self) -> float:\n    return (self.x ** 2 + self.y ** 2) ** 0.5\n```\n\n`point.magnitude` computes every time it is read; it is not stored. That is the right tool for a derived value — `MatchResult.tp` is `len(self.matched)`, and computing it beats keeping a second field in sync.\n\n### Frozen means frozen\n\n`frozen=True` blocks assignment: `point.x = 5.0` raises `FrozenInstanceError`. That is not a limitation to work around; it is what makes the instance safe to share and to hash.\n\n### When you want a setter, do not use @property\n\nA `@property` with no setter used where assignment was intended fails at runtime, not at review time. If the value must change, make it a field.",
  "code_examples": [
    {
      "id": "1.4-ex-0",
      "lang": "python",
      "caption": "A frozen dataclass with a derived @property, and what assignment does",
      "code": "from dataclasses import dataclass\n\n\n@dataclass(frozen=True)\nclass Point:\n    x: float\n    y: float\n\n    @property\n    def magnitude(self) -> float:\n        return (self.x ** 2 + self.y ** 2) ** 0.5\n\n\npoint = Point(3.0, 4.0)\nprint(point)\nprint(\"magnitude:\", point.magnitude)\ntry:\n    point.x = 5.0\nexcept Exception as error:\n    print(type(error).__name__, \"->\", error)\n",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "Point(x=3.0, y=4.0)\nmagnitude: 5.0\nFrozenInstanceError -> cannot assign to field 'x'"
    }
  ],
  "quiz": [
    {
      "q": "Why is `Finding` a Pydantic model rather than a dataclass?",
      "options": [
        "Pydantic is faster",
        "Because it crosses a boundary and must reject a stray key",
        "Because dataclasses cannot hold strings",
        "Because it needs a @property"
      ],
      "answer": 1,
      "why": "`extra=\"forbid\"` fails an unknown field at the boundary, which is the whole point of validating what a model returns."
    },
    {
      "q": "What does `@dataclass(frozen=True)` give you besides immutability?",
      "options": [
        "A setter for every field",
        "Hashability, because the instance cannot change",
        "Automatic JSON output",
        "Validation against a schema"
      ],
      "answer": 1,
      "why": "An object whose fields cannot change has a stable hash, so it can be a set member or a dict key — which is why MatchResult is frozen."
    },
    {
      "q": "`point.magnitude` — when is the value computed?",
      "options": [
        "Once, when the object is built",
        "Every time the attribute is read",
        "Never, until you call a method",
        "When the class is defined"
      ],
      "answer": 1,
      "why": "A @property is a method behind attribute syntax, so each read recomputes it — correct for a derived value that must never drift."
    }
  ],
  "try_it": {
    "prompt": "Make `Point` mutable (drop `frozen=True`), assign `point.x = 5.0`, and print `magnitude` again. Then put `frozen=True` back and compare the two runs.",
    "starter": "from dataclasses import dataclass\n\n\n@dataclass\nclass Point:\n    x: float\n    y: float\n\n    @property\n    def magnitude(self) -> float:\n        return (self.x ** 2 + self.y ** 2) ** 0.5\n\n\npoint = Point(3.0, 4.0)\npoint.x = 5.0\nprint(point, point.magnitude)\n",
    "solution": "from dataclasses import dataclass\n\n\n@dataclass\nclass Point:\n    x: float\n    y: float\n\n    @property\n    def magnitude(self) -> float:\n        return (self.x ** 2 + self.y ** 2) ** 0.5\n\n\npoint = Point(3.0, 4.0)\npoint.x = 5.0\nprint(point, point.magnitude)\n",
    "explanation": "Mutable, the second print is `Point(x=5.0, y=4.0) 6.4031242374328485` — the property recomputed, which is why a derived value needs no second field. Frozen, the assignment raises FrozenInstanceError instead."
  },
  "exercise": {
    "prompt": "In two or three sentences, explain when this repository uses a dataclass and when it uses a BaseModel, using `MatchResult` and `Finding` as the examples.",
    "hint": "One of them crosses a boundary where untrusted input arrives; the other never leaves the process.",
    "solution": "`Finding` is a `BaseModel` because it is built from untrusted input — a rule's dict or a model's JSON — and `extra=\"forbid\"` must reject an unknown field at that boundary. `MatchResult` is a frozen dataclass because it is internal: computed from trusted values, never parsed, and immutable so it can be hashed and compared cheaply.",
    "explanation": "The dividing line is trust, not taste: validate where data enters, and keep the internal shapes cheap."
  },
  "common_mistakes": [
    "Forgetting `frozen=True` on a type that is meant to be immutable, then mutating it somewhere and wondering why a cached count is wrong.",
    "Using a `@property` with no setter where the caller needs assignment — it fails at runtime with AttributeError, not at review time.",
    "Reaching for `BaseModel` for an internal helper: validation costs time, and there is nothing to validate."
  ],
  "project_links": [
    {
      "label": "MatchResult — a frozen dataclass with derived properties",
      "path": "benchmarks/matching.py",
      "lines": "320-345"
    },
    {
      "label": "Finding — the validated BaseModel, for contrast",
      "path": "app/models.py",
      "lines": "68-95"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-1-models.md — the models track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-1-models.md"
    },
    {
      "label": "ADR 0001 — why Pydantic v2 with strict models",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0001-strict-pydantic-v2.md"
    }
  ],
  "glossary_terms": [
    "dataclass — a class whose __init__, __repr__ and __eq__ are generated from its fields",
    "frozen — immutable and therefore hashable",
    "BaseModel — Pydantic's validated data class, used at boundaries",
    "@property — a method that reads like an attribute and recomputes on each read"
  ]
});
