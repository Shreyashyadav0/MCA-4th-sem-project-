# Learning path: rebuild the AI Code Reviewer from memory

This curriculum exists for one purpose: to take a working knowledge of this repository and turn
it into the ability to reproduce the repository. You will not read the codebase once and nod at it.
You will take it apart module by module, in dependency order, and after each module you will close
the file and write it again from memory until the test suite agrees with you. Seven tracks, roughly
90 hours of work, spread over sixteen weeks — three to four months at about five and a half hours a
week. The reward at the end is not familiarity with someone else's code. It is the ability to open
an empty directory and rebuild a provider-agnostic review pipeline, with its fallback chain, its
diff anchoring, its 63-rule engine and its GitHub posting path, from first principles and from
memory, and to prove each piece by running a test rather than by feeling confident about it.

Nothing here asks you to modify `app/`. The code is the reference implementation and stays as it is.
Your output is `rebuild/`, and your evidence is the test suite.

---

## Module dependency graph

Derived by parsing every `app/*.py` with the `ast` module and keeping only edges that point at
another file in `app/` — 40 edges across 13 files. Line counts are `wc -l`.

```
+-------------------------------+  imports:
| L0   models.py        (179)   |  nothing internal
|      config.py         (92)   |  nothing internal
+---------------+---------------+  (pydantic / pydantic-settings only)
                |
                |  models
+---------------v---------------+
| L1   parser.py        (583)   |  models
+---------------+---------------+  (+ models.AnchorStatus, models.Finding)
                |
                |  models, parser
+---------------v---------------+
| L2   rules.py        (1618)   |  models, parser
+---------------+---------------+  (DiffBundle, Finding, Severity, sort_findings)
                |
                |  models, parser, rules
+---------------v---------------+
| L3   mock_provider.py  (75)   |  models, parser, rules
+---------------+---------------+  (RULES, DiffBundle, Finding)
                |
                |  + config, mock_provider
+---------------v---------------+
| L4   sarvam_provider.py (991) |  models, parser, rules, config, mock_provider
+---------------+---------------+  (offline_diff_findings is the fallback target)
                |
                |  + sarvam_provider
+---------------v---------------+
| L5   openai_compat_          |  models, parser, rules, mock_provider,
|      provider.py      (738)   |  sarvam_provider  (LLMFinding, ProviderOutcome)
+---------------+---------------+  (defines PROVIDER_LOCAL, the shared config object)
                |
                |  + config, openai_compat_provider
+---------------v---------------+
| L6   engine.py        (385)   |  models, parser, rules, config,
+---------------+---------------+  openai_compat_provider
                |
                |  engine
    +-----------+------------+----------------+
    |           |            |                |
    v           v            v                v
 cli.py      main.py     __main__.py    github_client.py
 (549)       (1049)        (8)             (1258)
                                         models, parser, config only —
                                         NO engine edge
```

Edge list, exactly as the AST reports it (source -> targets):

| Module | Imports from `app/` |
| --- | --- |
| `models.py` | — |
| `config.py` | — |
| `parser.py` | models |
| `rules.py` | models, parser |
| `mock_provider.py` | models, parser, rules |
| `sarvam_provider.py` | models, parser, rules, config, mock_provider |
| `openai_compat_provider.py` | models, parser, rules, mock_provider, sarvam_provider |
| `engine.py` | models, parser, rules, config, openai_compat_provider |
| `cli.py` | models, parser, rules, config, engine, mock_provider, sarvam_provider, github_client |
| `main.py` | models, parser, rules, config, engine, mock_provider, github_client |
| `github_client.py` | models, parser, config |
| `__main__.py` | cli |
| `__init__.py` | — |

Three facts in that graph are worth stating explicitly, because a plausible guess gets them wrong:

1. **`rules.py` imports `parser.py`, not just `models.py`.** Every rule walks a `DiffBundle`'s added
   lines, so the rule engine cannot be understood before the diff parser.
2. **`engine.py` never imports `sarvam_provider.py` or `mock_provider.py` directly.** It imports
   `PROVIDER_LOCAL` from `openai_compat_provider` and reaches the rule engine through that module's
   `review_with_fallback(config=None)`. One mock implementation, one WARNING, no duplicate fallback.
3. **`github_client.py` has no `engine` edge.** It is a pure posting surface over anchored findings.
   It could be read right after `parser.py`; it is placed last because its 1,258 lines are breadth,
   not depth, and they only make sense once you have seen what produces a finding.

---

## The seven tracks

Hours are the estimate for *reading plus rebuilding from memory plus making the verification test
pass*, not for reading alone. They track real size and real conceptual density: `rules.py` is the
largest file after the surfaces and still gets fewer hours than `sarvam_provider.py`, because 63
rules of regex and line-shape matching are volume, while a provider adapter with a payload-repair
path and a fallback chain is depth. Difficulty: 1 = one careful read and you can rebuild it;
3 = you need the track document and one pass over the tests; 5 = expect several passes and
deliberate probing at the REPL before your rebuild is faithful.

