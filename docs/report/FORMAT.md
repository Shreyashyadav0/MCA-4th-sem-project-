# FORMAT.md — the report assembler

Everything a student needs to turn the markdown chapters in `docs/report/` into a
submittable MCSP-232 report, plus the things that must be done *by hand* before
the print-out is made.

Owner: `docs/report/assemble.py`. It writes four files and nothing else.

---

## 1. What it produces

| File | What it is |
|---|---|
| `MCSP-232-Project-Report.docx` | The full report, editable. Title page, certificate, acknowledgement, abstract, table of contents, list of figures, list of tables, then chapters 1–12. |
| `MCSP-232-Project-Report.pdf` | The same report, fixed, with **real page numbers already in the contents** (no F9 step). This is the file to print. |
| `MCSP-232-Project-Proposal.docx` | The synopsis alone, on its own cover. This is the proposal submission, not part of the report. |
| `MCSP-232-Project-Proposal.pdf` | The same synopsis, fixed. |

Both formats carry the same structure: A4, one-inch margins, Times New Roman
12 pt, 1.5 line spacing, justified body; `Heading 1` per chapter, `Heading 2` for
`x.y`, `Heading 3` for `x.y.z`; code listings in Consolas 9 pt on light grey;
tables as real Word tables with a header row and borders; figures centred with a
caption underneath; `Page X of Y` in the footer; the report title in the header;
a page break before every chapter.

---

## 2. How to run it

```bash
# from the repository root
pip install python-docx==1.2.0 reportlab pypdf pillow     # once
python docs/report/assemble.py --out docs/report/out
```

Flags:

| Flag | Effect |
|---|---|
| `--out DIR` | Where the four files go. Default `docs/report/out`. |
| `--report-dir DIR` | Read the markdown from somewhere else (used for test trees). Default: the directory holding `assemble.py`. |
| `--allow-missing` | Build a partial draft even when inputs are absent. Missing front pages become `[FILL: …]` placeholders and are reported. |
| `--inventory` | Print every fill-in token and exit. Builds nothing. |
| `--no-proposal` | Skip the proposal DOCX/PDF. |
| `--no-pdf` | Skip the report PDF (DOCX only). |

Exit codes: `0` success, `2` a required input is missing (nothing is written),
`1` anything else.

**Missing inputs.** The script does not guess. If `front-matter.md`, any of the
twelve chapter files, or `proposal/synopsis.md` is absent it names every absent
file in one message and exits with code 2 *before writing anything*:

```
assemble.py: cannot build — required input(s) are missing:
  - docs/report/front-matter.md
  - docs/report/chapters/05-testing-and-evaluation.md
  ...
2 file(s) absent. Nothing was written.
```

Chapters are matched on their **two-digit prefix** first, so
`chapters/05-testing-and-evaluation-draft.md` satisfies chapter 5 and the exact
name is only a fallback. Renaming a chapter file does not break the build; the
chapter *number* comes from the prefix, the chapter *title* from its `#` heading.

---

## 3. The input contract

### 3.1 `front-matter.md`

`##` sections are read by name (case- and punctuation-insensitive). Recognised:
`Title page`, `Certificate` (or `Certification`), `Acknowledgement` (or
`Acknowledgment`), `Abstract`. Any section named `Table of contents`,
`List of figures` or `List of tables` is ignored — those are generated.

The title page section is `key: value` lines:

```markdown
## Title page

title: Autonomous AI Code Reviewer & PR Assistant
programme: Master of Computer Applications (MCA)
course: MCSP-232 — Project
department: [FILL: department]
institution: [FILL: institution]
candidate: [FILL: candidate name]
roll: [FILL: enrolment number]
supervisor: [FILL: supervisor name]
session: [FILL: academic session]
date: [FILL: date of submission]
```

Keys are matched loosely (`roll` / `roll_no` / `enrolment_number`, `supervisor` /
`guide`, and so on). Any key that is absent falls back to a `[FILL: …]`
placeholder, which is then inventoried. Certificate, acknowledgement and abstract
are rendered in that fixed order whatever order they appear in the file.

### 3.2 Chapters

`chapters/01-introduction.md` … `chapters/12-glossary.md`, in that numeric order:

