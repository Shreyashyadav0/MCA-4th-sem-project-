#!/usr/bin/env python3
"""Deterministic matplotlib generator for the IGNOU MCSP-232 analysis diagrams.

Five figures are produced, all from this one script, with no external images,
no graphviz and no network access:

  dfd-level-0.png    context diagram: one process, three external entities,
                     two data stores
  dfd-level-1.png    seven processes, the same entities and stores
  dfd-level-2.png    process 2.0 and process 3.0 decomposed (2.1-2.5, 3.1-3.5)
  er-diagram.png     the six-table schema: roles, users, reviews, findings,
                     pr_posts, benchmark_runs
  class-diagram.png  the dataclasses of app/models.py, app/parser.py,
                     app/rules.py, the providers and app/github_client.py

Every box is sized from the measured width of the text it holds (see
``measure``), so a label can never overflow its box: the drawing code asserts
that each measured string fits inside the box it was sized for, that no two
boxes overlap, that no label sits on top of a box, and that each saved PNG is
larger than 20 KB.

Run from anywhere:

    python docs/diagrams/make_diagrams.py

Output goes next to this file. Layout is fixed (no randomness, no timestamps),
so two runs produce byte-identical PNGs.
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: ``True`` when matplotlib is installed. The drawing code needs it; the schema
#: reader in :func:`_er_columns` does not, and ``tests/test_diagram_generator.py``
#: imports this module on a machine where matplotlib is absent (CI installs only
#: ``requirements.lock``), so a missing matplotlib must not make the module
#: unimportable. Every drawing entry point raises instead.
try:  # pragma: no cover - the installed path is exercised by every real run
    import matplotlib

    matplotlib.use("Agg")

    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    from matplotlib.lines import Line2D
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon
    from matplotlib.path import Path as MPath
    from matplotlib.textpath import TextPath

    HAVE_MPL = True
except ImportError:  # pragma: no cover - only on a machine without matplotlib
    HAVE_MPL = False
    plt = None  # type: ignore[assignment]
    FontProperties = None  # type: ignore[assignment,misc]
    Line2D = None  # type: ignore[assignment,misc]
    FancyArrowPatch = None  # type: ignore[assignment,misc]
    FancyBboxPatch = None  # type: ignore[assignment,misc]
    Polygon = None  # type: ignore[assignment,misc]
    MPath = None  # type: ignore[assignment,misc]
    TextPath = None  # type: ignore[assignment,misc]

# --------------------------------------------------------------------------- #
# Canvas and palette
# --------------------------------------------------------------------------- #

HERE = Path(__file__).resolve().parent
DPI = 150
W, H = 13.0, 7.35          # inches; 1 data unit == 1 inch, aspect is equal

ACCENT = "#1F4E79"          # the single accent colour
ACCENT_TINT = "#DCE7F1"
ACCENT_SOFT = "#F1F6FA"
INK = "#1A1A1A"
NEUTRAL = "#4F4F4F"
NEUTRAL_TINT = "#EDEDEA"
PAPER = "#FFFFFF"
MUTED = "#5B6570"

T_TITLE = 13.5              # figure title
T_BOX = 9.4                 # box title
T_BODY = 7.7                # box body line
T_LABEL = 6.8               # flow / relationship label
T_LEG = 7.1                 # legend text

FONT = "DejaVu Sans"
FP_NORMAL = FontProperties(family=FONT, weight="normal") if HAVE_MPL else None
FP_BOLD = FontProperties(family=FONT, weight="bold") if HAVE_MPL else None

PAD_X = 0.10
PAD_Y = 0.075
LINE_FACTOR = 1.34          # line height as a multiple of font size
SAFETY = 1.04               # ink extents underestimate advance width slightly


def measure(text: str, size: float, bold: bool = False) -> float:
    """Width of ``text`` in inches at ``size`` points, ink box plus safety."""
    if not HAVE_MPL:  # pragma: no cover - guarded for the import-only path
        raise RuntimeError("matplotlib is required to draw the figures")
    if not text:
        return 0.0
    path = TextPath((0.0, 0.0), text, size=size, prop=FP_BOLD if bold else FP_NORMAL)
    return (path.get_extents().width / 72.0) * SAFETY


def line_h(size: float) -> float:
    """Height of one line of ``size``-point text, in inches."""
    return size * LINE_FACTOR / 72.0


# --------------------------------------------------------------------------- #
# Boxes
# --------------------------------------------------------------------------- #


@dataclass
class Box:
    """One labelled box, sized from its own text."""

    key: str
    cx: float
    cy: float
    title: str
    lines: list[str] = field(default_factory=list)
    kind: str = "process"          # process | entity | store | er | klass
    align: str = "center"          # center | left
    title_size: float = T_BOX
    body_size: float = T_BODY
    min_w: float = 0.0
    dashed: bool = False
    divider: bool = True           # separator under the title (er/klass only)
    width: float = 0.0
    height: float = 0.0

    # geometry helpers ------------------------------------------------------
    @property
    def x0(self) -> float:
        return self.cx - self.width / 2.0

    @property
    def x1(self) -> float:
        return self.cx + self.width / 2.0

    @property
    def y0(self) -> float:
        return self.cy - self.height / 2.0

    @property
    def y1(self) -> float:
        return self.cy + self.height / 2.0

    def edge(self, side: str, t: float = 0.5) -> tuple[float, float]:
        """A point on one edge; ``t`` runs 0..1 along that edge."""
        if side == "left":
            return (self.x0, self.y0 + t * self.height)
        if side == "right":
            return (self.x1, self.y0 + t * self.height)
        if side == "bottom":
            return (self.x0 + t * self.width, self.y0)
        if side == "top":
            return (self.x0 + t * self.width, self.y1)
        raise ValueError(side)

    def rect(self, pad: float = 0.0) -> tuple[float, float, float, float]:
        return (self.x0 - pad, self.y0 - pad, self.x1 + pad, self.y1 + pad)


def size_box(box: Box) -> None:
    """Set ``width`` and ``height`` from the text, then assert the text fits."""
    widest = max(
        [measure(box.title, box.title_size, bold=True)]
        + [measure(line, box.body_size) for line in box.lines]
        + [box.min_w]
    )
    box.width = round(widest + 2 * PAD_X + 0.006, 3)
    body = len(box.lines) * line_h(box.body_size)
    box.height = round(line_h(box.title_size) + body + 2 * PAD_Y + 0.006, 3)

    # The assertion the brief asks for: text must not overflow its box.
    inner = box.width - 2 * PAD_X + 1e-9
    assert measure(box.title, box.title_size, bold=True) <= inner, (
        f"{box.key}: title wider than box"
    )
    for line in box.lines:
        assert measure(line, box.body_size) <= inner, f"{box.key}: body wider than box"


# --------------------------------------------------------------------------- #
# Canvas
# --------------------------------------------------------------------------- #


class Canvas:
    """A figure with a title, boxes, arrows, labels and a legend."""

    def __init__(self, title: str) -> None:
        self.fig = plt.figure(figsize=(W, H), dpi=DPI, facecolor=PAPER)
        self.ax = self.fig.add_axes((0.0, 0.0, 1.0, 1.0))
        self.ax.set_xlim(0.0, W)
        self.ax.set_ylim(0.0, H)
        self.ax.set_aspect("equal")
        self.ax.axis("off")
        self.title = title
        lines = [title]
        if measure(title, T_TITLE, bold=True) > W - 0.7:
            # split on the em dash that separates "Figure n" from the caption
            head, _, tail = title.partition("\u2014")
            if tail:
                lines = [head.strip(), tail.strip()]
            else:
                raise AssertionError(f"title too wide and has no dash to split: {title}")
        for i, line in enumerate(lines):
            assert measure(line, T_TITLE, bold=True) <= W - 0.5, "title too wide"
            self.ax.text(
                W / 2.0,
                H - 0.10 - i * 0.26,
                line,
                ha="center",
                va="top",
                fontsize=T_TITLE,
                fontweight="bold",
                color=ACCENT,
                family=FONT,
            )
        self.boxes: dict[str, Box] = {}
        self.marks: list[tuple[str, float, float, float, float]] = []   # text rects
        self.labels: list[tuple[str, float, float, float, float]] = []

    # -- boxes --------------------------------------------------------------
    def box(
        self,
        key: str,
        cx: float,
        cy: float,
        title: str,
        lines: list[str] | None = None,
        kind: str = "process",
        **kw: object,
    ) -> Box:
        box = Box(key=key, cx=cx, cy=cy, title=title, lines=list(lines or []), kind=kind, **kw)  # type: ignore[arg-type]
        size_box(box)
        self.boxes[key] = box
        self._draw_box(box)
        return box

    def _draw_box(self, box: Box) -> None:
        if box.kind == "process":
            style = "round,pad=0,rounding_size=0.09"
            face, edge, lw = ACCENT_TINT, ACCENT, 1.35
        elif box.kind == "entity":
            style = "square,pad=0"
            face, edge, lw = NEUTRAL_TINT, NEUTRAL, 1.25
        elif box.kind == "store":
            style = "square,pad=0"
            face, edge, lw = ACCENT_SOFT, ACCENT, 1.25
        else:                      # er | klass
            style = "square,pad=0"
            face, edge, lw = PAPER, INK, 1.1

        patch = FancyBboxPatch(
            (box.x0, box.y0),
            box.width,
            box.height,
            boxstyle=style,
            facecolor=face,
            edgecolor=edge,
            linewidth=lw,
            linestyle=(0, (3.2, 2.0)) if box.dashed else "solid",
            zorder=3,
            mutation_aspect=1.0,
        )
        self.ax.add_patch(patch)

        if box.kind == "store":
            # barred left edge, the data-store half of the symbol
            self.ax.add_line(
                Line2D(
                    [box.x0 + 0.12, box.x0 + 0.12],
                    [box.y0, box.y1],
                    color=edge,
                    linewidth=lw,
                    zorder=4,
                )
            )

        top = box.y1 - PAD_Y
        ty = top - line_h(box.title_size) / 2.0
        ha = "left" if box.align == "left" else "center"
        tx = box.x0 + PAD_X if box.align == "left" else box.cx
        self.ax.text(
            tx,
            ty,
            box.title,
            ha=ha,
            va="center",
            fontsize=box.title_size,
            fontweight="bold",
            color=INK if box.kind in ("er", "klass") else ACCENT,
            family=FONT,
            zorder=5,
        )
        if box.divider and box.kind in ("er", "klass"):
            dy = top - line_h(box.title_size)
            self.ax.add_line(
                Line2D([box.x0, box.x1], [dy, dy], color=INK, linewidth=0.7, zorder=4)
            )

        cursor = top - line_h(box.title_size)
        for line in box.lines:
            cursor -= line_h(box.body_size) / 2.0
            self.ax.text(
                tx,
                cursor,
                line,
                ha=ha,
                va="center",
                fontsize=box.body_size,
                color=INK if box.kind in ("er", "klass") else NEUTRAL,
                family=FONT,
                zorder=5,
            )
            cursor -= line_h(box.body_size) / 2.0

    # -- arrows -------------------------------------------------------------
    def arrow(
        self,
        a: Box,
        sa: str,
        b: Box,
        sb: str,
        label: str = "",
        *,
        ta: float = 0.5,
        tb: float = 0.5,
        rad: float = 0.0,
        dashed: bool = False,
        lpos: tuple[float, float] | None = None,
        lsize: float = T_LABEL,
        both: bool = False,
        colour: str = ACCENT,
        diamond: bool = False,
    ) -> None:
        self.arrow_pts(
            a.edge(sa, ta),
            b.edge(sb, tb),
            label,
            rad=rad,
            dashed=dashed,
            lpos=lpos,
            lsize=lsize,
            both=both,
            colour=colour,
            diamond=diamond,
        )

    def arrow_pts(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        label: str = "",
        *,
        rad: float = 0.0,
        dashed: bool = False,
        lpos: tuple[float, float] | None = None,
        lsize: float = T_LABEL,
        both: bool = False,
        colour: str = ACCENT,
        diamond: bool = False,
    ) -> None:
        patch = FancyArrowPatch(
            posA=p0,
            posB=p1,
            arrowstyle="<|-|>" if both else "-|>",
            mutation_scale=7.5,
            shrinkA=0.0,
            shrinkB=0.0,
            linewidth=1.0,
            color=colour,
            linestyle=(0, (4.0, 2.2)) if dashed else "solid",
            connectionstyle=f"arc3,rad={rad}",
            zorder=2,
            joinstyle="miter",
        )
        self.ax.add_patch(patch)
        if diamond:
            self._diamond(p0, p1)
        if label:
            if lpos is not None:
                px, py = lpos
            else:
                mx, my = (p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0
                dx, dy = p1[0] - p0[0], p1[1] - p0[1]
                # offset perpendicular to the arrow, on the upper-left side
                norm = max((dx * dx + dy * dy) ** 0.5, 1e-6)
                px = mx + (-dy / norm) * 0.0
                py = my + (dx / norm) * 0.0
            self._label(label, px, py, lsize)

    def _diamond(self, p0: tuple[float, float], p1: tuple[float, float]) -> None:
        """Filled diamond at ``p0``: the UML mark for composition (whole end)."""
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        norm = max((dx * dx + dy * dy) ** 0.5, 1e-6)
        ux, uy = dx / norm, dy / norm
        px, py = -uy, ux
        cx, cy = p0[0] + ux * 0.085, p0[1] + uy * 0.085
        pts = [
            (p0[0], p0[1]),
            (cx + px * 0.045, cy + py * 0.045),
            (p0[0] + ux * 0.17, p0[1] + uy * 0.17),
            (cx - px * 0.045, cy - py * 0.045),
        ]
        self.ax.add_patch(
            Polygon(pts, closed=True, facecolor=ACCENT, edgecolor=ACCENT, zorder=3)
        )

    def route(
        self,
        pts: list[tuple[float, float]],
        label: str = "",
        *,
        dashed: bool = False,
        lpos: tuple[float, float] | None = None,
        lsize: float = T_LABEL,
        colour: str = ACCENT,
        diamond: bool = False,
    ) -> None:
        """An elbow-routed arrow through ``pts``; arrowhead on the last point."""
        path = MPath(
            pts,
            [MPath.MOVETO] + [MPath.LINETO] * (len(pts) - 1),
        )
        patch = FancyArrowPatch(
            path=path,
            arrowstyle="-|>",
            mutation_scale=7.5,
            shrinkA=0.0,
            shrinkB=0.0,
            linewidth=1.0,
            color=colour,
            linestyle=(0, (4.0, 2.2)) if dashed else "solid",
            zorder=2,
        )
        self.ax.add_patch(patch)
        if diamond:
            self._diamond(pts[0], pts[1])
        if label:
            if lpos is None:
                lpos = pts[len(pts) // 2]
            self._label(label, lpos[0], lpos[1], lsize)

    def _label(self, text: str, x: float, y: float, size: float) -> None:
        self.ax.text(
            x,
            y,
            text,
            ha="center",
            va="center",
            fontsize=size,
            color=MUTED,
            family=FONT,
            zorder=6,
            bbox=dict(boxstyle="round,pad=0.16", facecolor=PAPER, edgecolor="none", alpha=0.95),
        )
        w = measure(text, size)
        h = line_h(size)
        self.labels.append((text, x - w / 2.0, y - h / 2.0, x + w / 2.0, y + h / 2.0))

    # -- relationship (ER) --------------------------------------------------
    def relation(
        self,
        a: Box,
        sa: str,
        b: Box,
        sb: str,
        label: str = "",
        *,
        ta: float = 0.5,
        tb: float = 0.5,
        one_to_one: bool = False,
        lpos: tuple[float, float] | None = None,
        lsize: float = T_LABEL,
    ) -> None:
        """Draw a relationship line with crow's-foot / 1:N cardinality marks."""
        p0 = a.edge(sa, ta)
        p1 = b.edge(sb, tb)
        self.ax.add_line(
            Line2D([p0[0], p1[0]], [p0[1], p1[1]], color=INK, linewidth=0.9, zorder=2)
        )
        # the b end is the many end unless this is a 1:1 relationship
        for end, other, many in ((p0, p1, False), (p1, p0, not one_to_one)):
            if many:
                self._crows_foot(end, other)
            else:
                self._tick(end, other)
        for end, other, many in ((p0, p1, False), (p1, p0, not one_to_one)):
            dx, dy = other[0] - end[0], other[1] - end[1]
            norm = max((dx * dx + dy * dy) ** 0.5, 1e-6)
            gx = end[0] + dx / norm * 0.27
            gy = end[1] + dy / norm * 0.27
            self.ax.text(
                gx,
                gy,
                "N" if many else "1",
                ha="center",
                va="center",
                fontsize=lsize + 0.6,
                fontweight="bold",
                color=INK,
                family=FONT,
                zorder=6,
                bbox=dict(boxstyle="round,pad=0.10", facecolor=PAPER, edgecolor="none"),
            )
        if label:
            if lpos is None:
                mx, my = (p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0
                dx, dy = p1[0] - p0[0], p1[1] - p0[1]
                norm = max((dx * dx + dy * dy) ** 0.5, 1e-6)
                # sit beside the line, on its upper-left side
                lpos = (mx + (-dy / norm) * 0.14, my + (dx / norm) * 0.14)
            self._label(label, lpos[0], lpos[1], lsize)

    def _crows_foot(self, end: tuple[float, float], other: tuple[float, float]) -> None:
        dx, dy = other[0] - end[0], other[1] - end[1]
        norm = max((dx * dx + dy * dy) ** 0.5, 1e-6)
        ux, uy = dx / norm, dy / norm
        px, py = -uy, ux
        tipx, tipy = end[0] + ux * 0.15, end[1] + uy * 0.15
        for s in (-1.0, 0.0, 1.0):
            self.ax.add_line(
                Line2D(
                    [end[0], tipx + px * 0.075 * s],
                    [end[1], tipy + py * 0.075 * s],
                    color=INK,
                    linewidth=0.9,
                    zorder=2,
                )
            )

    def _tick(self, end: tuple[float, float], other: tuple[float, float]) -> None:
        dx, dy = other[0] - end[0], other[1] - end[1]
        norm = max((dx * dx + dy * dy) ** 0.5, 1e-6)
        ux, uy = dx / norm, dy / norm
        px, py = -uy, ux
        cx, cy = end[0] + ux * 0.16, end[1] + uy * 0.16
        self.ax.add_line(
            Line2D(
                [cx - px * 0.07, cx + px * 0.07],
                [cy - py * 0.07, cy + py * 0.07],
                color=INK,
                linewidth=0.9,
                zorder=2,
            )
        )

    # -- legend -------------------------------------------------------------
    def legend(
        self,
        entries: list[tuple[str, str]],
        y: float,
        *,
        x: float = 0.35,
        note: str = "",
    ) -> None:
        """A one-row legend: (kind, text) pairs laid out left to right."""
        cursor = x
        for kind, text in entries:
            gw = 0.30
            if kind == "process":
                self.ax.add_patch(
                    FancyBboxPatch(
                        (cursor, y - 0.075),
                        gw,
                        0.15,
                        boxstyle="round,pad=0,rounding_size=0.04",
                        facecolor=ACCENT_TINT,
                        edgecolor=ACCENT,
                        linewidth=1.1,
                        zorder=3,
                    )
                )
            elif kind == "entity":
                self.ax.add_patch(
                    FancyBboxPatch(
                        (cursor, y - 0.075),
                        gw,
                        0.15,
                        boxstyle="square,pad=0",
                        facecolor=NEUTRAL_TINT,
                        edgecolor=NEUTRAL,
                        linewidth=1.1,
                        zorder=3,
                    )
                )
            elif kind == "store":
                self.ax.add_patch(
                    FancyBboxPatch(
                        (cursor, y - 0.075),
                        gw,
                        0.15,
                        boxstyle="square,pad=0",
                        facecolor=ACCENT_SOFT,
                        edgecolor=ACCENT,
                        linewidth=1.1,
                        zorder=3,
                    )
                )
                self.ax.add_line(
                    Line2D(
                        [cursor + 0.08, cursor + 0.08],
                        [y - 0.075, y + 0.075],
                        color=ACCENT,
                        linewidth=1.1,
                        zorder=4,
                    )
                )
            elif kind == "table":
                self.ax.add_patch(
                    FancyBboxPatch(
                        (cursor, y - 0.075),
                        gw,
                        0.15,
                        boxstyle="square,pad=0",
                        facecolor=PAPER,
                        edgecolor=INK,
                        linewidth=1.0,
                        zorder=3,
                    )
                )
            elif kind == "dashed":
                self.ax.add_patch(
                    FancyBboxPatch(
                        (cursor, y - 0.075),
                        gw,
                        0.15,
                        boxstyle="square,pad=0",
                        facecolor=PAPER,
                        edgecolor=NEUTRAL,
                        linewidth=1.0,
                        linestyle=(0, (2.6, 1.6)),
                        zorder=3,
                    )
                )
            elif kind == "arrow":
                self.ax.add_patch(
                    FancyArrowPatch(
                        (cursor, y),
                        (cursor + gw, y),
                        arrowstyle="-|>",
                        mutation_scale=7.5,
                        linewidth=1.0,
                        color=ACCENT,
                        shrinkA=0,
                        shrinkB=0,
                        zorder=3,
                    )
                )
            elif kind == "composition":
                self.ax.add_line(
                    Line2D([cursor, cursor + gw], [y, y], color=ACCENT, linewidth=1.0, zorder=3)
                )
                self.ax.add_patch(
                    Polygon(
                        [
                            (cursor, y),
                            (cursor + 0.06, y + 0.045),
                            (cursor + 0.12, y),
                            (cursor + 0.06, y - 0.045),
                        ],
                        closed=True,
                        facecolor=ACCENT,
                        edgecolor=ACCENT,
                        zorder=4,
                    )
                )
                self.ax.add_patch(
                    FancyArrowPatch(
                        (cursor + gw - 0.05, y),
                        (cursor + gw, y),
                        arrowstyle="-|>",
                        mutation_scale=7.5,
                        linewidth=1.0,
                        color=ACCENT,
                        shrinkA=0,
                        shrinkB=0,
                        zorder=3,
                    )
                )
            elif kind == "dasharrow":
                self.ax.add_patch(
                    FancyArrowPatch(
                        (cursor, y),
                        (cursor + gw, y),
                        arrowstyle="-|>",
                        mutation_scale=7.5,
                        linewidth=1.0,
                        color=ACCENT,
                        linestyle=(0, (4.0, 2.2)),
                        shrinkA=0,
                        shrinkB=0,
                        zorder=3,
                    )
                )
            elif kind == "one":
                self.ax.add_line(
                    Line2D([cursor, cursor + gw], [y, y], color=INK, linewidth=0.9, zorder=3)
                )
                self.ax.add_line(
                    Line2D(
                        [cursor + gw - 0.03, cursor + gw - 0.03],
                        [y - 0.055, y + 0.055],
                        color=INK,
                        linewidth=0.9,
                        zorder=3,
                    )
                )
                self.ax.text(
                    cursor + gw + 0.055, y, "1", ha="left", va="center",
                    fontsize=T_LEG, fontweight="bold", color=INK, family=FONT, zorder=4,
                )
                cursor += 0.14
            elif kind == "many":
                self.ax.add_line(
                    Line2D([cursor, cursor + gw], [y, y], color=INK, linewidth=0.9, zorder=3)
                )
                for s in (-1.0, 0.0, 1.0):
                    self.ax.add_line(
                        Line2D(
                            [cursor, cursor + gw - 0.02],
                            [y, y + 0.062 * s],
                            color=INK,
                            linewidth=0.9,
                            zorder=3,
                        )
                    )
                self.ax.text(
                    cursor + gw + 0.055, y, "N", ha="left", va="center",
                    fontsize=T_LEG, fontweight="bold", color=INK, family=FONT, zorder=4,
                )
                cursor += 0.14
            elif kind == "gap":
                cursor += 0.12
                continue
            else:
                raise ValueError(kind)

            self.ax.text(
                cursor + gw + 0.06,
                y,
                text,
                ha="left",
                va="center",
                fontsize=T_LEG,
                color=NEUTRAL,
                family=FONT,
                zorder=4,
            )
            lx = cursor + gw + 0.06
            lw = measure(text, T_LEG)
            self.labels.append(
                (text, lx, y - line_h(T_LEG) / 2, lx + lw, y + line_h(T_LEG) / 2)
            )
            cursor += gw + 0.10 + measure(text, T_LEG) + 0.26

        if note:
            self.ax.text(
                x,
                y - 0.20,
                note,
                ha="left",
                va="center",
                fontsize=T_LEG - 0.3,
                color=MUTED,
                family=FONT,
                style="italic",
                zorder=4,
            )
            nw = measure(note, T_LEG - 0.3)
            self.labels.append(
                (note, x, y - 0.20 - line_h(T_LEG - 0.3) / 2, x + nw, y - 0.20 + line_h(T_LEG - 0.3) / 2)
            )

    # -- validation and output ---------------------------------------------
    def validate(self) -> None:
        """Assert nothing overlaps, nothing leaves the canvas, labels are clear."""
        keys = list(self.boxes)
        for i, k1 in enumerate(keys):
            b1 = self.boxes[k1]
            assert b1.x0 >= 0.02 and b1.x1 <= W - 0.02, f"{k1} leaves the canvas in x"
            assert b1.y0 >= 0.02 and b1.y1 <= H - 0.02, f"{k1} leaves the canvas in y"
            for k2 in keys[i + 1:]:
                b2 = self.boxes[k2]
                gap = 0.06
                overlap_x = min(b1.x1, b2.x1) - max(b1.x0, b2.x0) > -gap
                overlap_y = min(b1.y1, b2.y1) - max(b1.y0, b2.y0) > -gap
                assert not (overlap_x and overlap_y), f"boxes {k1} and {k2} overlap"

        for text, x0, y0, x1, y1 in self.labels:
            for key, box in self.boxes.items():
                ox = min(x1, box.x1) - max(x0, box.x0)
                oy = min(y1, box.y1) - max(y0, box.y0)
                assert not (ox > 0.01 and oy > 0.01), (
                    f"label {text!r} sits on box {key}"
                )


    def _crop_title_band(self, out: Path) -> None:
        """Remove the baked-in title strip at the top of the image.

        The report supplies its own numbered caption, so an internal title is a second,
        unnumbered heading printed directly above the real one. Cropping it also recovers
        vertical space, which matters in a 15-20 page synopsis.

        Args:
            out: The PNG just written.
        """
        try:
            from PIL import Image
        except ImportError:
            return
        with Image.open(out) as img:
            width, height = img.size
            img.crop((0, int(height * 0.085), width, height)).save(out)

    def save(self, name: str) -> Path:
        self.validate()
        out = HERE / name
        self.fig.savefig(
            out,
            dpi=DPI,
            facecolor=PAPER,
            metadata={"Software": "make_diagrams.py", "Creation Time": None},
        )
        plt.close(self.fig)
        self._crop_title_band(out)
        size = out.stat().st_size
        assert size > 20_000, f"{name} is only {size} bytes; the figure is empty"
        return out


# --------------------------------------------------------------------------- #
# Figure 1 - DFD level 0
# --------------------------------------------------------------------------- #


def dfd_level_0() -> Path:
    c = Canvas(
        "DFD Level 0 (Context Diagram): "
        "Autonomous AI Code Reviewer & PR Assistant"
    )

    proc = c.box(
        "p0", 6.5, 3.95,
        "0  Autonomous AI Code Reviewer & PR Assistant",
        ["reviews a diff or a source file", "and reports findings with a verdict"],
        min_w=3.3,
    )
    dev = c.box("dev", 1.75, 5.95, "Developer",
                ["submits a diff or", "a source file"], kind="entity")
    gh = c.box("gh", 11.15, 5.95, "GitHub",
               ["pull requests and", "review comments"], kind="entity")
    lm = c.box("lm", 11.15, 1.95, "LM Studio / Sarvam",
               ["OpenAI-compatible", "endpoint"], kind="entity")
    d1 = c.box("d1", 2.35, 1.95, "D1  Review Store",
               ["reviews, findings,", "post outcomes"], kind="store")
    d2 = c.box("d2", 6.5, 1.15, "D2  Users & Roles",
               ["who may review", "and post"], kind="store")

    c.arrow(dev, "right", proc, "left", "diff or source file, review request",
            ta=0.5, tb=0.80, lpos=(3.35, 5.42))
    c.arrow(proc, "left", dev, "bottom", "findings, verdict and mode",
            ta=0.22, tb=0.78, lpos=(3.35, 4.20))
    c.arrow(gh, "left", proc, "right", "pull-request diff and event",
            ta=0.5, tb=0.80, lpos=(9.85, 5.42))
    c.arrow(proc, "right", gh, "bottom", "inline and summary comments",
            ta=0.22, tb=0.78, lpos=(9.85, 4.20))
    c.arrow(proc, "right", lm, "top", "review prompt (added lines)",
            ta=0.06, tb=0.30, lpos=(8.55, 2.95))
    c.arrow(lm, "left", proc, "bottom", "JSON findings or an error",
            ta=0.15, tb=0.82, lpos=(8.60, 2.42))
    c.arrow(proc, "left", d1, "top", "review, findings, post outcome",
            ta=0.06, tb=0.30, lpos=(4.30, 2.95))
    c.arrow(d1, "top", proc, "bottom", "prior review marker",
            ta=0.15, tb=0.22, lpos=(3.05, 2.55))
    c.arrow(d2, "top", proc, "bottom", "user identity and role",
            ta=0.50, tb=0.50, lpos=(7.05, 2.55))

    c.legend(
        [
            ("process", "process"),
            ("entity", "external entity"),
            ("store", "data store (D1, D2)"),
            ("arrow", "data flow, labelled"),
        ],
        0.40,
        note="Level 0 shows the system as one process; the three external entities and the two data stores are the only things it talks to.",
    )
    return c.save("dfd-level-0.png")


# --------------------------------------------------------------------------- #
# Figure 2 - DFD level 1
# --------------------------------------------------------------------------- #


def dfd_level_1() -> Path:
    c = Canvas(
        "DFD Level 1: the seven processes of one review"
    )

    C1, C2, C3, C4, C5 = 1.30, 3.80, 6.55, 9.30, 11.90
    R1, R2, R3, R4 = 6.10, 4.55, 2.95, 1.40

    dev = c.box("dev", C1, R1, "Developer", ["diff or source", "file, request"],
                kind="entity", min_w=1.5)
    auth = c.box("p7", C2, R1, "7.0 Authenticate", ["& Authorise"], min_w=1.5)
    parse = c.box("p1", C3, R1, "1.0 Parse Diff", ["build DiffBundle", "of added lines"],
                  min_w=1.5)
    gh = c.box("gh", C4, R1, "GitHub", ["pull requests,", "webhook events"],
               kind="entity", min_w=1.5)

    d2 = c.box("d2", C1, R2, "D2  Users & Roles", ["role and permission"],
               kind="store", min_w=1.5)
    rules = c.box("p2", C3, R2, "2.0 Apply Rule Engine", ["63 rules, added lines"],
                  min_w=1.5)
    prov = c.box("p3", C4, R2, "3.0 Review with Provider", ["prompt, call, parse"],
                 min_w=1.5)
    lm = c.box("lm", C5, R2, "LM Studio /", ["Sarvam endpoint"], kind="entity",
               min_w=1.35)

    anchor = c.box("p4", C3, R3, "4.0 Anchor Findings", ["anchored / file_only"],
                   min_w=1.5)

    d1 = c.box("d1", C1, R4, "D1  Review Store", ["reviews, findings"],
               kind="store", min_w=1.5)
    persist = c.box("p6", C2, R4, "6.0 Persist Review", ["store the outcome"], min_w=1.5)
    publish = c.box("p5", C4, R4, "5.0 Publish to Pull Request", ["inline + summary"],
                    min_w=1.5)
    gh2 = c.box("gh2", C5, R4, "GitHub", ["same entity"], kind="entity", min_w=1.2)

    c.arrow(dev, "right", auth, "left", "request", ta=0.62, tb=0.72, lpos=(2.55, 6.35))
    c.arrow(auth, "left", dev, "right", "401 / 200", ta=0.28, tb=0.28, lpos=(2.55, 5.85))
    c.arrow(auth, "right", parse, "left", "authorised", ta=0.72, tb=0.72,
            lpos=(5.30, 6.35))
    c.arrow(gh, "left", parse, "right", "pull-request diff", ta=0.72, tb=0.72,
            lpos=(7.90, 6.35))
    c.arrow(d2, "top", auth, "bottom", "identity and role", ta=0.60, tb=0.35,
            lpos=(2.10, 5.35))

    c.arrow(parse, "bottom", rules, "top", "parsed DiffBundle", ta=0.25, tb=0.25,
            lpos=(5.75, 5.35))
    c.route(
        [parse.edge("right", 0.28), (7.90, 5.50), (C4, 5.50), prov.edge("top", 0.5)],
        "parsed DiffBundle",
        lpos=(8.25, 5.50),
    )
    c.arrow(prov, "right", lm, "left", "prompt", ta=0.75, tb=0.75, lpos=(10.74, 4.80))
    c.arrow(lm, "left", prov, "right", "answer / error", ta=0.25, tb=0.25,
            lpos=(10.74, 4.30))

    c.arrow(rules, "bottom", anchor, "top", "rule findings", ta=0.75, tb=0.75,
            lpos=(7.20, 3.75))
    c.arrow(prov, "bottom", anchor, "right", "model findings, mode", ta=0.40, tb=0.55,
            lpos=(8.15, 3.30))

    c.route(
        [anchor.edge("right", 0.30), (8.15, 2.35), (C4, 2.35), publish.edge("top", 0.5)],
        "anchored findings",
        lpos=(7.45, 2.35),
    )
    c.route(
        [anchor.edge("bottom", 0.28), (6.10, 2.10), (C2, 2.10), persist.edge("top", 0.5)],
        "review result and anchors",
        lpos=(4.95, 2.10),
    )
    c.arrow(publish, "left", persist, "right", "PostResult", ta=0.50, tb=0.50,
            lpos=(6.55, 1.40))
    c.arrow(publish, "right", gh2, "left", "comments", ta=0.75, tb=0.75, lpos=(10.82, 1.65))
    c.arrow(persist, "left", d1, "right", "stored review", ta=0.50, tb=0.50,
            lpos=(2.55, 1.40))

    c.legend(
        [
            ("process", "process"),
            ("entity", "external entity"),
            ("store", "data store"),
            ("arrow", "data flow"),
        ],
        0.38,
        note="GitHub is drawn twice (top right and bottom right) so that the diff-in and comment-out flows do not cross the diagram; it is one external entity.",
    )
    return c.save("dfd-level-1.png")


# --------------------------------------------------------------------------- #
# Figure 3 - DFD level 2
# --------------------------------------------------------------------------- #


def dfd_level_2() -> Path:
    c = Canvas(
        "DFD Level 2: process 2.0 (rule engine) and "
        "process 3.0 (provider review) decomposed"
    )

    # panel frames
    for x0, x1, label in (
        (0.25, 5.85, "Decomposition of process 2.0  \u2014  Apply Rule Engine"),
        (6.05, 12.75, "Decomposition of process 3.0  \u2014  Review with Provider"),
    ):
        c.ax.add_patch(
            FancyBboxPatch(
                (x0, 0.72),
                x1 - x0,
                5.88,
                boxstyle="round,pad=0,rounding_size=0.08",
                facecolor="#FAFBFD",
                edgecolor="#C9D6E2",
                linewidth=0.9,
                zorder=1,
            )
        )
        c.ax.text(
            (x0 + x1) / 2.0, 6.42, label,
            ha="center", va="center", fontsize=T_LEG + 0.6,
            color=ACCENT, fontweight="bold", family=FONT, zorder=4,
        )

    # -- left panel: 2.0 ----------------------------------------------------
    L = 3.05
    p2 = c.box("p2", L, 6.00, "2.0 Apply Rule Engine",
               ["receives the parsed DiffBundle"], min_w=2.9)
    s21 = c.box("s21", L, 5.00, "2.1 Scan Added Lines",
                ["every added line, once"], min_w=2.9)
    s22 = c.box("s22", L, 4.00, "2.2 Match Rule Patterns",
                ["63 registered rules"], min_w=2.9)
    s23 = c.box("s23", L, 3.00, "2.3 Apply Suppressions",
                ["# noqa and # nosec"], min_w=2.9)
    s24 = c.box("s24", L, 2.00, "2.4 Assign Severity",
                ["fixed per rule, floored"], min_w=2.9)
    s25 = c.box("s25", L, 1.05, "2.5 Emit Findings",
                ["list[Finding] to 4.0"], min_w=2.9)

    c.arrow(p2, "bottom", s21, "top", "line context", ta=0.5, tb=0.5, lpos=(3.90, 5.50))
    c.arrow(s21, "bottom", s22, "top", "candidate lines", ta=0.5, tb=0.5, lpos=(3.90, 4.50))
    c.arrow(s22, "bottom", s23, "top", "rule hits", ta=0.5, tb=0.5, lpos=(3.90, 3.50))
    c.arrow(s23, "bottom", s24, "top", "kept hits", ta=0.5, tb=0.5, lpos=(3.90, 2.50))
    c.arrow(s24, "bottom", s25, "top", "severity set", ta=0.5, tb=0.5, lpos=(3.90, 1.52))

    # -- right panel: 3.0 ---------------------------------------------------
    R = 9.00
    p3 = c.box("p3", R, 6.00, "3.0 Review with Provider",
               ["receives the parsed DiffBundle"], min_w=2.9)
    s31 = c.box("s31", R, 5.00, "3.1 Build Prompt",
                ["added lines, JSON schema"], min_w=2.9)
    s32 = c.box("s32", R, 4.00, "3.2 Call Endpoint",
                ["one chat completion"], min_w=2.9)
    lm = c.box("lm", 11.85, 4.00, "Sarvam / LM Studio",
               ["OpenAI-compatible"], kind="entity", min_w=1.5)
    s33 = c.box("s33", 8.40, 2.95, "3.3 Parse and Validate",
                ["files and lines checked"], min_w=2.5)
    s34 = c.box("s34", 11.55, 2.95, "3.4 Repair Retry",
                ["one more call"], min_w=2.0)
    s35 = c.box("s35", R, 1.75, "3.5 Fall Back to Rules",
                ["rule findings, mode=mock"], min_w=2.9)

    c.arrow(p3, "bottom", s31, "top", "DiffBundle", ta=0.5, tb=0.5, lpos=(9.70, 5.50))
    c.arrow(s31, "bottom", s32, "top", "prompt text", ta=0.5, tb=0.5, lpos=(9.70, 4.50))
    c.arrow(s32, "right", lm, "left", "prompt", ta=0.80, tb=0.80, lpos=(10.78, 4.42))
    c.arrow(lm, "left", s32, "right", "answer or error", ta=0.20, tb=0.20,
            lpos=(10.78, 3.56))
    c.arrow(s32, "bottom", s33, "top", "raw answer", ta=0.30, tb=0.55,
            lpos=(8.30, 3.48))
    c.arrow(s33, "right", s34, "left", "invalid JSON", ta=0.74, tb=0.74,
            lpos=(10.10, 3.13))
    c.arrow(s34, "left", s33, "right", "one retry", ta=0.26, tb=0.26,
            lpos=(10.10, 2.78))
    c.route(
        [s32.edge("left", 0.28), (6.75, 3.72), (6.75, 1.75), s35.edge("left", 0.5)],
        "401, timeout, 5xx",
        lpos=(7.55, 2.30),
        dashed=True,
    )

    c.legend(
        [
            ("process", "sub-process"),
            ("entity", "external entity"),
            ("arrow", "data flow"),
            ("dasharrow", "failure path, degrades to mock"),
        ],
        0.40,
        note="A second parse failure is not a fallback: the run stays live with zero findings. Only an unavailable or unconfigured endpoint reaches 3.5.",
    )
    return c.save("dfd-level-2.png")


# --------------------------------------------------------------------------- #
# Figure 4 - ER diagram
# --------------------------------------------------------------------------- #


def _strip_sql_comments(body: str) -> str:
    """Remove ``--`` comments from a DDL body, leaving string literals alone.

    A comment can sit on its own line or trail a column definition; both must go
    before the body is split on commas, or a comma inside a comment would invent a
    column.

    Args:
        body: The text between a table's opening and closing parentheses.

    Returns:
        The same text with every ``--`` comment removed.
    """
    out: list[str] = []
    for line in body.splitlines():
        quote = ""
        cut = len(line)
        for index, char in enumerate(line):
            if quote:
                if char == quote:
                    quote = ""
            elif char in "'\"":
                quote = char
            elif char == "-" and line[index : index + 2] == "--":
                cut = index
                break
        out.append(line[:cut])
    return "\n".join(out)


def _split_definitions(body: str) -> list[str]:
    """Split a DDL body on the commas that separate its definitions.

    A ``CHECK (x IN ('a', 'b'))`` constraint carries commas of its own, so the split
    is parenthesis-aware: a comma only ends a definition at nesting depth zero.

    Args:
        body: A table body with its comments already stripped.

    Returns:
        One string per column or table constraint, in source order.
    """
    definitions: list[str] = []
    depth = 0
    current: list[str] = []
    quote = ""
    for char in body:
        if quote:
            if char == quote:
                quote = ""
            current.append(char)
            continue
        if char in "'\"":
            quote = char
            current.append(char)
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            definitions.append("".join(current))
            current = []
            continue
        current.append(char)
    definitions.append("".join(current))
    return [item.strip() for item in definitions if item.strip()]


#: A definition that opens with one of these is a table constraint, not a column.
_TABLE_CONSTRAINTS = ("PRIMARY", "UNIQUE", "CHECK", "FOREIGN", "CONSTRAINT")


def _parse_schema_columns(schema: str) -> dict[str, list[tuple[str, str, list[str]]]]:
    """Parse ``CREATE TABLE`` statements into ``table -> [(column, type, tags)]``.

    The parser is deliberately structural rather than line-based, because a
    line-based regex silently drops a column whose definition wraps onto a second
    line, or whose type is written in lower case:

    * the body of each table is found by balancing parentheses, not by matching a
      trailing ``);``;
    * definitions are split on depth-zero commas, so a ``CHECK (... IN (...))``
      constraint does not split its own column in two;
    * the column type is read case-insensitively and may carry a length, as in
      ``CHAR(64)``.

    Args:
        schema: The DDL script, i.e. :data:`app.db.SCHEMA_SQL`.

    Returns:
        Mapping of table name to its columns in declaration order. A table that
        declares no columns maps to an empty list.
    """
    import re as _re

    tables: dict[str, list[tuple[str, str, list[str]]]] = {}
    for match in _re.finditer(
        r"CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\(", schema, _re.IGNORECASE
    ):
        name = match.group(1)
        index = match.end()
        depth = 1
        quote = ""
        while index < len(schema) and depth:
            char = schema[index]
            if quote:
                if char == quote:
                    quote = ""
            elif char in "'\"":
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            index += 1
        body = schema[match.end() : index - 1]

        columns: list[tuple[str, str, list[str]]] = []
        for definition in _split_definitions(_strip_sql_comments(body)):
            tokens = definition.split()
            if not tokens or tokens[0].upper() in _TABLE_CONSTRAINTS:
                continue
            column = tokens[0].strip('"`[]')
            type_ = tokens[1].upper() if len(tokens) > 1 else ""
            rest = " ".join(tokens[2:]).upper()
            tags: list[str] = []
            if "PRIMARY KEY" in rest:
                tags.append("PK")
            if "UNIQUE" in rest:
                tags.append("UNIQUE")
            foreign = _re.search(r"REFERENCES\s+(\w+)\s*\(\s*(\w+)", definition, _re.IGNORECASE)
            if foreign:
                tags.append(f"FK -> {foreign.group(1)}")
            if "CHECK" in rest:
                tags.append("CHECK")
            columns.append((column, type_, tags))
        tables[name] = columns
    return tables


def _er_columns() -> dict[str, list[str]]:
    """Read the six tables and their columns out of :data:`app.db.SCHEMA_SQL`.

    The figure is generated from the same constant the service applies, so it cannot
    describe a column the database does not have. ``app`` is imported lazily so this
    module still runs if the application package is not on the path, and matplotlib
    is not imported at all on this path, so the schema reader works on a machine
    that cannot draw.

    Returns:
        Mapping of table name to the display lines for its box. Each line is
        ``"<column><padding><TYPE><padding><tags>"``; the column name is its first
        whitespace-separated token, which is what
        ``tests/test_diagram_generator.py`` compares with ``PRAGMA table_info``.
    """
    import sys
    from pathlib import Path as _Path

    root = _Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from app.db import SCHEMA_SQL

    return {
        table: [
            f"{column:<15}{type_:<9} {' '.join(tags)}".rstrip()
            for column, type_, tags in columns
        ]
        for table, columns in _parse_schema_columns(SCHEMA_SQL).items()
    }


def er_diagram() -> Path:
    c = Canvas(
        "ER Diagram \u2014 six tables generated from SCHEMA_SQL"
        " (roles, users, reviews, findings, pr_posts, benchmark_runs)"
    )
    cols = _er_columns()
    layout = {
        "roles": (2.05, 6.05), "users": (2.05, 3.60), "reviews": (6.30, 4.35),
        "findings": (10.75, 6.05), "pr_posts": (10.75, 2.55), "benchmark_runs": (2.05, 1.58),
    }
    boxes = {}
    for name, (x, y) in layout.items():
        boxes[name] = c.box(name, x, y, name, cols.get(name, ["(table not found)"]),
                            kind="er", align="left", body_size=6.4, min_w=2.15)

    c.relation(boxes["roles"], "bottom", boxes["users"], "top", "role_id  1:N", ta=0.62, tb=0.38)
    c.relation(boxes["reviews"], "right", boxes["findings"], "left", "review_id  1:N", ta=0.86, tb=0.86)
    c.relation(boxes["reviews"], "right", boxes["pr_posts"], "left", "review_id  1:N (nullable)",
               ta=0.30, tb=0.72)
    return c.save("er-diagram.png")


# --------------------------------------------------------------------------- #
# Figure 5 - Class diagram
# --------------------------------------------------------------------------- #


def class_diagram() -> Path:
    c = Canvas(
        "Class Diagram: the dataclasses of models, parser, "
        "rules, providers and github_client"
    )

    b = 6.7    # member font
    sep = "\u2500" * 12

    reviewresult = c.box(
        "reviewresult", 1.75, 6.535, "ReviewResult", [
            "mode : str  /  target : str",
            "findings : list[Finding]",
            "notes : list[str]",
            sep,
            "counts() / verdict / to_json()",
        ], kind="klass", align="left", body_size=b, min_w=1.9,
    )
    finding = c.box(
        "finding", 1.75, 5.02, "Finding", [
            "file : str",
            "line : str  (\u201c42\u201d, \u201c42-45\u201d)",
            "severity : Severity",
            "issue : str",
            "suggested_fix : str",
            sep,
            "as_row() : dict",
        ], kind="klass", align="left", body_size=b, min_w=1.9,
    )
    anchored = c.box(
        "anchored", 1.75, 3.38, "AnchoredFinding", [
            "finding : Finding",
            "status : AnchorStatus",
            "hunk_header : str | None",
            "detail : str",
            sep,
            "as_row() : dict",
        ], kind="klass", align="left", body_size=b, min_w=1.9,
    )
    outcome = c.box(
        "outcome", 1.75, 1.80, "ProviderOutcome", [
            "mode : live | mock",
            "provider : str  /  model : str",
            "findings : list[Finding]",
            "reason : str",
            "latency_ms : float",
        ], kind="klass", align="left", body_size=b, min_w=1.9,
    )

    dresult = c.box(
        "dresult", 4.50, 6.11, "DiffReviewResult", [
            "mode : str  /  target : str",
            "files : list[FileSummary]",
            "findings : list[Finding]",
            "anchors : list[AnchoredFinding]",
            "notes : list[str]",
            sep,
            "sorted_anchors()",
            "counts() / verdict",
            "to_json() : str",
        ], kind="klass", align="left", body_size=b, min_w=2.1,
    )
    filediff = c.box(
        "filediff", 4.50, 4.145, "FileDiff", [
            "path : str  /  old_path : str",
            "change : ChangeKind",
            "hunks : list[Hunk]",
            "binary : bool",
            sep,
            "added_line_numbers()",
            "added_spans()",
            "hunk_for_line(n)",
        ], kind="klass", align="left", body_size=b, min_w=2.1,
    )
    hunk = c.box(
        "hunk", 4.50, 2.37, "Hunk", [
            "old_start, old_count : int",
            "new_start, new_count : int",
            "section : str",
            "lines : list[DiffLine]",
            sep,
            "header() : str",
            "added_lines() : list[int]",
        ], kind="klass", align="left", body_size=b, min_w=2.1,
    )
    diffline = c.box(
        "diffline", 4.50, 0.905, "DiffLine", [
            "kind : LineKind",
            "text : str",
            "old_lineno : int | None",
            "new_lineno : int | None",
        ], kind="klass", align="left", body_size=b, min_w=2.1,
    )

    rule = c.box(
        "rule", 7.25, 6.36, "Rule", [
            "id : str  /  title : str",
            "category : RuleCategory",
            "owasp : str",
            "severity : Severity",
            "check : LineContext -> RuleHit",
        ], kind="klass", align="left", body_size=b, min_w=2.0,
    )
    ctx = c.box(
        "ctx", 7.25, 4.705, "LineContext", [
            "path : str  /  lineno : int",
            "text : str",
            "added : tuple[(int, str)]",
            "index : int",
            sep,
            "scan_text / indent",
            "is_test_file : bool",
        ], kind="klass", align="left", body_size=b, min_w=2.0,
    )
    payload = c.box(
        "payload", 7.25, 3.115, "ReviewPayload", [
            "summary_body : str",
            "inline_comments : tuple",
            "event : str  /  dropped : tuple",
            "marker_seen : bool",
        ], kind="klass", align="left", body_size=b, min_w=2.0,
    )
    userctx = c.box(
        "userctx", 7.25, 1.86, "UserContext",
        ["implemented in app/auth.py"], kind="klass", align="left",
        body_size=b, min_w=1.7, dashed=True,
    )
    database = c.box(
        "database", 7.25, 1.05, "Database",
        ["implemented in app/auth.py"], kind="klass", align="left",
        body_size=b, min_w=1.7, dashed=True,
    )

    selection = c.box(
        "selection", 10.00, 6.55, "ProviderSelection", [
            "provider : str",
            "config : OpenAICompatConfig | None",
            "reason : str",
        ], kind="klass", align="left", body_size=b, min_w=2.1,
    )
    config = c.box(
        "config", 10.00, 5.175, "OpenAICompatConfig", [
            "base_url : str",
            "api_key : str  (repr=False)",
            "model : str",
            "provider_name : str",
            "timeout : float",
        ], kind="klass", align="left", body_size=b, min_w=2.1,
    )
    comment = c.box(
        "comment", 10.00, 3.675, "InlineComment", [
            "path : str  /  line : int",
            "side : str  /  body : str",
            "fingerprint : str",
        ], kind="klass", align="left", body_size=b, min_w=2.1,
    )
    postresult = c.box(
        "postresult", 10.00, 2.11, "PostResult", [
            "ok : bool",
            "inline_posted : int",
            "inline_demoted : int",
            "summary_posted : bool",
            "skipped_dup : bool",
            "error : str",
        ], kind="klass", align="left", body_size=b, min_w=2.1,
    )

    # composition: the whole holds the part (diamond at the whole end)
    c.arrow(reviewresult, "bottom", finding, "top", "", ta=0.35, tb=0.35, diamond=True)
    c.arrow(anchored, "top", finding, "bottom", "", ta=0.35, tb=0.35, diamond=True)
    c.route(
        [outcome.edge("left", 0.55), (0.45, 1.80), (0.45, 4.72), finding.edge("left", 0.25)],
        diamond=True,
    )
    c.arrow(dresult, "left", finding, "right", "", ta=0.25, tb=0.86, diamond=True)
    c.route(
        [dresult.edge("left", 0.42), (3.05, 5.55), (3.05, 3.50), anchored.edge("right", 0.45)],
        diamond=True,
    )
    c.arrow(dresult, "bottom", filediff, "top", "", ta=0.35, tb=0.35, diamond=True)
    c.arrow(filediff, "bottom", hunk, "top", "", ta=0.35, tb=0.35, diamond=True)
    c.arrow(hunk, "bottom", diffline, "top", "", ta=0.35, tb=0.35, diamond=True)
    c.arrow(rule, "bottom", ctx, "top", "", ta=0.72, tb=0.72, dashed=True)
    c.arrow(payload, "right", comment, "left", "", ta=0.75, tb=0.16, diamond=True)
    c.arrow(selection, "bottom", config, "top", "", ta=0.72, tb=0.72, diamond=True)

    c.ax.text(
        11.45, 5.05,
        "Dashed boxes are prescribed\nby the report but absent\nfrom the code: this snapshot\nhas no user, role or\ndatabase layer.",
        ha="left", va="center", fontsize=T_LEG - 0.6, color=MUTED,
        family=FONT, style="italic", zorder=4,
    )
    c.ax.text(
        11.45, 3.35,
        "No inheritance exists among\nthese classes. The only\ninheritance in the tree is\nthe GitHubError exception\nhierarchy.",
        ha="left", va="center", fontsize=T_LEG - 0.6, color=MUTED,
        family=FONT, style="italic", zorder=4,
    )

    c.legend(
        [
            ("table", "class / dataclass"),
            ("composition", "composition: the whole holds the part"),
            ("dasharrow", "dependency: uses"),
            ("dashed", "implemented in app/auth.py"),
        ],
        0.40,
        x=0.35,
    )
    return c.save("class-diagram.png")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

FIGURES = (
    ("dfd-level-0.png", dfd_level_0),
    ("dfd-level-1.png", dfd_level_1),
    ("dfd-level-2.png", dfd_level_2),
    ("er-diagram.png", er_diagram),
    ("class-diagram.png", class_diagram),
)


def main() -> int:
    made: list[Path] = []
    for name, build in FIGURES:
        path = build()
        digest = hashlib.md5(path.read_bytes()).hexdigest()
        made.append(path)
        print(f"{name:22s} {path.stat().st_size:8d} bytes  md5 {digest}")
    print(f"\n{len(made)} figures written to {HERE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
