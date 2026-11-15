/* 1.11 — subprocess, enough to read the CLI
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "1.11",
  "part": 1,
  "part_title": "Python fundamentals",
  "title": "subprocess, enough to read the CLI",
  "order": 111,
  "duration_min": 15,
  "concept_md": "### run, not Popen\n\n```python\nresult = subprocess.run([\"python\", \"--version\"], capture_output=True, text=True)\nprint(result.returncode, result.stdout.strip())\n```\n\n`subprocess.run` waits for the process, collects its output when you ask, and returns an object with `returncode`, `stdout` and `stderr`. `Popen` is for the cases `run` cannot express: streaming output while it happens, feeding stdin, or several processes at once.\n\nPass the command as a **list**, never a string with `shell=True`, unless you actually need a shell. A list cannot be word-split by surprise, and a filename with a space in it does not become two arguments.\n\n### The four arguments that matter\n\n- `capture_output=True` — collect stdout and stderr instead of letting them hit the terminal.\n- `text=True` — decode to `str` rather than bytes.\n- `check=True` — raise `CalledProcessError` on a non-zero exit, instead of returning quietly.\n- `timeout=` — kill it after N seconds. A test suite that hangs forever is worse than one that fails.\n\n### Why this repository barely uses it\n\nThe CLI reads a `.diff` file directly rather than shelling out to `git diff`. That is a deliberate choice with a concrete payoff: a CI runner with no repository checkout and no git binary can still review a diff, and the review does not depend on a subprocess's exit code.\n\nThe places it *does* shell out are the scripts, not the library: `scripts/learning_progress.py` runs `pytest` per learning track through `subprocess.run` and reads the exit code. `scripts/verify_offline.py` runs pytest in-process, with no subprocess at all.",
  "code_examples": [
    {
      "id": "1.11-ex-0",
      "lang": "console",
      "caption": "The same call the lesson shows, run for real",
      "code": "python -c \"import subprocess; r = subprocess.run(['python', '--version'], capture_output=True, text=True); print(r.returncode); print(r.stdout.strip())\"",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "the browser's Python has no process to spawn: Pyodide runs inside the page, with no subprocess module and no OS process table.",
      "expected_output": "0\nPython 3.12.13"
    }
  ],
  "quiz": [
    {
      "q": "Why pass the command as a list rather than a string?",
      "options": [
        "Because a shell re-splits a string",
        "Because a list is shorter to write than a carefully quoted string",
        "Because subprocess refuses to run a string on Linux and macOS",
        "Because a list lets you pass the same argument more than once"
      ],
      "answer": 0,
      "why": "With a string and a shell, quoting rules decide your arguments; a list removes the shell from the question entirely."
    },
    {
      "q": "What does `check=True` do?",
      "options": [
        "It prints the command's output to the terminal as it runs",
        "It retries the command once if the first attempt fails",
        "Raises CalledProcessError when the exit code is non-zero",
        "It captures stderr only and discards stdout entirely"
      ],
      "answer": 2,
      "why": "Without it a failing command returns quietly with a non-zero returncode, which is easy to ignore and hard to debug later."
    },
    {
      "q": "Why does the CLI read a .diff file instead of running `git diff`?",
      "options": [
        "Because piping a diff through a shell would lose its exit code",
        "Because diffs cannot be piped between two processes",
        "So the review never depends on a git binary or a checkout",
        "So it works in a CI runner with no repository and no git binary"
      ],
      "answer": 3,
      "why": "A diff on disk is the input; requiring a checkout and a git binary would make the tool useless in exactly the environment it targets."
    }
  ],
  "try_it": {
    "prompt": "Run `git status` through subprocess and print only its first line. Then run a command that does not exist and print the exception type.",
    "starter": "import subprocess\n\nresult = subprocess.run([\"git\", \"status\"], capture_output=True, text=True)\nlines = result.stdout.splitlines()\nprint(lines[0] if lines else \"not a git repository (exit %d)\" % result.returncode)\n",
    "solution": "import subprocess\n\nresult = subprocess.run([\"git\", \"status\"], capture_output=True, text=True)\nlines = result.stdout.splitlines()\nprint(lines[0] if lines else \"not a git repository (exit %d)\" % result.returncode)\n\ntry:\n    subprocess.run([\"definitely-not-a-command\"], check=True)\nexcept FileNotFoundError as error:\n    print(\"FileNotFoundError:\", error)\n",
    "explanation": "Inside a repository the first line is the branch line; outside one, git exits 128 with nothing on stdout and the fallback prints. The second block raises FileNotFoundError, because a missing executable fails before any exit code exists."
  },
  "exercise": {
    "prompt": "Run `grep -rn \"subprocess\" app/ scripts/` and report what you find: which module actually starts a process, and what the other hits are.",
    "hint": "Most of the hits are pattern strings and suggested-fix text inside rule definitions, not calls.",
    "solution": "```text\nThe only real caller is `scripts/learning_progress.py`, which imports subprocess and runs `pytest` once per learning track, reading each exit code. The hits in `app/rules.py` are pattern strings inside rules that detect subprocess use in *other people's* code. `app/` itself never starts a process, which is what makes the CLI runnable in a sandbox with no git.\n```",
    "explanation": "Reading the hits rather than counting them is the skill: a rule that detects `subprocess.run` is not a call to `subprocess.run`."
  },
  "common_mistakes": [
    "`shell=True` with a string, which hands your arguments to a shell and its quoting rules.",
    "Forgetting `text=True`, then comparing bytes to a string and getting a puzzling False.",
    "Assuming `check=True` covers a missing executable — that raises FileNotFoundError before any return code exists."
  ],
  "project_links": [
    {
      "label": "read_source — the input path this CLI actually takes",
      "path": "app/cli.py",
      "lines": "142-166"
    },
    {
      "label": "reviewer.py — the entry point that calls it",
      "path": "reviewer.py",
      "lines": "1-13"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/track-7-surfaces.md — the CLI surface",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/track-7-surfaces.md"
    }
  ],
  "glossary_terms": [
    "subprocess.run — run a command, wait, and return its exit code and output",
    "returncode — 0 for success; anything else is the failure the program chose",
    "capture_output — collect stdout and stderr instead of printing them",
    "shell=True — route the command through a shell; avoid it unless you need shell syntax"
  ]
});
