# Rebuild from memory — seven tracks

This directory is a **self-study scaffold**, not a second implementation. You rebuild
the reviewer from memory, one module at a time, and a verification test tells you
whether your memory was faithful. Nothing here is wired into the app: `rebuild/` is
never imported by `app/`, `tests/` or the entry points.

---

## Ground rules

1. **Never copy from `app/`.** Not a line, not a signature, not a docstring. The point
   of the exercise is to find out what you actually know.
2. **Close the tab, then build.** Write the module from memory with the source file
   shut. Only after your version runs do you open `app/<module>.py` and diff the two
   side by side. The diff is the lesson; the file is just the artefact.
3. **A rebuild passes** only when *both* of these hold:
   - its verification test is **green**, and
   - you can **explain the module out loud without opening it** — what it is
     responsible for, what its public surface is, what it refuses to do, and why the
     boundary sits where it does.

   Green alone is not a pass. If you cannot explain it, you copied it.
4. **Only one module in flight at a time.** Start the next track only after the
   previous one is green and explainable.
5. **Do not edit the verification tests to make them pass.** If a test looks wrong,
   the test is the contract; changing it is changing the exam. Note the disagreement
   and move on.
6. **Placeholders stay empty until you start.** The `.gitkeep` files exist only so the
   seven directories survive a clone. Replace a `.gitkeep` with `<module>.py` when you
   begin that track — do not delete the directory.

## Why the tests skip today

Each test file starts with

```python
pytestmark = pytest.mark.skipif(not REBUILD_FILE.exists(), reason="... not written yet")
```

so `python -m pytest -q rebuild/tests` is **green today with 59 skipped across 7 files**. That is
deliberate: the first green run after you write a module is meaningful, because it is
the first one that could have failed. A test that passed before you wrote anything
would prove nothing.

The moment `rebuild/<module>.py` exists, its test stops skipping and starts comparing
your module against the real one on shared inputs.

---

## The seven tracks

The track names are the *rebuild* directory names. The right-hand column says which
real modules each track stands for — the mapping is not one-to-one, because the
curriculum groups the small modules together.

| # | Track (`rebuild/…`) | Real modules | What you are rebuilding |
|---|---------------------|--------------|-------------------------|
| 1 | `models` | `app/models.py` | The finding contract: `Finding`, `AnchoredFinding`, `ReviewResult`, severity ladder, counts, ordering, verdict |
| 2 | `parser` | `app/parser.py` | Unified-diff parsing into `DiffBundle`/`FileDiff`/`Hunk`, path normalisation, added-line sets and spans, anchoring |
| 3 | `rules` | `app/rules.py` | The deterministic rule engine: the rule registry, line context, each check, `# noqa` suppression, `review_lines`/`review_diff` |
| 4 | `offline` | `app/mock_provider.py` + `app/config.py` | The "no LLM available" path, and the settings boundary that decides credentials vs. degradation |
| 5 | `providers` | `app/sarvam_provider.py` + `app/openai_compat_provider.py` | One chat-completions transport, prompt building, payload parsing, the retry budget, fallback |
| 6 | `engine` | `app/engine.py` | Provider selection and precedence, `ProviderSelection`, `review()` as the single entry point |
| 7 | `surfaces` | `app/cli.py` + `app/main.py` + `app/github_client.py` | The edges: CLI exit codes, the HTTP app, the GitHub posting payload and its idempotency markers |

Order matters: `models` → `parser` → `rules` → `offline` → `providers` → `engine` →
`surfaces` is the dependency order of the real code. Every track depends only on the
tracks before it.

### What each verification test compares

The tests do not check your module in isolation — they check that your module and the
real one **agree on the same inputs**:

- `models` — the same bad `line` strings are rejected, the same extra key is forbidden,
  the same rows/counts/verdicts come out.
- `parser` — the same added-line sets, spans and file counts on `samples/sample.diff`,
  the same `normalize_path` results, the same refusal of an empty diff.
- `rules` — the same findings (line + severity) on a seeded snippet, the same
  `min_severity` filtering, the same `# noqa` suppression, the same findings on the
  sample diff.
- `offline` — the same `offline_review` result shape and findings, the same notes.
- `providers` — the same findings parsed from the same model payload, the same
  rejection of non-JSON, the same prompt text, the same config validation.
- `engine` — the same provider chosen for the same environment, the same degradation,
  the same `ValueError` for an unknown request.
- `surfaces` — the same CLI exit codes for the same argv.

## How to run the verification tests

From the repository root:

```bash
# everything (today: 59 skipped across 7 files, exit 0)
python -m pytest -q rebuild/tests

# one track
python -m pytest -q rebuild/tests/test_rebuild_engine.py

# one track, verbose — use this while you are writing the module
python -m pytest rebuild/tests/test_rebuild_models.py -v

# the app's own suite must stay green — your rebuild must not touch it
python -m pytest -q tests
```

Or use the progress CLI, which reports what pytest says and nothing more:

```bash
python scripts/learning_progress.py status      # 7-row table, runs each test
python scripts/learning_progress.py status --fast   # table from last recorded run
python scripts/learning_progress.py check 6     # run ONLY track 6, exit = pytest's code
```

`check N` writes `.learning-progress.json` (gitignored) with the exit code, outcome and
an ISO timestamp per track. There are no streaks and no points — the file is a log, and
the only thing that counts is a green test you can also explain.
