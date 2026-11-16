/* 12.9 — The viva: three variants, and how honest each one is
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "12.9",
  "part": 12,
  "part_title": "Surfaces: CLI, API, webhook, GitHub",
  "title": "The viva: three variants, and how honest each one is",
  "order": 1209,
  "duration_min": 30,
  "concept_md": "### Three ways to run it, in ascending cost\n\n**A — offline mock.** The 63 rules, no network. This is the one that has been run end to end and captured; the transcripts in `DEMO.md` are real.\n\n**B — local via LM Studio.** The OpenAI-compatible adapter against a model on your machine. Unexercised in this repository: the live branch was verified with the real SDK against a stub server, not a real model. `DEMO.md` shows the output's shape, not a recorded run.\n\n**C — Sarvam.** The same adapter against `https://api.sarvam.ai/v1`. Unverified: no real key was ever used. The failure path is real and reproduced; no successful Sarvam review exists.\n\n### How to say it in a viva\n\nMatch `HANDOFF.md`'s ledger: real, simulated, deferred. A is real. B is simulated — the code path is real, the counterpart is a fake. C is deferred, and what has been captured is the rejection, not a review.\n\n### What not to claim\n\nThat any variant \"works with an LLM\". B and C are written to a protocol; the repository has no capture of either producing a review. Saying so is not modesty — it is the only claim the evidence supports, and a viva rewards the candidate who knows the difference.\n\n### The question you will be asked\n\n\"What happens if the model is unavailable?\" The answer is the whole design: the run degrades to the rule engine, labels itself mock, and logs one WARNING. That is true of all three variants, and it is the part that has been tested.",
  "code_examples": [
    {
      "id": "12.9-ex-0",
      "lang": "console",
      "caption": "The three variants and their status",
      "code": "grep -n '^| [ABC] —' DEMO.md | cut -c1-120",
      "runnable": false,
      "run_tier": "terminal",
      "expected_output": "13:| A — offline mock | `app/rules.py` (63 rules, no network) | **Exercised.** Transcripts in §2 are real, captured 2\n14:| B — local via LM Studio | `app/openai_compat_provider.py` against a real model | **Unexercised in this repo.** Th\n15:| C — Sarvam | the same adapter against `https://api.sarvam.ai/v1` | **Unverified.** No real key was ever used. The",
      "why_not": "the browser runner has no shell and does not embed the surface modules; this command runs from a checkout."
    }
  ],
  "quiz": [
    {
      "q": "Which variant has been captured end to end?",
      "options": [
        "B, the local model run",
        "A, the offline mock run",
        "C, the Sarvam call",
        "All three of them equally"
      ],
      "answer": 1,
      "why": "Its transcripts are real; B shows a shape and C has only a rejection captured."
    },
    {
      "q": "How should B be described?",
      "options": [
        "Real: it ran against a model",
        "Deferred: it was never written at all",
        "Simulated: real path, fake peer",
        "Unverified: no code exists"
      ],
      "answer": 2,
      "why": "The live branch was verified against a stub server, not a model."
    },
    {
      "q": "What is true of all three variants?",
      "options": [
        "They all need a real API key",
        "They all post a review comment",
        "They all measure their own accuracy",
        "A missing model degrades safely"
      ],
      "answer": 3,
      "why": "The fallback is the tested part, and it is the same in every variant."
    }
  ],
  "try_it": {
    "prompt": "Print the three variants and their stated status.",
    "starter": "",
    "solution": "```console\n$ grep -n '^| [ABC] —' DEMO.md\n```",
    "explanation": "One line each, with the status column saying exercised, unexercised or unverified."
  },
  "exercise": {
    "prompt": "Which of the three has a captured failure but no captured success?",
    "hint": "The rejection is real; the review is not.",
    "solution": "```console\n$ grep -n '§4.2\\|api.sarvam.ai' DEMO.md | head -3\n```\n\nC — Sarvam. The rejection was reproduced; no successful review exists.",
    "explanation": "A captured failure is evidence about the failure path, not about the feature."
  },
  "common_mistakes": [
    "Claiming any variant works with an LLM when no review was captured.",
    "Describing B as exercised because its tests pass.",
    "Framing the comparison against another tool instead of the ledger."
  ],
  "project_links": [
    {
      "label": "The three-variant table",
      "path": "DEMO.md",
      "lines": "11-586"
    },
    {
      "label": "The ledger this frames against",
      "path": "HANDOFF.md",
      "lines": "5-53"
    }
  ],
  "learn_more": [
    {
      "label": "DEMO.md — the variants",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/DEMO.md"
    },
    {
      "label": "HANDOFF.md — real, simulated, deferred",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/HANDOFF.md"
    }
  ],
  "glossary_terms": [
    "exercised — run end to end with a capture",
    "simulated — the path is real, the counterpart is fake",
    "deferred — needs a human, cannot be produced here"
  ]
});
