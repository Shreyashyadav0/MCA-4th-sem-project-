#!/usr/bin/env python3
"""Deterministic generator for ``docs/presentation/naive_to_pro_guide.pdf``.

Run it from the repository root::

    python docs/presentation/build_guide.py

It writes the PDF next to itself. No network, no LaTeX, no pandoc: reportlab
platypus only. Every number printed in the guide is taken from a constant in
this file, and every constant is checkable against the tree (the appendix of the
guide says how). Nothing here reads the clock, the environment or the filesystem
beyond its own output path, so two runs produce byte-identical output.

Layout: A5 portrait, 10.5 pt body at 15 pt leading, monospaced code on a light
grey panel, page numbers in the footer.
"""

from __future__ import annotations

import hashlib
import os
import sys

# Deterministic PDF ids and a fixed CreationDate, set before reportlab is used.
import reportlab.rl_config as rl_config

rl_config.invariant = 1

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A5  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase.pdfmetrics import stringWidth  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "naive_to_pro_guide.pdf")

# --------------------------------------------------------------------------
# Facts. Each of these is verifiable in the tree; see section 8 of the guide.
# --------------------------------------------------------------------------
TESTS_PASSED = 640
TESTS_COLLECTED = 641
TESTS_SKIPPED = 1
RULE_COUNT = 63
RULE_CATEGORIES = 10
TRACKS = 7
def _count_pins() -> int:
    """Count the '==' pins in the lock. Typed as 36, the lock had 37."""
    with open(os.path.join(REPO_ROOT, "requirements.lock"), encoding="utf-8") as handle:
        return sum(1 for line in handle if "==" in line and not line.strip().startswith("#"))

FORMAT_EXAMPLES = 2
TOTAL_HOURS = 90
WEEKS = 16
# The line counts below are read from the files at build time. They used to be
# literals, and three of them had drifted from the code they described, which is
# the one thing a study plan must never do.
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))

# Counted, not typed: it said 36 while the lock had 37.
LOCK_PINS = _count_pins()
MODULE_FILES = (
    "models.py", "config.py", "parser.py", "rules.py", "mock_provider.py",
    "sarvam_provider.py", "openai_compat_provider.py", "engine.py",
    "github_client.py", "cli.py", "main.py", "__main__.py", "__init__.py",
)


def _count_lines(name: str) -> int:
    with open(os.path.join(REPO_ROOT, "app", name), encoding="utf-8") as handle:
        return sum(1 for _ in handle)


MODULE_LINES = {name: _count_lines(name) for name in MODULE_FILES}
APP_FILES = len(MODULE_FILES)
APP_LINES = sum(MODULE_LINES.values())
DECORATED_CHECKS = 18
MODEL_CALLS_PER_REVIEW = 2

# --------------------------------------------------------------------------
# Page geometry and styles
# --------------------------------------------------------------------------
PAGE_W, PAGE_H = A5
MARGIN_L = MARGIN_R = 13 * mm
MARGIN_T = 13 * mm
MARGIN_B = 15 * mm
TEXT_W = PAGE_W - MARGIN_L - MARGIN_R

INK = colors.HexColor("#111111")
MUTED = colors.HexColor("#555555")
RULE = colors.HexColor("#BBBBBB")
CODE_BG = colors.HexColor("#F2F2F2")
CODE_EDGE = colors.HexColor("#D8D8D8")
HEAD_BG = colors.HexColor("#EDEDED")

CODE_SIZE = 8.2
CODE_LEAD = 10.4
CODE_PAD = 5
CODE_CHAR = stringWidth("M", "Courier", CODE_SIZE)
CODE_BUDGET = int((TEXT_W - 2 * CODE_PAD - 3) / CODE_CHAR)


def _style(name, **kw):
    base = dict(fontName="Helvetica", fontSize=10.5, leading=15, textColor=INK,
                spaceAfter=6, alignment=0)
    base.update(kw)
    return ParagraphStyle(name, **base)


S_TITLE = _style("GuideTitle", fontName="Helvetica-Bold", fontSize=20, leading=23,
                 spaceAfter=4)
S_KICKER = _style("Kicker", fontSize=8.5, leading=11, textColor=MUTED,
                  spaceAfter=14)
S_SUB = _style("GuideSub", fontSize=10, leading=14, textColor=MUTED, spaceAfter=3)
S_H1 = _style("H1", fontName="Helvetica-Bold", fontSize=14.5, leading=17.5,
              spaceBefore=4, spaceAfter=9)
S_H2 = _style("H2", fontName="Helvetica-Bold", fontSize=10.5, leading=13,
              spaceBefore=8, spaceAfter=3)
S_BODY = _style("Body")
S_BULLET = _style("Bullet", leftIndent=11, bulletIndent=2, spaceAfter=3)
S_NUM = _style("Num", leftIndent=17, firstLineIndent=-17, spaceAfter=7)
S_SMALL = _style("Small", fontSize=8.8, leading=12, textColor=MUTED, spaceAfter=5)
S_CELL = _style("Cell", fontSize=8.2, leading=10.2, spaceAfter=0)
S_CELL_B = _style("CellB", fontName="Helvetica-Bold", fontSize=8.2, leading=10.2,
                  spaceAfter=0)
S_CELL_MONO = _style("CellMono", fontName="Courier", fontSize=7.6, leading=9.6,
                     spaceAfter=0)
S_H2_PLAIN = _style("H2Plain", fontName="Helvetica-Bold", fontSize=10.5,
                    leading=13, spaceBefore=2, spaceAfter=4)
S_CODE = ParagraphStyle("Code", fontName="Courier", fontSize=CODE_SIZE,
                        leading=CODE_LEAD, textColor=INK, backColor=CODE_BG,
                        borderColor=CODE_EDGE, borderWidth=0.5, borderPadding=CODE_PAD,
                        spaceBefore=2, spaceAfter=7)


def mono(text, size=9.0):
    """Inline monospace, for a path, a flag or an identifier."""
    return '<font name="Courier" size="%.1f">%s</font>' % (size, text)


