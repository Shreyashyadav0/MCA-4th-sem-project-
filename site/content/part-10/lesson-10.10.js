/* 10.10 — The benchmark that has not been run
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "10.10",
  "part": 10,
  "part_title": "Providers and LLM APIs",
  "title": "The benchmark that has not been run",
  "order": 1010,
  "duration_min": 30,
  "concept_md": "### What exists\n\nA harness under `benchmarks/` that can compare findings against a labelled set, and a matcher that pairs a predicted finding with an expected one. `benchmarks/golden/` ships two format examples — `example_01` and `example_02` — which exist to show the file shape and are excluded from every metric; the manifest's `evaluation_samples` is empty. What does not exist is the labelled set.\n\n### What that means\n\n**There is no precision, recall or F1 figure for this tool, and no percentage of any kind.** Not a low one, not an estimate — none. The number cannot be computed without labels, and the labels have not been written.\n\n### Why not approximate it\n\nA figure produced from an unlabelled sample would be a guess wearing a number's clothes. It would be quoted, then cited, then believed, and nobody downstream would know it came from a harness with an empty input.\n\n### What would change it\n\nA labelled set: a sample of diffs, each with the findings a careful reader agrees are there. Then the harness produces real numbers, and the honest sentence becomes a measured one. Until then, the honest sentence is the one above — and any document that states a percentage is stating something this repository cannot support.\n\n### The habit worth keeping\n\nWhen a measurement is missing, write that it is missing. A gap that is named is a task; a gap that is filled with an estimate is a defect that will outlive everyone who knew.",
  "code_examples": [
    {
      "id": "10.10-ex-0",
      "lang": "console",
      "caption": "The harness is real; the labelled set is not",
      "code": "python - <<'PY'\nimport json, pathlib\n\nb = pathlib.Path(\"benchmarks\")\nprint(\"harness files:\", sorted(p.name for p in b.glob(\"*.py\")))\nmanifest = json.loads((b / \"golden\" / \"manifest.json\").read_text())\nprint(\"evaluation samples:\", manifest.get(\"evaluation_samples\"))\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "the browser runner does not embed the provider modules; this command runs from a checkout instead.",
      "expected_output": "harness files: ['__init__.py', 'collect_candidates.py', 'eval.py', 'label_helper.py', 'labelling.py', 'loader.py', 'matching.py', 'metrics.py', 'report.py', 'runner.py']\nevaluation samples: []"
    }
  ],
  "quiz": [
    {
      "q": "Which figure does this tool have for accuracy?",
      "options": [
        "An F1 score from the sample",
        "A recall figure from the harness",
        "None, because no labels exist",
        "A precision estimate from tests"
      ],
      "answer": 2,
      "why": "The harness needs labels to produce a number, and the labelled set has not been written."
    },
    {
      "q": "Why not estimate a figure from a sample?",
      "options": [
        "The matcher rejects unlabelled rows",
        "The harness cannot run without labels",
        "The sample is too small to use",
        "A guess would be cited as measured"
      ],
      "answer": 3,
      "why": "A number invented once gets quoted and believed, long after anyone remembers where it came from."
    },
    {
      "q": "What turns the honest sentence into a measured one?",
      "options": [
        "A labelled set of diffs",
        "A larger sample of diffs",
        "A faster matcher implementation",
        "A second provider to compare"
      ],
      "answer": 0,
      "why": "Labels are the missing input; more unlabelled data changes nothing about what can be computed."
    }
  ],
  "try_it": {
    "prompt": "List the harness files and show there is no labelled data.",
    "starter": "",
    "solution": "```console\n$ python -c \"import json,pathlib; print(json.loads(pathlib.Path('benchmarks/golden/manifest.json').read_text())['evaluation_samples'])\"\n[]\n```",
    "explanation": "The manifest's sample list is empty: the two example folders are format demonstrations, not labels."
  },
  "exercise": {
    "prompt": "Which module pairs a predicted finding with an expected one, and what does it need to run?",
    "hint": "The matcher is under benchmarks/.",
    "solution": "```console\n$ grep -n 'def ' benchmarks/matching.py | head -5\n```\n\nIt needs an expected finding for each predicted one — that is the labelled set that does not exist.",
    "explanation": "The pairing logic is written and tested; the input it pairs against is what is missing."
  },
  "common_mistakes": [
    "Quoting a precision or recall figure this repository cannot produce.",
    "Reading a green benchmark test as a benchmark result.",
    "Filling the gap with an estimate instead of naming it."
  ],
  "project_links": [
    {
      "label": "The matcher that needs labels",
      "path": "benchmarks/matching.py",
      "lines": "473-587"
    }
  ],
  "learn_more": [
    {
      "label": "benchmarks/ — the harness",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/benchmarks/matching.py"
    },
    {
      "label": "HANDOFF.md — what is deferred",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/HANDOFF.md"
    }
  ],
  "glossary_terms": [
    "labelled set — diffs with agreed findings, the missing input",
    "precision — of the findings reported, how many were right",
    "harness — the code that would compute a figure if it had input"
  ]
});
