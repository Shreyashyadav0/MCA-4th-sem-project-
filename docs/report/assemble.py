#!/usr/bin/env python3
"""assemble.py -- build the MCSP-232 project report (DOCX + PDF) and the
proposal (DOCX + PDF) from the markdown sources in docs/report/.

Usage
-----
    python docs/report/assemble.py --out docs/report/out

Inputs, in this fixed order
---------------------------
    docs/report/front-matter.md
    docs/report/chapters/01-introduction.md          (Chapter 1)
    docs/report/chapters/02-literature-review.md     (Chapter 2)
    docs/report/chapters/03-system-design.md         (Chapter 3)
    docs/report/chapters/04-implementation.md        (Chapter 4)
    docs/report/chapters/05-testing-and-evaluation.md(Chapter 5)
    docs/report/chapters/06-results-and-discussion.md(Chapter 6)
    docs/report/chapters/07-limitations.md           (Chapter 7)
    docs/report/chapters/08-conclusion-and-future-work.md (Chapter 8)
    docs/report/chapters/09-references.md            (Chapter 9)
    docs/report/chapters/10-appendix-a-commands.md   (Chapter 10)
    docs/report/chapters/11-appendix-b-screenshots.md(Chapter 11)
    docs/report/chapters/12-glossary.md              (Chapter 12)
    docs/report/proposal/synopsis.md

A chapter file is resolved by its two-digit numeric prefix first (so
`01-introduction-and-objectives.md` satisfies chapter 1), then by its exact
canonical name.  Anything still missing is reported by name; the build aborts
with exit code 2 unless --allow-missing is given.

Outputs
-------
    <out>/MCSP-232-Project-Report.docx
    <out>/MCSP-232-Project-Report.pdf
    <out>/MCSP-232-Project-Proposal.docx
    <out>/MCSP-232-Project-Proposal.pdf

Design notes that matter
------------------------
* python-docx cannot paginate, so the Word table of contents, list of figures
  and list of tables are *fields* (TOC \\o / TOC \\c).  Each one carries a
  cached result so the document is readable before it is refreshed; the student
  presses Ctrl+A then F9 to populate real page numbers.  See FORMAT.md.
* Figure and table captions embed a SEQ field so that TOC \\c "Figure" /
  TOC \\c "Table" can collect them.  The visible number is cached, so the
  caption reads correctly before F9 as well.
* Every [FILL: ...] and [FILL AFTER BENCHMARK: ...] token is rendered in bold
  red so it cannot be missed, and is inventoried in the run summary.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

# --------------------------------------------------------------------------
# Optional dependency imports, with one clear message instead of a traceback.
# --------------------------------------------------------------------------

_MISSING: list[str] = []
try:
    from docx import Document
    from docx.enum.section import WD_SECTION
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Mm, Pt, RGBColor
    from docx.enum.style import WD_STYLE_TYPE
except Exception:  # pragma: no cover
    _MISSING.append("python-docx")
    Document = None  # type: ignore

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether,
                                    NextPageTemplate, PageBreak, PageTemplate,
                                    Paragraph, Spacer, Table, TableStyle,
                                    XPreformatted)
    from reportlab.platypus.tableofcontents import TableOfContents
except Exception:  # pragma: no cover
    _MISSING.append("reportlab")

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    _MISSING.append("pypdf")
    PdfReader = None  # type: ignore

try:
    from PIL import Image as PILImage
except Exception:  # pragma: no cover
    PILImage = None  # type: ignore


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

REPORT_TITLE = "Autonomous AI Code Reviewer & PR Assistant"
REPORT_TITLE_SHORT = "Autonomous AI Code Reviewer & PR Assistant"
SUBMISSION_CODE = "MCSP-232"
PAGE_TARGET = (100, 125)          # physical pages, excluding code listings
DOCX_REPORT = "MCSP-232-Project-Report.docx"
PDF_REPORT = "MCSP-232-Project-Report.pdf"
DOCX_PROPOSAL = "MCSP-232-Project-Proposal.docx"
PDF_PROPOSAL = "MCSP-232-Project-Proposal.pdf"

# (number, canonical stem, fallback title)
CANONICAL_CHAPTERS: tuple[tuple[int, str, str], ...] = (
    (1, "01-introduction", "Introduction"),
    (2, "02-literature-review", "Literature Review"),
    (3, "03-system-design", "System Design"),
    (4, "04-implementation", "Implementation"),
    (5, "05-testing-and-evaluation", "Testing and Evaluation"),
    (6, "06-results-and-discussion", "Results and Discussion"),
    (7, "07-limitations", "Limitations"),
    (8, "08-conclusion-and-future-work", "Conclusion and Future Work"),
    (9, "09-references", "References"),
    (10, "10-appendix-a-commands", "Appendix A — Commands"),
    (11, "11-appendix-b-screenshots", "Appendix B — Screenshots"),
    (12, "12-glossary", "Glossary"),
)

# Front-matter sections that we generate ourselves; ignore if present in the
# markdown.
FRONT_MATTER_GENERATED = {"table of contents", "contents", "list of figures",
                          "list of tables", "list of listings"}

# Titles that should not be prefixed with "Chapter N".
NO_CHAPTER_PREFIX = re.compile(r"^\s*(appendix|references|bibliography|glossary|index)",
                               re.IGNORECASE)

# (accepted section-name keys, page title) for the three fixed front pages
FRONT_MATTER_PAGES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("certificate", "certification"), "Certificate"),
    (("acknowledgement", "acknowledgment"), "Acknowledgement"),
    (("abstract",), "Abstract"),
)

FILL_TOKEN_RE = re.compile(r"\[FILL(?:\s+AFTER\s+BENCHMARK)?\s*:[^\]]*\]")
FILL_TOKEN_SPLIT = re.compile(r"(\[FILL(?:\s+AFTER\s+BENCHMARK)?\s*:[^\]]*\])")

FIGURE_LINE_RE = re.compile(r"^\s*!\[(?P<alt>[^\]]*)\]\((?P<path>[^)]+)\)\s*$")
CAPTION_LINE_RE = re.compile(
    r"^\s*(?:\*\*|\*|_)?(?P<kind>Table|Listing|Code|Figure)\s*"
    r"(?P<num>[0-9]+(?:\.[0-9]+)*)?\s*"
    r"(?:\*\*|\*|_)?\s*[:—–\-]\s*(?P<text>.+?)(?:\*\*|\*|_)?\s*$",
    re.IGNORECASE)
HEADING_NUM_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
BULLET_RE = re.compile(r"^(\s*)[-*+]\s+(.*)$")
ORDERED_RE = re.compile(r"^(\s*)\d+[.)]\s+(.*)$")


# --------------------------------------------------------------------------
# Fill-in inventory
# --------------------------------------------------------------------------

@dataclass
class Inventory:
    """Collects every [FILL: ...] / [FILL AFTER BENCHMARK: ...] token seen."""

    entries: list[tuple[str, str]] = field(default_factory=list)

    def scan_text(self, relpath: str, text: str) -> None:
        for m in FILL_TOKEN_RE.finditer(text):
            self.entries.append((relpath, m.group(0)))

    def scan_file(self, relpath: str, path: Path) -> None:
        try:
            self.scan_text(relpath, path.read_text(encoding="utf-8"))
        except OSError:
            pass

    def add(self, relpath: str, token: str) -> None:
        self.entries.append((relpath, token))

    def by_file(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for relpath, token in self.entries:
            bucket = out.setdefault(relpath, [])
            if token not in bucket:
                bucket.append(token)
        return dict(sorted(out.items()))

    def __len__(self) -> int:
        return len(self.entries)


# --------------------------------------------------------------------------
# Markdown block model
# --------------------------------------------------------------------------

@dataclass
class Block:
    kind: str                      # heading | para | code | table | list | figure | quote | hr
    text: str = ""
    level: int = 0                 # heading level 1..3
    lines: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    ordered: bool = False
    items: list[str] = field(default_factory=list)
    path: str = ""
    caption: str = ""
    lang: str = ""
    number: str = ""               # display number, e.g. "3.1" or "7"
    label: str = ""                # full heading label, e.g. "Chapter 3 — Design"
    note: str = ""                 # auxiliary (e.g. missing figure path)



_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _sanitise(text: str) -> str:
    """Strip characters lxml refuses: control bytes, NULLs and lone surrogates."""
    text = text.replace("\x0c", "\n").replace("\t", "    ")
    text = _CONTROL_RE.sub("", text)
    return text.encode("utf-8", "replace").decode("utf-8")

def _split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    cells, buf, esc = [], [], False
    for ch in s:
        if esc:
            buf.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == "|":
            cells.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    cells.append("".join(buf).strip())
    return cells


def _is_table_start(lines: Sequence[str], i: int) -> bool:
    if i + 1 >= len(lines):
        return False
    return ("|" in lines[i] and "|" in lines[i + 1]
            and bool(TABLE_SEP_RE.match(lines[i + 1])))


def parse_markdown(text: str) -> list[Block]:
    """Parse the report's markdown dialect into a flat list of Blocks.

    Supported: #/##/### headings, paragraphs, fenced code blocks, pipe tables,
    bullet and ordered lists, blockquotes, horizontal rules, and
    `![Figure N.M — caption](path)` figure references.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[Block] = []
    i = 0
    n = len(lines)
    para: list[str] = []

    def flush_para() -> None:
        nonlocal para
        if not para:
            return
        joined = " ".join(x.strip() for x in para).strip()
        if joined:
            # A paragraph that is exactly a caption line stays a paragraph;
            # the table/code/figure emitters consume it as their caption.
            blocks.append(Block(kind="para", text=joined))
        para = []

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # fenced code -------------------------------------------------
        if stripped.startswith("```") or stripped.startswith("~~~"):
            flush_para()
            fence = stripped[:3]
            lang = stripped[3:].strip()
            i += 1
            body: list[str] = []
            while i < n and not lines[i].strip().startswith(fence):
                body.append(lines[i])
                i += 1
            i += 1  # closing fence
            blocks.append(Block(kind="code", lines=body, lang=lang))
            continue

        # headings ----------------------------------------------------
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush_para()
            level = min(len(m.group(1)), 3)
            blocks.append(Block(kind="heading", text=m.group(2).strip(), level=level))
            i += 1
            continue

        # horizontal rule ---------------------------------------------
        if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", line):
            flush_para()
            blocks.append(Block(kind="hr"))
            i += 1
            continue

        # figure reference --------------------------------------------
        fm = FIGURE_LINE_RE.match(line)
        if fm:
            flush_para()
            alt = fm.group("alt").strip()
            path = fm.group("path").strip()
            number, caption = "", alt
            am = re.match(r"^Figure\s+([0-9]+(?:\.[0-9]+)*)\s*[—–:-]\s*(.*)$", alt,
                          re.IGNORECASE)
            if am:
                number, caption = am.group(1), am.group(2).strip()
            blocks.append(Block(kind="figure", text=alt, path=path,
                                number=number, caption=caption))
            i += 1
            continue

        # table -------------------------------------------------------
        if _is_table_start(lines, i):
            flush_para()
            header = _split_row(lines[i])
            i += 2
            rows = [header]
            while i < n and lines[i].strip() and "|" in lines[i]:
                rows.append(_split_row(lines[i]))
                i += 1
            width = len(header)
            rows = [(r + [""] * width)[:width] for r in rows]
            blocks.append(Block(kind="table", rows=rows))
            continue

        # lists -------------------------------------------------------
        bm = BULLET_RE.match(line)
        om = ORDERED_RE.match(line)
        if bm or om:
            flush_para()
            ordered = bool(om)
            items: list[str] = []
            while i < n:
                cur = lines[i]
                b2 = BULLET_RE.match(cur)
                o2 = ORDERED_RE.match(cur)
                if b2 and not ordered:
                    items.append(b2.group(2).strip())
                elif o2 and ordered:
                    items.append(o2.group(2).strip())
                elif cur.strip() and cur.startswith(("  ", "\t")) and items:
                    items[-1] = items[-1] + " " + cur.strip()
                else:
                    break
                i += 1
            blocks.append(Block(kind="list", items=items, ordered=ordered))
            continue

        # blockquote --------------------------------------------------
        if stripped.startswith(">"):
            flush_para()
            quoted: list[str] = []
            while i < n and lines[i].strip().startswith(">"):
                quoted.append(lines[i].strip().lstrip(">").strip())
                i += 1
            blocks.append(Block(kind="quote", text=" ".join(q for q in quoted if q)))
            continue

        # blank -------------------------------------------------------
        if not stripped:
            flush_para()
            i += 1
            continue

        para.append(line)
        i += 1

    flush_para()
    return blocks


