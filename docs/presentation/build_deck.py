#!/usr/bin/env python3
"""Deterministic generator for docs/presentation/project_overview.pptx.

Structure: one list of slide definitions (SLIDES) plus a small set of renderer
functions. Nothing here reads the clock, the network or the environment, so two
runs over the same tree produce the same bytes.

Usage:
    python docs/presentation/build_deck.py [output.pptx]

Every number that appears in the deck is either structural (phase numbers, slide
numbers) or verifiable in this tree:

    597 passed + 1 skipped   python -m pytest -q tests          (598 collected)
    598 collected            python -m pytest --collect-only -q tests
    63 rules, 10 categories  app/rules.py RULE_COUNT, RuleCategory
    5 finding fields         app/models.py Finding
    3 provider modes         app/engine.py PROVIDERS
    7 learning tracks        docs/learning/track-*.md
    36 pinned dependencies   requirements.lock
    2 format examples        benchmarks/golden/manifest.json

Benchmark results are not known and are not guessed: they appear only as
`[FILL AFTER BENCHMARK: ...]` tokens.
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import sys
import zipfile
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

# --------------------------------------------------------------------------- #
# Geometry and palette
# --------------------------------------------------------------------------- #

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

ACCENT = RGBColor(0x0F, 0x2A, 0x4C)      # the single dark-blue accent
ACCENT_SOFT = RGBColor(0x2E, 0x54, 0x86)
PALE = RGBColor(0xEC, 0xF1, 0xF7)
INK = RGBColor(0x1A, 0x1F, 0x27)
MUTED = RGBColor(0x5A, 0x64, 0x72)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

TITLE_BAR_H = Inches(0.9)
BODY_TOP = Inches(1.06)
BODY_BOTTOM = Inches(7.34)
BODY_LEFT = Inches(0.62)
BODY_W = Inches(12.09)

MONO_FONT = "Consolas"
BODY_FONT = "Calibri"

MAX_BULLETS = 6
MAX_BULLET_WORDS = 14

# Fixed metadata so the saved file is byte-identical across runs.
FIXED_STAMP = _dt.datetime(2026, 11, 14, 9, 0, 0)


# --------------------------------------------------------------------------- #
# Slide definitions
#
# Each entry is a dict. Keys used by the renderer:
#   kind      "title" | "bullets" | "diagram" | "code" | "table"
#   title     string shown in the coloured title bar
#   eyebrow   optional small label above the title bar text
#   bullets   list of (level, text); level 0 or 1
#   mono      monospaced block text (verbatim)
#   mono_caption  small caption under the monospaced block
#   table     {"header": [...], "rows": [[...], ...], "widths": [in, in, ...]}
#   note_after_table  small line under the table
#   notes     speaker notes, 2-5 sentences
# --------------------------------------------------------------------------- #

SLIDES: list[dict] = [
    {
        "kind": "title",
        "title": "Autonomous AI Code Reviewer & PR Assistant",
        "subtitle": "A unified-diff reviewer with a deterministic rule engine and an optional model layer",
        "stack": "Python 3.12  |  FastAPI  |  Pydantic v2  |  OpenAI-compatible transport  |  pytest  |  GitHub REST",
        "lines": [
            "[FILL: candidate name  |  roll number]",
            "[FILL: supervisor  |  department  |  institution]",
            "MCA final-semester project  |  version 0.1.0  |  14 November 2026",
        ],
        "notes": (
            "Twenty seconds. Name the project and state in one sentence what it does: it "
            "reviews a pull-request diff and returns findings in a fixed five-field format, "
            "with or without a model. The stack line names every runtime dependency that "
            "matters. Do not read the title slide aloud."
        ),
    },
    {
        "kind": "bullets",
        "title": "Problem",
        "bullets": [
            (0, "Code review is the last gate before merge, and it is human."),
            (0, "Small pull requests wait for a reviewer; large ones get skimmed."),
            (0, "Linters and pattern analysers are fast and reproducible, but judge no semantics."),
            (0, "LLM reviewers read semantics, but are non-deterministic and availability-bound."),
            (0, "The gap: a reviewer that is both always available and measurable."),
        ],
        "notes": (
            "Ninety seconds. Establish that review latency is a queueing cost, not a "
            "tooling cost, and do not quote statistics that are not in this repository. "
            "The two existing options trade reproducibility for coverage. Land the gap in "
            "one sentence and stop, because the rest of the deck is the answer to it."
        ),
    },
    {
        "kind": "bullets",
        "title": "Objectives",
        "bullets": [
            (0, "Parse a unified diff and anchor every finding to a changed line."),
            (0, "Detect a defined set of security and quality defects deterministically."),
            (0, "Add an optional model layer that degrades without failing the review."),
            (0, "Post the review to a pull request, inline and idempotently."),
            (0, "Measure the result on a human-labelled dataset."),
            (0, "Keep the suite offline: no key, no network, no server."),
        ],
        "notes": (
            "Sixty seconds. Read the objectives as a list of things that can be marked done "
            "or not done. The first four are implemented and covered by the offline suite; "
            "the fifth is not, because no labelled dataset exists. Saying that here costs "
            "nothing and sets up the benchmark and real-versus-simulated slides."
        ),
    },
    {
        "kind": "diagram",
        "title": "Architecture",
        "mono_caption": "Rendered verbatim from ARCHITECTURE.md, section 1. No second diagram exists.",
        "bullets": [
            (0, "One entry point: review() in app/engine.py serves CLI, API and webhook."),
            (0, "Two boundaries: the five-field finding contract and the config boundary."),
            (0, "One router decides live versus offline; one adapter serves both providers."),
            (0, "A missing credential is data, not an exception."),
        ],
        "notes": (
            "Two minutes. Walk the diagram once, top to bottom, then stop. Spend the "
            "remaining time on the two boundaries rather than the component list: the "
            "five-field finding contract and the config boundary, where a missing credential "
            "is data. Point at the single router and say everything goes through it, which "
            "is why the fallback cannot be bypassed by accident."
        ),
    },
    {
        "kind": "table",
        "title": "Phases 1-6: what each phase fixed, and its tests",
        "table": {
            "header": ["Phase", "Interface fixed by the phase", "Tests collected"],
            "widths": [1.15, 8.85, 2.05],
            "rows": [
                ["1", "Scaffold, config boundary, finding contract, CLI", "14"],
                ["2", "Diff parsing and anchoring to changed line ranges", "11"],
                ["3", "Rule engine: 63 rules, 10 categories; API and webhook server", "234"],
                ["4", "Model review layer with a guaranteed local fallback", "87"],
                ["5", "Pull-request posting: inline, summary, idempotent", "113"],
                ["6", "One OpenAI-compatible adapter, two providers, one selector", "51"],
                ["--", "Benchmark harness: matching, metrics, runner", "73"],
                ["Total", "598 collected = 597 passed + 1 skipped", "583"],
            ],
        },
        "note_after_table": (
            "Counts are collected tests per phase's test files. The one skip is the "
            "live-server smoke test: it needs a real local model and opts in through an "
            "environment variable."
        ),
        "notes": (
            "Ninety seconds. Do not read the table row by row. Say the project was built in "
            "six phases, each with a fixed interface and its own tests, and that the counts "
            "are collected tests in that phase's test files. The suite total is 583 "
            "collected, which runs as 597 passed and 1 skipped, and the skip is the "
            "live-model smoke test that needs a real server."
        ),
    },
    {
        "kind": "bullets",
        "title": "The hybrid design: deterministic base, model on top",
        "bullets": [
            (0, "The rule engine always runs and returns the same findings for the same diff."),
            (0, "The model layer runs only when configured, and sees only added lines."),
            (0, "Model output is filtered before it becomes a finding: fenced JSON unwrapped."),
            (0, "Hallucinated files dropped, invented line numbers snapped, duplicates collapsed."),
            (0, "Each live finding is labelled (source: sarvam) or (source: local); none exists yet."),
        ],
        "notes": (
            "Two minutes. This is the design contribution, so slow down. The claim is not "
            "that a model reviews code; the claim is that the model's output is untrusted "
            "and passes a validator before it becomes a finding. Give one concrete rejected "
            "output: a finding for a file that is not in the diff. Then say the deterministic "
            "layer below means a model failure is a degradation, not an outage."
        ),
    },
    {
        "kind": "bullets",
        "title": "The key decision: the offline fallback",
        "bullets": [
            (0, "No key, blank key, --offline, SDK absent, 401, 403, 5xx, timeout, unparseable JSON."),
            (0, "Every one of those routes to the same local rule engine."),
            (0, "The run still exits 0 and still produces a review."),
            (0, "Exactly one warning names the provider label and the reason."),
            (0, "The result carries provider and model fields set from what ran."),
        ],
        "notes": (
            "Ninety seconds. Frame this as the decision the project would be worse without. "
            "The alternative, failing when the model is unavailable, makes a merge gate "
            "depend on someone else's uptime and on a credential that expires. The reporting "
            "half matters as much: the result says what actually ran rather than repeating "
            "what was configured."
        ),
    },
    {
        "kind": "bullets",
        "title": "Provider precedence: sarvam > local > mock",
        "bullets": [
            (0, "The order is fixed in app/engine.py, tested, and not configurable away."),
            (0, "SARVAM_API_KEY set selects sarvam; else LMSTUDIO_BASE_URL selects local; else mock."),
            (0, "Both set: sarvam wins, because the local demo path is one flag away."),
            (0, "--provider auto|local|sarvam|mock forces a choice for one run."),
            (0, "Forcing an unconfigured provider degrades to mock, naming the missing variable."),
            (0, "A blank value counts as unset, so an empty key degrades quietly."),
        ],
        "footnote": (
            "Neither model path is exercised here: sarvam has never had a real key, and the "
            "local branch was verified against a stub server, not a model."
        ),
        "notes": (
            "Sixty seconds. State the order, then state why it is locked: precedence that "
            "drifts with the environment makes any reported number unattributable. Both set "
            "means the hosted provider wins, and the local demo path is one flag away. "
            "Mention that forcing a provider never crashes; it degrades and names the "
            "missing variable. Neither model path has been exercised: the local branch was "
            "verified against a stub server and the hosted branch has never had a real key."
        ),
    },
    {
        "kind": "placeholders",
        "title": "Benchmark methodology: harness first, numbers later",
        "bullets": [
            (0, "Dataset: benchmarks/golden/, each sample a change.diff plus a hand-written expected.json."),
            (0, "Labels must be human-authored; a label copied from the tool measures nothing."),
            (0, "Matching: same file, overlapping range, equivalent category; one-to-one, greedy, largest overlap."),
            (0, "Greedy matching is documented: a near-miss can score as FP and FN."),
            (0, "Metrics: precision, recall, F1, false-positive rate, p50 and p95 latency."),
            (0, "Modes: rules, local, merged. Artifacts: metrics.csv, summary.json, summary.md, chart.png."),
        ],
        "placeholders": [
            "[FILL AFTER BENCHMARK: labelled sample count, and the per-category distribution]",
            "[FILL AFTER BENCHMARK: who labelled the samples, against which diff revision]",
            "[FILL AFTER BENCHMARK: results table - one row per mode, from metrics.csv]",
            "[FILL AFTER BENCHMARK: latency p50 and p95 per mode, from summary.json]",
        ],
        "notes": (
            "Ninety seconds. Explain the methodology before any result and be explicit that "
            "the repository holds two format examples and no labelled evaluation samples, so "
            "the harness is demonstrated, not scored. The placeholders on this slide are "
            "deliberate and are filled from benchmarks/out after a labelled run. If asked why "
            "there are no numbers, the answer is that labels written by the tool measure nothing."
        ),
    },
    {
        "kind": "table",
        "title": "What is real and what is simulated",
        "table": {
            "header": ["Item", "Status"],
            "widths": [4.55, 7.5],
            "rows": [
                ["63-rule engine, CLI, API, diff parsing, anchoring",
                 "Implemented; covered by the offline suite (597 passed, 1 skipped)."],
                ["Zero-network, zero-credential operation",
                 "Verified: verify_offline.py blocks sockets, then runs the suite."],
                ["Benchmark harness end to end",
                 "Runs over two format examples; those numbers are a smoke test, not results."],
                ["Labelled evaluation dataset",
                 "Does not exist; evaluation_samples in the manifest is empty."],
                ["Local-model provider",
                 "Verified against a stub OpenAI-compatible server; never a real model."],
                ["Sarvam provider",
                 "Never exercised; no real key was used at any point."],
                ["Pull-request posting",
                 "Verified against simulated GitHub clients; no live post recorded."],
            ],
        },
        "note_after_table": (
            "Read as a ledger: built and tested, built and unexercised, or not built at all."
        ),
        "notes": (
            "Two minutes. Do not soften this slide; read it as a ledger. Say which parts are "
            "built and tested and which are built but unexercised, and why: no key, no local "
            "model and no labelled data in the build environment. An examiner who finds an "
            "unexercised path that was claimed as verified will discount everything else."
        ),
    },
    {
        "kind": "code",
        "title": "Demo script: variant A, offline mock",
        "bullets": [
            (0, "Variant A needs no key, no network and no configuration."),
            (0, "The bundled sample diff yields four findings and a blocking verdict."),
            (0, "mode, provider and model are set from what actually ran."),
            (0, "The same engine answers over HTTP with no credential of any kind."),
        ],
        "mono": (
            "# DEMO.md, section 2: the offline variant, copy-pasteable from the repo root\n"
            "python reviewer.py samples/sample.diff\n"
            "python reviewer.py samples/sample.diff --json | jq '.mode, .verdict'\n"
            "\n"
            "# terminal 1\n"
            "uvicorn app.main:app --port 8000\n"
            "\n"
            "# terminal 2\n"
            "curl -s localhost:8000/test-review | jq '.stats'\n"
            "curl -s localhost:8000/health | jq '{status, mode, rules, provider}'"
        ),
        "notes": (
            "Two minutes. Show screenshots rather than a live terminal, because a live demo "
            "fails for reasons unrelated to the work. Narrate the CLI run in one pass: four "
            "findings, three CRITICAL and one MEDIUM, verdict block, exit code 0. Then the "
            "HTTP response, because it answers what is actually running in one line."
        ),
    },
    {
        "kind": "bullets",
        "title": "Limitations",
        "bullets": [
            (0, "No labelled dataset exists, so there is no measured result yet."),
            (0, "The local path is stub-verified, not verified against a real model."),
            (0, "The hosted Sarvam path has never run live; no real key was used."),
            (0, "Labels are one person's judgement; inter-annotator agreement is not measured."),
            (0, "Greedy line-based matching scores a near-miss as both FP and FN."),
            (0, "The idempotency marker is a public HTML comment a third party can suppress."),
        ],
        "notes": (
            "Ninety seconds. Pick the two limitations that bound the claims, no labelled "
            "dataset and an unexercised model path, and say what each one costs the "
            "conclusion. Do not read all six. End on the interpreter pin, because it shows "
            "the project has a maintenance horizon."
        ),
    },
    {
        "kind": "bullets",
        "title": "Future work",
        "bullets": [
            (0, "Label a dataset with more than one annotator, and report agreement."),
            (0, "Run the benchmark on real local-model output, not on a stub."),
            (0, "Verify the hosted path with a live key and record the transcript."),
            (0, "Replace the public marker with an author-filtered or HMAC-derived one."),
            (0, "Extend the rule engine with data-flow analysis across functions."),
            (0, "Move off the end-of-life interpreter; it is a project, not a chore."),
        ],
        "notes": (
            "Sixty seconds. Pair each item with the constraint that blocks it, not just the "
            "wish: the dataset needs an annotator, the local run needs hardware, the marker "
            "change needs a format decision. That distinction is what separates future work "
            "from a wish list."
        ),
    },
    {
        "kind": "bullets",
        "title": "References",
        "bullets": [
            (0, "OWASP Top Ten: the taxonomy the 63 rules map onto."),
            (0, "Python 3.12, FastAPI and Pydantic v2 documentation."),
            (0, "OpenAI-compatible chat-completions protocol, used by both model providers."),
            (0, "LM Studio and Sarvam AI API documentation."),
            (0, "GitHub REST API: pull request review comments."),
            (0, "This repository: ARCHITECTURE.md, TESTING.md, benchmarks/CONTRACT.md, docs/decisions/."),
        ],
        "notes": (
            "Twenty seconds. Do not read the references. Say the report carries the full "
            "bibliography and that this slide lists the sources that shaped the design. Then "
            "stop and invite questions."
        ),
    },
]


# --------------------------------------------------------------------------- #
# Validation helpers (run at build time, so a bad slide cannot be shipped)
# --------------------------------------------------------------------------- #


def _words(text: str) -> int:
    return len(text.split())


def _sentences(text: str) -> int:
    return len([p for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p])


def validate(defs: list[dict]) -> None:
    """Fail the build on a rule violation rather than shipping a bad deck."""
    problems: list[str] = []
    for i, d in enumerate(defs, start=1):
        notes = d.get("notes", "")
        if not notes.strip():
            problems.append(f"slide {i}: empty notes")
        elif not 2 <= _sentences(notes) <= 5:
            problems.append(f"slide {i}: notes have {_sentences(notes)} sentences")
        bullets = d.get("bullets", [])
        if len(bullets) > MAX_BULLETS:
            problems.append(f"slide {i}: {len(bullets)} bullets")
        for level, text in bullets:
            if level not in (0, 1):
                problems.append(f"slide {i}: bad bullet level {level}")
            if _words(text) > MAX_BULLET_WORDS:
                problems.append(f"slide {i}: {_words(text)}-word bullet: {text!r}")
    if not 12 <= len(defs) <= 15:
        problems.append(f"deck has {len(defs)} slides, outside 12-15")
    if problems:
        raise SystemExit("deck validation failed:\n  " + "\n  ".join(problems))


# --------------------------------------------------------------------------- #
# Renderer primitives
# --------------------------------------------------------------------------- #


def _blank(prs: Presentation):
    """A slide carrying a real title placeholder, so the deck has a usable outline."""
    return prs.slides.add_slide(prs.slide_layouts[5])  # "Title Only"


def _rect(slide, left, top, width, height, fill: RGBColor, line: RGBColor | None = None):
    from pptx.enum.shapes import MSO_SHAPE

    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(1)
    shape.shadow.inherit = False
    return shape


def _bring_to_front(slide, shape) -> None:
    """Placeholders are created before our shapes, so move one to the front."""
    tree = slide.shapes._spTree
    element = shape._element
    tree.remove(element)
    tree.append(element)


def _textbox(slide, left, top, width, height, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(left, top, width, height)
    frame = box.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = anchor
    frame.margin_left = 0
    frame.margin_right = 0
    frame.margin_top = 0
    frame.margin_bottom = 0
    return box


def _title_bar(slide, text: str, eyebrow: str | None = None) -> None:
    _rect(slide, 0, 0, SLIDE_W, TITLE_BAR_H, ACCENT)
    _rect(slide, 0, TITLE_BAR_H, SLIDE_W, Emu(int(Inches(0.045))), ACCENT_SOFT)
    placeholder = slide.shapes.title
    if placeholder is not None:
        placeholder.left = BODY_LEFT
        placeholder.top = Inches(0.12) if eyebrow else Inches(0.16)
        placeholder.width = Inches(11.9)
        placeholder.height = Inches(0.62)
        frame = placeholder.text_frame
        frame.word_wrap = True
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        frame.margin_left = 0
        frame.margin_right = 0
        frame.margin_top = 0
        frame.margin_bottom = 0
    else:
        box = _textbox(
            slide,
            BODY_LEFT,
            Inches(0.14) if eyebrow else Inches(0.22),
            Inches(11.9),
            Inches(0.6),
            anchor=MSO_ANCHOR.MIDDLE,
        )
        frame = box.text_frame
    if eyebrow:
        p0 = frame.paragraphs[0]
        run0 = p0.add_run()
        run0.text = eyebrow
        run0.font.size = Pt(11)
        run0.font.bold = True
        run0.font.name = BODY_FONT
        run0.font.color.rgb = RGBColor(0xA8, 0xBE, 0xDC)
        p = frame.add_paragraph()
    else:
        p = frame.paragraphs[0]
    run = p.add_run()
    run.text = text
    run.font.size = Pt(26)
    run.font.bold = True
    run.font.name = BODY_FONT
    run.font.color.rgb = WHITE
    p.alignment = PP_ALIGN.LEFT
    if eyebrow:
        p0.alignment = PP_ALIGN.LEFT
    if placeholder is not None:
        _bring_to_front(slide, placeholder)


def _footer(slide, number: int) -> None:
    left = _textbox(slide, BODY_LEFT, Inches(7.08), Inches(7.4), Inches(0.28))
    lp = left.text_frame.paragraphs[0]
    lr = lp.add_run()
    lr.text = "Autonomous AI Code Reviewer & PR Assistant"
    lr.font.size = Pt(9)
    lr.font.name = BODY_FONT
    lr.font.color.rgb = MUTED
    right = _textbox(slide, Inches(11.2), Inches(7.08), Inches(1.5), Inches(0.28))
    rp = right.text_frame.paragraphs[0]
    rp.alignment = PP_ALIGN.RIGHT
    rr = rp.add_run()
    rr.text = str(number)
    rr.font.size = Pt(9)
    rr.font.name = BODY_FONT
    rr.font.color.rgb = MUTED


def _bullets(slide, bullets, left, top, width, height, size: int = 20) -> None:
    box = _textbox(slide, left, top, width, height)
    frame = box.text_frame
    first = True
    for level, text in bullets:
        p = frame.paragraphs[0] if first else frame.add_paragraph()
        first = False
        p.level = level
        p.space_after = Pt(14 if level == 0 else 8)
        p.line_spacing = 1.0
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = ("- " if level == 1 else "") + text
        run.font.size = Pt(size if level == 0 else size - 2)
        run.font.name = BODY_FONT
        run.font.color.rgb = INK
    # accent square bullets are drawn as text prefixes only; keep the frame tight
    return box


def _mono(slide, text: str, left, top, width, height, fill=PALE, caption: str | None = None):
    """Draw a monospaced block, shrinking the font until it fits the box."""
    pad = Inches(0.14)
    inner_w_pt = (width - 2 * pad) / 914400 * 72
    inner_h_pt = (height - 2 * pad) / 914400 * 72
    lines = text.rstrip("\n").split("\n")
    widest = max(len(line) for line in lines) or 1

    size = 4.0
    probe = 16.0
    while probe >= 4.0:
        # Consolas advance width is ~0.55 em; line height ~1.2 em.
        if lines_len_ok(lines, widest, probe, inner_w_pt, inner_h_pt):
            size = probe
            break
        probe -= 0.25

    box = _rect(slide, left, top, width, height, fill, ACCENT_SOFT)
    frame = box.text_frame
    frame.word_wrap = False
    frame.margin_left = pad
    frame.margin_right = pad
    frame.margin_top = pad
    frame.margin_bottom = pad
    frame.vertical_anchor = MSO_ANCHOR.TOP
    # one paragraph per line so line spacing and wrapping stay predictable
    for i, line in enumerate(lines):
        para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        para.line_spacing = 1.0
        para.space_after = Pt(0)
        para.space_before = Pt(0)
        para.alignment = PP_ALIGN.LEFT
        r = para.add_run()
        r.text = line if line else " "
        r.font.size = Pt(size)
        r.font.name = MONO_FONT
        r.font.color.rgb = INK
    if caption:
        cap = _textbox(
            slide, left, top + height + Inches(0.06), width, Inches(0.3)
        )
        cp = cap.text_frame.paragraphs[0]
        cr = cp.add_run()
        cr.text = caption
        cr.font.size = Pt(11)
        cr.font.name = BODY_FONT
        cr.font.color.rgb = MUTED
    return size


def lines_len_ok(lines, widest, pt, inner_w_pt, inner_h_pt) -> bool:
    width_needed = widest * pt * 0.55
    height_needed = len(lines) * pt * 1.22
    return width_needed <= inner_w_pt * 0.99 and height_needed <= inner_h_pt * 0.99


def _table(slide, spec: dict, top, left=BODY_LEFT) -> Emu:
    header = spec["header"]
    rows = spec["rows"]
    widths = spec["widths"]
    row_h = Inches(0.42 if len(header) == 3 else 0.5)
    n_rows = len(rows) + 1
    total_w = Inches(sum(widths))
    shape = slide.shapes.add_table(n_rows, len(header), left, top, total_w, row_h * n_rows)
    table = shape.table
    for i, w in enumerate(widths):
        table.columns[i].width = Inches(w)
    for r in range(n_rows):
        table.rows[r].height = row_h

    def fill_cell(cell, text, bold=False, size=12, colour=INK, bg=None):
        cell.margin_left = Inches(0.09)
        cell.margin_right = Inches(0.09)
        cell.margin_top = Inches(0.03)
        cell.margin_bottom = Inches(0.03)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        if bg is not None:
            cell.fill.solid()
            cell.fill.fore_color.rgb = bg
        frame = cell.text_frame
        frame.word_wrap = True
        p = frame.paragraphs[0]
        p.space_after = Pt(0)
        p.line_spacing = 1.0
        run = p.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.name = BODY_FONT
        run.font.color.rgb = colour

    for c, text in enumerate(header):
        fill_cell(table.cell(0, c), text, bold=True, size=12, colour=WHITE, bg=ACCENT)
    for r, row in enumerate(rows, start=1):
        is_total = row[0].lower() in ("total",)
        bg = PALE if (r % 2 == 0 or is_total) else WHITE
        for c, text in enumerate(row):
            fill_cell(
                table.cell(r, c),
                text,
                bold=(c == 0 or is_total),
                size=12,
                colour=INK,
                bg=bg,
            )
    return top + row_h * n_rows


# --------------------------------------------------------------------------- #
# Slide renderers
# --------------------------------------------------------------------------- #


def render_title(slide, spec: dict) -> None:
    _rect(slide, 0, 0, SLIDE_W, Inches(4.35), ACCENT)
    _rect(slide, 0, Inches(4.35), SLIDE_W, Emu(int(Inches(0.06))), ACCENT_SOFT)

    placeholder = slide.shapes.title
    if placeholder is not None:
        placeholder.left = Inches(0.9)
        placeholder.top = Inches(1.5)
        placeholder.width = Inches(11.5)
        placeholder.height = Inches(1.9)
        frame = placeholder.text_frame
        frame.word_wrap = True
        frame.vertical_anchor = MSO_ANCHOR.TOP
        frame.margin_left = 0
        frame.margin_right = 0
        frame.margin_top = 0
        frame.margin_bottom = 0
    else:
        box = _textbox(slide, Inches(0.9), Inches(1.5), Inches(11.5), Inches(1.9))
        frame = box.text_frame
    p = frame.paragraphs[0]
    p.line_spacing = 1.0
    p.alignment = PP_ALIGN.LEFT
    run = p.add_run()
    run.text = spec["title"]
    run.font.size = Pt(44)
    run.font.bold = True
    run.font.name = BODY_FONT
    run.font.color.rgb = WHITE
    if placeholder is not None:
        _bring_to_front(slide, placeholder)

    sub = _textbox(slide, Inches(0.9), Inches(3.35), Inches(11.2), Inches(0.8))
    sp = sub.text_frame.paragraphs[0]
    sp.alignment = PP_ALIGN.LEFT
    sr = sp.add_run()
    sr.text = spec["subtitle"]
    sr.font.size = Pt(18)
    sr.font.name = BODY_FONT
    sr.font.color.rgb = RGBColor(0xC9, 0xD8, 0xEC)

    stack = _textbox(slide, Inches(0.9), Inches(4.75), Inches(11.6), Inches(0.5))
    stp = stack.text_frame.paragraphs[0]
    strun = stp.add_run()
    strun.text = spec["stack"]
    strun.font.size = Pt(13)
    strun.font.bold = True
    strun.font.name = BODY_FONT
    strun.font.color.rgb = ACCENT

    lines = _textbox(slide, Inches(0.9), Inches(5.55), Inches(11.2), Inches(1.4))
    lf = lines.text_frame
    for i, text in enumerate(spec["lines"]):
        para = lf.paragraphs[0] if i == 0 else lf.add_paragraph()
        para.space_after = Pt(6)
        r = para.add_run()
        r.text = text
        r.font.size = Pt(14)
        r.font.name = BODY_FONT
        r.font.color.rgb = MUTED


def render_bullets(slide, spec: dict) -> None:
    size = 22 if len(spec["bullets"]) <= 5 else 20
    _bullets(slide, spec["bullets"], BODY_LEFT, Inches(1.45), BODY_W, Inches(4.9), size=size)
    footnote = spec.get("footnote")
    if footnote:
        box = _textbox(slide, BODY_LEFT, Inches(6.35), BODY_W, Inches(0.7))
        frame = box.text_frame
        frame.word_wrap = True
        para = frame.paragraphs[0]
        para.alignment = PP_ALIGN.LEFT
        para.line_spacing = 1.05
        run = para.add_run()
        run.text = footnote
        run.font.size = Pt(13)
        run.font.italic = True
        run.font.name = BODY_FONT
        run.font.color.rgb = MUTED


def render_placeholders(slide, spec: dict) -> None:
    _bullets(slide, spec["bullets"], BODY_LEFT, Inches(1.4), BODY_W, Inches(3.5), size=18)
    mono_text = "\n".join(spec["placeholders"])
    _mono(
        slide,
        mono_text,
        BODY_LEFT,
        Inches(5.12),
        BODY_W,
        Inches(1.55),
        caption="Placeholders, not estimates. Fill from benchmarks/out after a labelled run.",
    )


def render_diagram(slide, spec: dict) -> None:
    diagram = load_diagram()
    _mono(
        slide,
        diagram,
        BODY_LEFT,
        Inches(1.12),
        Inches(6.3),
        Inches(5.82),
    )
    _bullets(
        slide,
        spec["bullets"],
        Inches(7.2),
        Inches(1.3),
        Inches(5.5),
        Inches(4.4),
        size=17,
    )
    cap = _textbox(slide, Inches(7.2), Inches(5.85), Inches(5.5), Inches(0.9))
    cp = cap.text_frame.paragraphs[0]
    cp.line_spacing = 1.05
    cr = cp.add_run()
    cr.text = spec["mono_caption"]
    cr.font.size = Pt(12)
    cr.font.italic = True
    cr.font.name = BODY_FONT
    cr.font.color.rgb = MUTED


def render_code(slide, spec: dict) -> None:
    _bullets(slide, spec["bullets"], BODY_LEFT, Inches(1.35), BODY_W, Inches(2.35), size=18)
    _mono(
        slide,
        spec["mono"],
        BODY_LEFT,
        Inches(3.72),
        BODY_W,
        Inches(2.85),
        caption="Exact commands from DEMO.md section 2 (variant A). Nothing here needs a key.",
    )


def render_table(slide, spec: dict) -> None:
    bottom = _table(slide, spec["table"], Inches(1.28))
    note = spec.get("note_after_table")
    if note:
        box = _textbox(
            slide, BODY_LEFT, bottom + Inches(0.18), BODY_W, Inches(0.6)
        )
        p = box.text_frame.paragraphs[0]
        r = p.add_run()
        r.text = note
        r.font.size = Pt(12)
        r.font.italic = True
        r.font.name = BODY_FONT
        r.font.color.rgb = MUTED


RENDERERS = {
    "title": render_title,
    "bullets": render_bullets,
    "diagram": render_diagram,
    "code": render_code,
    "table": render_table,
    "placeholders": render_placeholders,
}


# --------------------------------------------------------------------------- #
# Source data pulled verbatim from the repository
# --------------------------------------------------------------------------- #


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_diagram() -> str:
    """Return the ASCII diagram from ARCHITECTURE.md, unmodified."""
    path = repo_root() / "ARCHITECTURE.md"
    text = path.read_text(encoding="utf-8")
    section = text.split("## 1. System diagram", 1)[1]
    section = section.split("Two properties", 1)[0]
    block = re.search(r"```\n(.*?)```", section, re.S)
    if block is None:
        raise SystemExit("no fenced diagram found in ARCHITECTURE.md section 1")
    return block.group(1).rstrip("\n")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def _freeze_archive(path: Path) -> None:
    """Rewrite the OPC zip with fixed timestamps so two builds are byte-identical.

    python-pptx stamps each zip entry with the wall clock; the archive content is
    already deterministic, so only the entry headers need pinning.
    """
    with zipfile.ZipFile(path) as src:
        parts = sorted(
            ((info.filename, src.read(info.filename)) for info in src.infolist()),
            key=lambda pair: pair[0],
        )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as dst:
        for name, data in parts:
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 14, 9, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            dst.writestr(info, data)


def build(defs: list[dict] = SLIDES, out_path: Path | None = None) -> Path:
    validate(defs)
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    for i, spec in enumerate(defs, start=1):
        slide = _blank(prs)
        kind = spec["kind"]
        if kind == "title":
            render_title(slide, spec)
        else:
            _title_bar(slide, spec["title"], spec.get("eyebrow"))
            RENDERERS[kind](slide, spec)
            _footer(slide, i)

        notes_frame = slide.notes_slide.notes_text_frame
        notes_frame.text = spec["notes"]

    props = prs.core_properties
    props.title = "Autonomous AI Code Reviewer & PR Assistant"
    props.subject = "MCA final-semester project overview"
    props.author = "docs/presentation/build_deck.py"
    props.last_modified_by = "docs/presentation/build_deck.py"
    props.revision = 1
    props.created = FIXED_STAMP
    props.modified = FIXED_STAMP

    target = out_path or (Path(__file__).resolve().parent / "project_overview.pptx")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".pptx.tmp")
    prs.save(str(tmp))
    _freeze_archive(tmp)
    os.replace(tmp, target)
    return target


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0]) if argv else None
    target = build(out_path=out)
    prs = Presentation(str(target))
    print(f"wrote {target} ({target.stat().st_size} bytes, {len(prs.slides)} slides)")
    for i, slide in enumerate(prs.slides, start=1):
        title = slide.shapes.title.text if slide.shapes.title else "-"
        notes = slide.notes_slide.notes_text_frame.text
        print(f"{i:>2}  {title[:52]:<52}  notes: {len(notes)} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