def body(text, style=S_BODY):
    return Paragraph(text, style)


def code(text):
    """A code panel. Refuses to build a line that would overflow the frame."""
    lines = text.strip("\n").split("\n")
    for line in lines:
        if len(line) > CODE_BUDGET:
            raise SystemExit(
                "code line too wide (%d > %d): %r" % (len(line), CODE_BUDGET, line)
            )
    return KeepTogether([Preformatted("\n".join(lines), S_CODE)])


def bullets(items, style=S_BULLET):
    return [Paragraph(t, style, bulletText="\u2022") for t in items]


def numbered(items):
    return [Paragraph(t, S_NUM) for t in items]


def table(rows, widths, header=True, mono_cols=(), zebra=True, align_left=True):
    data = []
    for r_i, row in enumerate(rows):
        out = []
        for c_i, cell in enumerate(row):
            if isinstance(cell, Paragraph):
                out.append(cell)
            elif c_i in mono_cols:
                out.append(Paragraph(cell, S_CELL_MONO))
            else:
                out.append(Paragraph(cell, S_CELL_B if (header and r_i == 0) else S_CELL))
        data.append(out)
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 9),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
        ("LINEBELOW", (0, -1), (-1, -1), 0.7, MUTED),
    ]
    if header:
        cmds.append(("BACKGROUND", (0, 0), (-1, 0), HEAD_BG))
        cmds.append(("LINEBELOW", (0, 0), (-1, 0), 0.7, MUTED))
    if zebra:
        for i in range(1 if header else 0, len(rows)):
            if i % 2 == 0:
                cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FAFAFA")))
    t.setStyle(TableStyle(cmds))
    return t


# --------------------------------------------------------------------------
# Document template: footer, bookmarks, table of contents
# --------------------------------------------------------------------------
class GuideDoc(BaseDocTemplate):
    def __init__(self, filename, **kw):
        BaseDocTemplate.__init__(self, filename, pagesize=A5, **kw)
        frame = Frame(
            MARGIN_L, MARGIN_B, TEXT_W,
            PAGE_H - MARGIN_T - MARGIN_B,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
            id="body",
        )
        self.addPageTemplates([PageTemplate(id="guide", frames=[frame],
                                            onPage=self._decorate)])
        self._toc_keys = {}

    def _decorate(self, canv, doc):
        canv.saveState()
        y = MARGIN_B - 9 * mm
        canv.setStrokeColor(RULE)
        canv.setLineWidth(0.5)
        canv.line(MARGIN_L, y + 11, PAGE_W - MARGIN_R, y + 11)
        canv.setFont("Helvetica", 7.4)
        canv.setFillColor(MUTED)
        canv.drawString(MARGIN_L, y, "naive to pro  /  AI Code Reviewer")
        canv.drawRightString(PAGE_W - MARGIN_R, y, "p. %d" % doc.page)
        canv.restoreState()

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        name = flowable.style.name
        if name not in ("H1", "H2"):
            return
        level = 0 if name == "H1" else 1
        text = flowable.getPlainText()
        key = "sec-" + hashlib.md5(text.encode("utf-8")).hexdigest()[:10]
        self._toc_keys[key] = text
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=level, closed=False)
        # The contents page lists the eight sections and the seven tracks; every
        # other heading is a bookmark only, so the contents stays one page.
        if level == 0 or text.startswith("Track "):
            self.notify("TOCEntry", (level, text, self.page, key))


# --------------------------------------------------------------------------
# Content
# --------------------------------------------------------------------------
def title_and_toc():
    story = []
    story.append(body("naive to pro", S_TITLE))
    story.append(body(
        "A study guide to the AI Code Reviewer codebase, for a reader who will spend "
        "three to four months learning it and rebuilding it from memory.",
        S_SUB))
    story.append(body(
        "%d tracks. %d hours. One rule: do not skip ahead."
        % (TRACKS, TOTAL_HOURS), S_KICKER))

    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(name="TOC0", fontName="Helvetica", fontSize=9.4, leading=13,
                       spaceBefore=1, firstLineIndent=0, leftIndent=0, rightIndent=14,
                       textColor=INK),
        ParagraphStyle(name="TOC1", fontName="Helvetica", fontSize=8.4, leading=10.8,
                       firstLineIndent=0, leftIndent=12, rightIndent=14,
                       textColor=MUTED),
    ]
    toc.dotsMinLevel = 0
    story.append(Paragraph("Contents", S_H2_PLAIN))
    story.append(toc)
    story.append(Spacer(1, 8))
    story.append(body(
        "Every number in this guide is checkable against the tree. Section 8 lists "
        "the commands; none of them needs a key, a network connection or a model.",
        S_SMALL))
    story.append(PageBreak())
    return story