# --------------------------------------------------------------------------
# Front matter
# --------------------------------------------------------------------------


def _strip_chapter_prefix(title: str, number: int) -> str:
    """Drop a leading "Chapter N:" / "Chapter N -" so the label is not doubled.

    Args:
        title: The chapter title as authored in the markdown heading.
        number: The chapter number the assembler is about to prefix.

    Returns:
        The title with any redundant chapter prefix removed.
    """
    cleaned = re.sub(rf"^\s*chapter\s*{number}\s*[:.\-—]\s*", "", title, flags=re.I)
    cleaned = re.sub(rf"^\s*{number}\s*[.:\-—]?\s+", "", cleaned)
    cleaned = re.sub(rf"^\s*{number}\s*[.:\-—]\s*", "", cleaned)
    return cleaned or title

TITLE_FIELDS = [
    ("title", "Project title", REPORT_TITLE),
    ("programme", "Programme", "Master of Computer Applications (MCA)"),
    ("course", "Course", f"{SUBMISSION_CODE} — Project"),
    ("department", "Department", "[FILL: department]"),
    ("institution", "Institution", "[FILL: institution]"),
    ("candidate", "Candidate", "Shreyash Yadav"),
    ("roll", "Enrolment number", "[FILL: enrolment number]"),
    ("supervisor", "Supervisor", "[FILL: supervisor name]"),
    ("study_centre", "Study Centre", "[FILL: study centre]"),
    ("regional_centre", "Regional Centre", "[FILL: regional centre]"),
    ("session", "Session", "[FILL: academic session]"),
    ("date", "Date of submission", "[FILL: date of submission]"),
]


