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
  "concept_md": "### run, not Popen\n\n```python\nresult = subprocess.run([\"python\", \"--version\"], capture_output=True, text=True)\nprint(result.returncode, result.stdout.strip())\n```\n\n`subprocess.run` waits for the process, collects its output when you ask, and returns an object with `returncode`, `stdout` and `stderr`. `Popen` is for the cases `run` cannot express: streaming output while it happens, feeding stdin, or several processes at once.\n\nPass the command as a **list**, never a string with `shell=True`, unless you actually need a shell. A list cannot be word-split by surprise, and a filename with a space in it does not become two arguments.\n\n### The four arguments that matter\n\n- `capture_output=True` — collect stdout and stderr instead of letting them hit the terminal.\n- `text=True` — decode to `str` rather than bytes.\n- `check=True` — raise `CalledProcessError` on a non-zero exit, instead of returning quietly.\n- `timeout=` — kill it after N seconds. A test suite that hangs forever is worse than one that fails.\n\n### Why this repository barely uses it\n\nThe CLI reads a `.diff` file directly rather than shelling out to `git diff`. That is a deliberate choice with a concrete payoff: a CI runner with no repository checkout and no git binary can still review a diff, and the review does not depend on a subprocess's exit code.\n\nThe places it *does* shell out are the scripts — `scripts/verify_offline.py`, the Makefile targets — not the library.",
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
        "It is shorter",
        "A list cannot be re-split by a shell, so a filename with a space stays one argument",
        "Strings are not allowed",
        "Lists are faster"
      ],
      "answer": 1,
      "why": "With a string and a shell, quoting rules decide your arguments; a list removes the shell from the question entirely."
    },
    {
      "q": "What does `check=True` do?",
      "options": [
        "Verifies the command exists",
        "Raises CalledProcessError when the exit code is non-zero",
        "Prints the output",
        "Retries once"
      ],
      "answer": 1,
      "why": "Without it a failing command returns quietly with a non-zero returncode, which is easy to ignore and hard to debug later."
    },
    {
      "q": "Why does the CLI read a .diff file instead of running `git diff`?",
      "options": [
        "Because git is slow",
        "So it works in a CI runner with no repository and no git binary",
        "Because subprocess is deprecated",
        "Because diffs cannot be piped"
      ],
      "answer": 1,
      "why": "A diff on disk is the input; requiring a checkout and a git binary would make the tool useless in exactly the environment it targets."
    }
  ],
  "try_it": {
    "prompt": "Run `git status` through subprocess and print only its first line. Then run a command that does not exist and print the exception type.",
    "starter": "import subprocess\n\nresult = subprocess.run([\"git\", \"status\"], capture_output=True, text=True)\nprint(result.stdout.splitlines()[:1])\n",
    "solution": "import subprocess\n\nresult = subprocess.run([\"git\", \"status\"], capture_output=True, text=True)\nprint(result.stdout.splitlines()[:1])\n\ntry:\n    subprocess.run([\"definitely-not-a-command\"], check=True)\nexcept FileNotFoundError as error:\n    print(\"FileNotFoundError:\", error)\n",
    "explanation": "The first print shows the branch line; the second raises FileNotFoundError, because a missing executable fails before any exit code exists. That is why `check=True` does not cover everything — a missing binary is a different failure."
  },
  "exercise": {
    "prompt": "Explain why this CLI does not shell out to git, and what that buys in a CI runner with no repository. Cite the module that reads the input.",
    "hint": "Look at what `read_source` in app/cli.py accepts.",
    "solution": "`app/cli.py` reads its input with `read_source(path)`: a file path, checked for existence, size and UTF-8. It never runs git, so the tool works on a bare `.diff` produced anywhere — a GitHub export, a patch in an email, a CI job that has the diff but no checkout. It also removes a subprocess from the review path, so the exit code means 'the review ran', not 'git succeeded'.",
    "explanation": "The input is a diff, not a repository. Taking the smaller input is what makes the offline claim true."
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
      "lines": "142-168"
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