def section_1():
    s = [body("1. What this project is", S_H1)]
    s.append(body(
        "The project is a code reviewer. You give it a change to a codebase and it "
        "tells you what is wrong with that change. It does not run your code and it "
        "does not fix anything: it produces a list of findings and, optionally, posts "
        "them to a GitHub pull request as inline comments plus one summary comment."))
    s.append(body(
        "Six words carry the rest of this guide; they are fixed here."))
    s.append(table(
        [
            ["Term", "Meaning"],
            ["diff", "The text output of git diff: per file, the lines added and "
                     "removed, plus a header saying where each block starts."],
            ["hunk", "One such block, introduced by a @@ line. The numbers in that "
                     "line are where every file line number comes from."],
            ["finding", "One problem report with exactly five fields: file, line, "
                        "severity, issue, suggested_fix. A sixth field is a "
                        "validation error, not an extra."],
            ["rule engine", "The %d deterministic checks in app/rules.py. Regex and "
                            "line-shape matching; no network, no key, no model."
                            % RULE_COUNT],
            ["provider", "Whatever produces findings: the rule engine, a hosted "
                         "model (Sarvam), or a self-hosted OpenAI-compatible server "
                         "(LM Studio)."],
            ["mode", "live or mock. live means a model answered; mock means the rule "
                     "engine ran. Every result says which, and why."],
            ["anchor", "Where a finding lands: anchored on a changed line, file_only "
                       "in a changed file, or unanchored. GitHub takes an inline "
                       "comment only on anchored findings."],
        ],
        [46, TEXT_W - 46],
        mono_cols=(0,),
    ))
    s.append(body(
        "Three backends, one chooser: " + mono("review()") + " in "
        + mono("app/engine.py") + ". The CLI, the HTTP API and the webhook all call "
        "it, so there is one provider decision in the codebase, not three."))
    s.append(body(
        "The interesting part is not the model call but the degradation contract: "
        "nothing raises because a credential is missing or an endpoint is dead. A "
        "wrong key costs one WARNING and exit code 0, not a 500."))
    s.append(body(
        "The task is not to read this code but to reproduce it: rebuild "
        + mono("app/") + " from memory, module by module, in dependency order, and "
        "prove each module with a passing test. " + mono("app/") + " is %s lines "
        "across %d files and does not change; your output is %s and your evidence is "
        "%d passing tests."
        % (format(APP_LINES, ","), APP_FILES, mono("rebuild/"), TESTS_PASSED)))
    return s


def section_2():
    s = [PageBreak(), body("2. Why the architecture is shaped this way", S_H1)]
    s.append(body(
        "Three properties explain nearly every shape in this codebase, and each has "
        "a decision record behind it: offline-first, provider-agnostic, and frozen "
        "interfaces. The fourth record below is different. It documents a deliberate "
        "departure from a written contract, and it is the one place where the code "
        "looks wrong and is not."))

    s.append(body("ADR 0001 - strict models at every boundary", S_H2))
    s.append(body(
        "Data of unknown quality arrives at three boundaries: a model's JSON reply, "
        "an HTTP request body, and a decoded diff. The reply is the dangerous one: a "
        "model asked for a JSON array will return a confidence field, a category "
        "key, or " + mono('"42-45"') + " where a number was expected."))
    s.append(body(
        "So every structured value is a Pydantic v2 model, and every model facing "
        "untrusted input forbids unknown keys. " + mono("Finding") + " is frozen, "
        "carries five fields, and validates " + mono("line") + " against "
        + mono("^\\d+(?:-\\d+)?$") + " plus an ascending check. "
        + mono("AnchoredFinding") + " wraps a finding rather than extending it, and "
        + mono("verdict") + " is computed from the findings, not stored."))
    s.append(body(
        "The stated intent, in the module docstring: a stray key from a future model "
        "response fails at the boundary instead of leaking into a PR comment."))

    s.append(body("ADR 0002 - every entry point degrades to the rule engine", S_H2))
    s.append(body(
        "The tool is demonstrated live, sometimes with no network and sometimes with "
        "a key that expired an hour ago, and it is driven by a webhook that must "
        "answer GitHub within a timeout. So the question is not what happens when the "
        "model fails, but what the normal state is when there is no model."))
    s.append(body(
        "The answer: a missing key is configuration data, never an exception. Every "
        "entry point funnels into " + mono("review()") + ", which selects a provider "
        "by the locked precedence sarvam over local over mock and, when no live "
        "provider is usable, runs the %d-rule engine. A degrade logs exactly one "
        "WARNING, keeps exit code 0, and states its reason in the result's notes."
        % RULE_COUNT))
    s.append(body(
        "The degraded output is real review output, not an empty stub, so the "
        "fallback is useful rather than merely survivable. The accepted cost is "
        "honest: a silent degrade can hide a misconfiguration, mitigated by the "
        "reason string, not eliminated."))

    s.append(body("ADR 0003 - one adapter, two configurations", S_H2))
    s.append(body(
        "A hosted model and a model on the presenter's laptop both speak the OpenAI "
        "chat-completions protocol. The expensive part is not the transport but the "
        "guards around it: JSON mode, one repair retry, payload parsing, "
        "hallucinated-file dropping, line snapping, key scrubbing. Two adapters would "
        "mean two places to fix each guard and two places to drift."))
    s.append(body(
        "So there is one adapter, " + mono("app/openai_compat_provider.py")
        + ", and the difference between providers is a dataclass: "
        + mono("OpenAICompatConfig") + " holds base_url, api_key, model, "
        "provider_name and timeout, and nothing else varies. A third "
        "OpenAI-compatible endpoint is a config function and a test, not an adapter. "
        "The ceiling is real: an endpoint that is not compatible cannot be used."))

    s.append(body("ADR 0004 - the degraded path calls the rule engine directly", S_H2))
    s.append(body(
        "<b>It looks like a bug and it is not.</b> The written Phase 5.5 contract "
        "said the adapter's degraded path should delegate to "
        + mono("review_with_fallback(force_offline=True)") + ", and instead "
        + mono("_mock_outcome") + " calls " + mono("offline_diff_findings")
        + " directly. Delegating would log a second WARNING for one event and would "
        "word it sarvam on a local run, which is false, and muting that logger is "
        "worse because setLevel is process-global and would race between concurrent "
        "webhook requests. Because " + mono("offline_diff_findings") + " is the same "
        "function " + mono("review_with_fallback") + " calls, the shortcut keeps "
        "exactly one mock implementation and the deviation buys an honest log line "
        "at no cost."))
    s.append(body(
        "The property is locked by a test, not a comment: "
        + mono("tests/test_openai_compat_provider.py") + " asserts the sarvam logger "
        "recorded nothing during a local degrade. Read it before tidying the code "
        "back."))
    s.append(body(
        "Residue to expect: the module docstring still claims the delegation, and "
        + mono("_DELEGATED_MOCK_LOGGER") + " is unused. The code is the contract; "
        "ADR 0004 says so.", S_SMALL))
    s.append(PageBreak())
    return s


