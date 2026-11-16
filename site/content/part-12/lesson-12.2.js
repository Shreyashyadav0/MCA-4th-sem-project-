/* 12.2 — Three outputs from one run
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "12.2",
  "part": 12,
  "part_title": "Surfaces: CLI, API, webhook, GitHub",
  "title": "Three outputs from one run",
  "order": 1202,
  "duration_min": 25,
  "concept_md": "### The same findings, three shapes\n\nThe CLI prints a human summary by default, one JSON object with `--json`, and more detail with `--verbose`. All three come from one `ProviderOutcome`, so they cannot disagree about what was found.\n\n### The human summary\n\nGrouped by severity, with the file and line, the issue and the suggested fix. It ends with the verdict and, when the run was degraded, the reason — because a reader of a terminal is the person most likely to be misled by an unlabelled fallback.\n\n### The JSON object\n\nThe outcome serialised: mode, provider, model, findings, reason, latency. A script reads `mode` first, because a mock run and a live run are different claims about the same findings.\n\n### Why verbose is not a fourth shape\n\nIt adds notes — which provider was selected and why, what the fallback did — to the same summary. The distinction is detail, not structure, which is why a reader can trust that `--verbose` shows nothing the JSON hides.\n\n### What a reader of the terminal needs first\n\nThe verdict, then the findings, then the reason if the run was degraded. That order is deliberate: a person who reads only the first line should still know whether the review blocked, and a person who reads two lines should know whether a model was involved.",
  "code_examples": [
    {
      "id": "12.2-ex-0",
      "lang": "console",
      "caption": "One run, and the mode it reports",
      "code": "python reviewer.py samples/sample.diff --diff --offline 2>&1 | tail -4",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "   Suggested Fix : Annotate it: `def render(value: str) -> str:` — every parameter and the return type.\n   Anchor        : anchored @ @@ -0,0 +1,5 @@\n\nverdict  : block",
      "why_not": "the browser runner has no shell and does not embed the surface modules; this command runs from a checkout."
    }
  ],
  "quiz": [
    {
      "q": "What do all three outputs share?",
      "options": [
        "One formatter function",
        "One JSON schema",
        "One ProviderOutcome",
        "One exit code path"
      ],
      "answer": 2,
      "why": "Three renderings of one object cannot disagree about the findings or the mode."
    },
    {
      "q": "What should a script read first?",
      "options": [
        "latency, and then the mode",
        "model, then the provider name",
        "reason, then the verdict",
        "mode, then the findings"
      ],
      "answer": 3,
      "why": "A mock run and a live run are different claims about identical findings."
    },
    {
      "q": "What does --verbose add?",
      "options": [
        "Notes added to the same summary",
        "A fourth output format entirely",
        "The raw provider responses",
        "A second findings list"
      ],
      "answer": 0,
      "why": "It changes detail, not structure, so nothing is hidden from the JSON reader."
    }
  ],
  "try_it": {
    "prompt": "Run the sample diff offline and look at the last lines.",
    "starter": "",
    "solution": "```console\n$ python reviewer.py samples/sample.diff --diff --offline | tail -4\n```",
    "explanation": "The summary ends with the verdict and the reason the run was degraded."
  },
  "exercise": {
    "prompt": "Which key in the JSON output tells you the run was degraded, and what value does it hold?",
    "hint": "It is a literal with two values.",
    "solution": "```console\n$ python reviewer.py samples/sample.diff --diff --offline --json | python -c \"import json,sys; print(json.load(sys.stdin)['mode'])\"\n```\n\n`mock` — and `live` when a provider actually ran.",
    "explanation": "The field is a literal, so a caller branches on it rather than inferring from an empty reason."
  },
  "common_mistakes": [
    "Writing a separate formatter per output and letting them drift.",
    "Reading the findings before the mode.",
    "Treating --verbose as a different schema."
  ],
  "project_links": [
    {
      "label": "The notes a verbose run adds",
      "path": "app/cli.py",
      "lines": "183-200"
    }
  ],
  "learn_more": [
    {
      "label": "app/cli.py — the formatters",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/cli.py"
    },
    {
      "label": "DEMO.md — captured transcripts",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/DEMO.md"
    }
  ],
  "glossary_terms": [
    "render — turn one object into a display shape",
    "verbose — more detail, same structure",
    "verdict — the approve or block decision"
  ]
});
