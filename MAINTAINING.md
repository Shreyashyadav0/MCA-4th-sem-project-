# Maintaining this project

For a reader with no AI and no memory of the conversation that built it. If you are
adding a lesson, fixing a checker or running the gate, this file is enough.

---

## 1. The shape of the thing

Two halves that must not drift apart:

| Half | Where | What it is |
|---|---|---|
| The tool | `app/`, `reviewer.py`, `tests/` | A deterministic code reviewer: 63 rules, an optional LLM layer, offline-first |
| The site | `site/` | 110 lessons across 13 parts that teach the tool |

The site is **derived from the tool**. A lesson that quotes a line number, a file size
or a count is making a claim about `app/` at that commit. When the code moves, the
lesson is wrong, and `check_ranges.py` is what notices.

---

## 2. Running the gate

Every change to the site must leave all of this green. Run it from the repo root:

```console
$ python site/tools/validate_lessons.py     # schema, counts, manifest
$ python site/tools/check_ranges.py         # every line reference
$ python site/tools/check_quiz.py           # option length and answer spread
$ python site/tools/embed_sources.py --check
$ python site/tools/build_standalone.py --check
$ python -m pytest -q tests | tail -1
$ grep -rhoE '\b(582|597|598|509|630)\b' site/    # must print nothing
```

Expected output at the freeze:

```
OK lessons=110 parts_covered=13 manifest_entries=110
232 ranges checked, 0 problems
questions: 330 | key is unique longest: 0 | all four within 3 chars: 0
OK repo-sources.js matches 7 embedded files
OK standalone.html is current
640 passed, 1 skipped
```

`make verify` runs the suite and the validator together; it needs `bash`, `python` and
the lock installed (`pip install -r requirements.lock`).

---

## 3. What each checker does

**`validate_lessons.py`** — parses every lesson file and asserts the frozen contract:
fifteen keys exactly, `part_title` matching `contracts.js` character for character,
`order` equal to `part*100 + n`, every terminal example carrying both `expected_output`
and `why_not`, every `project_links.lines` matching `^\d+(-\d+)?$` and fitting its file,
and the manifest agreeing with the three pages. It prints
`OK lessons=<n> parts_covered=<n> manifest_entries=<n>` or a `FAIL` line per problem.

**`check_ranges.py`** — every `project_links` range must start on the first line of the
construct its label names and end on that construct's last line. It rejects a range that
begins or ends on a blank line, dangles a comma or an open bracket, or stops while the
block continues below. `--fix` rewrites the ones it can.

**`check_quiz.py`** — three rules. The correct option must not be the unique longest;
the four options must not all sit within three characters of each other; and **no part
may put more than half its keys at one answer index** (parts of five or more questions).
That third rule exists because Part 10 shipped 30 of 30 keys at index 0 while the
site-wide spread looked healthy.

**`embed_sources.py`** — inlines the seven source files the browser runner needs into
`site/content/repo-sources.js`. `--check` fails if the file is stale.

**`build_standalone.py`** — inlines every CSS file and script into one
`site/standalone.html` that works from `file://`. `--check` fails if it is stale.

---

## 4. Adding a lesson

A lesson is one JavaScript file that pushes one object onto `window.LESSONS`. Fifteen
keys, no more and no fewer.

1. **Pick the id and the order.** Part `n`, lesson `m`: file
   `site/content/part-<n>/lesson-<n>.<m>.js`, `"id": "<n>.<m>"`,
   `"order": <n>*100 + m`. Ids are strings; orders are integers.

2. **Copy the shape from a neighbour.** Open the lesson before yours and copy its
   skeleton. The fifteen keys are `id`, `part`, `part_title`, `title`, `order`,
   `duration_min`, `concept_md`, `code_examples`, `quiz`, `try_it`, `exercise`,
   `common_mistakes`, `project_links`, `learn_more`, `glossary_terms`.

3. **`part_title`** must equal the title in `site/assets/contracts.js` for that part,
   byte for byte. Copy it from there; do not retype it.

4. **`concept_md`** is 200 to 450 words, opens with a `###` heading (never a code
   fence), and uses `###` for its sections.

5. **`code_examples`** — every example is executed at build time and its real stdout
   becomes `expected_output`. Terminal-tier examples also carry a `why_not` saying why
   the browser cannot run them. **Never type an output.** If you cannot run it, it does
   not ship.

6. **`quiz`** — three questions, four options each. Draft the four options at
   near-equal length and *distinct from each other* first, then decide which is correct
   and place it by rotation (`(part + question) % 4`). Writing the truest-sounding
   longest option is what creates the length tell, and lengthening a copy of the key is
   what creates duplicate options — both have happened repeatedly.

7. **`project_links`** — each entry is `{label, path, lines}`. `lines` is `"N"` or
   `"N-M"` and must cover exactly the construct the label names.

8. **`learn_more`** — absolute GitHub URLs only:
   `https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/<path>`.

9. **Wire it in four places, in the same order**: `site/assets/manifest.js`,
   `site/index.html`, `site/lesson.html`, `site/tryit.html`. Each gets one
   `<script src="content/part-<n>/lesson-<n>.<m>.js"></script>` line after the previous
   lesson's.

10. **Run the gate.** All seven commands in section 2.

11. **Regenerate the derived files**: `build_standalone.py` and `embed_sources.py`.

---

## 5. The nine auditor lanes