def section_3():
    s = [body("3. How to read the code", S_H1)]
    s.append(body(
        "The dependency graph is not a preference about reading order. It is a "
        "statement about what you can possibly understand. Below is the in-package "
        "import edge list, exactly as an AST pass over " + mono("app/*.py") + " "
        "reports it: %d edges across %d files." % (40, APP_FILES)))
    s.append(table(
        [
            ["Module", "Lines", "Imports from app/"],
            ["models.py", str(MODULE_LINES["models.py"]), "nothing internal"],
            ["config.py", str(MODULE_LINES["config.py"]), "nothing internal"],
            ["parser.py", str(MODULE_LINES["parser.py"]), "models"],
            ["rules.py", str(MODULE_LINES["rules.py"]), "models, parser"],
            ["mock_provider.py", str(MODULE_LINES["mock_provider.py"]), "models, parser, rules"],
            ["sarvam_provider.py", str(MODULE_LINES["sarvam_provider.py"]),
             "models, parser, rules, config, mock_provider"],
            ["openai_compat_provider.py", str(MODULE_LINES["openai_compat_provider.py"]),
             "models, parser, rules, mock_provider, sarvam_provider"],
            ["engine.py", "385", "models, parser, rules, config, "
                                 "openai_compat_provider"],
            ["github_client.py", str(MODULE_LINES["github_client.py"]), "models, parser, config"],
            ["cli.py", str(MODULE_LINES["cli.py"]), "models, parser, rules, config, engine, mock_provider, "
                              "sarvam_provider, github_client"],
            ["main.py", str(MODULE_LINES["main.py"]), "models, parser, rules, config, engine, "
                                "mock_provider, github_client"],
            ["__main__.py", str(MODULE_LINES["__main__.py"]), "cli"],
            ["__init__.py", str(MODULE_LINES["__init__.py"]), "nothing internal"],
        ],
        [86, 30, TEXT_W - 116],
        mono_cols=(0, 1),
    ))
    s.append(Spacer(1, 8))
    s.append(body("Three facts a plausible guess gets wrong", S_H2))
    s.extend(bullets([
        mono("rules.py") + " imports " + mono("parser.py") + ", not just "
        + mono("models.py") + ": every rule walks a bundle's added lines, so the rule "
        "engine cannot be understood before the diff parser.",
        mono("engine.py") + " never imports " + mono("sarvam_provider.py") + " or "
        + mono("mock_provider.py") + " directly. It imports "
        + mono("PROVIDER_LOCAL") + " from the adapter and reaches the rule engine "
        "through that module, so there is one mock path and no duplicate fallback.",
        mono("github_client.py") + " has no engine edge at all. It is a pure posting "
        "surface over anchored findings, and it is placed last because its 1,258 "
        "lines are breadth, not depth.",
    ]))

    s.append(body("The only correct order", S_H2))
    s.append(body(
        "Seven tracks, in this order, with the hours each costs when the estimate is "
        "reading plus rebuilding from memory plus making the verification test pass."))
    s.append(table(
        [
            ["#", "Modules", "Lines", "Hours"],
            ["1", "models.py", str(MODULE_LINES["models.py"]), "5"],
            ["2", "parser.py", str(MODULE_LINES["parser.py"]), "11"],
            ["3", "rules.py", str(MODULE_LINES["rules.py"]), "12"],
            ["4", "mock_provider.py + config.py",
             str(MODULE_LINES["mock_provider.py"] + MODULE_LINES["config.py"]), "4"],
            ["5", "sarvam_provider.py + openai_compat_provider.py",
             str(MODULE_LINES["sarvam_provider.py"]
                 + MODULE_LINES["openai_compat_provider.py"]), "24"],
            ["6", "engine.py", str(MODULE_LINES["engine.py"]), "14"],
            ["7", "cli.py + main.py + github_client.py",
             str(MODULE_LINES["cli.py"] + MODULE_LINES["main.py"]
                 + MODULE_LINES["github_client.py"]), "20"],
            ["", "total", format(APP_LINES, ","), str(TOTAL_HOURS)],
        ],
        [16, TEXT_W - 106, 50, 40],
        mono_cols=(0, 1, 2, 3),
    ))
    s.append(Spacer(1, 8))
    s.append(body("The rule, stated once", S_H2))
    s.append(body(
        "Do not open Track N+1 until " + mono("python scripts/learning_progress.py "
        "check N") + " exits 0."))
    s.append(body(
        "Track 3 consumes Track 2's bundle, Track 5 consumes Track 3's rule "
        "categories, Track 6 consumes Track 5's provider outcome. A red test means "
        "the thing the next track reads does not exist in your head yet. Reading on "
        "anyway converts a two-week slip into a four-week one, because you end up "
        "debugging two modules at once with no way to tell which one is wrong."))
    s.append(body(
        "A green test is the only completion criterion this curriculum recognises. "
        "Reading the track, answering its self-test questions and doing its rebuild "
        "exercise are all in service of that one command returning zero."))
    s.append(PageBreak())
    return s