| # | Name in this tree | # | Name in this tree |
|---|---|---|---|
| 1 | `01-introduction` | 7 | `07-reports-and-layouts` |
| 2 | `02-system-analysis` | 8 | `08-results-and-discussion` |
| 3 | `03-system-design` | 9 | `09-future-scope` |
| 4 | `04-coding` | 10 | `10-bibliography` |
| 5 | `05-testing` | 11 | `11-appendices` |
| 6 | `06-system-security` | 12 | `12-glossary` |

All twelve are present. The names above are the ones this tree uses; the assembler
keys on the two-digit prefix, so the list is descriptive, not prescriptive — the
skeleton names it was written against (`02-literature-review`, `09-references`, …)
would still build.

The `#` heading becomes `Chapter N — <title>`. Chapters whose title begins with
*Appendix*, *References*, *Bibliography* or *Glossary* keep their own title
without the `Chapter N` prefix, so `Appendix A` reads as `Appendix A — Commands`.

### 3.3 Markdown dialect

Supported, and no more: `#`/`##`/`###` headings, paragraphs, fenced code blocks,
pipe tables, bullet and numbered lists, blockquotes, `---` rules, and figure
references. Inline `**bold**`, `*italic*`, `` `code` `` and `[text](url)` are
carried through.

**Captions are the line next to the block**, and are optional:

- A table's caption is the paragraph **immediately above** it:
  `Table 1.1 — Review latency by change size` (a fully italic line works too).
  Without one the table is still numbered and rendered, just with no title.
- A listing's caption is the paragraph immediately **above or below** the fence:
  `Listing 2.1 — the deterministic entry point`.
- A figure is its own line, exactly:

  ```markdown
  ![Figure 3.1 — Component map](fig-3-1-architecture.png)
  ```

  The path is resolved against `docs/report/`, `docs/`, the repository root and
  finally `docs/diagrams/<basename>`. **If the image is not found the build does
  not fail**: a bordered box is drawn in its place, carrying the missing path in
  red, and the figure is counted as missing in the summary. The caption is
  rendered either way.

Display numbers: figures keep the number written in the markdown (`Figure 3.1`).
Tables and listings are numbered sequentially through the whole report (`Table 7`,
`Listing 12`), because the markdown carries no reliable number for them.

### 3.4 Fill-in tokens

`[FILL: …]` and `[FILL AFTER BENCHMARK: …]` are recognised anywhere in any input
file. They are rendered **bold red** in both the DOCX and the PDF so they cannot
be missed on a printed page, and every one found is listed at the end of the run.

---

## 4. The F9 step (Word only — the PDF needs nothing)

python-docx cannot paginate, so Word's table of contents cannot be computed by
the script. The DOCX therefore contains three genuine Word **fields** — a table of
contents, a list of figures and a list of tables — each with a cached placeholder
result so the document is readable immediately:

> [Table of contents — a Word field. Select all (Ctrl+A), then press F9 to build
> it with page numbers.]

To populate them:

1. Open `MCSP-232-Project-Report.docx` in Microsoft Word.
2. Click anywhere in the document body.
3. Press **Ctrl+A** (select all), then press **F9**.
4. If Word asks, choose **Update entire table** — not "update page numbers only".
5. Check that the contents now shows chapters with page numbers, and that the
   lists of figures and tables each list their captions.
6. Save the file. Print from Word, or print the PDF instead.

Word may also offer to update fields when the file is opened (the document sets
`updateFields`, so the prompt usually appears) — that does the same job.

Two things follow from this, and both matter:

- **After F9 the page count changes.** The fields expand from one line to two or
  three pages. Re-read the page count afterwards, not before (see §6).
- **The PDF does not need this step.** reportlab computes the contents, the list
  of figures and the list of tables with real page numbers in a multi-pass build,
  and adds a PDF bookmark per chapter and per sub-heading. If the only thing
  wanted is a print-out, print the PDF and skip Word entirely.

Caption numbering is the one place the DOCX carries cached numbers: each caption
embeds a `SEQ Figure` / `SEQ Table` field with its number already displayed, so
`Figure 3.1 — Component map` reads correctly before F9 as well as after.

---

## 5. What must be filled before submitting

The report currently contains **unfilled placeholders by design**. No benchmark
has been run, so sections 5 and 6 carry no numbers — and must not be given any
that the harness did not produce. The assembler refuses to invent them.