def parse_front_matter(text: str) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Return (title-page fields, [(section name, body markdown)])."""
    fields: dict[str, str] = {}
    sections: list[tuple[str, str]] = []
    current: str | None = None
    buf: list[str] = []
    pre: list[str] = []

    def close() -> None:
        nonlocal current, buf
        if current is not None:
            sections.append((current, "\n".join(buf).strip()))
        buf = []

    for line in text.replace("\r\n", "\n").split("\n"):
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            close()
            current = m.group(1).strip()
            continue
        if current is None:
            pre.append(line)
        else:
            buf.append(line)
    close()

    # key: value lines, from the pre-amble and from any "title page" section
    kv_source = list(pre)
    for name, body in sections:
        if re.sub(r"[^a-z]", "", name.lower()) in ("titlepage", "cover", "coverpage"):
            kv_source.extend(body.split("\n"))
    for line in kv_source:
        kv = re.match(r"^\s*[*_-]*\s*([A-Za-z][A-Za-z /_()]+?)\s*[*_-]*\s*:\s*(.+?)\s*$", line)
        if not kv:
            continue
        key = kv.group(1).strip().lower().replace(" ", "_").replace("/", "_")
        val = kv.group(2).strip().strip("*_").strip()
        if val:
            fields[key] = val
    return fields, sections


FIELD_ALIASES = {
    "title": ("title", "project_title", "project"),
    "programme": ("programme", "program", "degree", "course_name"),
    "course": ("course", "course_code", "paper"),
    "department": ("department", "dept", "school"),
    "institution": ("institution", "university", "college"),
    "candidate": ("candidate", "student", "candidate_name", "name"),
    "roll": ("roll", "roll_no", "roll_number", "enrolment_no", "enrolment_number",
             "enrollment_no", "enrollment_number"),
    "supervisor": ("supervisor", "guide", "mentor", "supervisor_name"),
    "session": ("session", "academic_session", "year"),
    "date": ("date", "submission_date", "date_of_submission"),
}


def title_values(fields: dict[str, str], inventory: Inventory,
                 source: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, _label, default in TITLE_FIELDS:
        val = None
        for alias in FIELD_ALIASES.get(key, (key,)):
            if alias in fields and fields[alias].strip():
                val = fields[alias].strip()
                break
        if val is None:
            val = default
            if FILL_TOKEN_RE.search(val):
                inventory.add(source, val)
        out[key] = val
    return out


# --------------------------------------------------------------------------
# Chapters
# --------------------------------------------------------------------------

@dataclass
class Chapter:
    number: int
    title: str
    blocks: list[Block]
    source: str
    is_front_matter: bool = False
    label: str = ""


def resolve_chapter_file(chapters_dir: Path, number: int, stem: str) -> Path | None:
    exact = chapters_dir / f"{stem}.md"
    if exact.is_file():
        return exact
    matches = sorted(glob.glob(str(chapters_dir / f"{number:02d}-*.md")))
    if matches:
        return Path(matches[0])
    return None


def load_chapters(report_dir: Path, inventory: Inventory,
                  allow_missing: bool) -> tuple[list[Chapter], list[str], list[str]]:
    chapters_dir = report_dir / "chapters"
    found: list[Chapter] = []
    missing: list[str] = []

    for number, stem, fallback in CANONICAL_CHAPTERS:
        path = resolve_chapter_file(chapters_dir, number, stem) if chapters_dir.is_dir() else None
        if path is None:
            missing.append(f"chapters/{stem}.md")
            continue
        rel = f"chapters/{path.name}"
        text = path.read_text(encoding="utf-8")
        inventory.scan_text(rel, text)
        blocks = parse_markdown(text)
        title = fallback
        if blocks and blocks[0].kind == "heading" and blocks[0].level == 1:
            title = blocks[0].text.strip() or fallback
            blocks = blocks[1:]
        found.append(Chapter(number=number, title=title, blocks=blocks, source=rel))

    if missing and not allow_missing:
        listing = "\n".join(f"  - docs/report/{m}" for m in missing)
        raise SystemExit(
            "assemble.py: missing chapter file(s) — nothing was built.\n"
            f"{listing}\n\n"
            "Chapter files are resolved by two-digit prefix (01-, 02-, ...), so a\n"
            "differently-named file for that chapter is accepted. Create the file(s)\n"
            "above, or re-run with --allow-missing to build a partial draft from the\n"
            "chapters that do exist."
        )
    return found, [c.source for c in found], missing


def load_front_matter(report_dir: Path, inventory: Inventory,
                      allow_missing: bool) -> tuple[dict[str, str], list[tuple[str, str]], str]:
    path = report_dir / "front-matter.md"
    if not path.is_file():
        if not allow_missing:
            raise SystemExit(
                "assemble.py: missing front matter — nothing was built.\n"
                f"  - docs/report/front-matter.md\n\n"
                "front-matter.md supplies the title page, certificate, acknowledgement\n"
                "and abstract. Create it, or re-run with --allow-missing to generate\n"
                "placeholder pages carrying [FILL: ...] tokens."
            )
        fields: dict[str, str] = {}
        sections: list[tuple[str, str]] = []
        return fields, sections, "(absent)"
    text = path.read_text(encoding="utf-8")
    inventory.scan_text("front-matter.md", text)
    fields, sections = parse_front_matter(text)
    return fields, sections, "front-matter.md"


# --------------------------------------------------------------------------
# Numbering pass shared by both renderers
# --------------------------------------------------------------------------

def annotate(chapters: list[Chapter]) -> dict[str, int]:
    """Fill in Block.label / Block.number and return counters used."""
    counts = {"figures": 0, "tables": 0, "listings": 0, "tables_missing_caption": 0}
    per_ch: dict[str, int] = {}
    for ch in chapters:
        title = ch.title
        if NO_CHAPTER_PREFIX.match(title):
            ch.label = title
        else:
            ch.label = f"Chapter {ch.number} — {_strip_chapter_prefix(title, ch.number)}"
        h2 = h3 = 0
        blocks = ch.blocks
        for idx, b in enumerate(blocks):
            if b.kind == "heading":
                if b.level == 2:
                    h2 += 1
                    h3 = 0
                    m = HEADING_NUM_RE.match(b.text)
                    if m:
                        b.label = b.text
                    else:
                        b.label = f"{ch.number}.{h2}  {b.text}"
                elif b.level == 3:
                    h3 += 1
                    m = HEADING_NUM_RE.match(b.text)
                    if m:
                        b.label = b.text
                    else:
                        b.label = f"{ch.number}.{h2}.{h3}  {b.text}"
                else:
                    b.label = b.text
            elif b.kind == "code":
                counts["listings"] += 1
                per_ch["listings"] = per_ch.get("listings", 0) + 1
                b.number = f"{ch.number}.{per_ch['listings']}"
                cap = _take_previous_caption(blocks, idx, "Listing")
                if cap is None:
                    cap = _take_next_caption(blocks, idx, "Listing")
                b.caption = cap or ""
            elif b.kind == "table":
                counts["tables"] += 1
                per_ch["tables"] = per_ch.get("tables", 0) + 1
                cap = _take_previous_caption(blocks, idx, "Table")
                explicit = getattr(blocks[idx - 1], "label", "") if idx else ""
                b.number = explicit or f"{ch.number}.{per_ch['tables']}"
                if cap is None:
                    counts["tables_missing_caption"] += 1
                    cap = ""
                b.caption = cap
            elif b.kind == "figure":
                counts["figures"] += 1
                if not b.number:
                    b.number = f"{ch.number}.{counts['figures']}"
    return counts


def _take_previous_caption(blocks: list[Block], idx: int, kind: str) -> str | None:
    """Consume an immediately preceding caption paragraph, if it is one.

    A caption paragraph is `Table 3.1 — text`, `Listing 4: text`, or a fully
    italic line `*Table 3.1 — text*`.
    """
    if idx == 0:
        return None
    prev = blocks[idx - 1]
    if prev.kind != "para" or prev.note == "consumed-caption":
        return None
    m = CAPTION_LINE_RE.match(prev.text)
    if not m or m.group("kind").lower() != kind.lower():
        return None
    text = m.group("text").strip()
    number = (m.group("num") or "").strip()
    prev.note = "consumed-caption"
    prev.text = ""
    prev.label = number
    return text


def _take_next_caption(blocks: list[Block], idx: int, kind: str) -> str | None:
    """Consume an immediately following caption paragraph, if it is one."""
    if idx + 1 >= len(blocks):
        return None
    nxt = blocks[idx + 1]
    if nxt.kind != "para" or nxt.note == "consumed-caption":
        return None
    m = CAPTION_LINE_RE.match(nxt.text)
    if not m or m.group("kind").lower() != kind.lower():
        return None
    text = m.group("text").strip()
    nxt.note = "consumed-caption"
    nxt.text = ""
    return text


def walk_figures(chapters: Iterable[Chapter]) -> list[Block]:
    return [b for ch in chapters for b in ch.blocks if b.kind == "figure"]


def walk_tables(chapters: Iterable[Chapter]) -> list[Block]:
    return [b for ch in chapters for b in ch.blocks if b.kind == "table"]


def walk_listings(chapters: Iterable[Chapter]) -> list[Block]:
    return [b for ch in chapters for b in ch.blocks if b.kind == "code"]


# --------------------------------------------------------------------------
# Figure path resolution
# --------------------------------------------------------------------------

def resolve_figure(path: str, report_dir: Path) -> Path | None:
    """Resolve a markdown image path against the repository layout."""
    root = report_dir.parent.parent
    diagrams = root / "docs" / "diagrams"
    raw = Path(path)
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append(report_dir / raw)
        candidates.append(report_dir.parent / raw)
        candidates.append(root / raw)
        candidates.append(diagrams / raw.name)
        candidates.append(diagrams / raw)
    for c in candidates:
        try:
            if c.is_file():
                return c
        except OSError:
            continue
    return None


# --------------------------------------------------------------------------
# DOCX helpers
# --------------------------------------------------------------------------

def _force_font(element, name: str) -> None:
    """Set every rFonts slot on a style/run rPr element to `name`."""
    rpr = element.find(qn("w:rPr"))
    if rpr is None:
        rpr = OxmlElement("w:rPr")
        element.insert(0, rpr)
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rfonts.get(qn(attr)) is not None:
            del rfonts.attrib[qn(attr)]
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), name)


def _shade(element_pr, fill: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    element_pr.append(shd)


def _para_border(paragraph, color: str = "BFBFBF", sz: int = 6,
                 sides: Sequence[str] = ("top", "left", "bottom", "right"),
                 space: int = 4) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    for side in sides:
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:space"), str(space))
        el.set(qn("w:color"), color)
        pbdr.append(el)
    ppr.append(pbdr)


def _add_field(paragraph, instruction: str, cached: str = "",
               font: str | None = None, size: float | None = None,
               bold: bool = False, italic: bool = False,
               color: RGBColor | None = None):
    """Insert a complex Word field with a cached result."""
    def mkrun(text: str | None = None):
        run = paragraph.add_run(text if text is not None else "")
        if font:
            run.font.name = font
            _force_font(run._r, font)
        if size:
            run.font.size = Pt(size)
        if bold:
            run.bold = True
        if italic:
            run.italic = True
        if color is not None:
            run.font.color.rgb = color
        return run

    r1 = mkrun()
    fc = OxmlElement("w:fldChar")
    fc.set(qn("w:fldCharType"), "begin")
    r1._r.append(fc)

    r2 = mkrun()
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = f" {instruction} "
    r2._r.append(it)

    r3 = mkrun()
    fc = OxmlElement("w:fldChar")
    fc.set(qn("w:fldCharType"), "separate")
    r3._r.append(fc)

    mkrun(cached)

    r5 = mkrun()
    fc = OxmlElement("w:fldChar")
    fc.set(qn("w:fldCharType"), "end")
    r5._r.append(fc)


INLINE_RE = re.compile(
    r"(\*\*.+?\*\*|__.+?__|`[^`\n]+`|\*[^*\n]+?\*|(?<![A-Za-z0-9_])_[^_\n]+?_(?![A-Za-z0-9_])"
    r"|\[[^\]]+\]\([^)]+\))"
)


def _iter_inline(text: str):
    """Yield (kind, text) tuples: plain | bold | italic | code | link."""
    pos = 0
    for m in INLINE_RE.finditer(text):
        if m.start() > pos:
            yield ("plain", text[pos:m.start()])
        token = m.group(0)
        if token.startswith("**") or token.startswith("__"):
            yield ("bold", token[2:-2])
        elif token.startswith("`"):
            yield ("code", token[1:-1])
        elif token.startswith("["):
            lm = re.match(r"\[([^\]]+)\]\(([^)]+)\)", token)
            yield ("link", (lm.group(1), lm.group(2)))  # type: ignore[arg-type]
        else:
            yield ("italic", token[1:-1])
        pos = m.end()
    if pos < len(text):
        yield ("plain", text[pos:])


def _emit_token_aware(paragraph, text: str, *, font=None, size=None,
                      bold=False, italic=False, color=None) -> None:
    """Write `text` as runs, colouring any [FILL: ...] token bold red."""
    parts = FILL_TOKEN_SPLIT.split(text)
    for part in parts:
        if not part:
            continue
        is_token = bool(FILL_TOKEN_RE.fullmatch(part))
        run = paragraph.add_run(part)
        if font:
            run.font.name = font
            _force_font(run._r, font)
        if size:
            run.font.size = Pt(size)
        run.bold = True if is_token else bold
        run.italic = italic
        if is_token:
            run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)
        elif color is not None:
            run.font.color.rgb = color


class DocxBuilder:
    """Renders the parsed blocks into a Word document."""

    def __init__(self, title_values: dict[str, str], *, with_header: bool = True,
                 doc_code: str = "PROJECT REPORT"):
        if Document is None:
            raise SystemExit(
                "assemble.py: python-docx is not installed.\n"
                "  pip install python-docx==1.2.0"
            )
        self.doc = Document()
        self.tv = title_values
        self.doc_code = doc_code
        self.with_header = with_header
        self._setup_page()
        self._setup_styles()
        self._setup_header_footer()

    # -- setup -------------------------------------------------------
    def _setup_page(self) -> None:
        sec = self.doc.sections[0]
        sec.page_width = Mm(210)
        sec.page_height = Mm(297)
        for attr in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
            setattr(sec, attr, Inches(1))
        sec.header_distance = Inches(0.5)
        sec.footer_distance = Inches(0.5)
        sec.different_first_page_header_footer = True

    def _setup_styles(self) -> None:
        styles = self.doc.styles

        normal = styles["Normal"]
        normal.font.name = "Times New Roman"
        normal.font.size = Pt(12)
        _force_font(normal.element, "Times New Roman")
        pf = normal.paragraph_format
        pf.line_spacing = 1.5
        pf.space_after = Pt(6)
        pf.space_before = Pt(0)
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

        specs = {1: (16, 18, 10), 2: (14, 14, 6), 3: (12, 12, 6)}
        for level, (size, before, after) in specs.items():
            st = styles[f"Heading {level}"]
            st.font.name = "Times New Roman"
            st.font.size = Pt(size)
            st.font.bold = True
            st.font.italic = False
            st.font.color.rgb = RGBColor(0, 0, 0)
            _force_font(st.element, "Times New Roman")
            color_el = st.element.find(qn("w:rPr"))
            if color_el is not None:
                c = color_el.find(qn("w:color"))
                if c is not None:
                    for attr in ("w:themeColor", "w:themeShade", "w:themeTint"):
                        if c.get(qn(attr)) is not None:
                            del c.attrib[qn(attr)]
            spf = st.paragraph_format
            spf.space_before = Pt(before)
            spf.space_after = Pt(after)
            spf.line_spacing = 1.5
            spf.keep_with_next = True
            spf.alignment = WD_ALIGN_PARAGRAPH.LEFT

        # Caption style (used by LOF/LOT field collection)
        try:
            cap = styles["Caption"]
        except KeyError:
            cap = styles.add_style("Caption", WD_STYLE_TYPE.PARAGRAPH)
            cap.base_style = styles["Normal"]
        cap.font.name = "Times New Roman"
        cap.font.size = Pt(10)
        cap.font.italic = True
        cap.font.bold = False
        cap.font.color.rgb = RGBColor(0, 0, 0)
        _force_font(cap.element, "Times New Roman")
        cpf = cap.paragraph_format
        cpf.line_spacing = 1.0
        cpf.space_before = Pt(4)
        cpf.space_after = Pt(8)
        cpf.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cpf.keep_with_next = False

    def _setup_header_footer(self) -> None:
        sec = self.doc.sections[0]
        if self.with_header:
            hp = sec.header.paragraphs[0]
            hp.text = ""
            hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = hp.add_run(self.tv.get("title", REPORT_TITLE))
            run.font.name = "Times New Roman"
            run.font.size = Pt(9)
            run.italic = True
            _force_font(run._r, "Times New Roman")
            _para_border(hp, color="808080", sz=4, sides=("bottom",), space=2)

        fp = sec.footer.paragraphs[0]
        fp.text = ""
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = fp.add_run("Page ")
        r.font.name = "Times New Roman"
        r.font.size = Pt(10)
        _add_field(fp, "PAGE", "1", font="Times New Roman", size=10)
        r = fp.add_run(" of ")
        r.font.name = "Times New Roman"
        r.font.size = Pt(10)
        _add_field(fp, "NUMPAGES", "1", font="Times New Roman", size=10)

    def ask_word_to_update_fields(self) -> None:
        settings = self.doc.settings.element
        el = OxmlElement("w:updateFields")
        el.set(qn("w:val"), "true")
        settings.append(el)

    # -- primitive emitters -----------------------------------------
    def page_break(self) -> None:
        p = self.doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.add_run().add_break(WD_BREAK.PAGE)

    def para(self, text: str = "", *, style: str | None = None,
             align=None, size: float | None = None, bold: bool = False,
             italic: bool = False, space_before: float | None = None,
             space_after: float | None = None, indent: float | None = None,
             keep_with_next: bool = False):
        p = self.doc.add_paragraph(style=style)
        pf = p.paragraph_format
        if align is not None:
            pf.alignment = align
        if space_before is not None:
            pf.space_before = Pt(space_before)
        if space_after is not None:
            pf.space_after = Pt(space_after)
        if indent is not None:
            pf.left_indent = Inches(indent)
        if keep_with_next:
            pf.keep_with_next = True
        if text:
            self._inline_runs(p, text, size=size, bold=bold, italic=italic)
        return p

    def _inline_runs(self, paragraph, text: str, *, size=None, bold=False,
                     italic=False, font=None, color=None) -> None:
        for kind, payload in _iter_inline(text):
            if kind == "plain":
                _emit_token_aware(paragraph, payload, font=font, size=size,
                                  bold=bold, italic=italic, color=color)
            elif kind == "bold":
                _emit_token_aware(paragraph, payload, font=font, size=size,
                                  bold=True, italic=italic, color=color)
            elif kind == "italic":
                _emit_token_aware(paragraph, payload, font=font, size=size,
                                  bold=bold, italic=True, color=color)
            elif kind == "code":
                _emit_token_aware(paragraph, payload, font="Consolas",
                                  size=(size or 12) - 1.5, bold=False,
                                  italic=False, color=color)
            elif kind == "link":
                label, url = payload  # type: ignore[misc]
                _emit_token_aware(paragraph, label, font=font, size=size,
                                  bold=bold, italic=italic, color=color)
                if url and not url.startswith("#"):
                    tail = paragraph.add_run(f" ({url})")
                    tail.font.name = "Times New Roman"
                    tail.font.size = Pt((size or 12) - 1)
                    tail.font.color.rgb = RGBColor(0x40, 0x40, 0x40)

    # -- structured emitters ----------------------------------------
    def heading(self, text: str, level: int, *, page_break_before: bool = False):
        p = self.doc.add_paragraph(style=f"Heading {level}")
        if page_break_before:
            p.paragraph_format.page_break_before = True
        _emit_token_aware(p, text, font="Times New Roman")
        return p

    def caption(self, kind: str, number: str, text: str) -> None:
        """Caption paragraph: `Figure 3.` + SEQ field + ` — caption`."""
        p = self.doc.add_paragraph(style="Caption")
        base = {"Figure": 10, "Table": 10}.get(kind, 10)
        r = p.add_run(f"{kind} ")
        r.font.name = "Times New Roman"
        r.font.size = Pt(base)
        r.bold = True
        r2 = p.add_run(f"{number.rsplit('.', 1)[0]}." if "." in number else "")
        r2.font.name = "Times New Roman"
        r2.font.size = Pt(base)
        r2.bold = True
        if "." in number:
            cached = number.rsplit(".", 1)[1]
        else:
            cached = number
        _add_field(p, f"SEQ {kind} \\* ARABIC", cached, font="Times New Roman",
                   size=base, bold=True)
        if text:
            r3 = p.add_run(" — ")
            r3.font.name = "Times New Roman"
            r3.font.size = Pt(base)
            _emit_token_aware(p, text, font="Times New Roman", size=base, italic=True)
        return p

    def code_block(self, block: Block) -> None:
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
        pf.space_before = Pt(6)
        pf.space_after = Pt(2)
        pf.left_indent = Inches(0.12)
        pf.right_indent = Inches(0.12)
        pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
        pf.keep_together = True
        _shade(p._p.get_or_add_pPr(), "F2F2F2")
        _para_border(p, color="D0D0D0", sz=6, space=6)

        body = "\n".join(block.lines) if block.lines else " "
        for i, line in enumerate(body.split("\n")):
            run = p.add_run(line if line else " ")
            run.font.name = "Consolas"
            run.font.size = Pt(9)
            _force_font(run._r, "Consolas")
            if i < body.count("\n"):
                run.add_break()

        cap = self.doc.add_paragraph()
        cap.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        cap.paragraph_format.space_before = Pt(2)
        cap.paragraph_format.space_after = Pt(10)
        cap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r = cap.add_run(f"Listing {block.number}")
        r.font.name = "Times New Roman"
        r.font.size = Pt(10)
        r.bold = True
        listing_title = block.caption or getattr(self, "_last_heading", "")
        if listing_title:
            _emit_token_aware(cap, f" — {listing_title}", font="Times New Roman",
                              size=10, italic=True)

    def table_block(self, block: Block) -> None:
        rows = block.rows
        ncols = len(rows[0]) if rows else 0
        if not ncols:
            return
        # caption above the table (Word convention)
        cap_text = block.caption or getattr(self, "_last_heading", "")
        cap_num = getattr(block, "label", "") or block.number
        if getattr(self, "_in_chapter", False) or getattr(self, "_number_tables", False):
            self.caption("Table", cap_num, cap_text)

        table = self.doc.add_table(rows=len(rows), cols=ncols)
        table.style = "Table Grid"
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = True

        for r_idx, row in enumerate(rows):
            for c_idx, cell_text in enumerate(row):
                cell = table.cell(r_idx, c_idx)
                cell.text = ""
                p = cell.paragraphs[0]
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.line_spacing = 1.0
                p.paragraph_format.alignment = (WD_ALIGN_PARAGRAPH.LEFT if c_idx == 0
                                                else WD_ALIGN_PARAGRAPH.LEFT)
                self._inline_runs(p, cell_text, size=10,
                                  bold=(r_idx == 0))
                if r_idx == 0:
                    _shade(cell._tc.get_or_add_tcPr(), "E8E8E8")

        # repeat header row across pages
        tr = table.rows[0]._tr
        trPr = tr.get_or_add_trPr()
        header = OxmlElement("w:tblHeader")
        header.set(qn("w:val"), "true")
        trPr.append(header)

        spacer = self.doc.add_paragraph()
        spacer.paragraph_format.space_after = Pt(4)
        spacer.paragraph_format.line_spacing = 1.0

    def figure_block(self, block: Block, report_dir: Path,
                     missing: list[tuple[str, str]]) -> None:
        resolved = resolve_figure(block.path, report_dir)
        if resolved is not None:
            width_in = 5.9
            if PILImage is not None:
                try:
                    with PILImage.open(resolved) as im:
                        px_w = im.size[0]
                    natural = px_w / 96.0
                    width_in = min(5.9, max(1.5, natural))
                except Exception:
                    pass
            self.doc.add_picture(str(resolved), width=Inches(width_in))
            pic_para = self.doc.paragraphs[-1]
            pic_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pic_para.paragraph_format.space_before = Pt(8)
            pic_para.paragraph_format.space_after = Pt(2)
            pic_para.paragraph_format.keep_with_next = True
            embedded = True
        else:
            missing.append((block.number, block.path))
            box = self.doc.add_table(rows=1, cols=1)
            box.style = "Table Grid"
            box.alignment = WD_TABLE_ALIGNMENT.CENTER
            cell = box.cell(0, 0)
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(24)
            p.paragraph_format.space_after = Pt(24)
            r = p.add_run(f"[figure missing — {block.path}]")
            r.font.name = "Consolas"
            r.font.size = Pt(9)
            r.bold = True
            r.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)
            _force_font(r._r, "Consolas")
            r2 = p.add_run("\nPlace the PNG/SVG export at this path, then rebuild.")
            r2.font.name = "Times New Roman"
            r2.font.size = Pt(9)
            r2.italic = True
            embedded = False

        self.caption("Figure", block.number, block.caption or block.text)
        # caption() consumes the block caption; return embedding state
        return None  # type: ignore[return-value]

    def quote_block(self, block: Block) -> None:
        p = self.para(block.text, indent=0.4, italic=True)
        _para_border(p, color="A0A0A0", sz=6, sides=("left",), space=8)

    def list_block(self, block: Block) -> None:
        for i, item in enumerate(block.items, start=1):
            bullet = f"{i}. " if block.ordered else "\u2022 "
            p = self.doc.add_paragraph()
            pf = p.paragraph_format
            pf.left_indent = Inches(0.35)
            pf.first_line_indent = Inches(-0.2)
            pf.space_after = Pt(3)
            pf.line_spacing = 1.5
            pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            r = p.add_run(bullet)
            r.font.name = "Times New Roman"
            r.font.size = Pt(12)
            self._inline_runs(p, item)

    def blocks(self, blocks: list[Block], report_dir: Path,
               missing_figs: list[tuple[str, str]]) -> None:
        for b in blocks:
            if b.kind == "heading":
                self.heading(b.label or b.text, b.level)
            elif b.kind == "para":
                if b.text:
                    self.para(b.text)
            elif b.kind == "code":
                self.code_block(b)
            elif b.kind == "table":
                self.table_block(b)
            elif b.kind == "figure":
                self.figure_block(b, report_dir, missing_figs)
            elif b.kind == "list":
                self.list_block(b)
            elif b.kind == "quote":
                self.quote_block(b)
            elif b.kind == "hr":
                p = self.doc.add_paragraph()
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(8)
                _para_border(p, color="BFBFBF", sz=4, sides=("bottom",), space=1)

    # -- front matter pages -----------------------------------------
    def title_page(self) -> None:
        self.para(space_after=0)
        self.para(self.tv["institution"], align=WD_ALIGN_PARAGRAPH.CENTER,
                  size=14, bold=True, space_after=2)
        self.para(self.tv["department"], align=WD_ALIGN_PARAGRAPH.CENTER,
                  size=12, space_after=18)
        self.para(f"({SUBMISSION_CODE} — {self.doc_code})",
                  align=WD_ALIGN_PARAGRAPH.CENTER, size=11, bold=True,
                  space_after=30)
        self.para(self.tv["title"], align=WD_ALIGN_PARAGRAPH.CENTER, size=20,
                  bold=True, space_after=8)
        self.para("A deterministic rule engine with an optional LLM review layer",
                  align=WD_ALIGN_PARAGRAPH.CENTER, size=11, italic=True, space_after=34)
        self.para("Submitted in partial fulfilment of the requirements for the award of",
                  align=WD_ALIGN_PARAGRAPH.CENTER, size=11, space_after=2)
        self.para(self.tv["programme"], align=WD_ALIGN_PARAGRAPH.CENTER, size=12,
                  bold=True, space_after=26)
        self.para("Submitted by", align=WD_ALIGN_PARAGRAPH.CENTER, size=11,
                  space_after=2)
        self.para(self.tv["candidate"], align=WD_ALIGN_PARAGRAPH.CENTER, size=13,
                  bold=True, space_after=2)
        self.para(f"Enrolment No. {self.tv['roll']}", align=WD_ALIGN_PARAGRAPH.CENTER,
                  size=11, space_after=2)
        self.para(f"Study Centre: {self.tv.get('study_centre', '')}",
                  align=WD_ALIGN_PARAGRAPH.CENTER, size=11, space_after=2)
        self.para(f"Regional Centre: {self.tv.get('regional_centre', '')}",
                  align=WD_ALIGN_PARAGRAPH.CENTER, size=11, space_after=20)
        self.para("Under the supervision of", align=WD_ALIGN_PARAGRAPH.CENTER,
                  size=11, space_after=2)
        self.para(self.tv["supervisor"], align=WD_ALIGN_PARAGRAPH.CENTER, size=13,
                  bold=True, space_after=24)
        self.para(self.tv["session"], align=WD_ALIGN_PARAGRAPH.CENTER, size=11,
                  space_after=2)
        self.para(self.tv["date"], align=WD_ALIGN_PARAGRAPH.CENTER, size=11)

    def front_section(self, name: str, body: str, report_dir: Path,
                      missing_figs: list[tuple[str, str]]) -> None:
        self.page_break()
        self.heading(name, 1)
        blocks = parse_markdown(body) if body.strip() else []
        if not blocks:
            self.para(f"[FILL: {name.lower()} text — this page was not supplied in "
                      f"front-matter.md]")
            return
        self.blocks(blocks, report_dir, missing_figs)

    def toc_field(self) -> None:
        p = self.doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.15
        _add_field(
            p, r'TOC \o "1-3" \h \z \u',
            cached="[Table of contents — a Word field. Select all (Ctrl+A), then press "
                   "F9 to build it with page numbers.]",
            font="Times New Roman", size=11, italic=False,
        )
        self.para("Right-click anywhere in the field above and choose "
                  "\u201cUpdate Field\u201d, or press Ctrl+A then F9, to populate the "
                  "contents with page numbers.", size=10, italic=True,
                  space_before=10, align=WD_ALIGN_PARAGRAPH.LEFT)

    def caption_list_field(self, kind: str) -> None:
        p = self.doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.15
        _add_field(
            p, f'TOC \\h \\z \\c "{kind}"',
            cached=f"[List of {kind}s — a Word field. Press Ctrl+A then F9 to build it.]",
            font="Times New Roman", size=11,
        )
        self.para("Same field-update step as the table of contents.", size=10,
                  italic=True, space_before=8, align=WD_ALIGN_PARAGRAPH.LEFT)

    def save(self, path: Path) -> None:
        self.ask_word_to_update_fields()
        self.doc.save(str(path))


# --------------------------------------------------------------------------
# PDF builder (reportlab platypus)
# --------------------------------------------------------------------------

_TOTAL_PAGES: int | None = None
_FOOTER_TITLE = REPORT_TITLE_SHORT


def _pdf_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _pdf_inline(text: str) -> str:
    """Convert the report's inline markdown to reportlab mini-HTML."""
    placeholders: list[str] = []

    def stash(html: str) -> str:
        placeholders.append(html)
        return f"\x00{len(placeholders) - 1}\x00"

    text = _pdf_escape(text)

    # inline code first, so ** inside code is not eaten
    def code_repl(m: re.Match) -> str:
        return stash(f'<font face="Courier">{m.group(1)}</font>')

    text = re.sub(r"`([^`\n]+)`", code_repl, text)

    def fill_repl(m: re.Match) -> str:
        return stash(f'<font color="#C00000"><b>{m.group(0)}</b></font>')

    text = FILL_TOKEN_RE.sub(fill_repl, text)

    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*\n]+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)

    for i, html in enumerate(placeholders):
        text = text.replace(f"\x00{i}\x00", html)
    return text