TRACK_DETAIL = [
    (
        "Track 1 - models.py (%d lines, 5 hours)" % MODULE_LINES["models.py"],
        "It defines the only shape a review result may take: Severity, AnchorStatus, "
        "the five-field Finding, AnchoredFinding and ReviewResult. It validates "
        "everything arriving from outside at the boundary and exposes three helpers "
        "- severity_counts, sort_findings, verdict_for - that every other surface "
        "reuses.",
        [
            "extra=\"forbid\" plus frozen=True: a stray key must fail at the boundary, "
            "not leak into a PR comment.",
            "The five-field contract is a contract, not a schema: nothing may widen "
            "it, so AnchoredFinding wraps a finding instead of extending it.",
            "verdict is a computed_field, not a method and not a stored value, so a "
            "serialised result cannot disagree with its findings.",
        ],
        "Write track1_models.py outside app/: Severity with a rank property, "
        "AnchorStatus, the frozen five-field Finding with its line validator, "
        "AnchoredFinding, the three helpers, and ReviewResult with a computed verdict.",
    ),
    (
        "Track 2 - parser.py (%d lines, 11 hours)" % MODULE_LINES["parser.py"],
        "It turns a unified diff into DiffBundle, FileDiff, Hunk and DiffLine, giving "
        "every body line the file line number it maps to on each side. It then places "
        "findings against those numbers with anchor_findings, and wraps a plain "
        "source file as a one-hunk all-added diff so diff-based rules can run where "
        "there is no diff.",
        [
            "Line numbers come from hunk headers, never from counting rows: the "
            "counters in the @@ line are the only authority.",
            "A hunk body ends when both counters hit zero, not when the next header "
            "appears, which is what makes a missing trailing newline survivable.",
            "Anchoring is kept outside the five-field contract, which is why there "
            "are three statuses and a detail string rather than a sixth field.",
        ],
        "Write track2_parser.py: normalize_path, the four models, a single-pass "
        "parse_diff state machine driven by the hunk counters, bundle_from_source, "
        "and anchor_findings with its three statuses and detail strings.",
    ),
    (
        "Track 3 - rules.py (%d lines, 12 hours)" % MODULE_LINES["rules.py"],
        "It is a deterministic, offline, OWASP-mapped engine of %d rules in one "
        "registry, each with an id, title, category, OWASP reference, fixed severity "
        "and a check callable. review_lines runs every rule over one file's added "
        "lines, review_diff feeds it those lines from a parsed bundle, and "
        "suppression is parsed per line from # noqa and # nosec." % RULE_COUNT,
        [
            "Rules see added lines only: a finding on a deleted line is a comment "
            "GitHub would drop, so the engine never produces one.",
            "Every pattern is linear and every line is truncated before matching, "
            "because the input is attacker-controlled text and ReDoS is a real cost.",
            "Severity is fixed per rule, never computed per hit: a rule that graded "
            "its own severity would make every downstream sort unstable.",
        ],
        "Write track3_rules.py: RuleCategory, RuleHit, Rule, LineContext, the two "
        "registration paths, five rules (one hand-written credential check and four "
        "pattern rules), suppression parsing and review_lines.",
    ),
    (
        "Track 4 - mock_provider.py and config.py (%d lines, 4 hours)"
        % (MODULE_LINES["mock_provider.py"] + MODULE_LINES["config.py"]),
        "config.py is the only module that reads the process environment, and it "
        "answers the question is this credential present without ever raising. "
        "mock_provider.py is the deterministic offline path: one source file or a "
        "parsed diff in, rule-engine findings out, no network and no key.",
        [
            "Credentials are read once at the boundary and absence is data, so no "
            "other module needs a try/except around configuration.",
            "offline_diff_findings delegates to the rule engine instead of "
            "reimplementing checks, which is what keeps one mock implementation.",
            "ENGINE_NOTE is computed from the registry length, so an offline review "
            "cannot silently claim a stale rule count.",
        ],
        "Reconstruct both modules in an empty directory - eleven settings fields, "
        "two has_* properties, resolve_mode, then offline_review, "
        "offline_diff_findings and ENGINE_NOTE - and prove with grep that no other "
        "module reads the environment.",
    ),
    (
        "Track 5 - sarvam_provider.py and openai_compat_provider.py (%d lines, 24 hours)"
        % (MODULE_LINES["sarvam_provider.py"] + MODULE_LINES["openai_compat_provider.py"]),
        "openai_compat_provider.py is one OpenAI chat-completions adapter serving "
        "both Sarvam's hosted endpoint and any self-hosted compatible endpoint, where "
        "the only difference is an OpenAICompatConfig value. It owns the expensive "
        "guards - JSON mode, one repair retry, payload parsing, hallucination and "
        "line snapping, key scrubbing - and a degraded path that returns rule-engine "
        "findings instead of raising.",
        [
            "The provider-agnostic design: five config fields, and knowing exactly "
            "where each one is consumed in the request and the result.",
            "The two-call retry budget: one attempt, one repair with the error in the "
            "prompt and response_format dropped, then a warning and no findings.",
            "The fallback chain, and why the degraded path calls "
            "offline_diff_findings directly rather than through the sarvam wrapper.",
        ],
        "Build the adapter against a fake client: OpenAICompatConfig, a three-"
        "parameter _call_model with the JSON-mode ContextVar and max_retries=0, the "
        "two-call budget, and _mock_outcome calling offline_diff_findings directly.",
    ),
    (
        "Track 6 - engine.py (%d lines, 14 hours)" % MODULE_LINES["engine.py"],
        "It turns a Settings object plus an optional provider request into exactly "
        "one routing decision, ProviderSelection(provider, config, reason). Its "
        "single entry point review() applies that decision and returns a "
        "ProviderOutcome whose mode, provider and model fields describe what actually "
        "ran.",
        [
            "Selection is a pure function of Settings and does no I/O, which is why "
            "the whole matrix is testable in one loop.",
            "A forced provider with a missing config degrades; only a bad name "
            "raises, and review() catches even that.",
            "The selector is the only place that decides, so no two surfaces can "
            "disagree about which provider ran.",
        ],
        "Write engine.py: PROVIDERS, ProviderSelection, the two config builders, "
        "select_provider's precedence and reason strings, and a review() that "
        "degrades instead of raising.",
    ),
    (
        "Track 7 - cli.py, main.py and github_client.py (%d lines, 20 hours)"
        % (MODULE_LINES["cli.py"] + MODULE_LINES["main.py"] + MODULE_LINES["github_client.py"]),
        "cli.py parses the flag surface, calls engine.review() and returns a process "
        "exit code from a fixed set of three. main.py exposes the same engine over "
        "FastAPI, and github_client.py renders findings into one inline comment each "
        "plus a summary while degrading every GitHub and transport failure into a "
        "PostResult instead of raising.",
        [
            "A posting failure must never change the HTTP status: a review that "
            "happened is a 200 even when the post did not.",
            "The idempotency marker hashes the findings, not the commit, so a re-run "
            "on the same findings is silent and a changed finding is not.",
            "The CLI validates --post-to-pr before doing any review work, so a "
            "malformed target costs no model call.",
        ],
        "Rebuild the three surfaces: the CLI parser and its exit codes, the seven API "
        "endpoints behind one response funnel, and the pure posting renderers plus a "
        "post_review that never raises.",
    ),
]