**The authoritative list is printed by every run**, at the end:

```
Fill-in inventory: 28 token(s) in 5 file(s)
  chapters/01-introduction.md
    - [FILL AFTER BENCHMARK: measured peak resident memory and per-review wall-clock latency on the submission machine, for the rules mode and the local mode]
  chapters/02-system-analysis.md
    ...
```

To get it without building anything: `python docs/report/assemble.py --inventory`.

### 5.1 The tokens the skeleton defines

This is the set that is actually in the tree, as printed by
`python docs/report/assemble.py --inventory` (28 occurrences in 5 files). The count
is of *occurrences*, not distinct texts: `[FILL: enrolment number]` appears in both
`front-matter.md` and `proposal/synopsis.md` and is counted twice. `docs/report/SKELETON.md`
defines the original expected set; the chapters have since added their own tokens,
and the inventory, not this table, is authoritative.

| # | Token | File |
|---|---|---|
| 1 | `[FILL AFTER BENCHMARK: measured peak resident memory and per-review wall-clock latency on the submission machine, for the rules mode and the local mode]` | `chapters/01-introduction.md` |
| 2 | `[FILL AFTER BENCHMARK: measured values]` | `chapters/02-system-analysis.md` |
| 3 | `[FILL AFTER BENCHMARK: p50 and p95 review latency per mode]` | `chapters/02-system-analysis.md` |
| 4 | `[FILL AFTER BENCHMARK: precision/recall/F1 per mode]` | `chapters/08-results-and-discussion.md` |
| 5 | `[FILL AFTER BENCHMARK: latency p50/p95]` | `chapters/08-results-and-discussion.md` |
| 6 | `[FILL AFTER BENCHMARK: false-positive rate per mode and per-category breakdown]` | `chapters/08-results-and-discussion.md` |
| 7 | `[FILL: ...]` | `front-matter.md` |
| 8 | `[FILL: enrolment number]` | `front-matter.md` |
| 9 | `[FILL: study centre]` | `front-matter.md` |
| 10 | `[FILL: regional centre]` | `front-matter.md` |
| 11 | `[FILL: guide name and designation]` | `front-matter.md` |
| 12 | `[FILL: July 2026 / January 2027 session]` | `front-matter.md` |
| 13 | `[FILL: date of submission]` | `front-matter.md` |
| 14 | `[FILL: designation]` | `front-matter.md` |
| 15 | `[FILL: department, institution]` | `front-matter.md` |
| 16 | `[FILL: date]` | `front-matter.md` |
| 17 | `[FILL: place]` | `front-matter.md` |
| 18 | `[FILL: guide name]` | `front-matter.md` |
| 19 | `[FILL AFTER BENCHMARK: abstract result sentence]` | `front-matter.md` |
| 20 | `[FILL: department]` | `front-matter.md` |
| 21 | `[FILL: institution]` | `front-matter.md` |
| 22 | `[FILL: supervisor name]` | `front-matter.md` |
| 23 | `[FILL: academic session]` | `front-matter.md` |
| 24 | `[FILL: enrolment number]` | `proposal/synopsis.md` |
| 25 | `[FILL: study centre]` | `proposal/synopsis.md` |
| 26 | `[FILL: regional centre]` | `proposal/synopsis.md` |
| 27 | `[FILL: guide name and designation]` | `proposal/synopsis.md` |
| 28 | `[FILL: July 2026 / January 2027 session]` | `proposal/synopsis.md` |

### 5.2 The tokens that are not benchmark-dependent

These are yours to fill now — they are personal and institutional, not results:

- `title page` — candidate name, enrolment number, supervisor, department,
  institution, session, date of submission (whichever of these the title page
  section does not already carry).
- Certificate, acknowledgement, abstract body — the parts that are not a result.
- `chapters/10-bibliography.md` — 23 entries, one consistent style, each with its
  access date and a note saying where the report relies on it.
- `chapters/12-glossary.md` — terms actually used in the report.

### 5.3 Before you print

- [ ] `grep -rn "FILL" docs/report` returns nothing.
- [ ] Every number in chapters 5 and 6 exists in a file under `benchmarks/out/`.
- [ ] No sentence quotes `example_01` or `example_02` as a result.
- [ ] The abstract's result sentence matches chapter 5's table exactly.
- [ ] F9 has been pressed in Word (§4), or the PDF is being used instead.
- [ ] Every `Figure N.M` referenced in the text exists under `docs/diagrams/` —
      the run summary lists any that do not.

