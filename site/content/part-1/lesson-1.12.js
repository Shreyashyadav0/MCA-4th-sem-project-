/* 1.12 — Typing: Optional, Union, Literal, TypedDict, Protocol
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "1.12",
  "part": 1,
  "part_title": "Python fundamentals",
  "title": "Typing: Optional, Union, Literal, TypedDict, Protocol",
  "order": 112,
  "duration_min": 25,
  "concept_md": "### Four tools, four jobs\n\n- **`X | None`** (the modern `Optional[X]`) — the value may be absent. `min_severity: Severity | None = None` in `app/engine.py` means \"no threshold\".\n- **`Union[A, B]` / `A | B`** — one of a fixed set of *types*. Useful when the shapes differ.\n- **`Literal[\"a\", \"b\"]`** — one of a fixed set of *values*. `ChangeKind = Literal[\"added\", \"modified\", \"deleted\", \"renamed\"]` in `app/parser.py` says a string, but only these four.\n- **`Protocol`** — structural typing: \"anything with this method\". No inheritance required.\n\n### Why Literal beats str\n\n`provider: str` accepts `\"sarvam\"`, `\"SARVAM\"`, `\"openai\"` and a typo. `app/main.py` types its request field as `Literal[\"auto\", \"local\", \"sarvam\", \"mock\"]` — four values, one of which (`auto`) asks the engine to choose rather than naming a provider. A closed set written as a type is documentation the tools enforce.\n\n### Why Protocol is the interesting one\n\n```python\nclass Provider(Protocol):\n    name: str\n    def review(self, diff: str) -> list[str]: ...\n```\n\nAny class with `name` and `review` satisfies it. The caller does not import the implementation, and the implementation does not inherit from anything. This repository does not declare a `Protocol` itself — Sarvam and LM Studio enter through one OpenAI-compatible adapter by convention rather than by a declared interface — but the property it relies on is the same one: two providers, one shape, no shared base class.\n\n### TypedDict, briefly (a general technique, not used here)\n\n`TypedDict` describes a dict with fixed keys and value types — the JSON payload case. It is a dict at runtime, so it costs nothing, and a checker catches `payload[\"sevrity\"]`.\n\n### Two rules of thumb\n\nPick one spelling for \"may be absent\" and keep it: `X | None` everywhere, not a mix with `Optional`. And reach for `Protocol` when two things share behaviour but not ancestry — that is the decoupling, not the type itself.",
  "code_examples": [
    {
      "id": "1.12-ex-0",
      "lang": "python",
      "caption": "A Protocol with two implementations, and a Literal alias",
      "code": "from typing import Literal, Protocol\n\n\nclass Provider(Protocol):\n    name: str\n\n    def review(self, diff: str) -> list[str]: ...\n\n\nclass MockProvider:\n    name = \"mock\"\n\n    def review(self, diff: str) -> list[str]:\n        return [\"rule-engine finding\"]\n\n\nclass LocalProvider:\n    name = \"local\"\n\n    def review(self, diff: str) -> list[str]:\n        return [\"model finding\"]\n\n\ndef run(provider: Provider, diff: str) -> list[str]:\n    print(\"running\", provider.name)\n    return provider.review(diff)\n\n\nprint(run(MockProvider(), \"diff\"))\nprint(run(LocalProvider(), \"diff\"))\n\nMode = Literal[\"mock\", \"local\", \"sarvam\"]\nprint(\"Literal aliases:\", Mode)\n",
      "runnable": true,
      "run_tier": "browser",
      "expected_output": "running mock\n['rule-engine finding']\nrunning local\n['model finding']\nLiteral aliases: typing.Literal['mock', 'local', 'sarvam']"
    }
  ],
  "quiz": [
    {
      "q": "What does `Protocol` give you that inheritance does not?",
      "options": [
        "Multiple inheritance, which a plain class cannot otherwise use",
        "Faster method dispatch, because no lookup table has to be built",
        "Structural typing: any class with the right methods fits, without importing it",
        "Runtime validation of every argument that a method receives"
      ],
      "answer": 2,
      "why": "The caller depends on a shape, not a name, which is why a provider can be swapped without either side importing the other."
    },
    {
      "q": "`app/main.py` types the provider field as `Literal[\"auto\", \"local\", \"sarvam\", \"mock\"]` rather than `str`. What does that buy?",
      "options": [
        "It runs faster, because the value is validated only once",
        "A checker rejects any other string before the request is served",
        "It allows more values than a plain string field would",
        "It makes the field optional in the request body"
      ],
      "answer": 1,
      "why": "`str` accepts every string including a typo; the Literal turns the closed set into something the tools check, which is the difference between a comment and a constraint."
    },
    {
      "q": "`min_severity: Severity | None = None` means what?",
      "options": [
        "A severity is required and None is not allowed",
        "The threshold is optional; None means no threshold",
        "Severity may be passed as a plain string as well",
        "It is a longer spelling of a required parameter"
      ],
      "answer": 1,
      "why": "The repository gets that decoupling by convention — one OpenAI-compatible adapter both providers speak — so a Protocol is how you would state the same property in the type system, not a class the code already declares."
    }
  ],
  "try_it": {
    "prompt": "Add a third provider class that satisfies the Protocol without inheriting from it, and pass it to `run`.",
    "starter": "class CachedProvider:\n    name = \"cached\"\n\n    def review(self, diff: str) -> list[str]:\n        return [\"cached finding\"]\n",
    "solution": "from typing import Protocol\n\n\nclass Provider(Protocol):\n    name: str\n\n    def review(self, diff: str) -> list[str]: ...\n\n\ndef run(provider: Provider, diff: str) -> list[str]:\n    print(\"running\", provider.name)\n    return provider.review(diff)\n\n\nclass CachedProvider:\n    name = \"cached\"\n\n    def review(self, diff: str) -> list[str]:\n        return [\"cached finding\"]\n\n\nprint(run(CachedProvider(), \"diff\"))\n",
    "explanation": "It prints `running cached` then `['cached finding']`. Nothing had to inherit from `Provider` — that is structural typing: the shape is the contract."
  },
  "exercise": {
    "prompt": "Rewrite `provider: str` as `provider: Literal[\"mock\", \"local\", \"sarvam\"]` in a small snippet, and show what happens when you pass `\"openai\"`.",
    "hint": "The type checker rejects it; the interpreter does not. Say which one you are demonstrating.",
    "solution": "from typing import Literal, get_args\n\nMode = Literal[\"mock\", \"local\", \"sarvam\"]\n\n\ndef review(provider: Mode) -> str:\n    return provider\n\n\nprint(\"legal values:\", get_args(Mode))\nprint(review(\"mock\"))\n# review(\"openai\")  -> mypy: Argument 1 has incompatible type \"Literal['openai']\"\n",
    "explanation": "At runtime the annotation is ignored, so `review(\"openai\")` runs. The protection is static: a checker flags the call before it ships, which is the whole value of the Literal — the interpreter will not save you."
  },
  "common_mistakes": [
    "Mixing `Optional[X]` and `X | None` in one codebase, so a reader has to work out whether the difference is meaningful.",
    "Reaching for `Union` when the two things share behaviour: a `Protocol` decouples them, a Union makes every caller handle both types.",
    "Believing annotations are enforced at runtime. They are not; Pydantic's validation is what enforces, and only at the boundary where it is used."
  ],
  "project_links": [
    {
      "label": "PROVIDERS and the selection result",
      "path": "app/engine.py",
      "lines": "60-100"
    },
    {
      "label": "The Literal aliases this lesson cites",
      "path": "app/parser.py",
      "lines": "55-60"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-5-providers.md — the providers track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-5-providers.md"
    },
    {
      "label": "ADR 0003 — one provider-agnostic OpenAI-compatible transport",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/decisions/0003-provider-agnostic-openai-compat.md"
    }
  ],
  "glossary_terms": [
    "Protocol — a type defined by its methods, satisfied without inheritance",
    "Literal — a type restricted to specific values",
    "Optional / X | None — the value may be absent",
    "TypedDict — a dict with fixed keys and value types, checked statically"
  ]
});