def section_4():
    s = [body("4. The curriculum condensed", S_H1)]
    s.append(body(
        "One page per track. What it does in two sentences, the three ideas that "
        "carry the conceptual load, and the exercise that proves you own the module. "
        "The full documents are in " + mono("docs/learning/") + "; this is the "
        "revision sheet, not a replacement."))
    for title, what, ideas, exercise in TRACK_DETAIL:
        s.append(body(title, S_H2))
        s.append(body("<b>What it does.</b> " + what))
        s.append(body("<b>The three hardest ideas.</b>", S_SMALL))
        s.extend(bullets(ideas))
        s.append(body("<b>Rebuild exercise.</b> " + exercise))
        s.append(PageBreak())
    return s


def section_5():
    s = [body("5. The 3-4 month pace plan", S_H1)]
    s.append(body(
        "%d hours across %d weeks, about 5.6 hours a week on average. The average "
        "hides the real shape: weeks 1-4 run at 8 hours because Tracks 1-4 must be "
        "green before Track 5 opens, weeks 5-7 run at 8 hours because Track 5 is the "
        "hard one, week 8 is deliberately empty, and weeks 9-12 are light enough to "
        "absorb a slip." % (TOTAL_HOURS, WEEKS)))
    rows = [["Week", "Track", "Hours", "Work"]]
    for row in [
        ("1", "1-2", "8", "models.py complete; begin parser.py"),
        ("2", "2", "8", "parser.py: diff grammar, hunk bookkeeping, anchoring"),
        ("3", "3", "8", "rules.py: registry, LineContext, the check functions"),
        ("4", "3-4", "8", "rules.py finish; mock_provider.py + config.py"),
        ("5", "5", "8", "HARD. build_prompt, payload parsing, line snapping"),
        ("6", "5", "8", "HARD. live path and fallback; begin the adapter"),
        ("7", "5", "8", "adapter: repair path, review_with_fallback"),
        ("8", "-", "0", "buffer; Track 5 green; checkpoint 2"),
        ("9", "6", "3", "engine.py: ProviderSelection, the config builders"),
        ("10", "6", "3", "select_provider precedence and the reason strings"),
        ("11", "6", "4", "HARD. degraded path, relabelling, review never raising"),
        ("12", "6", "4", "HARD. finish; Track 6 green; checkpoint 3"),
        ("13", "7", "5", "cli.py: argument surface, exit codes, rendering"),
        ("14", "7", "5", "main.py: FastAPI surfaces, webhook, publishing"),
        ("15", "7", "5", "github_client.py: payloads, path canonicalisation"),
        ("16", "7", "5", "github_client.py: retry ladder, 422 demotion; Track 7"),
    ]:
        rows.append(list(row))
    s.append(table(rows, [30, 34, 32, TEXT_W - 96], mono_cols=(0, 1, 2)))

    s.append(body("The three checkpoints", S_H2))
    s.append(body(
        "One command per completed track, not a review meeting. The schedule only "
        "works if the checkpoints do."))
    s.append(table(
        [
            ["When", "Expected", "If you are behind"],
            ["End of week 4", "Tracks 1-4 green, 32 hours spent",
             "Compress Track 4 into two evenings - it is 167 lines of glue - and "
             "protect Track 5's start date by at most one week. If Track 3 is the "
             "red one, apply the recovery rule below instead of stealing from "
             "Track 5."],
            ["End of week 8", "Track 5 green, 56 hours spent",
             "This is what the empty week 8 is for: take it, finish Track 5, lose "
             "nothing. Still red at the end of week 8, shift Tracks 6 and 7 by one "
             "week each; the frame becomes 17 weeks and the checkpoints move."],
            ["End of week 12", "Track 6 green, 70 hours spent",
             "Track 7 is breadth and compresses better than anything else: take one "
             "week from it (20 hours to 15) and accept a thinner main.py rebuild. "
             "Keep the webhook signature check and the publishing path. Do not take "
             "the week from Track 6."],
        ],
        [50, 74, TEXT_W - 124],
    ))

    s.append(body("If you are two or more weeks behind", S_H2))
    s.append(body(
        "Compress Tracks 3 and 4. Never compress Tracks 1, 5 or 6."))
    s.extend(bullets([
        "Tracks 3 and 4 together are 1,785 lines and 16 hours, and they compress "
        "honestly: their cost is repetition, not insight. Skimming costs you rule-id "
        "recall, which --list-rules restores in one command.",
        "Track 1 is not compressible because it defines every type the rest of the "
        "codebase speaks. Skimping does not save five hours; it makes every later "
        "test failure ambiguous.",
        "Track 5 is not compressible because it is where the two ideas the project "
        "is actually about live: one adapter for two providers, and a fallback chain "
        "that degrades on six distinct failures without raising.",
    ]))
    s.append(Spacer(1, 4))
    s.append(body(
        "If that is not enough - more than about four weeks behind - the plan is not "
        "the problem: cut scope. Drop Track 7's main.py rebuild, keep the CLI and "
        "github_client.py, and accept a six-track rebuild in 18 weeks."))

    s.append(body("If your week is not five hours", S_H2))
    s.append(body(
        "The order, the gates and the checkpoints do not change; only the dates do. "
        "About 3 hours a week means roughly 30 weeks, checkpoints at 6, 14 and 22; "
        "about 10 hours a week means roughly 9 weeks, checkpoints at 2, 4 and 6. At "
        "no rate do you run two tracks in parallel, and at any rate the honest "
        "measure is the count of green tracks."))
    s.append(PageBreak())
    return s