def _plain_caption(kind: str, block: Block) -> str:
    text = block.caption or block.text
    return f"{kind} {block.number}" + (f" — {text}" if text else "")


class PdfBuilder:
    def __init__(self, title_values: dict[str, str], path: Path,
                 doc_code: str = "PROJECT REPORT"):
        if BaseDocTemplate is None:
            raise SystemExit(
                "assemble.py: reportlab is not installed.\n  pip install reportlab"
            )
        self.tv = title_values
        self.path = path
        self.doc_code = doc_code
        self.story: list = []
        self._bookmark_id = 0
        self._setup_styles()
        self.doc = BaseDocTemplate(
            str(path), pagesize=A4,
            leftMargin=25 * mm, rightMargin=20 * mm,
            topMargin=25 * mm, bottomMargin=22 * mm,
            title=title_values.get("title", REPORT_TITLE),
            author=title_values.get("candidate", ""),
            subject=f"{SUBMISSION_CODE} project report",
        )
        frame = Frame(self.doc.leftMargin, self.doc.bottomMargin,
                      self.doc.width, self.doc.height, id="body")
        self.doc.addPageTemplates([
            PageTemplate(id="first", frames=[frame], onPage=self._on_first),
            PageTemplate(id="later", frames=[frame], onPage=self._on_later),
        ])
        self.doc.afterFlowable = self._after_flowable  # type: ignore[assignment]
        self.frame_width = self.doc.width

    # -- styles ------------------------------------------------------
    def _setup_styles(self) -> None:
        ss = getSampleStyleSheet()
        self.body = ParagraphStyle(
            "BodyTNR", parent=ss["Normal"], fontName="Times-Roman", fontSize=12,
            leading=18, alignment=TA_JUSTIFY, spaceAfter=6, spaceBefore=0,
            firstLineIndent=0, allowWidows=1, allowOrphans=1,
        )
        self.body_left = ParagraphStyle("BodyTNRLeft", parent=self.body,
                                        alignment=TA_LEFT)
        self.h1 = ParagraphStyle(
            "H1TNR", parent=ss["Heading1"], fontName="Times-Bold", fontSize=16,
            leading=20, spaceBefore=6, spaceAfter=12, alignment=TA_LEFT,
            textColor=colors.black,
        )
        self.h2 = ParagraphStyle(
            "H2TNR", parent=self.h1, fontSize=14, leading=18, spaceBefore=14,
            spaceAfter=8,
        )
        self.h3 = ParagraphStyle(
            "H3TNR", parent=self.h1, fontSize=12, leading=16, spaceBefore=12,
            spaceAfter=6,
        )
        self.caption = ParagraphStyle(
            "CaptionTNR", parent=self.body, fontSize=10, leading=13,
            alignment=TA_CENTER, spaceBefore=4, spaceAfter=10,
        )
        self.code = ParagraphStyle(
            "CodeCourier", parent=ss["Code"], fontName="Courier", fontSize=8.5,
            leading=10.5, alignment=TA_LEFT, spaceBefore=0, spaceAfter=0,
            leftIndent=0,
        )
        self.cell = ParagraphStyle("CellTNR", parent=self.body, fontSize=9.5,
                                   leading=12, alignment=TA_LEFT, spaceAfter=0)
        self.cell_head = ParagraphStyle("CellHeadTNR", parent=self.cell,
                                        fontName="Times-Bold")
        self.quote = ParagraphStyle("QuoteTNR", parent=self.body, fontName="Times-Italic",
                                    leftIndent=18, spaceBefore=6, spaceAfter=10)

    # -- page furniture ---------------------------------------------
    def _on_first(self, canv, doc) -> None:
        """Cover page: no header, no page number (it is counted, not printed)."""
        return

    def _on_later(self, canv, doc) -> None:
        canv.saveState()
        canv.setFont("Times-Italic", 8.5)
        canv.setFillColor(colors.HexColor("#555555"))
        canv.drawCentredString(A4[0] / 2, A4[1] - 15 * mm, _FOOTER_TITLE)
        canv.setStrokeColor(colors.HexColor("#999999"))
        canv.setLineWidth(0.4)
        canv.line(doc.leftMargin, A4[1] - 17 * mm,
                  A4[0] - doc.rightMargin, A4[1] - 17 * mm)
        canv.setFillColor(colors.black)
        canv.setFont("Times-Roman", 10)
        total = _TOTAL_PAGES if _TOTAL_PAGES else 1
        canv.drawCentredString(A4[0] / 2, 12 * mm, f"Page {doc.page} of {total}")
        canv.restoreState()

    def _after_flowable(self, flowable) -> None:
        cap_kind = getattr(flowable, "_cap_kind", None)
        if cap_kind:
            self.doc.notify(f"{cap_kind}Entry",
                            (0, flowable._cap_text, self.doc.page))
            return
        level = getattr(flowable, "_toc_level", None)
        if level is None:
            return
        text = getattr(flowable, "_toc_text", "")
        self._bookmark_id += 1
        key = f"bm{self._bookmark_id}"
        self.doc.canv.bookmarkPage(key)
        self.doc.canv.addOutlineEntry(text, key, level=level, closed=(level > 0))
        self.doc.notify("TOCEntry", (level, text, self.doc.page))

    # -- emitters ---------------------------------------------------
    def _heading(self, text: str, level: int, *, page_break_before: bool = False):
        style = {1: self.h1, 2: self.h2, 3: self.h3}[level]
        if page_break_before:
            self.story.append(NextPageTemplate("later"))
            self.story.append(PageBreak())
        p = Paragraph(_pdf_inline(text), style)
        p._toc_level = level - 1          # type: ignore[attr-defined]
        p._toc_text = text                # type: ignore[attr-defined]
        self._last_heading = text
        if level == 1 and text.strip().lower().startswith("chapter"):
            self._in_chapter = True
        self._last_heading = text
        if level == 1 and text.strip().lower().startswith("chapter"):
            self._in_chapter = True
        self.story.append(p)
        return p

    def _para(self, text: str) -> None:
        self.story.append(Paragraph(_pdf_inline(text), self.body))

    def _code(self, block: Block) -> None:
        """Render a fenced block, split so no table cell exceeds a page frame.

        A single-cell Table cannot split across pages, so a 100-line listing would raise
        LayoutError. Chunking keeps every flowable well under the frame height.
        """
        lines = block.lines or [" "]
        safe = [ln.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") for ln in lines]
        chunk_size = 34
        chunks = [safe[i:i + chunk_size] for i in range(0, len(safe), chunk_size)] or [[" "]]
        for chunk in chunks:
            inner = XPreformatted("\n".join(chunk), self.code)
            t = Table([[inner]], colWidths=[self.frame_width])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F2F2F2")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            self.story.append(t)
        listing_title = block.caption or getattr(self, "_last_heading", "")
        cap = f"<b>Listing {block.number}</b>"
        if listing_title:
            cap += f" — <i>{_pdf_inline(listing_title)}</i>"
        self.story.append(Paragraph(cap, ParagraphStyle(
            "ListingCap", parent=self.caption, alignment=TA_LEFT, fontSize=10,
            spaceBefore=3, spaceAfter=10)))

    def _table(self, block: Block) -> None:
        rows = block.rows
        if not rows:
            return
        ncols = len(rows[0])
        avail = self.frame_width
        first = max(0.12, 0.30)
        rest = (1.0 - first) / max(1, ncols - 1)
        widths = [avail * first] + [avail * rest] * (ncols - 1)
        data = []
        for r_idx, row in enumerate(rows):
            style = self.cell_head if r_idx == 0 else self.cell
            data.append([Paragraph(_pdf_inline(c), style) for c in row])
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#808080")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8E8E8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        if not (getattr(self, "_in_chapter", False) or getattr(self, "_number_tables", False)):
            self.story.append(t)
            self.story.append(Spacer(1, 8))
            return
        caption_text = block.caption or getattr(self, "_last_heading", "")
        cap_num = getattr(block, "label", "") or block.number
        cap = f"<b>Table {cap_num}</b>"
        if caption_text:
            cap += f" — <i>{_pdf_inline(caption_text)}</i>"
        cap_para = Paragraph(cap, self.caption)
        cap_para._cap_kind = "Table"
        cap_para._cap_text = (f"Table {block.number} — {caption_text}"
                               if caption_text else f"Table {block.number}")
        self.story.append(KeepTogether([cap_para, t]))
        self.story.append(Spacer(1, 8))

    def _figure(self, block: Block, report_dir: Path,
                missing: list[tuple[str, str]]) -> None:
        resolved = resolve_figure(block.path, report_dir)
        cap = f"<b>Figure {block.number}</b>"
        if block.caption or block.text:
            cap += f" — <i>{_pdf_inline(block.caption or block.text)}</i>"
        if resolved is not None:
            try:
                from reportlab.lib.utils import ImageReader
                iw, ih = ImageReader(str(resolved)).getSize()
                scale = getattr(self, "image_scale", 1.0)
                w = min(self.frame_width * 0.97, iw * 72.0 / 96.0) * scale
                h = w * ih / iw
                max_h = getattr(self, "figure_max_mm", 150) * mm
                if h > max_h:
                    h = max_h
                    w = h * iw / ih
                cap_para = Paragraph(cap, self.caption)
                cap_para._cap_kind = "Figure"
                cap_para._cap_text = _plain_caption("Figure", block)
                pair = [Image(str(resolved), width=w, height=h), cap_para]
                if getattr(self, "figure_keep_together", True):
                    self.story.append(KeepTogether(pair))
                else:
                    self.story.extend(pair)
                return
            except Exception:
                pass
        missing.append((block.number, block.path))
        box = Table([[Paragraph(
            f'<font face="Courier" color="#C00000"><b>[figure missing — '
            f'{_pdf_escape(block.path)}]</b></font><br/>'
            f'<i>Place the image at this path, then rebuild.</i>',
            self.caption)]],
            colWidths=[self.frame_width], rowHeights=[35 * mm])
        box.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#808080")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        cap_para = Paragraph(cap, self.caption)
        cap_para._cap_kind = "Figure"
        cap_para._cap_text = _plain_caption("Figure", block)
        self.story.append(KeepTogether([box, cap_para]))

    def _list(self, block: Block) -> None:
        for i, item in enumerate(block.items, start=1):
            bullet = f"{i}." if block.ordered else "\u2022"
            self.story.append(Paragraph(
                f"{bullet}\u00a0\u00a0{_pdf_inline(item)}",
                ParagraphStyle("Bullet", parent=self.body, leftIndent=18,
                               firstLineIndent=-12, spaceAfter=3)))

    def _quote(self, block: Block) -> None:
        self.story.append(Paragraph(_pdf_inline(block.text), self.quote))

    def blocks(self, blocks: list[Block], report_dir: Path,
               missing_figs: list[tuple[str, str]]) -> None:
        for b in blocks:
            if b.kind == "heading":
                self._heading(b.label or b.text, b.level)
            elif b.kind == "para":
                if b.text:
                    self._para(b.text)
            elif b.kind == "code":
                self._code(b)
            elif b.kind == "table":
                self._table(b)
            elif b.kind == "figure":
                self._figure(b, report_dir, missing_figs)
            elif b.kind == "list":
                self._list(b)
            elif b.kind == "quote":
                self._quote(b)
            elif b.kind == "hr":
                self.story.append(Spacer(1, 6))

    # -- front matter -----------------------------------------------
    def title_page(self) -> None:
        tv = self.tv
        s = self.body
        centre = ParagraphStyle("C", parent=s, alignment=TA_CENTER)
        self.story += [
            Spacer(1, 10 * mm),
            Paragraph(_pdf_inline(tv["institution"]),
                      ParagraphStyle("Inst", parent=centre, fontName="Times-Bold",
                                     fontSize=14, spaceAfter=2)),
            Paragraph(_pdf_inline(tv["department"]), centre),
            Spacer(1, 8 * mm),
            Paragraph(f"({SUBMISSION_CODE} — {self.doc_code})",
                      ParagraphStyle("Code2", parent=centre, fontName="Times-Bold",
                                     fontSize=11)),
            Spacer(1, 16 * mm),
            Paragraph(_pdf_inline(tv["title"]),
                      ParagraphStyle("Title", parent=centre, fontName="Times-Bold",
                                     fontSize=20, leading=26, spaceAfter=6)),
            Paragraph("A deterministic rule engine with an optional LLM review layer",
                      ParagraphStyle("Sub", parent=centre, fontName="Times-Italic",
                                     fontSize=11)),
            Spacer(1, 18 * mm),
            Paragraph("Submitted in partial fulfilment of the requirements for the "
                      "award of", centre),
            Paragraph(_pdf_inline(tv["programme"]),
                      ParagraphStyle("Prog", parent=centre, fontName="Times-Bold",
                                     fontSize=12)),
            Spacer(1, 14 * mm),
            Paragraph("Submitted by", centre),
            Paragraph(_pdf_inline(tv["candidate"]),
                      ParagraphStyle("Cand", parent=centre, fontName="Times-Bold",
                                     fontSize=13)),
            Paragraph(f"Enrolment No. {_pdf_inline(tv['roll'])}", centre),
            Spacer(1, 12 * mm),
            Paragraph("Under the supervision of", centre),
            Paragraph(_pdf_inline(tv["supervisor"]),
                      ParagraphStyle("Sup", parent=centre, fontName="Times-Bold",
                                     fontSize=13)),
            Spacer(1, 12 * mm),
            Paragraph(_pdf_inline(tv["session"]), centre),
            Paragraph(_pdf_inline(tv["date"]), centre),
            NextPageTemplate("later"),
        ]

    def toc(self, kind: str = "contents") -> None:
        """Emit the table of contents, or one of the two caption lists.

        Page numbers come from reportlab's multiBuild pass, so all three front
        lists carry real numbers -- there is no F9 equivalent to press here.
        """
        low = kind.strip().lower()
        if low in ("contents", "table of contents"):
            self._heading("Table of Contents", 1, page_break_before=True)
            toc = TableOfContents()
            toc.levelStyles = [
                ParagraphStyle("TOC1", fontName="Times-Bold", fontSize=11,
                               leading=16, leftIndent=0, firstLineIndent=0,
                               spaceBefore=4, dotsMinLevel=0),
                ParagraphStyle("TOC2", fontName="Times-Roman", fontSize=11,
                               leading=15, leftIndent=14, firstLineIndent=0,
                               dotsMinLevel=0),
                ParagraphStyle("TOC3", fontName="Times-Roman", fontSize=10,
                               leading=14, leftIndent=28, firstLineIndent=0,
                               dotsMinLevel=0),
            ]
            self.story.append(toc)
            return

        label = "Figure" if "figure" in low else "Table"
        self._heading(kind, 1, page_break_before=True)
        cap_toc = TableOfContents(notifyKind=f"{label}Entry")
        cap_toc.levelStyles = [ParagraphStyle(
            f"{label}TOC", fontName="Times-Roman", fontSize=10.5, leading=15,
            leftIndent=0, firstLineIndent=0, spaceBefore=2, dotsMinLevel=0)]
        self.story.append(cap_toc)

    def front_section(self, name: str, body: str, report_dir: Path,
                      missing_figs: list[tuple[str, str]]) -> None:
        self._heading(name, 1, page_break_before=True)
        blocks = parse_markdown(body) if body.strip() else []
        if not blocks:
            self.story.append(Paragraph(
                f'<font color="#C00000"><b>[FILL: {name.lower()} text — this page was '
                f'not supplied in front-matter.md]</b></font>', self.body))
            return
        self.blocks(blocks, report_dir, missing_figs)

    def build(self) -> None:
        self.doc.multiBuild(self.story, maxPasses=25)


# --------------------------------------------------------------------------
# Document plans
# --------------------------------------------------------------------------

def build_report_docx(out_path: Path, tv: dict[str, str], fields: dict[str, str],
                      sections: list[tuple[str, str]], chapters: list[Chapter],
                      report_dir: Path, inventory: Inventory,
                      missing_figs: list[tuple[str, str]]) -> None:
    b = DocxBuilder(tv)
    b.title_page()

    section_map = {re.sub(r"[^a-z]", "", n.lower()): (n, body) for n, body in sections}
    # certificate, acknowledgement and abstract, in that order, each exactly once
    for canonical_list, display in FRONT_MATTER_PAGES:
        body = next((section_map[c][1] for c in canonical_list if c in section_map), None)
        if body is None:
            token = f"[FILL: {display.lower()} text]"
            inventory.add("front-matter.md (generated)", token)
            body = token
        b.front_section(display, body, report_dir, missing_figs)

    # contents
    b.page_break()
    b.heading("Table of Contents", 1)
    b.toc_field()

    b.page_break()
    b.heading("List of Figures", 1)
    b.caption_list_field("Figure")
    b.page_break()
    b.heading("List of Tables", 1)
    b.caption_list_field("Table")

    for ch in chapters:
        b.heading(ch.label, 1, page_break_before=True)
        b.blocks(ch.blocks, report_dir, missing_figs)

    b.save(out_path)


def build_report_pdf(out_path: Path, tv: dict[str, str],
                     sections: list[tuple[str, str]], chapters: list[Chapter],
                     report_dir: Path, missing_figs: list[tuple[str, str]]) -> None:
    b = PdfBuilder(tv, out_path)
    b.title_page()

    section_map = {re.sub(r"[^a-z]", "", n.lower()): (n, body) for n, body in sections}
    for canonical_list, display in FRONT_MATTER_PAGES:
        body = next((section_map[c][1] for c in canonical_list if c in section_map), None)
        if body is None:
            body = "[FILL: this page was not supplied in front-matter.md]"
        b.front_section(display, body, report_dir, missing_figs)

    b.toc("Table of Contents")
    b.toc("List of Figures")
    b.toc("List of Tables")

    for ch in chapters:
        b._heading(ch.label, 1, page_break_before=True)
        b.blocks(ch.blocks, report_dir, missing_figs)

    b.build()


def build_proposal(out_docx: Path, out_pdf: Path, tv: dict[str, str],
                   blocks: list[Block], report_dir: Path,
                   missing_figs: list[tuple[str, str]]) -> None:
    """Proposal/synopsis: front page + the synopsis body, nothing else."""
    title = tv.get("title", REPORT_TITLE)
    ptv = dict(tv)
    ptv["title"] = f"{title} — Project Synopsis"

    heading = "Project Synopsis"
    body = list(blocks)
    if body and body[0].kind == "heading" and body[0].level == 1:
        heading = body[0].text.strip() or heading
        body = body[1:]

    b = DocxBuilder(ptv, with_header=True, doc_code="PROJECT PROPOSAL")
    # A synopsis is a 15-20 page document, so it is set denser than the report:
    # 11 pt on 1.15 spacing instead of 12 pt on 1.5. Same content, compliant length.
    _normal = b.doc.styles["Normal"]
    _normal.font.size = Pt(11)
    _normal.paragraph_format.line_spacing = 1.15
    _normal.paragraph_format.space_after = Pt(4)
    b._number_tables = True
    b.title_page()
    b.page_break()
    b.heading(heading, 1)
    b.blocks(body, report_dir, missing_figs)
    b.save(out_docx)

    def _proposal_pdf(target: Path, figs: list) -> None:
        p = PdfBuilder(ptv, target, doc_code="PROJECT PROPOSAL")
        p.image_scale = 0.85
        p._number_tables = True
        p.figure_keep_together = False
        p.figure_max_mm = 78
        p.body = ParagraphStyle("PropBody", parent=p.body, fontSize=10,
                                leading=12.6, spaceAfter=2)
        p.code = ParagraphStyle("PropCode", parent=p.code, fontSize=7.6, leading=9.0)
        if hasattr(p, "bullet"):
            p.bullet = ParagraphStyle("PropBullet", parent=p.bullet, fontSize=10,
                                      leading=12.6, spaceAfter=1)
        p.title_page()
        p._heading(heading, 1, page_break_before=True)
        p.blocks(body, report_dir, figs)
        p.build()

    two_pass_pdf(_proposal_pdf, out_pdf, missing_figs)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def word_count(chapters: list[Chapter]) -> tuple[int, int]:
    """(prose words excluding code listings and table cells, all words)."""
    prose = 0
    total = 0
    for ch in chapters:
        for b in ch.blocks:
            if b.kind in ("para", "quote"):
                total += len(b.text.split())
                prose += len(b.text.split())
            elif b.kind == "heading":
                total += len(b.text.split())
                prose += len(b.text.split())
            elif b.kind == "list":
                for it in b.items:
                    total += len(it.split())
                    prose += len(it.split())
            elif b.kind == "code":
                total += sum(len(line.split()) for line in b.lines)
            elif b.kind == "table":
                total += sum(len(c.split()) for row in b.rows for c in row)
            elif b.kind == "figure":
                total += len((b.caption or b.text).split())
                prose += len((b.caption or b.text).split())
    return prose, total


def two_pass_pdf(build, final_path: Path, missing_out: list) -> int | None:
    """Build a PDF twice so "Page X of Y" carries the true total.

    The first pass is thrown away; only its page count is kept. The second pass
    writes the real file and records missing figures into `missing_out`.
    """
    global _TOTAL_PAGES
    with tempfile.TemporaryDirectory() as td:
        probe = Path(td) / "probe.pdf"
        _TOTAL_PAGES = None
        build(probe, [])
        _TOTAL_PAGES = pdf_page_count(probe)
        build(final_path, missing_out)
        return _TOTAL_PAGES


def pdf_page_count(path: Path) -> int | None:
    if PdfReader is None or not path.is_file():
        return None
    try:
        return len(PdfReader(str(path)).pages)
    except Exception:
        return None


def pages_with_listings(path: Path) -> int:
    """Count PDF pages whose text carries a 'Listing N' caption.

    An estimate of the pages that the page-count rule excludes: a listing's
    caption sits on the same page as (or immediately after) its code block.
    """
    if PdfReader is None or not path.is_file():
        return 0
    try:
        reader = PdfReader(str(path))
        hits = 0
        for page in reader.pages:
            if re.search(r"\bListing \d+", page.extract_text() or ""):
                hits += 1
        return hits
    except Exception:
        return 0


def print_inventory(inventory: Inventory, stream=sys.stdout) -> None:
    grouped = inventory.by_file()
    total = sum(len(v) for v in grouped.values())
    print(f"\nFill-in inventory: {total} token(s) in {len(grouped)} file(s)")
    if not total:
        print("  (none found — every placeholder has been filled)")
        return
    for relpath in sorted(grouped):
        print(f"  {relpath}")
        for token in grouped[relpath]:
            print(f"    - {token}")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def die(message: str, code: int = 2) -> "NoReturn":  # noqa: F821
    """Print a build-stopping message to stderr and exit non-zero."""
    print(message, file=sys.stderr)
    raise SystemExit(code)


def preflight(report_dir: Path, need_proposal: bool) -> list[str]:
    """Return every required input that is absent, as repo-relative paths."""
    missing: list[str] = []
    if not (report_dir / "front-matter.md").is_file():
        missing.append("docs/report/front-matter.md")
    chapters_dir = report_dir / "chapters"
    for number, stem, _fallback in CANONICAL_CHAPTERS:
        if not chapters_dir.is_dir():
            missing.append(f"docs/report/chapters/{stem}.md")
            continue
        if resolve_chapter_file(chapters_dir, number, stem) is None:
            missing.append(f"docs/report/chapters/{stem}.md")
    if need_proposal and not (report_dir / "proposal" / "synopsis.md").is_file():
        missing.append("docs/report/proposal/synopsis.md")
    return missing

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Assemble the MCSP-232 report and proposal from markdown.")
    ap.add_argument("--out", default="docs/report/out",
                    help="output directory (default: docs/report/out)")
    ap.add_argument("--report-dir", default=None,
                    help="directory holding front-matter.md, chapters/, proposal/ "
                         "(default: the directory containing this script)")
    ap.add_argument("--allow-missing", action="store_true",
                    help="build a partial draft even if chapter files are absent")
    ap.add_argument("--inventory", action="store_true",
                    help="print the fill-in inventory and exit without building")
    ap.add_argument("--no-proposal", action="store_true",
                    help="skip the proposal DOCX/PDF")
    ap.add_argument("--no-pdf", action="store_true", help="skip PDF output")
    args = ap.parse_args(argv)

    missing_deps = sorted(set(_MISSING))
    if missing_deps:
        raise SystemExit(
            "assemble.py: missing dependencies: " + ", ".join(missing_deps) + "\n"
            "  pip install -r requirements.lock   # or: pip install python-docx==1.2.0 "
            "reportlab pypdf pillow"
        )

    here = Path(__file__).resolve().parent
    report_dir = Path(args.report_dir).resolve() if args.report_dir else here
    out_dir = Path(args.out).resolve()

    inventory = Inventory()

    # ---- pre-flight: name every missing input in one message -------------
    missing_inputs = preflight(report_dir, need_proposal=not args.no_proposal)
    if missing_inputs and not args.allow_missing and not args.inventory:
        listing = "\n".join(f"  - {m}" for m in missing_inputs)
        die(
            "assemble.py: cannot build — required input(s) are missing:\n"
            f"{listing}\n\n"
            f"{len(missing_inputs)} file(s) absent. Nothing was written.\n"
            "Chapters are matched on their two-digit prefix, so 01-anything.md\n"
            "satisfies chapter 1; the canonical name is only a fallback.\n\n"
            "Create the file(s) above, or run with --allow-missing to build a\n"
            "partial draft from whatever exists (missing pages are then replaced\n"
            "by [FILL: ...] placeholders and reported)."
        )

    fields, sections, fm_source = load_front_matter(report_dir, inventory, True)
    chapters, found, missing = load_chapters(report_dir, inventory, True)
    tv = title_values(fields, inventory, fm_source)

    synopsis_path = report_dir / "proposal" / "synopsis.md"
    synopsis_blocks: list[Block] | None = None
    if synopsis_path.is_file():
        stext = synopsis_path.read_text(encoding="utf-8")
        inventory.scan_text("proposal/synopsis.md", stext)
        synopsis_blocks = parse_markdown(stext)
    elif not args.no_proposal:
        print("assemble.py: proposal/synopsis.md is absent — skipping the proposal "
              "DOCX/PDF.", file=sys.stderr)

    counts = annotate(chapters)
    if synopsis_blocks is not None:
        annotate([Chapter(number=1, title="Synopsis", blocks=synopsis_blocks,
                          source="proposal/synopsis.md")])

    if args.inventory:
        print(f"Report directory: {report_dir}")
        print(f"Chapters found: {len(found)}  missing: {len(missing)}")
        if missing:
            for m in missing:
                print(f"  MISSING  docs/report/{m}")
        print_inventory(inventory)
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    missing_figs: list[tuple[str, str]] = []
    embedded_figs = 0

    # --- DOCX ------------------------------------------------------
    docx_path = out_dir / DOCX_REPORT
    build_report_docx(docx_path, tv, fields, sections, chapters, report_dir,
                      inventory, missing_figs)

    # --- PDF (two passes so "Page X of Y" carries the true total) ---
    global _TOTAL_PAGES
    pdf_path = out_dir / PDF_REPORT
    if not args.no_pdf:
        missing_figs.clear()
        two_pass_pdf(
            lambda target, figs: build_report_pdf(target, tv, sections, chapters,
                                                  report_dir, figs),
            pdf_path, missing_figs)

    # --- proposal --------------------------------------------------
    prop_docx = prop_pdf = None
    if synopsis_blocks is not None and not args.no_proposal:
        prop_docx = out_dir / DOCX_PROPOSAL
        prop_pdf = out_dir / PDF_PROPOSAL
        build_proposal(prop_docx, prop_pdf, tv, synopsis_blocks, report_dir,
                       missing_figs)

    # --- figure accounting -----------------------------------------
    figs = walk_figures(chapters)
    missing_paths = {p for _n, p in missing_figs}
    embedded_figs = sum(1 for f in figs if f.path not in missing_paths)
    missing_fig_count = len(figs) - embedded_figs

    prose_words, all_words = word_count(chapters)
    pages = pdf_page_count(pdf_path) if pdf_path else None

    # --- summary ---------------------------------------------------
    print("=" * 74)
    print(f"MCSP-232 assembler — report directory: {report_dir}")
    print("=" * 74)
    print(f"Front matter  : {fm_source}")
    print(f"Chapters found: {len(found)}/12")
    for src in found:
        print(f"  ok       docs/report/{src}")
    if missing:
        for m in missing:
            print(f"  MISSING  docs/report/{m}")
        print("  (partial draft: --allow-missing was given)")
    print(f"Figures       : {len(figs)} referenced, {embedded_figs} embedded, "
          f"{missing_fig_count} missing")
    for num, path in missing_figs:
        print(f"  missing  Figure {num}: {path}")
    print(f"Tables        : {counts['tables']} rendered "
          f"({counts['tables_missing_caption']} without a caption line)")
    print(f"Listings      : {counts['listings']}")
    print(f"Word count    : {prose_words:,} prose words "
          f"({all_words:,} including code listings and table cells)")
    if pages is not None:
        lo, hi = PAGE_TARGET
        code_pages = pages_with_listings(pdf_path)
        excl = pages - code_pages
        verdict = ("inside" if lo <= excl <= hi
                   else "BELOW" if excl < lo else "ABOVE")
        verb = "carries" if code_pages == 1 else "carry"
        print(f"PDF pages     : {pages} total, {code_pages} of them {verb} code "
              f"listings, so about {excl} non-coding pages")
        print(f"                target {lo}-{hi} excluding coding: {verdict} the range")
    else:
        print("PDF pages     : not built")
    print("\nOutputs:")
    for p in (docx_path, pdf_path, prop_docx, prop_pdf):
        if p and p.is_file():
            print(f"  {p}  ({p.stat().st_size / 1024:.0f} KB)")
    print_inventory(inventory)
    print("\nNext: open the DOCX and press Ctrl+A then F9 to populate the table of "
          "contents,\nlist of figures and list of tables. See docs/report/FORMAT.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