A wave is not finished until it has been audited. Nine independent reviewers, each
read-only, each with its own lane:

| # | Lane | What it hunts |
|---|---|---|
| 1 | Schema | Fifteen keys, `part_title`, `order`, manifest and page wiring |
| 2 | Anchors | Every `project_links` range against the construct it names |
| 3 | Factual claims | Every statement about `app/` — re-executed, not trusted |
| 4 | Quiz | Correct keys, duplicate options, length tells, answer spread |
| 5 | Prose | Word counts, severed sentences, shared paragraphs, doable exercises |
| 6 | Links and paths | Every `learn_more` href resolving on `main` |
| 7 | Accessibility | Contrast ratios, focus, heading order, keyboard reach |
| 8 | Responsive layout | Overflow, clipping, overlap at 375, 768 and 1440, light and dark |
| 9 | Consistency and honesty | Contradictions between parts; unsupported claims; the ledger |

Run them in two batches, fix every CRITICAL and HIGH, then **re-audit the fixes with
three** — anchors, claims, layout.

---

## 6. The four standing rules

These were each learned by getting them wrong.

**1. Re-audit after every fix batch, not only after a wave.** In four consecutive
rounds, the fixes were the largest source of new defects — 20 findings in one round,
five of them duplicate options created by the fix itself. A fix is a change, and a
change needs the same scrutiny as the thing it fixed.

**2. After fixing a checker, break something on purpose and confirm it fails.**
`check_ranges.py` sat vacuous for a whole session, reporting "0 problems", because a
guard compared a value to itself. The per-part quiz rule only counts once it has been
seen to fire. A checker that cannot see is worse than no checker.

**3. Quiz spread is checked per part, not site-wide.** Eighteen of eighteen keys at one
index hid behind a healthy site-wide average. The site-wide number is an average, and an
average hides a part that is entirely wrong.

**4. Every example runs at build time.** An output you did not see is a fabrication, and
two of them shipped before this rule existed. If a command cannot be run, the example
does not go in.

---

## 7. Where the non-negotiables live

| Rule | Enforced by |
|---|---|
| 13 parts, 110 lessons, no renames, no part 13 | `contracts.js` + `validate_lessons.py` |
| Fifteen schema keys per lesson | `validate_lessons.py` |
| `order = part*100 + n` | `validate_lessons.py` |
| Ranges start and end on a construct | `check_ranges.py` |
| No unique-longest quiz key, no per-part skew | `check_quiz.py` |
| 582, 597, 598, 509, 630 nowhere under `site/` | the gate's grep |
| No test count in any lesson | review, plus the grep |
| Every example executed | `expected_output` + review |
| Manifest and three pages agree | `validate_lessons.py` |
| Never touch `app/`, `tests/`, `benchmarks/`, `docs/learning/` | review |

---

## 8. Release

```console
$ git tag -a v1.1-site -m "Learning site complete: 110 lessons, 13 parts"
$ git push
$ git push --tags
$ git archive --format=zip --prefix=ai-code-reviewer/ -o ai-code-reviewer-site-$(date +%Y%m%d).zip HEAD
$ sha256sum ai-code-reviewer-site-*.zip | tee SHA256SUMS.txt
```

`git archive` packages only tracked files, so `.git`, `.venv`, `__pycache__` and
`benchmarks/out` cannot appear. Verify with `unzip -l` that it lists 110 lesson files.

---

## 9. When real labels exist: the one documented step for lesson 10.10

10.10 currently says, correctly, that no precision, recall or F1 figure exists. **Do
not change that lesson until labels exist.** When they do, this is the only sequence
that may change it:

1. **Label.** `python benchmarks/labelling.py` — see `LABELLING.md`. At least 20
   samples, and the session must include findings you added that the tool missed.

2. **Score.**
   ```console
   $ python -m benchmarks.eval --labels
   ```
   It prints precision, recall and F1 per mode with the sample count beside each
   figure. Copy the figures **from that output only**.

3. **Edit 10.10 in `site/content/part-10/lesson-10.10.js`** — this is the one lesson a
   labelling pass may change. Replace the paragraph beginning "There is no precision,
   recall or F1 figure for this tool" with the measured values, and **keep the sample
   count in the same sentence** as each figure. Keep the closing section about why an
   estimate would have been worse; it is still the reason the number took a year.

4. **Update the lesson's quiz.** Its first question keys "None, because no labels
   exist". Re-key it to the measured result and rewrite the `why`.

5. **Run the gate**, all seven commands in section 2. The `check_quiz.py` per-part rule
   and `check_ranges.py` both apply.

6. **Regenerate** `build_standalone.py`, then commit as
   `10.10 — measured figures from N labelled samples`.

If a figure cannot be traced to a line of `benchmarks.eval --labels` output, it does not
go in the lesson. That rule has already caught two fabricated captures in this project.

## 10. What is not done, and is a person's work

- **The benchmark's labels.** The harness, the matcher and the labelling tool are all
  real; the hand-written labels are not, so there is still no precision, recall or F1
  figure. `LABELLING.md` is the procedure; section 9 above is the step that turns the
  first real labels into 10.10's figures.
- **A real model.** Variant B has never had one behind it here, and variant C never had
  a real key. `DEMO.md` and `HANDOFF.md` are the ledger for that, and they win any
  disagreement.
- **A browser on a real machine, and printed pages on paper.** Headless Chromium is
  evidence, not proof.