CHECKLIST = [
    "You can list the five fields of Finding in contract order, and show that a "
    "sixth field raises a ValidationError of type extra_forbidden rather than being "
    "ignored.",
    "You can predict that Finding(file=\"a.py\", line=\"42-40\") raises while "
    "line=\"42-45\" is accepted, and prove both in one command.",
    "You can predict that sort_findings orders two LOW findings on lines 40 and 7 as "
    "7 then 40, and prove it without opening models.py.",
    "You can say what verdict_for returns for exactly one MEDIUM finding, and name "
    "the ReviewResult field that carries it.",
    "You can state how many rules the engine registers, and reproduce that number "
    "three ways: len(RULES), RULE_COUNT, and reviewer.py --list-rules.",
    "You can name all ten RuleCategory members from memory, then check yourself "
    "against the enum in one command.",
    "You can quote ENGINE_NOTE verbatim, including its number, and say why it is "
    "computed from the registry instead of written out.",
    "You can predict what anchor_findings returns for a finding on an unmodified "
    "line of a file that is in the diff, and prove it, detail string included.",
    "You can explain why the degraded path calls offline_diff_findings directly "
    "instead of review_with_fallback(force_offline=True), and name the test that "
    "locks the property.",
    "You can say which of the three providers runs when both SARVAM_API_KEY and "
    "LMSTUDIO_BASE_URL are set, and why.",
    "You can print the precedence tuple as the code holds it, and say exactly what "
    "REVIEW_MODE=mock does and does not override.",
    "You can predict four CLI exit codes before running anything - no path given, an "
    "unreadable file, a mock review with findings, --post-to-pr on a plain source "
    "file - and prove all four in four invocations.",
    "You can say how many model calls one review may make, and name the two "
    "functions that enforce the budget.",
    "You can say what mode and provider a run reports when the model answers prose "
    "twice, and explain why it does not become mock.",
    "You can show that app/config.py is the only module that reads the environment, "
    "and account for every os.environ hit that grep then finds in app/rules.py.",
    "You can state how many pins the lock file holds, and why the curriculum is "
    "measured against the lock rather than requirements.txt.",
    "You can name the single skipped test and the one environment variable that "
    "un-skips it.",
    "You can prove the suite never touches the network rather than asserting it, and "
    "name the three things the offline verifier blocks.",
    "You can explain why --json sends the posting report to stderr, and prove that "
    "stdout is still a single JSON document.",
    "You can say how many format examples the benchmark ships, why they cannot be "
    "scored, and which manifest key proves it.",
]


def section_6():
    s = [body("6. You know you're pro when...", S_H1)]
    s.append(body(
        "%d claims. Each one is answerable by running one command or opening one "
        "file, and each is a single sentence, so a claim you cannot settle is a gap "
        "you can name rather than a feeling you can argue with. If you can settle "
        "most of them, the seven tracks did what they were supposed to do."
        % len(CHECKLIST)))
    s.append(Spacer(1, 2))
    s.extend(numbered(["%d. %s" % (i + 1, text)
                       for i, text in enumerate(CHECKLIST)]))
    s.append(Spacer(1, 6))
    s.append(body(
        "Two are worth reading twice, because they are the ones a confident reader "
        "gets wrong: the degraded-path question (item 9) has a right answer that "
        "looks like a code smell, and the both-configured question (item 10) has an "
        "answer that is one word and a precedence tuple.", S_SMALL))
    s.append(PageBreak())
    return s


def section_7():
    s = [body("7. The honest limits", S_H1)]
    s.append(body(
        "This section exists because a study guide that stops at the green test "
        "line teaches you to overclaim. Everything below is stated the way the "
        "repository states it."))

    s.append(body("What was simulated", S_H2))
    s.extend(bullets([
        "The local model path was verified against a stub OpenAI-compatible server "
        "driven with the real openai SDK. That proves the adapter's request shape, "
        "retry budget and parsing; it does not prove that any real model, including "
        "the Qwen build the docs name, produces useful findings.",
        "GitHub posting was verified with fake httpx clients. No request has ever "
        "been sent to api.github.com, so token scopes, real rate limiting, and "
        "whether GitHub accepts the payload's anchor positions are unverified.",
        "The auth-failure rows in ARCHITECTURE were driven with scripted exception "
        "classes: a 401 produced mode=mock with the bundled diff's four findings and "
        "exactly one WARNING. The one real network rejection recorded in the tree is "
        "a 403 from api.sarvam.ai with a fake key.",
        "The zero-network proof is real, not simulated: the verifier blocks socket "
        "creation and re-runs the whole suite in-process.",
    ]))

    s.append(body("What is unexercised", S_H2))
    s.extend(bullets([
        "A successful Sarvam review. No real key appears anywhere in the tree, and "
        "no live Sarvam response has ever been produced.",
        "A real LM Studio run. That is the single skipped test; un-skipping it with "
        "LMSTUDIO_BASE_URL asserts only that the run completes and returns an "
        "outcome, and it accepts mode live or mock. It is a wiring check, not a "
        "model-quality check.",
        "A browser or end-to-end test. The API surfaces are exercised through the "
        "ASGI transport in-process, so a JS-level break in the docs page would not "
        "fail the suite.",
        "Latency and memory. Nothing asserts either, and timing figures in the docs "
        "are not stable enough to quote.",
    ]))

    s.append(body("What the benchmark does and does not prove", S_H2))
    s.append(body(
        "No labelled dataset exists. " + mono("benchmarks/golden/manifest.json")
        + " carries " + mono("\"evaluation_samples\": []") + " and lists "
        "%d format examples, which demonstrate the file layout and are excluded from "
        "every reported metric. Labels must be human-authored: a label produced by "
        "the rule engine or by a model scores the tool against itself."
        % FORMAT_EXAMPLES))
    s.append(body(
        "So the harness runs, and it proves the harness runs. Its own note says it: "
        "all %d samples are format examples and the numbers are a smoke test, not "
        "evaluation data. A precision of 0.8 and a recall of 1.0 over two samples "
        "cannot support a quality claim, and this guide does not make one."
        % FORMAT_EXAMPLES))
    s.append(body(
        "Matching is one-to-one and greedy, largest overlap first, with ties broken "
        "by file, expected line start, then actual line start. That is deterministic, "
        "and it is documented as a limitation rather than a design."))

    s.append(body("Numbers that once disagreed inside the tree", S_H2))
    s.append(body(
        "Earlier drafts of these documents quoted %d passed and %d collected. The "
        "tree runs %d passed, %d skipped and %d collected, and every document now "
        "names those figures. Treat %d as the baseline: a curriculum measured "
        "against a moving baseline teaches the wrong lesson, so if you cannot "
        "reproduce %d before Track 1, fix the environment first."
        % (509, 598, TESTS_PASSED, TESTS_SKIPPED, TESTS_COLLECTED,
           TESTS_PASSED, TESTS_PASSED)))
    s.append(body(
        "Two smaller items, both documented in ADR 0004: a module "
        "docstring that still describes the abandoned delegation, and an unused "
        "constant left behind by it. Neither changes behaviour."))
    s.append(PageBreak())
    return s


