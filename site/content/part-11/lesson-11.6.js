/* 11.6 — Guided read: the engine in five blocks
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "11.6",
  "part": 11,
  "part_title": "The engine and the fallback",
  "title": "Guided read: the engine in five blocks",
  "order": 1106,
  "duration_min": 30,
  "concept_md": "### Reading `app/engine.py` in order\n\n**The constants and the docstring** first — `PROVIDERS`, `REQUEST_AUTO`, and the sentence that says the module owns no transport. **The selection record** — `ProviderSelection`, a dataclass of provider, config and reason. **The two config builders** — what each provider needs before it can be called. **The selector** — one function, four accepted requests, a reason for every answer. **The entry point** — `review()` with its four knobs and its branch order, plus `_mock_outcome` for the relabel.\n\n### Why that order\n\nBecause no name is used before it is defined, and the file reads as a decision followed by its implementation. The docstring at the top is the claim; the last block is the code that keeps it.\n\n### What to look for as you read\n\nEvery branch returns a `ProviderOutcome`, never raises for a configuration reason. Every reason names something a reader can act on. And the live call appears exactly once, at the end.\n\n### The rebuild exercise\n\n`rebuild/tests/test_rebuild_engine.py` asks you to reimplement the selection and the fallback against a small suite. Start with `ProviderSelection`, then the builders, then the branch order in `review()` — the order is what the tests check most closely.",
  "code_examples": [
    {
      "id": "11.6-ex-0",
      "lang": "console",
      "caption": "The five blocks, in file order",
      "code": "grep -n '^class \\|^def \\|^PROVIDERS\\|^REQUEST_AUTO' app/engine.py",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "66:PROVIDERS: tuple[str, ...] = (\"sarvam\", \"local\", \"mock\")\n72:REQUEST_AUTO: str = \"auto\"\n83:class ProviderSelection:\n99:def _non_blank(value: str | None) -> bool:\n113:def config_for_sarvam(settings: Settings) -> OpenAICompatConfig | None:\n135:def config_for_local(settings: Settings) -> OpenAICompatConfig | None:\n159:def _local_missing(settings: Settings) -> str:\n174:def _mock_selection(reason: str) -> ProviderSelection:\n186:def _live_selection(provider: str, config: OpenAICompatConfig, reason: str) -> ProviderSelection:\n200:def select_provider(settings: Settings, *, requested: str = \"auto\") -> ProviderSelection:\n284:def _mock_outcome(\n320:def review(",
      "why_not": "the browser runner does not embed app/engine.py or the provider modules; this command runs from a checkout instead."
    }
  ],
  "quiz": [
    {
      "q": "Which block comes first in the file?",
      "options": [
        "The entry point",
        "The selection record",
        "The selector function on every run",
        "The constants and docstring"
      ],
      "answer": 3,
      "why": "The docstring is the claim about transport ownership; the blocks below implement it."
    },
    {
      "q": "How many times does the live call appear?",
      "options": [
        "Once, at the end",
        "Once per provider",
        "Twice, for local and sarvam",
        "Never in this file"
      ],
      "answer": 0,
      "why": "A single call site is what makes the transport claim checkable by reading."
    },
    {
      "q": "What does every branch return?",
      "options": [
        "A list of findings",
        "A ProviderOutcome",
        "A boolean and a reason",
        "An exception"
      ],
      "answer": 1,
      "why": "No configuration reason raises, so a surface never has to catch one."
    }
  ],
  "try_it": {
    "prompt": "List the file's top-level definitions in order.",
    "starter": "",
    "solution": "```console\n$ grep -n '^class \\|^def ' app/engine.py\n```",
    "explanation": "The selection record, the builders, the selector and the entry point — five blocks in dependency order."
  },
  "exercise": {
    "prompt": "Which function is defined last, and why does that matter for the transport claim?",
    "hint": "The last definition is the one a surface calls.",
    "solution": "```console\n$ grep -n '^def ' app/engine.py | tail -2\n```\n\n`review()` — and its single live call at the end is the only place the network is reached.",
    "explanation": "Reading to the end is enough to confirm that the engine delegates rather than transports."
  },
  "common_mistakes": [
    "Reimplementing the selector before the selection record.",
    "Reading the branch order as arbitrary; it encodes which promise wins.",
    "Assuming a rebuild needs the adapter to pass its tests."
  ],
  "project_links": [
    {
      "label": "The selection record",
      "path": "app/engine.py",
      "lines": "82-96"
    },
    {
      "label": "The rebuild suite",
      "path": "rebuild/tests/test_rebuild_engine.py",
      "lines": "1-86"
    }
  ],
  "learn_more": [
    {
      "label": "app/engine.py",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/engine.py"
    },
    {
      "label": "rebuild/README.md — the rebuild exercises",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/rebuild/README.md"
    }
  ],
  "glossary_terms": [
    "guided read — a walk through a file in dependency order",
    "block — a group of definitions that belong together",
    "rebuild exercise — reimplementing a module against its tests"
  ]
});
