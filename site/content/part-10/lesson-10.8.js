/* 10.8 — What leaves the process, and what does not
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "10.8",
  "part": 10,
  "part_title": "Providers and LLM APIs",
  "title": "What leaves the process, and what does not",
  "order": 1008,
  "duration_min": 25,
  "concept_md": "### The prompt is the boundary\n\nA live review sends the diff's added lines to a model. That is the one moment data leaves the machine, and it is worth knowing exactly what goes.\n\n### What is sent\n\nThe added lines with their file paths and line numbers, and the instructions that ask for the five-field shape. Not the repository, not the history, not the `.env`, not the keys.\n\n### What is not\n\nAnything not in the diff. A rule engine sees only added lines, and the prompt is built from the same bundle, so a live review cannot leak a file the diff did not touch.\n\n### Why the boundary is documented rather than assumed\n\nBecause \"we only send the diff\" is the kind of claim that quietly stops being true. Writing it down, and keeping the prompt builder reading the same bundle the rules read, is what makes it checkable — and it is what a reader should verify before pointing this at a private repository.\n\n### What a reader can check\n\nThe prompt is built from the same `DiffBundle` the rules read, so the two cannot disagree about scope. Reading `build_prompt` and the rule loop side by side is the verification: if both take the bundle, nothing outside the diff can reach a model.",
  "code_examples": [
    {
      "id": "10.8-ex-0",
      "lang": "console",
      "caption": "The bundle a prompt is built from holds only the diff",
      "code": "python - <<'PY'\nimport pathlib\nfrom app.parser import parse_diff_file\n\nbundle = parse_diff_file(pathlib.Path(\"samples/sample.diff\"))\nprint(\"files:\", [f.path for f in bundle.files])\nprint(\"added lines:\", sum(len(f.added_spans) for f in bundle.files))\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "the browser runner does not embed the provider modules; this command runs from a checkout instead.",
      "expected_output": "files: ['app/db.py', 'app/report.py']\nadded lines: 3"
    }
  ],
  "quiz": [
    {
      "q": "What leaves the process on a live review?",
      "options": [
        "The added lines and their paths",
        "The whole repository tree",
        "The changed files in full",
        "The diff and the environment"
      ],
      "answer": 1,
      "why": "The prompt is built from the same bundle the rules read, so nothing outside the diff goes out."
    },
    {
      "q": "Why is the boundary written down?",
      "options": [
        "The tests need a description",
        "The vendor requires a written statement",
        "A quiet assumption stops being true",
        "The prompt must be versioned"
      ],
      "answer": 2,
      "why": "Keeping the claim visible and the builder reading the same bundle is what makes it checkable later."
    },
    {
      "q": "What does a rule engine see?",
      "options": [
        "The diff and the repository",
        "The whole file it sits in",
        "The file and its history",
        "Only the added lines"
      ],
      "answer": 3,
      "why": "The same restriction applies to the prompt, because both read one bundle."
    }
  ],
  "try_it": {
    "prompt": "Print the paths the sample diff touches.",
    "starter": "",
    "solution": "```console\n$ python -c \"import pathlib; from app.parser import parse_diff_file; print([f.path for f in parse_diff_file(pathlib.Path('samples/sample.diff')).files])\"\n```",
    "explanation": "Two paths, which is the whole of what a live review would send for that sample."
  },
  "exercise": {
    "prompt": "How many added lines would the sample diff send, and which function counts them?",
    "hint": "The bundle carries spans per file.",
    "solution": "```console\n$ python -c \"import pathlib; from app.parser import parse_diff_file; b=parse_diff_file(pathlib.Path('samples/sample.diff')); print(sum(len(f.added_spans) for f in b.files))\"\n```",
    "explanation": "The count is small, which is the point: a review sends the change, not the codebase."
  },
  "common_mistakes": [
    "Assuming a live review sends the file rather than the diff.",
    "Building the prompt from something other than the bundle the rules read.",
    "Treating the boundary as obvious instead of writing it down."
  ],
  "project_links": [
    {
      "label": "The bundle a prompt is built from",
      "path": "app/parser.py",
      "lines": "206-245"
    },
    {
      "label": "Where the provider is called",
      "path": "app/engine.py",
      "lines": "320-387"
    }
  ],
  "learn_more": [
    {
      "label": "app/engine.py — the entry point",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/engine.py"
    },
    {
      "label": "app/parser.py — the bundle",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/app/parser.py"
    }
  ],
  "glossary_terms": [
    "prompt — the text sent to a model",
    "boundary — the point where data leaves the process",
    "bundle — the parsed diff both rules and prompts read"
  ]
});