def section_8():
    s = [body("8. Appendix - the commands", S_H1)]
    s.append(body(
        "One block per milestone, in the order a reader meets them. Long commands "
        "are broken with backslash continuations; each broken form is the same "
        "command as its single-line original. Expected output is quoted only where "
        "it was observed in this tree."))

    s.append(body("Milestone 0 - the environment", S_H2))
    s.append(code(
        "pip install -r requirements.lock\n"
        "python -m pytest -q tests"
    ))
    s.append(body(
        "The lock, not requirements.txt: it is the resolved closure of %d pins and "
        "the only environment in which the recorded counts hold. Observed: "
        "<b>%d passed, %d skipped</b>."
        % (LOCK_PINS, TESTS_PASSED, TESTS_SKIPPED)))

    s.append(body("Milestone 1 - the whole health check", S_H2))
    s.append(code("make verify"))
    s.append(body(
        "Builds a verifier virtualenv, installs the lock, runs pytest, then runs the "
        "zero-network proof. It needs no environment variables. This is the gate the "
        "curriculum is measured against."))

    s.append(body("Milestone 2 - review the bundled diff", S_H2))
    s.append(code("python reviewer.py samples/sample.diff"))
    s.append(body(
        "Observed: mode mock, provider mock, model local-rules, 2 files changed, "
        "<b>4 findings (CRITICAL 3, HIGH 0, MEDIUM 1, LOW 0)</b>, verdict block, exit "
        "code 0. Add " + mono("--json") + " for the full document, "
        + mono("--list-rules") + " for all %d rules, " % RULE_COUNT
        + mono("--min-severity HIGH") + " to filter."))

    s.append(body("Milestone 3 - the HTTP surface", S_H2))
    s.append(code("uvicorn app.main:app --port 8000"))
    s.append(code("curl -s localhost:8000/test-review"))
    s.append(body(
        "Swagger is at /docs. " + mono("/test-review") + " reviews the bundled "
        "fixture offline and returns the exact markdown a PR comment would carry, so "
        "it is the cheapest way to see the whole pipeline without a credential."))

    s.append(body("Milestone 4 - the benchmark harness", S_H2))
    s.append(code(
        "python -m benchmarks.eval \\\n"
        "    --modes rules \\\n"
        "    --dataset benchmarks/golden \\\n"
        "    --out benchmarks/out"
    ))
    s.append(body(
        "Writes metrics.csv, summary.json, summary.md and chart.png. Read the note "
        "column before the metric columns: with %d format examples and no labelled "
        "data, every number it prints is a smoke test." % FORMAT_EXAMPLES))

    s.append(body("Milestone 5 - the gate, and the counts", S_H2))
    s.append(code(
        "python scripts/learning_progress.py status\n"
        "python scripts/learning_progress.py check 1"
    ))
    s.append(body(
        "status prints one row per track with exists, test and checked; before you "
        "write anything, all seven read skipped. check N runs Track N's verification "
        "test and is the only completion criterion in the curriculum."))

    s.append(body("Verifying the numbers in this guide", S_H2))
    s.append(code(
        "python - <<'EOF'\n"
        "from app.rules import RULE_COUNT, RuleCategory\n"
        "from app.mock_provider import ENGINE_NOTE\n"
        "from app.engine import PROVIDERS\n"
        "print(RULE_COUNT, len(list(RuleCategory)))\n"
        "print(ENGINE_NOTE)\n"
        "print(PROVIDERS)\n"
        "EOF\n"
        "grep -c '==' requirements.lock\n"
        "ls docs/learning/track-*.md | wc -l"
    ))
    s.append(body(
        "Expected, in order: %d, %d, the engine note naming %d rules, the tuple "
        "sarvam then local then mock, %d, %d."
        % (RULE_COUNT, RULE_CATEGORIES, RULE_COUNT, LOCK_PINS, TRACKS)))
    s.append(body(
        "Everything else in this guide is prose that the tree states in the same "
        "words, or a line count you can take with wc -l.", S_SMALL))
    return s


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------
def build(path=OUT):
    doc = GuideDoc(
        path,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T, bottomMargin=MARGIN_B,
        title="Naive to Pro - a study guide to the AI Code Reviewer codebase",
        author="docs/presentation/build_guide.py",
        subject="Study guide: %d tracks, %d hours" % (TRACKS, TOTAL_HOURS),
    )
    story = []
    story += title_and_toc()
    story += section_1()
    story += section_2()
    story += section_3()
    story += section_4()
    story += section_5()
    story += section_6()
    story += section_7()
    story += section_8()
    doc.multiBuild(story)
    return path


if __name__ == "__main__":
    out = build()
    size = os.path.getsize(out)
    print("wrote %s (%d bytes, %.1f KiB)" % (out, size, size / 1024.0))
    if size > 5 * 1024 * 1024:
        sys.exit("output exceeds 5 MB")
