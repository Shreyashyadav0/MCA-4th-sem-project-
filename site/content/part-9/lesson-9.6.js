/* 9.6 — Pinned dependencies: direct pins and a lock
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "9.6",
  "part": 9,
  "part_title": "Configuration and offline-first",
  "title": "Pinned dependencies: direct pins and a lock",
  "order": 906,
  "duration_min": 25,
  "concept_md": "### Two files, two jobs\n\n`requirements.txt` lists the eight direct dependencies, each pinned exactly with `==`. `requirements.lock` adds the transitive and development pins — thirty-seven in all — and is what CI installs. There are no ranges in either file.\n\n### Why both\n\nTwo pins in two files answer two questions: the direct list says what the project asks for, and the lock says what was installed. Installing without the lock means today's install can differ from yesterday's, which is how a suite that was green on Monday fails on Tuesday with no code change.\n\n### The lock is generated, never edited\n\nEditing a version by hand in the lock makes the file a lie about what was tested. The regeneration procedure lives in `docs/REPRODUCIBILITY.md`, and the rule is simple: change the pin in requirements.txt, regenerate the lock, commit both.\n\n### What the pin count means\n\nThirty-seven pins at this commit. The count is a fact about the lock, not a target — and the guide now computes it from the file rather than carrying a typed number, because a typed one had already drifted.\n\n### Why the lock is the longer file\n\nThe lock is longer because it is transitive: the eight direct pins pull in twenty-nine more. That is why CI installs the lock and a reader reads the list.\n\n### The cost\n\nA lock has to be regenerated when a dependency needs a security bump, and that regeneration can surface an incompatibility at an inconvenient time. That is the trade: an inconvenient moment now instead of an unexplained failure later.",
  "code_examples": [
    {
      "id": "9.6-ex-0",
      "lang": "python",
      "caption": "Count the pins, and show the first",
      "code": "python - <<'PY'\nimport pathlib\n\nlock = pathlib.Path(\"requirements.lock\").read_text().splitlines()\npins = [l for l in lock if \"==\" in l and not l.strip().startswith(\"#\")]\nprint(\"pins:\", len(pins))\nprint(\"first pin:\", pins[0])\nPY",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "the browser runner has Python but no shell, so this command cannot run there; it needs a checkout on disk.",
      "expected_output": "pins: 37\nfirst pin: annotated-doc==0.0.6"
    }
  ],
  "quiz": [
    {
      "q": "What does the lock file record?",
      "options": [
        "The project's direct needs",
        "What would be compatible with the code",
        "Exactly what was tested",
        "The Python version only"
      ],
      "answer": 2,
      "why": "A pin says what ran; the direct list says what the project asks for, and the two answer different questions."
    },
    {
      "q": "How is a pin in the lock changed?",
      "options": [
        "Add a second pin beside the first one",
        "Edit the version by hand",
        "Delete the line and reinstall",
        "Regenerate it from the direct pins"
      ],
      "answer": 3,
      "why": "A hand-edited lock lies about what was tested, so the direct pin changes first and the lock is regenerated."
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
    "Editing a version in the lock instead of the direct pin.",
    "Installing without the lock in CI, so the run is not reproducible.",
    "Treating the pin count as a quality target."
  ],
  "project_links": [
    {
      "label": "The direct pins a human reads",
      "path": "requirements.txt",
      "lines": "1-8"
    },
    {
      "label": "The whole lock, comments and pins",
      "path": "requirements.lock",
      "lines": "1-40"
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
    "direct dependency — a package the project names itself",
    "lock file — the record of what was installed"
  ]
});
