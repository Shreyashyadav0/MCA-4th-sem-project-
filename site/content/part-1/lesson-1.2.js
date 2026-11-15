/* 1.2 — Lists, dicts, sets and comprehensions
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "1.2",
  "part": 1,
  "part_title": "Python fundamentals",
  "title": "Lists, dicts, sets and comprehensions",
  "order": 102,
  "duration_min": 20,
  "concept_md": "### The four containers, and when each wins\n\nA **list** keeps order and allows duplicates — findings in the order they will be printed. A **dict** maps a key to a value and remembers insertion order — counts per severity, or one finding by id. A **set** answers \"have I seen this?\" in constant time and has no order — the distinct files a review touched. A **tuple** is an immutable, hashable sequence — which is why it can be a set member or a dict key.\n\nThe rule of thumb: if you need to look things up, use a dict or a set; if you need to keep them in order, use a list.\n\n### Comprehensions are a for-loop with the bookkeeping removed\n\n```python\ncounts = {severity: len(items) for severity, items in by_severity.items()}\nfiles = {finding.file for finding in findings}\n```\n\nThe first is a dict comprehension, the second a set comprehension. Both do in one line what three lines of `append` would do, and both are still readable. The moment a comprehension needs two `if`s and a nested loop, write the loop — this repository does, in `app/rules.py`, where clarity beats compactness. The lazy cousin of the comprehension, the generator expression, is lesson 1.9.\n\n### Grouping without a library\n\n`setdefault` is the oldest grouping idiom in Python and still the clearest:\n\n```python\nby_severity.setdefault(finding.severity.value, []).append(finding)\n```\n\n`collections.defaultdict(list)` is the same thing with a nicer type. `Counter` is for counting, not grouping.\n\n### What this repository does\n\n`severity_counts` in `app/models.py` builds a dict keyed by the four severity names and returns it, so the verdict can be computed from counts rather than by scanning findings again. `sort_findings` returns a new list rather than mutating the one it was given — a small discipline that makes every caller safe.",
  "code_examples": [
    {
      "id": "1.2-ex-0",
      "lang": "python",
      "caption": "Group real Finding objects with a dict comprehension and a set",
      "code": "from app.models import Finding\n\nfindings = [\n    Finding(file=\"app/db.py\", line=\"3\", severity=\"CRITICAL\", issue=\"Token literal\", suggested_fix=\"Read it from the environment.\"),\n    Finding(file=\"app/db.py\", line=\"3\", severity=\"CRITICAL\", issue=\"SQL interpolation\", suggested_fix=\"Pass parameters.\"),\n    Finding(file=\"app/report.py\", line=\"1\", severity=\"MEDIUM\", issue=\"Missing annotations\", suggested_fix=\"Annotate it.\"),\n]\n\nby_severity = {}\nfor finding in findings:\n    by_severity.setdefault(finding.severity.value, []).append(finding)\n\ncounts = {severity: len(items) for severity, items in by_severity.items()}\nprint(counts)\n\nfiles = {finding.file for finding in findings}\nprint(len(files), \"distinct files:\", sorted(files))\n",
      "runnable": true,
      "run_tier": "browser",
      "packages": [
        "pydantic"
      ],
      "files": [
        "app/__init__.py",
        "app/models.py"
      ],
      "expected_output": "{'CRITICAL': 2, 'MEDIUM': 1}\n2 distinct files: ['app/db.py', 'app/report.py']"
    }
  ],
  "quiz": [
    {
      "q": "You need the distinct file names a review touched. Which container?",
      "options": [
        "A list",
        "A set",
        "A tuple",
        "A dict of lists"
      ],
      "answer": 1,
      "why": "A set removes duplicates as you insert and answers membership in constant time, which is exactly the question 'which files'."
    },
    {
      "q": "Why does `severity_counts` in app/models.py return a dict?",
      "options": [
        "So the verdict reads counts instead of rescanning the findings list",
        "Because a dict is faster to build than a list of findings at every call site",
        "Because JSON cannot encode a list of counts without keys",
        "Because the findings were already stored in a dict shape"
      ],
      "answer": 0,
      "why": "Counts are computed once and the verdict reads them; rescanning the list for each threshold would be the same work twice."
    },
    {
      "q": "What does `setdefault(key, []).append(x)` do?",
      "options": [
        "Replaces the key's value with x",
        "Raises KeyError if the key is missing from the mapping",
        "Creates an empty list on first use, then appends to it",
        "Sorts the list before appending"
      ],
      "answer": 2,
      "why": "setdefault returns the existing value or inserts the default, so the append always lands on a list — grouping without an if."
    }
  ],
  "try_it": {
    "prompt": "Add one more finding to the list and count them per **file** instead of per severity. Use the same `setdefault` shape, then rewrite it as a dict comprehension.",
    "starter": "from app.models import Finding\n\nfindings = [\n    Finding(file=\"app/db.py\", line=\"3\", severity=\"CRITICAL\", issue=\"a\", suggested_fix=\"b\"),\n    Finding(file=\"app/report.py\", line=\"1\", severity=\"MEDIUM\", issue=\"c\", suggested_fix=\"d\"),\n]\n\nper_file = {}\nfor finding in findings:\n    per_file.setdefault(finding.file, 0)\n    per_file[finding.file] += 1\nprint(per_file)\n",
    "solution": "from app.models import Finding\n\nfindings = [\n    Finding(file=\"app/db.py\", line=\"3\", severity=\"CRITICAL\", issue=\"a\", suggested_fix=\"b\"),\n    Finding(file=\"app/db.py\", line=\"7\", severity=\"CRITICAL\", issue=\"c\", suggested_fix=\"d\"),\n    Finding(file=\"app/report.py\", line=\"1\", severity=\"MEDIUM\", issue=\"e\", suggested_fix=\"f\"),\n]\n\nper_file = {}\nfor finding in findings:\n    per_file.setdefault(finding.file, 0)\n    per_file[finding.file] += 1\nprint(per_file)\n\nnames = {finding.file for finding in findings}\ncounts = {name: sum(1 for f in findings if f.file == name) for name in names}\nprint(counts)\n",
    "explanation": "Both print the same counts — `{'app/db.py': 2, 'app/report.py': 1}` — though not necessarily in the same order: the comprehension is driven by a set, so key order is unspecified. The second form is the dict comprehension the prompt asked for; `Counter` from `collections` is the same thing with a name."
  },
  "exercise": {
    "prompt": "Deduplicate the findings by `(file, line)` — two rules can fire on the same line, and the CLI reports both — and print how many distinct positions survive. Use a set of tuples.",
    "hint": "Build the tuple from `finding.file` and `finding.line`; `len(set_of_tuples)` is the answer.",
    "solution": "from app.models import Finding\n\nfindings = [\n    Finding(file=\"app/db.py\", line=\"3\", severity=\"CRITICAL\", issue=\"Token literal\", suggested_fix=\"Read it from the environment.\"),\n    Finding(file=\"app/db.py\", line=\"3\", severity=\"CRITICAL\", issue=\"SQL interpolation\", suggested_fix=\"Pass parameters.\"),\n    Finding(file=\"app/report.py\", line=\"1\", severity=\"MEDIUM\", issue=\"Missing annotations\", suggested_fix=\"Annotate it.\"),\n]\n\nseen = {(finding.file, finding.line) for finding in findings}\nprint(len(seen), \"distinct positions\", sorted(seen))\n",
    "explanation": "It prints `2 distinct positions [('app/db.py', '3'), ('app/report.py', '1')]`, because the two CRITICAL findings share app/db.py line 3 — which is what the CLI shows too. A tuple works as a set member because it is immutable and hashable; a list would raise TypeError."
  },
  "common_mistakes": [
    "Using a list where membership is the question. `if finding in findings` is linear; a set is constant time, and the difference shows at 63 rules over a large diff.",
    "Mutating a list while iterating it. `sort_findings` returns a new list for exactly this reason.",
    "Reaching for a nested comprehension when a `for` loop with `setdefault` reads better. This repository writes the loop."
  ],
  "project_links": [
    {
      "label": "Severity and Finding: the two types these exercises build on",
      "path": "app/models.py",
      "lines": "46-105"
    },
    {
      "label": "severity_counts — the count helper this lesson mirrors",
      "path": "app/models.py",
      "lines": "125-130"
    },
    {
      "label": "The rule registry a comprehension would flatten",
      "path": "app/rules.py",
      "lines": "112-124"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-1-models.md — the models track",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-1-models.md"
    }
  ],
  "glossary_terms": [
    "dict comprehension — `{k: v for ...}`, building a mapping in one expression",
    "set comprehension — `{x for ...}`, deduplicating as it builds",
    "hashable — the object has a stable hash and never compares unequal to itself, so a set can find it; lists and dicts are not hashable",
    "setdefault — insert-if-missing that returns the value, the grouping idiom"
  ]
});