---

## 6. Page count: the honest position

The requirement is **100–125 pages excluding coding**. The assembler prints the
current figure on every run. This is the real line from the run that produced the
files in `docs/report/out/` (2026-11-14):

```
PDF pages     : 137 total, 29 of them carry code listings, so about 108 non-coding pages
                target 100-125 excluding coding: inside the range
```

Read it as follows:

- **`N total`** — pages in `MCSP-232-Project-Report.pdf`, counted with `pypdf`.
- **`M of them carry code listings`** — pages whose text contains a `Listing N`
  caption, i.e. pages a listing sits on. This is an *estimate* of the coding
  pages the rule excludes; a page holding both prose and code is still counted as
  a coding page, so the non-coding figure is a slight under-estimate.
- **`about N−M non-coding pages`** — the number to compare against 100–125.

**Current count: 137 pages, 108 of them non-coding — inside the range, with 17
pages of headroom.** The same run reported 12/12 chapters found, 10 figures
referenced and embedded (0 missing), 35 tables, 59 listings, and 24,765 prose
words (34,323 including code listings and table cells). The proposal is **20
pages**, inside its own limit.

That 137 is a *PDF* count. The DOCX needs the **F9 step** before any page count is
read off it (§4): its table of contents, list of figures and list of tables are
Word fields with a one-line cached placeholder, so before F9 the DOCX is shorter
than it will print, and after F9 the contents expands from one line to two or
three pages. Ctrl+A then F9, choose *Update entire table*, save — or print the
PDF, which needs no F9 at all.

Two consequences worth stating plainly:

- At 24,765 prose words the report sits inside 100–125 non-coding pages, but on
  the strength of 108, not of a comfortable margin. If an edit takes the printed
  count under 100, the fix is more substance in chapters 3, 4 and 6 — not larger
  type, wider margins or filler.
- If it comes in over 125, the coding pages are the first thing to recount by
  hand, because the estimate above is conservative in the wrong direction.

---

## 7. Physical submission

Per the MCSP-232 project requirements, the report is not submitted as a file:

1. **Two printed copies** of the report — both complete, both bound as the
   programme requires, both identical to the PDF the assembler produced.
2. **One CD** (or the medium the current guidelines name) carrying the
   executable and its source, so the examiner can run what the report describes.
   Burn it from the repository, not from a partial copy; include the run
   instructions.
3. **The original approved proforma** — the synopsis/proforma that was approved
   before the work started, in its original form. This is a physical document; the
   assembler cannot produce or replace it.

Confirm the current wording of these requirements against the programme
guidelines before the submission date — the count of copies, the medium and the
binding rules are the kind of detail that changes between sessions, and this file
does not override them.

The proposal (`MCSP-232-Project-Proposal.docx` / `.pdf`) is the synopsis
submission and is not part of the bound report.

---

## 8. Known limitations

1. **The DOCX table of contents is a field, not a computed table.** Until F9 is
   pressed it shows a placeholder. This is a python-docx limitation, not a bug:
   the library has no layout engine and cannot know a heading's page number.
   The PDF has real page numbers for exactly this reason.
2. **The DOCX list of figures and list of tables are also fields** (`TOC \c`),
   populated in the same F9 pass. They depend on the captions carrying `SEQ`
   fields, which the assembler writes.
3. **Cached numbers go stale if chapters are edited in Word.** Re-run the
   assembler rather than hand-editing captions, so numbering stays consistent.
4. **Long code lines wrap** in the PDF (Courier 8.5 pt inside a shaded box) and
   are not clipped; in Word a long line wraps inside the shaded paragraph. Keep
   listings to about 90 characters per line.
5. **No index, no footnotes, no endnotes.** Not required here, and not supported
   by this parser.
6. **Tables are laid out with equal column widths** in the PDF (the first column
   a little wider); Word autofits. A table with one very wide column may look
   better hand-adjusted in the DOCX before printing.
7. **`--allow-missing` output is a draft, not a submission.** It exists so the
   document can be reviewed while chapters are still being written; the exit-code-2
   path is the correct one for a real build.