| # | Module(s) | Lines | Hours | Diff. | You understand this module when... |
| --- | --- | --- | --- | --- | --- |
| 1 | `models.py` | 179 | 5 | 2 | You can predict, without running anything, that `sort_findings` puts two LOW findings on lines 40 and 7 in the order `7, 40`, that `verdict_for` returns `"approve with comments"` for a single MEDIUM, and that `Finding(file="a.py", line="42-40", ...)` raises — then prove all three in one `python -c` call. |
| 2 | `parser.py` | 583 | 11 | 4 | Given a diff whose only added line is 11, you can predict that `anchor_findings` returns `anchored` for a finding on line 11, `file_only` for line 12, and `unanchored` for a file absent from the diff, and prove it by running `parse_diff` + `anchor_findings` once. |
| 3 | `rules.py` | 1618 | 12 | 3 | You can name the rule id that fires on `os.system(cmd)` and on `hashlib.md5(x)`, state whether a bare `# noqa` on that line suppresses everything, and confirm both by calling `review_lines` on a two-line list and reading the `(rule: ...)` suffix in `issue`. |
| 4 | `mock_provider.py` + `config.py` | 75 + 92 = 167 | 4 | 2 | You can quote `ENGINE_NOTE` verbatim, including the number 63, and predict that `offline_diff_findings` on a bundle with no added lines returns `[]` with no exception — then prove both in one command. |
| 5 | `sarvam_provider.py` + `openai_compat_provider.py` | 991 + 738 = 1729 | 24 | 5 | You can list the four short-circuits in `review_with_fallback` in order (`force_offline`, no key, no SDK, `REVIEW_MODE=mock`) plus the fifth path (any live failure), predict `mode`/`provider` for each, and demonstrate the degradation with `Settings()` and no key in one call that touches no network. |
| 6 | `engine.py` | 385 | 14 | 4 | You can predict `select_provider`'s `provider` for all four `requested` values across the four credential states (neither set, key only, base URL only, both set), including that `REVIEW_MODE=mock` does *not* override an explicit `requested`, and prove the matrix with a 16-case loop in one command. |
| 7 | `cli.py` + `main.py` + `github_client.py` | 549 + 1049 + 1258 = 2856 | 20 | 3 | You can predict four exit codes before running the CLI — no path given is 2, an unreadable file is 1, a mock review with findings is 0, `--post-to-pr` on a plain source file is 1 — and prove all four with four shell invocations. |

Total: 90 hours. `app/` is 7,528 lines including `__init__.py` and `__main__.py`.

If a track's estimate feels wrong for you, the honest calibration is line count and how many
distinct failure modes the module handles — not how long the file felt while reading it.

---

## How to study a track

One track at a time, in order, and the same five steps every time.

1. **Read the file.** Top to bottom, once, without the track document. Docstrings in this repository
   are unusually complete; use them, and note every function whose behaviour you could not have
   predicted from its name alone.
2. **Read the track document.** `docs/learning/track-N-*.md` walks the same file in the same order
   and names the decisions that are load-bearing rather than incidental.
3. **Answer the self-test questions** in the corresponding `docs/learning/answers/` file *before*
   reading its answers. Write your answer down. An answer you composed and then checked is
   knowledge; an answer you read is recognition.
4. **Do the rebuild exercise** in `rebuild/`. The exercise gives you the module's public surface and
   the test file, not the implementation. Write the module from memory, then diff your version
   against `app/<module>.py` and account for every difference you did not anticipate.
5. **Run the verification test.** `python scripts/learning_progress.py check N`. Green means the
   track is done. A test that passes on the second run after you changed your own code is still a
   pass; a test that passes because you re-read the original is not.

The loop is deliberately asymmetric: steps 1–2 are cheap, steps 3–4 are where the time goes, and
step 5 is a gate, not a formality.

---

## What you need before starting

- **Python 3.12.** `.python-version` pins 3.12.13; the pinned dependencies require 3.11+, and
  3.10 reached end of life on 2026-10-01, so the project targets 3.12.
- **The pinned dependency set installed:** `pip install -r requirements.lock`. Installed from the
  lock, not from `requirements.txt` — the lock is what Docker and CI use, and it is the only
  environment in which the recorded test counts hold.
- **`make verify` green.** That recipe builds its own verifier venv, installs the lock, runs
  `pytest` and then proves zero network access. On the tree this curriculum was written against it
  reports `597 passed, 1 skipped`. That 597 is the figure for the frozen baseline this curriculum
  was written against; current `main` reports `640 passed, 1 skipped` (641 collected). If you cannot
  reproduce 640 before Track 1, stop and fix the environment: a curriculum measured against a moving
  baseline teaches you the wrong lesson.
- **A place to write.** `rebuild/` exists and is yours. Nothing you write there is imported by
  `app/`.

You do not need a Sarvam API key, an LM Studio server or a GitHub token to complete any track. The
mock path is a real path, not a stub, and every track's verification runs offline.

---

## Where everything is

| File or directory | What it holds |
| --- | --- |
| `track-1-*.md` … `track-7-*.md` | One document per track, in the order of the table above. Each names the load-bearing decisions in its module and the failure modes to expect. |
| `answers/` | The self-test answers, one file per track. Read them after writing your own, never before. |
| `PACE.md` | The 16-week schedule, the three checkpoints, the recovery rule and the green-test gate. |
| `../decisions/` | The seven ADRs that explain *why*: strict Pydantic v2, offline-first fallback, provider-agnostic OpenAI-compat, the degraded path calling offline findings directly, 422 demoting a single finding rather than the whole post, labels being human-authored, and greedy one-to-one matching. Read `0002` before Track 5 and `0004` before Track 6. |
| `../../rebuild/README.md` | How the rebuild exercises are structured, what each one gives you, and how to diff your work against `app/`. |
| `scripts/learning_progress.py` | The gate: `check N` runs track N's verification test. Being added in this wave. |

Track documents are named `track-N-<slug>.md` with the module name as the slug. `ls docs/learning/`
is the authority on the exact names in your checkout; if a slug differs, the number is what the
schedule in `PACE.md` refers to.

---

## One rule, stated once

Do not open Track N+1 until `python scripts/learning_progress.py check N` is green. The dependency
graph above is not a suggestion about reading order — it is a statement about what you can possibly
understand. Track 5 makes no sense without Track 3's `RuleCategory`, and Track 6 makes no sense
without Track 5's `ProviderOutcome`. `PACE.md` repeats this rule because it is the one rule in this
curriculum that people break.
