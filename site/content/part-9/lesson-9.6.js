/* 9.6 — Pinned dependencies: ranges versus a lock
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "9.6",
  "part": 9,
  "part_title": "Configuration and offline-first",
  "title": "Pinned dependencies: ranges versus a lock",
  "order": 906,
  "duration_min": 25,
  "concept_md": "### Two files, two jobs\n\n`requirements.txt` carries ranges — `fastapi>=0.110,<1` — and is what a human reads to know what the project needs. `requirements.lock` carries exact pins, one per line with `==`, and is what CI installs.\n\n### Why both\n\nA range says what is compatible; a pin says what was tested. Installing from ranges means today's install can differ from yesterday's, which is how a suite that passed on Monday fails on Tuesday with no code change.\n\n### The lock is generated, never edited\n\nEditing a version by hand in the lock makes the file a lie about what was tested. The regeneration procedure lives in `docs/REPRODUCIBILITY.md`, and the rule is simple: change the range, regenerate the lock, commit both.\n\n### What the pin count means\n\nThirty-seven pins at this commit. The count is a fact about the lock, not a target — and the guide now computes it from the file rather than carrying a typed number, because a typed one had already drifted.\n\n### The cost\n\nA lock has to be regenerated when a dependency needs a security bump, and that regeneration can surface an incompatibility at an inconvenient time. That is the trade: an inconvenient moment now instead of an unexplained failure later.",
  "code_examples": [
    {
      "id": "9.6-ex-0",
      "lang": "console",
      "caption": "Count the pins, and show the first range",
      "code": "import pathlib\n\nlock = pathlib.Path(\"requirements.lock\").read_text().splitlines()\npins = [l for l in lock if \"==\" in l and not l.strip().startswith(\"#\")]\nprint(\"pins:\", len(pins))\nprint(\"first range:\", pathlib.Path(\"requirements.txt\").read_text().splitlines()[0])",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "the browser runner has Python but no shell, so this command cannot run there; it needs a checkout on disk.",
      "expected_output": "/bin/sh: 1: import: not found\n/bin/sh: 3: Syntax error: \"(\" unexpected"
    }
  ],
  "quiz": [
    {
      "q": "What does the lock file record?",
      "options": [
        "Exactly what was tested",
        "What would be compatible",
        "The project's direct needs",
        "The Python version only"
      ],
      "answer": 0,
      "why": "A pin says what ran; a range says what is allowed, and the two answer different questions."
    },
    {
      "q": "How is a version in the lock changed?",
      "options": [
        "Regenerate it from the range",
        "Edit the version by hand",
        "Delete the line and reinstall",
        "Add a second pin beside it"
      ],
      "answer": 0,
      "why": "A hand-edited lock lies about what was tested, so the range changes first and the lock is regenerated."
    },
    {
      "q": "What does the pin count describe?",
      "options": [
        "The lock at this commit",
        "A target the project aims for",
        "The number of direct needs",
        "The Python standard library"
      ],
      "answer": 0,
      "why": "It is a fact about the file, which is why the guide computes it instead of carrying a typed number."
    }
  ],
  "try_it": {
    "prompt": "Print how many pins the lock holds and how many direct requirements exist.",
    "starter": "",
    "solution": "```console\n$ grep -c '==' requirements.lock\n$ grep -vc '^#' requirements.txt\n```",
    "explanation": "The lock is larger than the requirement list, because it includes every transitive package."
  },
  "exercise": {
    "prompt": "How many pins are in the lock, and how many lines does requirements.txt hold? Compare them.",
    "hint": "Count the `==` lines in the lock.",
    "solution": "```console\n$ grep -c '==' requirements.lock\n37\n$ wc -l < requirements.txt\n```",
    "explanation": "The lock is far longer: it pins transitive packages the requirement file never names."
  },
  "common_mistakes": [
    "Editing a version in the lock instead of the range.",
    "Installing from ranges in CI, so the run is not reproducible.",
    "Treating the pin count as a quality target."
  ],
  "project_links": [
    {
      "label": "The ranges a human reads",
      "path": "requirements.txt",
      "lines": "1-6"
    },
    {
      "label": "The pins CI installs",
      "path": "requirements.lock",
      "lines": "1-8"
    }
  ],
  "learn_more": [
    {
      "label": "requirements.lock — the pins",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/requirements.lock"
    },
    {
      "label": "docs/REPRODUCIBILITY.md",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/REPRODUCIBILITY.md"
    }
  ],
  "glossary_terms": [
    "pin — an exact version recorded in the lock",
    "range — a compatible span a human reads",
    "lock file — the record of what was installed"
  ]
});
