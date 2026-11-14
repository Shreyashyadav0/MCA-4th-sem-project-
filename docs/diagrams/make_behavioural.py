#!/usr/bin/env python3
"""Behavioural diagrams and project-planning charts for the MCSP-232 report.

Six PNG figures, all drawn with matplotlib primitives only (no graphviz, no
network access), plus ``planning.md`` carrying the PERT arithmetic:

    use-case-diagram.png     actors, system boundary, <<include>> / <<extend>>
    activity-diagram.png     end-to-end review flow with the decision nodes
    sequence-diagram.png     CLI -> FastAPI -> engine -> adapter -> ... -> GitHub
    state-diagram.png        the PR-posting state machine of app/github_client.py
    pert-chart.png           node network, three-point estimates, critical path
    gantt-chart.png          16-week schedule, milestones, completion state

Everything the figures assert about the system is read from the repository:

* ``app/main.py``        endpoints, the 422/401 status codes, the webhook flow
* ``app/engine.py``      provider precedence ``sarvam > local > mock``
* ``app/openai_compat_provider.py``  the single JSON repair retry
* ``app/github_client.py``           marker check, 422 demotion, 429 retry
* ``app/parser.py``      ``anchor_findings`` and the three anchor statuses
* ``ARCHITECTURE.md``    sections 2, 3, 5, 6 (precedence, fallback, anchoring,
                         idempotency marker)
* ``CHANGELOG.md``       which phases are complete, and when
* ``docs/learning/PACE.md``  the 16-week frame the Gantt is drawn in

The PERT numbers are computed here -- forward pass, backward pass, slack and the
critical path are all derived, never typed in. Running the script twice produces
byte-identical files (no timestamps, no randomness, fixed rcParams).

Run:  python docs/diagrams/make_behavioural.py
"""

from __future__ import annotations

import hashlib
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import (  # noqa: E402
    Circle,
    Ellipse,
    FancyArrowPatch,
    FancyBboxPatch,
    Polygon,
    Rectangle,
)

# --------------------------------------------------------------------------- #
# Determinism and shared look
# --------------------------------------------------------------------------- #

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "figure.dpi": 150,
        "savefig.dpi": 150,
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "text.antialiased": True,
        "lines.antialiased": True,
    }
)

DPI = 150
UPI = 10.0  # data units per inch, so a 15 x 10 inch figure is 150 x 100 units

PALETTE = {
    "ink": "#1f2933",
    "muted": "#5c6b7a",
    "grid": "#d5dce4",
    "paper": "#ffffff",
    "actor": "#2f5d8a",
    "actor_fill": "#e6eef7",
    "usecase": "#eaf1f9",
    "usecase_edge": "#2f5d8a",
    "support": "#f2f5f8",
    "support_edge": "#7b8794",
    "boundary": "#8a97a5",
    "process": "#e7f1ea",
    "process_edge": "#3f7d5a",
    "decision": "#fdf2dd",
    "decision_edge": "#b4761e",
    "terminal": "#f6e5e8",
    "terminal_edge": "#8c3b46",
    "start": "#dcefe2",
    "start_edge": "#2f7a4d",
    "critical": "#b3261e",
    "normal": "#5c6b7a",
    "bar_plan": "#cfe0f0",
    "bar_done": "#2f5d8a",
    "buffer": "#f0e6d2",
    "milestone": "#b4761e",
}

OUT_DIR = Path(__file__).resolve().parent

#: Texts registered for the overflow audit, reset per figure.
_TRACKED: list[dict] = []


def _reset_tracking() -> None:
    """Start a fresh overflow-audit list for the next figure."""
    _TRACKED.clear()


def _units_per_char(fontsize: float) -> float:
    """Width of one average glyph, in data units, for ``fontsize`` points."""
    return 0.52 * fontsize / 72.0 * UPI


def wrap(text: str, width_units: float, fontsize: float, pad: float = 0.86) -> str:
    """Hard-wrap ``text`` so it fits ``width_units`` at ``fontsize``.

    Args:
        text: The label.
        width_units: Box width in data units.
        fontsize: Point size the label will be drawn at.
        pad: Fraction of the width considered usable.

    Returns:
        The wrapped label, newline separated.
    """
    usable = width_units * pad
    per_char = _units_per_char(fontsize)
    cols = max(6, int(usable / per_char))
    out: list[str] = []
    for line in text.split("\n"):
        out.append(textwrap.fill(line, cols) if line else "")
    return "\n".join(out)


def _track(text_artist, bx0: float, by0: float, bx1: float, by1: float) -> None:
    """Register a text artist and the box it must stay inside."""
    _TRACKED.append(
        {"t": text_artist, "b": (bx0, by0, bx1, by1), "orig": text_artist.get_fontsize()}
    )


def audit_overflow(fig, ax, name: str, tol: float = 1.2) -> None:
    """Shrink any label that spills out of its box, then report.

    The check is geometric, not visual: every registered label's rendered window
    extent is compared with the display-space rectangle of its box. Labels are
    reduced 0.4 pt at a time (to a 5.0 pt floor) until nothing spills.

    Args:
        fig: The figure being built.
        ax: The axes the labels live on.
        name: Figure name, for the printed report.
        tol: Allowed spill in display pixels.
    """
    floor = 5.0
    for _ in range(14):
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        worst = False
        for item in _TRACKED:
            bb = item["t"].get_window_extent(renderer)
            bx0, by0, bx1, by1 = item["b"]
            dx0, dy0 = ax.transData.transform((bx0, by0))
            dx1, dy1 = ax.transData.transform((bx1, by1))
            lo_x, hi_x = min(dx0, dx1), max(dx0, dx1)
            lo_y, hi_y = min(dy0, dy1), max(dy0, dy1)
            spills = (
                bb.x0 < lo_x - tol
                or bb.x1 > hi_x + tol
                or bb.y0 < lo_y - tol
                or bb.y1 > hi_y + tol
            )
            if spills:
                fs = item["t"].get_fontsize()
                if fs > floor:
                    item["t"].set_fontsize(max(floor, fs - 0.4))
                    worst = True
        if not worst:
            break
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    offenders = 0
    shrunk = 0
    for item in _TRACKED:
        bb = item["t"].get_window_extent(renderer)
        bx0, by0, bx1, by1 = item["b"]
        dx0, dy0 = ax.transData.transform((bx0, by0))
        dx1, dy1 = ax.transData.transform((bx1, by1))
        lo_x, hi_x = min(dx0, dx1), max(dx0, dx1)
        lo_y, hi_y = min(dy0, dy1), max(dy0, dy1)
        if (
            bb.x0 < lo_x - tol
            or bb.x1 > hi_x + tol
            or bb.y0 < lo_y - tol
            or bb.y1 > hi_y + tol
        ):
            offenders += 1
        if item["t"].get_fontsize() < item["orig"] - 1e-9:
            shrunk += 1
    print(f"  {name}: {len(_TRACKED)} labels, {shrunk} auto-shrunk, {offenders} overflowing")


def canvas(width_in: float, height_in: float, title: str, subtitle: str | None = None):
    """Create a figure whose data units are 1/10 inch, with axis furniture off."""
    _reset_tracking()
    fig = plt.figure(figsize=(width_in, height_in))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width_in * UPI)
    ax.set_ylim(0, height_in * UPI)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.text(
        width_in * UPI / 2,
        height_in * UPI - 4.2,
        title,
        ha="center",
        va="center",
        fontsize=13.5,
        fontweight="bold",
        color=PALETTE["ink"],
    )
    if subtitle:
        ax.text(
            width_in * UPI / 2,
            height_in * UPI - 8.6,
            subtitle,
            ha="center",
            va="center",
            fontsize=8.6,
            color=PALETTE["muted"],
            style="italic",
        )
    return fig, ax


def save(fig, name: str) -> Path:
    """Write ``name`` deterministically and return its path."""
    path = OUT_DIR / name
    fig.savefig(
        path,
        dpi=DPI,
        facecolor="white",
        edgecolor="none",
        metadata={"Software": None, "Creation Time": None},
    )
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- #
# Drawing primitives
# --------------------------------------------------------------------------- #


def box(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    *,
    face: str = PALETTE["process"],
    edge: str = PALETTE["process_edge"],
    fontsize: float = 8.4,
    lw: float = 1.4,
    radius: float = 2.2,
    bold: bool = False,
    color: str | None = None,
    ls: str = "solid",
    track: bool = True,
):
    """Draw a rounded box with centred, wrapped, auto-fitted text."""
    patch = FancyBboxPatch(
        (x - w / 2, y - h / 2),
        w,
        h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        linewidth=lw,
        edgecolor=edge,
        facecolor=face,
        linestyle=ls,
        zorder=3,
    )
    ax.add_patch(patch)
    label = wrap(text, w, fontsize, pad=0.84)
    t = ax.text(
        x,
        y,
        label,
        ha="center",
        va="center",
        fontsize=fontsize,
        color=color or PALETTE["ink"],
        fontweight="bold" if bold else "normal",
        linespacing=1.25,
        zorder=5,
    )
    if track:
        _track(t, x - w / 2 + 0.6, y - h / 2 + 0.4, x + w / 2 - 0.6, y + h / 2 - 0.4)
    return patch, t


def diamond(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    *,
    fontsize: float = 7.8,
    face: str | None = None,
    edge: str | None = None,
    lw: float = 1.4,
):
    """Draw a decision diamond; the text sits inside the inscribed rectangle."""
    pts = [(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)]
    ax.add_patch(
        Polygon(
            pts,
            closed=True,
            facecolor=face or PALETTE["decision"],
            edgecolor=edge or PALETTE["decision_edge"],
            linewidth=lw,
            zorder=3,
        )
    )
    inner_w = w * 0.52
    inner_h = h * 0.52
    label = wrap(text, inner_w, fontsize, pad=0.98)
    t = ax.text(
        x,
        y,
        label,
        ha="center",
        va="center",
        fontsize=fontsize,
        color=PALETTE["ink"],
        linespacing=1.2,
        zorder=5,
    )
    _track(t, x - inner_w / 2, y - inner_h / 2, x + inner_w / 2, y + inner_h / 2)
    return t


def arrow(
    ax,
    p0,
    p1,
    *,
    color: str = PALETTE["ink"],
    lw: float = 1.3,
    style: str = "-|>",
    ls: str = "solid",
    rad: float = 0.0,
    label: str | None = None,
    lpos: float = 0.5,
    loff=(0.0, 1.8),
    lxy: tuple[float, float] | None = None,
    fontsize: float = 7.4,
    lcolor: str | None = None,
    zorder: int = 2,
):
    """Draw an arrow from ``p0`` to ``p1``, with an optional white-backed label."""
    ax.add_patch(
        FancyArrowPatch(
            p0,
            p1,
            arrowstyle=style,
            mutation_scale=11,
            linewidth=lw,
            color=color,
            linestyle=ls,
            shrinkA=0.0,
            shrinkB=0.0,
            connectionstyle=f"arc3,rad={rad}",
            zorder=zorder,
        )
    )
    if label:
        if lxy is not None:
            lx, ly = lxy
        else:
            lx = p0[0] + (p1[0] - p0[0]) * lpos + loff[0]
            ly = p0[1] + (p1[1] - p0[1]) * lpos + loff[1]
        ax.text(
            lx,
            ly,
            label,
            ha="center",
            va="center",
            fontsize=fontsize,
            color=lcolor or PALETTE["muted"],
            style="italic",
            zorder=6,
            bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.92),
        )


def orth_arrow(ax, points, *, color=None, lw: float = 1.25, label: str | None = None,
               lxy: tuple[float, float] | None = None, fontsize: float = 7.0):
    """Route an edge through right-angled bends, arrowhead on the last segment."""
    color = color or PALETTE["ink"]
    xs = [pt[0] for pt in points]
    ys = [pt[1] for pt in points]
    ax.plot(xs[:-1] + [points[-1][0]], ys[:-1] + [points[-1][1]],
            color=color, lw=lw, solid_capstyle="round", zorder=2)
    arrow(ax, points[-2], points[-1], color=color, lw=lw)
    if label and lxy:
        ax.text(lxy[0], lxy[1], label, ha="center", va="center",
                fontsize=fontsize, color=PALETTE["muted"], style="italic",
                linespacing=1.15, zorder=6,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none",
                          alpha=0.95))


def ellipse_edge(cx: float, cy: float, w: float, h: float, tx: float, ty: float):
    """Point on an ellipse boundary in the direction of ``(tx, ty)``."""
    dx = tx - cx
    dy = ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    a = w / 2.0
    b = h / 2.0
    scale = 1.0 / ((dx * dx) / (a * a) + (dy * dy) / (b * b)) ** 0.5
    return cx + dx * scale, cy + dy * scale


def actor(ax, x: float, y: float, label: str, *, scale: float = 1.0):
    """Draw a stick figure with the actor's name underneath."""
    s = scale
    head_r = 1.9 * s
    top = y + 6.0 * s
    ax.add_patch(
        Circle((x, top - head_r), head_r, facecolor=PALETTE["actor_fill"],
               edgecolor=PALETTE["actor"], linewidth=1.4, zorder=4)
    )
    body_top = top - 2 * head_r
    body_bottom = body_top - 4.6 * s
    ax.plot([x, x], [body_top, body_bottom], color=PALETTE["actor"], lw=1.4, zorder=4)
    ax.plot(
        [x - 3.0 * s, x + 3.0 * s],
        [body_top - 1.1 * s, body_top - 1.1 * s],
        color=PALETTE["actor"],
        lw=1.4,
        zorder=4,
    )
    ax.plot(
        [x - 2.4 * s, x, x + 2.4 * s],
        [body_bottom - 3.0 * s, body_bottom, body_bottom - 3.0 * s],
        color=PALETTE["actor"],
        lw=1.4,
        zorder=4,
    )
    t = ax.text(
        x,
        body_bottom - 4.6 * s,
        label,
        ha="center",
        va="top",
        fontsize=8.2,
        fontweight="bold",
        color=PALETTE["actor"],
        zorder=5,
    )
    return (x, top - head_r), t


# --------------------------------------------------------------------------- #
# 1. Use-case diagram
# --------------------------------------------------------------------------- #

UC_LEFT_ACTORS = [
    ("Developer\n(CLI user)", 12.0, 59.0),
    ("CI System", 12.0, 77.0),
    ("Administrator", 12.0, 10.0),
]
UC_RIGHT_ACTORS = [
    ("AI Provider", 138.0, 35.0),
    ("GitHub", 138.0, 58.0),
]

#: (label, x, y, primary?)  primary = one of the nine named use cases.
UC_CASES = [
    ("Review Diff", 50.0, 83.0, True),
    ("Review Source File", 50.0, 71.0, True),
    ("Choose Provider", 50.0, 59.0, True),
    ("View Review History", 50.0, 47.0, True),
    ("Run Benchmark", 50.0, 35.0, True),
    ("Review with Provider", 78.0, 83.0, False),
    ("Anchor Findings", 78.0, 71.0, False),
    ("Post Review to PR", 78.0, 59.0, True),
    ("Receive Webhook", 78.0, 47.0, True),
    ("Manage Users and Roles", 78.0, 35.0, True),
    ("Fall Back to Rules", 106.0, 83.0, False),
    ("Authenticate", 106.0, 71.0, False),
]

#: actor -> use case associations, by label.
UC_LINKS = [
    ("Developer\n(CLI user)", "Review Diff"),
    ("Developer\n(CLI user)", "Review Source File"),
    ("Developer\n(CLI user)", "Choose Provider"),
    ("Developer\n(CLI user)", "Run Benchmark"),
    ("Developer\n(CLI user)", "View Review History"),
    ("CI System", "Review Diff"),
    ("CI System", "Review Source File"),
    ("Administrator", "Manage Users and Roles"),
    ("Administrator", "View Review History"),
    ("GitHub", "Post Review to PR"),
    ("GitHub", "Receive Webhook"),
    ("AI Provider", "Review with Provider"),
]

#: (from, to, kind) with kind in {"include", "extend"}.
UC_DEPS = [
    ("Review Diff", "Review with Provider", "include"),
    ("Review Diff", "Anchor Findings", "include"),
    ("Post Review to PR", "Authenticate", "include"),
    ("Fall Back to Rules", "Review with Provider", "extend"),
]


def build_use_case() -> Path:
    """Actors, system boundary and the include/extend web."""
    fig, ax = canvas(
        15,
        11,
        "Use-case diagram — AI Code Reviewer & PR Assistant",
        "Actors outside the boundary; <<include>> and <<extend>> follow ARCHITECTURE.md sections 2, 3 and 5",
    )

    bx0, by0, bx1, by1 = 34.0, 5.0, 118.0, 92.0
    ax.add_patch(
        FancyBboxPatch(
            (bx0, by0),
            bx1 - bx0,
            by1 - by0,
            boxstyle="round,pad=0,rounding_size=2.5",
            linewidth=1.6,
            edgecolor=PALETTE["boundary"],
            facecolor="#fbfcfe",
            linestyle=(0, (6, 3)),
            zorder=1,
        )
    )
    ax.text(
        (bx0 + bx1) / 2,
        by1 - 3.0,
        "System boundary — the reviewer service (app/)",
        ha="center",
        va="center",
        fontsize=8.4,
        color=PALETTE["muted"],
        fontweight="bold",
        zorder=5,
    )

    anchor: dict[str, tuple[float, float]] = {}
    for label, x, y, primary in UC_CASES:
        w, h = 21.0, 9.0
        ax.add_patch(
            Ellipse(
                (x, y),
                w,
                h,
                facecolor=PALETTE["usecase"] if primary else PALETTE["support"],
                edgecolor=PALETTE["usecase_edge"] if primary else PALETTE["support_edge"],
                linewidth=1.5 if primary else 1.1,
                linestyle="solid" if primary else (0, (4, 2)),
                zorder=3,
            )
        )
        t = ax.text(
            x,
            y,
            wrap(label, w * 0.86, 7.6, pad=0.98),
            ha="center",
            va="center",
            fontsize=7.6,
            color=PALETTE["ink"],
            linespacing=1.2,
            zorder=5,
        )
        _track(t, x - w * 0.40, y - h * 0.36, x + w * 0.40, y + h * 0.36)
        anchor[label] = (x, y)

    actor_pts: dict[str, tuple[float, float]] = {}
    for label, x, y in UC_LEFT_ACTORS + UC_RIGHT_ACTORS:
        pt, _ = actor(ax, x, y, label)
        actor_pts[label] = (x, y)

    for a_label, uc_label in UC_LINKS:
        ax_x, ax_y = actor_pts[a_label]
        ux, uy = anchor[uc_label]
        p0 = ellipse_edge(ax_x, ax_y, 3.0, 12.0, ux, uy)
        p1 = ellipse_edge(ux, uy, 21.0, 9.0, ax_x, ax_y)
        ax.plot(
            [p0[0], p1[0]],
            [p0[1], p1[1]],
            color=PALETTE["actor"],
            lw=0.9,
            alpha=0.62,
            zorder=2,
        )

    for src, dst, kind in UC_DEPS:
        sx, sy = anchor[src]
        dx_, dy_ = anchor[dst]
        p0 = ellipse_edge(sx, sy, 21.0, 9.0, dx_, dy_)
        p1 = ellipse_edge(dx_, dy_, 21.0, 9.0, sx, sy)
        label = f"<<{kind}>>"
        if kind == "extend":
            arrow(ax, p0, p1, color=PALETTE["critical"], lw=1.3, ls=(0, (5, 2)),
                  label=label, lpos=0.5, loff=(0.0, -2.6), fontsize=7.2,
                  lcolor=PALETTE["critical"])
        else:
            arrow(ax, p0, p1, color=PALETTE["support_edge"], lw=1.2, ls=(0, (5, 2)),
                  label=label, lpos=0.5, loff=(0.0, 2.2), fontsize=7.2)

    # Legend
    lx, ly = 92.0, 15.0
    ax.add_patch(
        FancyBboxPatch((lx - 1.0, ly - 10.0), 24.0, 17.0,
                       boxstyle="round,pad=0,rounding_size=1.6",
                       facecolor="#f7f9fb", edgecolor=PALETTE["grid"], linewidth=1.0,
                       zorder=2)
    )
    ax.text(lx, ly + 4.0, "Legend", fontsize=8.0, fontweight="bold",
            color=PALETTE["ink"], zorder=5)
    ax.add_patch(Ellipse((lx + 3.6, ly - 0.4), 6.6, 3.2, facecolor=PALETTE["usecase"],
                         edgecolor=PALETTE["usecase_edge"], linewidth=1.3, zorder=4))
    ax.text(lx + 8.0, ly - 0.4, "primary", fontsize=7.0,
            va="center", color=PALETTE["ink"], zorder=5)
    ax.add_patch(Ellipse((lx + 3.6, ly - 4.4), 6.6, 3.2, facecolor=PALETTE["support"],
                         edgecolor=PALETTE["support_edge"], linewidth=1.0,
                         linestyle=(0, (4, 2)), zorder=4))
    ax.text(lx + 8.0, ly - 4.4, "supporting", fontsize=7.0,
            va="center", color=PALETTE["ink"], zorder=5)
    ax.plot([lx + 0.2, lx + 6.8], [ly - 8.2, ly - 8.2], color=PALETTE["support_edge"],
            lw=1.2, linestyle=(0, (5, 2)), zorder=4)
    ax.text(lx + 8.0, ly - 8.2, "include / extend", fontsize=7.0,
            va="center", color=PALETTE["ink"], zorder=5)

    audit_overflow(fig, ax, "use-case")
    return save(fig, "use-case-diagram.png")


# --------------------------------------------------------------------------- #
# 2. Activity diagram
# --------------------------------------------------------------------------- #
#
# Traced from the code, not from the report's prescription:
#
#   app/main.py                      _build_response (422), _verify_signature (401),
#                                    the WebhookAck 200s, _persist_review,
#                                    _publish_review
#   app/engine.py                    select_provider, review
#   app/openai_compat_provider.py    review_diff_live (attempt 1, one repair
#                                    retry, empty live review on a double failure),
#                                    review_with_fallback (degradation)
#   app/db.py                        store_review, store_pr_post
#   app/github_client.py             build_payload, post_review (marker check,
#                                    422 demotion, single 429 retry)
#
# There is no "re-read the body as source code" step anywhere in the code: a body
# that carries neither `diff` nor `code` is a 422, and a diff that does not parse
# is a 422. The repair retry belongs to the provider path, one panel further down.

ACT_NODES = [
    # id, kind, x, y, w, h, text
    ("start", "start", 42.0, 218.0, 44.0, 6.4,
     "Start: request in — /review, /test-review or /webhook"),
    ("dbody", "decision", 42.0, 205.8, 34.0, 12.0,
     "Body valid? (pydantic: provider literal, NUL bytes)"),
    ("e422v", "end", 10.0, 205.8, 18.0, 9.0, "422 body rejected"),
    ("dsig", "decision", 42.0, 190.3, 34.0, 13.0,
     "Signature valid? (HMAC-SHA256, only when GITHUB_WEBHOOK_SECRET is set)"),
    ("e401", "end", 10.0, 190.3, 18.0, 9.0, "401 signature mismatch"),
    ("evt", "decision", 42.0, 174.8, 32.0, 12.0, "Reviewed event and action?"),
    ("eign", "end", 10.0, 174.8, 18.0, 9.0, "200 ignored (WebhookAck)"),
    ("src", "action", 42.0, 161.3, 44.0, 9.0,
     "Pick the diff source: inline diff → GitHub API → fixture"),
    ("dsrc", "decision", 42.0, 147.8, 32.0, 12.0, "diff or code supplied?"),
    ("e422n", "end", 10.0, 147.8, 18.0, 9.0, "422 neither supplied"),
    ("dparse", "decision", 42.0, 132.8, 32.0, 12.0, "parse_diff succeeds?"),
    ("e422p", "end", 10.0, 132.8, 18.0, 9.0, "422 unparseable diff"),
    ("engine", "action", 42.0, 119.3, 44.0, 9.0,
     "engine.review() → select_provider: sarvam > local > mock"),
    ("dlive", "decision", 42.0, 105.8, 32.0, 12.0, "Live provider selected?"),
    # provider band — the single repair retry lives here, not on the HTTP body
    ("attempt", "action", 68.0, 88.0, 22.0, 10.0,
     "Attempt 1: _call_model, response_format = json_object"),
    ("dhard", "decision", 68.0, 74.0, 22.0, 12.0, "Non-repairable error?"),
    ("djson", "decision", 68.0, 59.5, 22.0, 11.0, "Answer parses?"),
    ("repair", "action", 68.0, 46.0, 22.0, 10.0,
     "One repair retry: _repair_prompt, response_format dropped"),
    ("dretry", "decision", 68.0, 32.5, 22.0, 11.0, "Retry parses?"),
    ("ezero", "end", 68.0, 18.5, 24.0, 10.0,
     "End: live review, zero findings (one WARNING, no mock fallback)"),
    ("mock", "action", 18.0, 74.0, 26.0, 12.0,
     "offline_diff_findings(): local rule engine, one WARNING, mode = mock"),
    ("findings", "action", 40.0, 48.0, 32.0, 10.0,
     "Findings in hand: rule-engine or live-model findings"),
    ("connA", "connector", 40.0, 24.0, 5.2, 5.2, "A"),
    # panel B — assemble, persist, publish
    ("connB", "connector", 110.0, 218.0, 5.2, 5.2, "A"),
    ("build", "action", 110.0, 207.0, 44.0, 9.0,
     "Build the response: anchor_findings, render_comment, stats, verdict"),
    ("persist", "action", 110.0, 193.0, 44.0, 12.0,
     "Persist the review — Database.store_review(); a failure logs one WARNING "
     "and leaves the response unchanged"),
    ("dpublish", "decision", 110.0, 178.0, 32.0, 12.0, "Publish this review?"),
    ("eunpub", "end", 148.0, 178.0, 20.0, 12.0,
     "End: 200 — not published, posting null"),
    ("payload", "action", 110.0, 161.0, 44.0, 12.0,
     "build_payload(): anchored findings → inline comments (cap 30), the rest "
     "into the summary"),
    ("dmarker", "decision", 110.0, 146.0, 32.0, 12.0, "Summary marker already on the PR?"),
    ("edup", "end", 148.0, 146.0, 20.0, 12.0, "End: duplicate, nothing posted (200)"),
    ("inline", "action", 110.0, 131.0, 44.0, 12.0,
     "Post the inline review comments (a 429 waits Retry-After, one retry)"),
    ("d422", "decision", 110.0, 116.0, 32.0, 12.0, "422 on an inline comment?"),
    ("demote", "action", 148.0, 116.0, 20.0, 12.0, "Demote that comment into the summary"),
    ("summary", "action", 110.0, 101.0, 44.0, 11.0,
     "Post the summary comment (same single 429 retry)"),
    ("prpost", "action", 110.0, 88.0, 44.0, 9.0,
     "Persist the posting outcome — store_pr_post()"),
    ("dposted", "decision", 110.0, 74.0, 30.0, 11.0, "Posting succeeded?"),
    ("eok", "end", 148.0, 74.0, 20.0, 12.0, "End: 200 — posting.ok = true"),
    ("efail", "end", 148.0, 57.0, 20.0, 12.0,
     "End: 200 — posting.ok = false, one WARNING"),
]

#: (src, dst, label, options). ``options`` may carry:
#:   ``way``   explicit right-angled route through these points
#:   ``lxy``   explicit label position
#:   ``rad``   curvature for a straight edge
ACT_EDGES = [
    ("start", "dbody", "", {}),
    ("dbody", "e422v", "no", {}),
    ("dbody", "dsig", "yes", {}),
    ("dsig", "e401", "no", {}),
    ("dsig", "evt", "yes", {}),
    ("evt", "eign", "no", {}),
    ("evt", "src", "yes", {}),
    ("src", "dsrc", "", {}),
    ("dsrc", "e422n", "no", {}),
    ("dsrc", "dparse", "yes", {}),
    ("dparse", "e422p", "no", {}),
    ("dparse", "engine", "yes", {}),
    ("engine", "dlive", "", {}),
    ("dlive", "attempt", "yes", {"lxy": (54.0, 100.0)}),
    ("dlive", "mock", "no", {"lxy": (24.0, 96.0)}),
    ("attempt", "dhard", "", {}),
    ("dhard", "djson", "no", {}),
    ("dhard", "mock", "yes", {"lxy": (41.0, 76.4)}),
    ("djson", "repair", "no", {}),
    ("djson", "findings", "yes",
     {"way": [(57.0, 59.5), (40.0, 59.5), (40.0, 53.0)], "lxy": (46.0, 61.8)}),
    ("repair", "dretry", "", {}),
    ("dretry", "findings", "yes",
     {"way": [(57.0, 32.5), (48.0, 32.5), (48.0, 43.0)], "lxy": (52.6, 34.9)}),
    ("dretry", "ezero", "no", {}),
    ("mock", "findings", "",
     {"way": [(18.0, 68.0), (18.0, 48.0), (24.0, 48.0)]}),
    ("findings", "connA", "", {"lxy": (51.0, 36.0)}),
    ("connB", "build", "", {}),
    ("build", "persist", "", {}),
    ("persist", "dpublish", "", {}),
    ("dpublish", "eunpub", "no", {}),
    ("dpublish", "payload", "yes", {}),
    ("payload", "dmarker", "", {}),
    ("dmarker", "edup", "yes", {}),
    ("dmarker", "inline", "no", {}),
    ("inline", "d422", "", {}),
    ("d422", "demote", "yes", {}),
    ("demote", "summary", "",
     {"way": [(148.0, 110.0), (148.0, 101.0), (132.0, 101.0)]}),
    ("d422", "summary", "no", {}),
    ("summary", "prpost", "", {}),
    ("prpost", "dposted", "", {}),
    ("dposted", "eok", "yes", {}),
    ("dposted", "efail", "no",
     {"way": [(110.0, 68.5), (110.0, 57.0), (138.0, 57.0)]}),
]

#: Notes printed under panel B, each one a fact from the source.
ACT_NOTES = [
    "Publish needs all four: action in {opened, reopened, synchronize}; a "
    "GITHUB_TOKEN; a webhook secret (or WEBHOOK_ALLOW_UNSIGNED=1); and a real "
    "pull-request diff — a fixture review is never posted.",
    "A non-repairable provider failure (auth, permission, connection, timeout, "
    "429, 5xx) degrades to the rule engine. A second parse failure does not: the "
    "run stays live with zero findings.",
    "A body carrying both 'diff' and 'code' is reviewed as the diff, and 'code' is "
    "ignored. /test-review?path= outside the project root answers 403, a missing "
    "file 404.",
    "No storage or posting failure can change the status: each is logged once at "
    "WARNING and the answer stays 200.",
]


def connector(ax, x: float, y: float, size: float, letter: str, note: str = "") -> None:
    """Draw an on-page connector: a circle carrying a letter, plus an optional note.

    Args:
        ax: The axes to draw on.
        x: Centre x, in data units.
        y: Centre y, in data units.
        size: Diameter, in data units.
        letter: The letter that matches this connector to its partner.
        note: Text printed beside the circle; empty for none.
    """
    ax.add_patch(
        Circle((x, y), size / 2.0, facecolor="white", edgecolor=PALETTE["ink"],
               linewidth=1.3, zorder=4)
    )
    ax.text(x, y, letter, ha="center", va="center", fontsize=8.0,
            fontweight="bold", color=PALETTE["ink"], zorder=5)
    if note:
        ax.text(x + size / 2.0 + 1.2, y, note, ha="left", va="center",
                fontsize=6.9, color=PALETTE["muted"], style="italic", zorder=5)


def note_block(ax, x: float, y_top: float, width: float, items: list[str],
               fontsize: float = 6.6) -> None:
    """Draw a light panel of wrapped notes.

    Args:
        ax: The axes to draw on.
        x: Left edge of the panel.
        y_top: Top edge of the panel.
        width: Panel width in data units.
        items: One paragraph per note; each is bulleted and wrapped.
        fontsize: Point size for the note text.
    """
    wrapped = [wrap(item, width - 3.4, fontsize, pad=0.97) for item in items]
    line_units = fontsize * 1.34 / 72.0 * UPI
    height = 3.0 + sum(len(text.split("\n")) for text in wrapped) * line_units
    ax.add_patch(
        FancyBboxPatch((x, y_top - height), width, height,
                       boxstyle="round,pad=0,rounding_size=1.4",
                       facecolor="#fbfcfd", edgecolor=PALETTE["grid"],
                       linewidth=0.9, zorder=2)
    )
    ax.text(x + 1.6, y_top - 2.0, "Notes — each line is a branch in the code",
            fontsize=6.8, fontweight="bold", color=PALETTE["ink"],
            ha="left", va="center", zorder=5)
    cursor = y_top - 3.0 - line_units
    for text in wrapped:
        for index, line in enumerate(text.split("\n")):
            ax.text(x + 2.0 if index == 0 else x + 3.4, cursor,
                    ("• " if index == 0 else "") + line,
                    fontsize=fontsize, color=PALETTE["muted"],
                    ha="left", va="center", zorder=5)
            cursor -= line_units


def _edge_label_xy(p0: tuple[float, float], p1: tuple[float, float]) -> tuple[float, float]:
    """Place a yes/no label beside the middle of an edge, never on a box edge.

    A vertical edge takes its label to the right, a horizontal edge above it, so
    the white label backer sits on empty canvas rather than on a border.

    Args:
        p0: Start of the edge.
        p1: End of the edge.

    Returns:
        The label centre, in data units.
    """
    mx, my = (p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0
    if abs(p1[1] - p0[1]) >= abs(p1[0] - p0[0]):
        return mx + 3.6, my
    return mx, my + 2.2


def build_activity() -> Path:
    """The real review flow: request → provider → response → persist → publish."""
    fig, ax = canvas(
        16,
        24,
        "Activity diagram — one review, from request to stored history and posted comment",
        "Panel A: the review path. Panel B: assemble, persist and publish. Every "
        "decision and terminal is a branch in app/main.py, app/engine.py, "
        "app/openai_compat_provider.py, app/db.py or app/github_client.py",
    )

    geo = {n[0]: n for n in ACT_NODES}

    def attach(nid: str, towards: tuple[float, float]) -> tuple[float, float]:
        """Boundary point of node ``nid`` facing ``towards``."""
        _, kind, x, y, w, h, _ = geo[nid]
        tx, ty = towards
        if kind == "decision":
            dx, dy = tx - x, ty - y
            if dx == 0 and dy == 0:
                return x, y
            a, b = w / 2, h / 2
            s = min(a / abs(dx) if dx else 1e9, b / abs(dy) if dy else 1e9)
            return x + dx * s, y + dy * s
        if kind == "connector":
            dx, dy = tx - x, ty - y
            dist = (dx * dx + dy * dy) ** 0.5 or 1.0
            r = w / 2.0
            return x + dx / dist * r, y + dy / dist * r
        return ellipse_edge(x, y, w, h * 1.08, tx, ty)

    for nid, kind, x, y, w, h, text in ACT_NODES:
        if kind == "start":
            box(ax, x, y, w, h, text, face=PALETTE["start"],
                edge=PALETTE["start_edge"], fontsize=8.0, radius=h / 2, bold=True)
        elif kind == "end":
            box(ax, x, y, w, h, text, face=PALETTE["terminal"],
                edge=PALETTE["terminal_edge"], fontsize=7.6, radius=h / 2, lw=1.6)
            box(ax, x, y, w - 1.6, h - 1.6, "", face="none",
                edge=PALETTE["terminal_edge"], radius=(h - 1.6) / 2, lw=0.9,
                track=False)
        elif kind == "decision":
            diamond(ax, x, y, w, h, text, fontsize=7.4)
        elif kind == "connector":
            connector(ax, x, y, w, text)
        else:
            box(ax, x, y, w, h, text, face=PALETTE["process"],
                edge=PALETTE["process_edge"], fontsize=7.8)

    connector(ax, 40.0, 24.0, 5.2, "A", "findings → panel B")
    connector(ax, 110.0, 218.0, 5.2, "A", "from panel A")

    for src, dst, label, opts in ACT_EDGES:
        way = opts.get("way")
        if way:
            points = [attach(src, way[0])] + list(way) + [attach(dst, way[-1])]
            lxy = opts.get("lxy")
            if label and lxy is None:
                lxy = ((way[0][0] + way[1][0]) / 2.0, way[0][1] + 2.2)
            orth_arrow(ax, points, lw=1.2, label=label or None, lxy=lxy,
                       fontsize=7.0)
            continue
        p0 = attach(src, (geo[dst][2], geo[dst][3]))
        p1 = attach(dst, (geo[src][2], geo[src][3]))
        lxy = opts.get("lxy")
        if label and lxy is None:
            lxy = _edge_label_xy(p0, p1)
        arrow(ax, p0, p1, color=PALETTE["ink"], lw=1.2,
              rad=opts.get("rad", 0.0), label=label or None,
              loff=(0.0, 1.6), fontsize=7.0, lpos=0.45, lxy=lxy)

    # Panel headings and the divider between them.
    for hx, heading in (
        (40.0, "A — review path"),
        (110.0, "B — assemble, persist and publish"),
    ):
        ax.text(hx, 227.0, heading, ha="center", va="center", fontsize=9.4,
                fontweight="bold", color=PALETTE["ink"], zorder=5)
    ax.plot([81.0, 81.0], [6.0, 222.0], color=PALETTE["grid"], lw=1.0,
            linestyle=(0, (4.0, 3.0)), zorder=1)

    # Legend, bottom left of panel A.
    lx, ly = 4.0, 36.0
    ax.add_patch(
        FancyBboxPatch((lx - 1.4, ly - 13.0), 30.0, 19.0,
                       boxstyle="round,pad=0,rounding_size=1.6",
                       facecolor="#f7f9fb", edgecolor=PALETTE["grid"], linewidth=1.0)
    )
    ax.text(lx, ly + 4.0, "Legend", fontsize=7.6, fontweight="bold",
            color=PALETTE["ink"], zorder=5)
    box(ax, lx + 3.0, ly + 0.2, 6.0, 2.8, "", face=PALETTE["process"],
        edge=PALETTE["process_edge"], radius=1.0, lw=1.1, track=False)
    ax.text(lx + 7.4, ly + 0.2, "action", fontsize=7.0, va="center",
            color=PALETTE["ink"], zorder=5)
    diamond(ax, lx + 3.0, ly - 3.6, 7.0, 3.4, "", fontsize=6.5)
    ax.text(lx + 7.4, ly - 3.6, "decision", fontsize=7.0, va="center",
            color=PALETTE["ink"], zorder=5)
    box(ax, lx + 3.0, ly - 7.4, 6.0, 2.8, "", face=PALETTE["terminal"],
        edge=PALETTE["terminal_edge"], radius=1.4, lw=1.2, track=False)
    ax.text(lx + 7.4, ly - 7.4, "terminal", fontsize=7.0, va="center",
            color=PALETTE["ink"], zorder=5)
    connector(ax, lx + 3.0, ly - 11.2, 3.4, "A")
    ax.text(lx + 7.4, ly - 11.2, "connector", fontsize=7.0, va="center",
            color=PALETTE["ink"], zorder=5)

    note_block(ax, 86.0, 44.0, 70.0, ACT_NOTES)

    audit_overflow(fig, ax, "activity")
    return save(fig, "activity-diagram.png")


# --------------------------------------------------------------------------- #
# 3. Sequence diagram
# --------------------------------------------------------------------------- #

SEQ_LIFELINES = [
    ("CLI / HTTP client", 14.0),
    ("FastAPI\n(main.py)", 30.0),
    ("engine\n(engine.py)", 46.0),
    ("adapter\n(openai_compat)", 62.0),
    ("Provider endpoint\n(Sarvam | LM Studio)", 80.0),
    ("Rule engine\n(rules.py)", 98.0),
    ("Parser / anchorer\n(parser.py)", 116.0),
    ("Review store\n(db.py, SQLite)", 132.0),
    ("GitHub API\n(PR comments)", 150.0),
]

#: (from_idx, to_idx, y, label, dashed?)  idx None == self-call on from_idx.
SEQ_MSGS = [
    (0, 1, 100.0, "POST /review  {diff | code, provider}", False),
    (1, 2, 95.0, "engine.review(bundle, settings, provider)", False),
    (2, None, 91.0, "select_provider(): sarvam > local > mock", False),
    (2, 3, 80.5, "review_with_fallback(bundle, config)", False),
    (3, 4, 75.5, "POST /chat/completions (JSON object mode)", False),
    (4, 3, 70.5, "completion JSON", True),
    (3, 2, 65.5, "findings list, lines snapped to added lines", True),
    (2, 5, 57.0, "offline_diff_findings(bundle)  [degraded]", False),
    (5, 2, 52.0, "findings from the 63 deterministic rules", True),
    (2, 6, 44.0, "anchor_findings(findings, bundle)", False),
    (6, 2, 39.0, "AnchoredFinding[]: anchored | file_only | unanchored", True),
    (2, 1, 34.0, "ProviderOutcome(mode, provider, model)", True),
    (1, 7, 29.0, "persist review, then hold result for the response", False),
    (1, 0, 24.0, "200 review JSON", True),
    (1, 8, 17.0, "post_review(owner, repo, pr, payload, token)", False),
    (8, 1, 12.0, "201 | 422 | 429 | 401", True),
    (1, 8, 7.0, "per-comment retry, then summary comment (marker)", False),
]

SEQ_ACTIVE = {
    0: (98.0, 22.0),
    1: (92.0, 4.5),
    2: (97.0, 32.0),
    3: (82.5, 63.5),
    4: (77.5, 68.5),
    5: (59.0, 50.0),
    6: (46.0, 37.0),
    7: (31.0, 27.0),
    8: (19.0, 5.0),
}


def build_sequence() -> Path:
    """Nine lifelines, activation bars, return arrows and one alt block."""
    fig, ax = canvas(
        16,
        13,
        "Sequence diagram — a review request and the PR post",
        "alt block: live provider path versus the deterministic mock path (engine.py, openai_compat_provider.py)",
    )

    top = 104.0
    for idx, (label, x) in enumerate(SEQ_LIFELINES):
        ax.add_patch(
            FancyBboxPatch(
                (x - 6.6, top + 0.6), 13.2, 7.2,
                boxstyle="round,pad=0,rounding_size=1.2",
                facecolor=PALETTE["actor_fill"], edgecolor=PALETTE["actor"],
                linewidth=1.2, zorder=4,
            )
        )
        t = ax.text(x, top + 4.2, label, ha="center", va="center", fontsize=7.2,
                    fontweight="bold", color=PALETTE["actor"], linespacing=1.15,
                    zorder=5)
        _track(t, x - 6.2, top + 1.0, x + 6.2, top + 7.4)
        ax.plot([x, x], [top, 2.5], color=PALETTE["grid"], lw=1.1,
                linestyle=(0, (4, 3)), zorder=1)

    for idx, (y0, y1) in SEQ_ACTIVE.items():
        x = SEQ_LIFELINES[idx][1]
        ax.add_patch(
            Rectangle((x - 0.7, y1), 1.4, y0 - y1, facecolor="#c9d8e8",
                      edgecolor=PALETTE["actor"], linewidth=0.8, zorder=3)
        )

    # alt frame
    fx0, fx1 = 62.0 - 7.2, 80.0 + 7.2
    ax.add_patch(
        Rectangle((fx0, 49.0), fx1 - fx0, 38.5, facecolor="none",
                  edgecolor=PALETTE["decision_edge"], linewidth=1.3, zorder=2)
    )
    ax.add_patch(
        Polygon([[fx0, 87.5], [fx0 + 26.0, 87.5], [fx0 + 26.0, 84.7],
                 [fx0 + 23.6, 82.5], [fx0, 82.5]], closed=True,
                facecolor="#fdf2dd", edgecolor=PALETTE["decision_edge"],
                linewidth=1.0, zorder=3)
    )
    ax.text(fx0 + 1.0, 85.6, "alt  [live: a key or a local endpoint is configured]",
            fontsize=7.0, va="center", color=PALETTE["ink"], zorder=5)
    ax.plot([fx0, fx1], [61.6, 61.6], color=PALETTE["decision_edge"], lw=0.9,
            linestyle=(0, (4, 3)), zorder=3)
    ax.text(fx0 + 1.0, 63.0,
            "else  [no key, no SDK, REVIEW_MODE=mock, timeout, bad JSON]",
            fontsize=7.0, va="center", color=PALETTE["ink"], zorder=5)

    for src, dst, y, label, dashed in SEQ_MSGS:
        x0 = SEQ_LIFELINES[src][1]
        if dst is None:
            # self-call: a short bracket on the same lifeline
            ax.add_patch(
                FancyArrowPatch(
                    (x0 + 0.7, y + 0.9), (x0 + 0.7, y - 0.9),
                    arrowstyle="-|>", mutation_scale=9, linewidth=1.0,
                    color=PALETTE["ink"],
                    connectionstyle="arc3,rad=-1.6", zorder=4,
                )
            )
            ax.text(x0 + 9.0, y, label, fontsize=7.0, va="center",
                    ha="left", color=PALETTE["ink"], style="italic", zorder=5)
            continue
        x1 = SEQ_LIFELINES[dst][1]
        left_to_right = x1 > x0
        start = x0 + (0.7 if left_to_right else -0.7)
        end = x1 + (-0.7 if left_to_right else 0.7)
        ax.add_patch(
            FancyArrowPatch(
                (start, y), (end, y),
                arrowstyle="-|>" if not dashed else "-|>",
                mutation_scale=9,
                linewidth=1.15 if not dashed else 1.0,
                color=PALETTE["ink"] if not dashed else PALETTE["muted"],
                linestyle="solid" if not dashed else (0, (4, 2.5)),
                shrinkA=0, shrinkB=0, zorder=4,
            )
        )
        ax.text((start + end) / 2, y + 1.35, label, ha="center", va="bottom",
                fontsize=7.0, color=PALETTE["ink"],
                style="italic" if dashed else "normal", zorder=5,
                bbox=dict(boxstyle="round,pad=0.10", fc="white", ec="none",
                          alpha=0.9))

    ax.plot([3.0, 156.0], [21.0, 21.0], color=PALETTE["grid"], lw=1.0,
            linestyle=(0, (6, 3)), zorder=1)
    ax.text(3.0, 22.4,
            "webhook path: pull_request opened | reopened | synchronize, GITHUB_TOKEN set",
            fontsize=7.2, va="bottom", color=PALETTE["muted"], style="italic",
            zorder=5)

    ax.text(3.0, 9.0, "Solid arrow: call.  Dashed arrow: return.  Bars: activation.",
            fontsize=7.2, va="center", color=PALETTE["muted"], zorder=5)

    audit_overflow(fig, ax, "sequence")
    return save(fig, "sequence-diagram.png")


# --------------------------------------------------------------------------- #
# 4. State diagram
# --------------------------------------------------------------------------- #

STATE_NODES = [
    # id, x, y, w, h, text, kind
    ("idle", 16.0, 92.0, 20.0, 9.0, "Idle", "state"),
    ("marker", 44.0, 92.0, 24.0, 9.0, "Checking Marker", "state"),
    ("inline", 74.0, 92.0, 22.0, 9.0, "Posting Inline", "state"),
    ("summary", 106.0, 92.0, 24.0, 9.0, "Posting Summary", "state"),
    ("done", 134.0, 92.0, 16.0, 9.0, "Done", "final"),
    ("dup", 44.0, 62.0, 24.0, 9.0, "Skipped Duplicate", "final"),
    ("demote", 100.0, 64.0, 22.0, 9.0, "Demoting", "state"),
    ("failed", 68.0, 24.0, 20.0, 9.0, "Failed", "final"),
]

#: (src, dst, label, rad, label position) — label position is explicit so that
#: no two edge labels can land on the same spot.
STATE_EDGES = [
    ("idle", "marker", "token present, payload non-empty", 0.0, (30.0, 93.9)),
    ("marker", "inline", "summary marker absent", 0.0, (59.0, 93.9)),
    ("inline", "summary", "2xx", 0.0, (90.0, 93.7)),
    ("summary", "done", "2xx", 0.0, (120.0, 93.7)),
    ("marker", "dup", "summary marker already on the PR", 0.0, (44.0, 74.0)),
    ("inline", "demote", "422: line not in the diff\n429 twice: demote all", 0.22,
     (79.0, 74.5)),
    ("demote", "summary", "each comment retried singly; repeats demoted", 0.0,
     (100.0, 78.0)),
    ("demote", "failed", "401/403, 5xx, transport error", 0.0, (97.0, 42.0)),
]

#: Right-angled failure routes into the Failed state, kept clear of every box.
STATE_ELBOWS = [
    ([(16.0, 87.5), (16.0, 30.0), (60.0, 30.0), (60.0, 28.5)],
     "no token: skip the post", (24.0, 32.0)),
    ([(50.0, 87.5), (50.0, 80.0), (64.0, 80.0), (64.0, 28.5)],
     "401/403, 429, 5xx, transport error", (52.0, 81.6)),
    ([(110.0, 87.5), (110.0, 82.0), (74.0, 82.0), (74.0, 28.5)],
     "", (0.0, 0.0)),
    ([(118.0, 90.0), (124.0, 90.0), (124.0, 24.0), (78.0, 24.0)],
     "non-2xx or transport error", (124.0, 52.0)),
]


def build_state() -> Path:
    """The posting state machine of app/github_client.py, with its failure edges."""
    fig, ax = canvas(
        15,
        11.5,
        "State diagram — the PR posting state machine (app/github_client.py)",
        "post_review() never raises: every failure is a state, and the webhook still answers GitHub with HTTP 200",
    )

    geo = {n[0]: n for n in STATE_NODES}

    for nid, x, y, w, h, text, kind in STATE_NODES:
        if kind == "final":
            box(ax, x, y, w, h, text, face=PALETTE["terminal"],
                edge=PALETTE["terminal_edge"], fontsize=8.4, radius=2.0, lw=1.6,
                bold=True)
            box(ax, x, y, w - 1.8, h - 1.8, "", face="none",
                edge=PALETTE["terminal_edge"], radius=1.6, lw=0.9, track=False)
        else:
            box(ax, x, y, w, h, text, face=PALETTE["usecase"],
                edge=PALETTE["usecase_edge"], fontsize=8.4, radius=2.2, bold=True)

    # initial pseudo-state
    ax.add_patch(Circle((4.0, 92.0), 1.5, facecolor=PALETTE["ink"],
                        edgecolor=PALETTE["ink"], zorder=4))
    arrow(ax, (5.5, 92.0), (6.0, 92.0), color=PALETTE["ink"], lw=1.4)
    ax.text(4.0, 96.2, "start", fontsize=7.2, ha="center", color=PALETTE["muted"],
            style="italic")

    def edge_point(nid, towards):
        _, x, y, w, h, _, _ = geo[nid]
        return ellipse_edge(x, y, w, h * 1.06, towards[0], towards[1])

    for src, dst, label, rad, lxy in STATE_EDGES:
        sx, sy = geo[src][1], geo[src][2]
        dx_, dy_ = geo[dst][1], geo[dst][2]
        p0 = edge_point(src, (dx_, dy_))
        p1 = edge_point(dst, (sx, sy))
        if src == "inline" and dst == "demote":
            p0 = (geo[src][1] - 4.0, geo[src][2] - 4.5)
            p1 = (geo[dst][1] - 11.0, geo[dst][2] + 1.0)
        if src == "demote" and dst == "failed":
            p0 = (geo[src][1] - 4.0, geo[src][2] - 4.5)
            p1 = (geo[dst][1] + 6.0, geo[dst][2] + 4.5)
        arrow(ax, p0, p1, color=PALETTE["ink"], lw=1.25, rad=rad, label=label,
              lxy=lxy, fontsize=7.0)

    for points, label, lxy in STATE_ELBOWS:
        if label:
            orth_arrow(ax, points, label=label, lxy=lxy)
        else:
            orth_arrow(ax, points)

    # self-loop for the single 429 retry
    ax.add_patch(
        FancyArrowPatch(
            (65.0, 96.5), (73.0, 96.5),
            arrowstyle="-|>", mutation_scale=11, linewidth=1.1,
            color=PALETTE["decision_edge"], connectionstyle="arc3,rad=1.0",
            zorder=2,
        )
    )
    ax.text(74.0, 101.2, "429: sleep Retry-After, retry once", fontsize=6.9,
            ha="center", va="center", color=PALETTE["muted"], style="italic",
            bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.92),
            zorder=6)

    ax.add_patch(
        FancyBboxPatch((4.0, 4.0), 46.0, 12.0,
                       boxstyle="round,pad=0,rounding_size=1.6",
                       facecolor="#f7f9fb", edgecolor=PALETTE["grid"], linewidth=1.0)
    )
    ax.text(5.4, 13.4, "Legend", fontsize=8.0, fontweight="bold",
            color=PALETTE["ink"], zorder=5)
    box(ax, 8.4, 9.0, 6.4, 3.4, "", face=PALETTE["usecase"],
        edge=PALETTE["usecase_edge"], radius=1.0, lw=1.1, track=False)
    ax.text(13.2, 9.0, "working state", fontsize=7.2, va="center",
            color=PALETTE["ink"], zorder=5)
    box(ax, 28.0, 9.0, 6.4, 3.4, "", face=PALETTE["terminal"],
        edge=PALETTE["terminal_edge"], radius=1.0, lw=1.2, track=False)
    ax.text(32.8, 9.0, "terminal state", fontsize=7.2, va="center",
            color=PALETTE["ink"], zorder=5)
    ax.text(5.4, 5.8,
            "PostResult(ok, inline_posted, inline_demoted, summary_posted, skipped_dup, error)",
            fontsize=6.8, va="center", color=PALETTE["muted"], style="italic",
            zorder=5)

    audit_overflow(fig, ax, "state")
    return save(fig, "state-diagram.png")


# --------------------------------------------------------------------------- #
# 5. PERT network
# --------------------------------------------------------------------------- #

@dataclass
class Activity:
    """One PERT activity with its three-point estimate and schedule slots."""

    ident: str
    name: str
    preds: tuple[str, ...]
    optimistic: float
    likely: float
    pessimistic: float
    expected: float = 0.0
    variance: float = 0.0
    es: float = 0.0
    ef: float = 0.0
    ls: float = 0.0
    lf: float = 0.0

    @property
    def slack(self) -> float:
        """Total float: how many days the activity can slip without moving the end."""
        return self.ls - self.es

    @property
    def sd(self) -> float:
        """Standard deviation of the three-point estimate."""
        return (self.pessimistic - self.optimistic) / 6.0

    @property
    def critical(self) -> bool:
        """True when the activity sits on a zero-slack path."""
        return abs(self.slack) < 1e-9


ACTIVITIES = [
    Activity("A", "Requirements and scope", (), 4, 6, 11),
    Activity("B", "System design and contracts", ("A",), 5, 8, 13),
    Activity("C", "Rule engine (63 rules)", ("B",), 8, 12, 18),
    Activity("D", "Parser and anchoring", ("B",), 6, 9, 14),
    Activity("E", "Provider layer (adapter + engine)", ("C", "D"), 10, 15, 24),
    Activity("F", "API surface (FastAPI + webhook)", ("C", "D"), 7, 10, 16),
    Activity("G", "GitHub posting (marker, 422, 429)", ("E", "F"), 8, 11, 18),
    Activity("H", "Benchmark harness", ("E",), 5, 8, 14),
    Activity("I", "Testing and hardening", ("G", "H"), 6, 10, 16),
    Activity("J", "Documentation and reproducibility", ("I",), 4, 6, 10),
]

#: Working days per week, used to put the PERT result on the 16-week Gantt.
DAYS_PER_WEEK = 5.0
#: Weeks the schedule is drawn over (docs/learning/PACE.md).
PLAN_WEEKS = 16.0

PERT_POS = {
    "A": (14.0, 62.0),
    "B": (34.0, 62.0),
    "C": (54.0, 80.0),
    "D": (54.0, 44.0),
    "E": (76.0, 84.0),
    "F": (76.0, 46.0),
    "G": (98.0, 84.0),
    "H": (98.0, 46.0),
    "I": (118.0, 62.0),
    "J": (138.0, 62.0),
}


def schedule(activities: list[Activity]) -> dict[str, Activity]:
    """Run the PERT forward and backward passes, in place.

    Forward: ``EF = ES + te``, ``ES = max(EF of predecessors)``.
    Backward from the project finish: ``LF = min(LS of successors)``,
    ``LS = LF - te``. Slack is ``LS - ES``; zero slack is the critical path.

    Args:
        activities: The network, in topological order.

    Returns:
        The same activities, keyed by id, with every field filled.
    """
    by_id = {a.ident: a for a in activities}
    for a in activities:
        a.expected = (a.optimistic + 4 * a.likely + a.pessimistic) / 6.0
        a.variance = ((a.pessimistic - a.optimistic) / 6.0) ** 2

    for a in activities:
        a.es = max((by_id[p].ef for p in a.preds), default=0.0)
        a.ef = a.es + a.expected

    finish = max(a.ef for a in activities)
    successors: dict[str, list[str]] = {a.ident: [] for a in activities}
    for a in activities:
        for p in a.preds:
            successors[p].append(a.ident)

    for a in reversed(activities):
        succ = successors[a.ident]
        a.lf = min((by_id[s].ls for s in succ), default=finish)
        a.ls = a.lf - a.expected
    return by_id


def critical_path(by_id: dict[str, Activity]) -> list[Activity]:
    """Walk the zero-slack activities from the start, largest EF first."""
    current = [a for a in by_id.values() if a.critical and not a.preds]
    path: list[Activity] = []
    while current:
        node = sorted(current, key=lambda a: (a.ef, a.ident))[0]
        path.append(node)
        nxt = [
            by_id[s]
            for s in by_id
            if node.ident in by_id[s].preds and by_id[s].critical
            and by_id[s].es >= node.ef - 1e-9
        ]
        current = nxt
    return path


def all_paths(by_id: dict[str, Activity]) -> list[tuple[list[str], float]]:
    """Enumerate every start-to-finish path with its expected duration."""
    starts = [a for a in by_id.values() if not a.preds]
    out: list[tuple[list[str], float]] = []

    def walk(node: Activity, trail: list[str], total: float) -> None:
        trail = trail + [node.ident]
        total = total + node.expected
        succ = [a for a in by_id.values() if node.ident in a.preds]
        if not succ:
            out.append((trail, total))
            return
        for s in succ:
            walk(s, trail, total)

    for s in starts:
        walk(s, [], 0.0)
    return sorted(out, key=lambda p: -p[1])


def build_pert() -> Path:
    """Node network with expected times, the critical path, and a legend."""
    by_id = schedule(ACTIVITIES)
    path = critical_path(by_id)
    total = sum(a.expected for a in path)
    on_path = {a.ident for a in path}

    fig, ax = canvas(
        16,
        10.5,
        "PERT network — expected time per activity and the critical path",
        f"te = (O + 4M + P) / 6 in working days; critical path {'-'.join(a.ident for a in path)} = {total:.2f} days "
        f"({total / DAYS_PER_WEEK:.2f} weeks of a {PLAN_WEEKS:.0f}-week plan)",
    )

    w, h = 17.0, 12.4

    for aid, (x, y) in PERT_POS.items():
        a = by_id[aid]
        critical = aid in on_path
        box(
            ax, x, y, w, h, "",
            face="#fdeceb" if critical else "#f4f6f8",
            edge=PALETTE["critical"] if critical else PALETTE["normal"],
            lw=2.0 if critical else 1.2, radius=1.6, track=False,
        )
        ax.text(x - w / 2 + 1.2, y + h / 2 - 2.2, aid, fontsize=9.2,
                fontweight="bold", ha="left", va="center",
                color=PALETTE["critical"] if critical else PALETTE["ink"], zorder=6)
        t1 = ax.text(x, y + 1.4, wrap(a.name, w - 2.4, 6.6, pad=0.99),
                     ha="center", va="center", fontsize=6.6, linespacing=1.15,
                     color=PALETTE["ink"], zorder=6)
        _track(t1, x - w / 2 + 0.8, y - 0.6, x + w / 2 - 0.8, y + h / 2 - 3.4)
        ax.text(x, y - h / 2 + 2.0,
                f"te={a.expected:.2f}   ES={a.es:.2f}  EF={a.ef:.2f}",
                fontsize=6.4, ha="center", va="center",
                color=PALETTE["critical"] if critical else PALETTE["muted"],
                zorder=6)

    for a in ACTIVITIES:
        sx, sy = PERT_POS[a.ident]
        for p in a.preds:
            px, py = PERT_POS[p]
            critical = a.ident in on_path and p in on_path
            dx = 1.0 if sx > px else -1.0
            p0 = (px + dx * w / 2, py + (0.0 if abs(py - sy) < 1e-9 else
                                         (h / 2 - 2.6) * (1 if sy > py else -1)))
            p1 = (sx - dx * w / 2, sy + (0.0 if abs(py - sy) < 1e-9 else
                                         -(h / 2 - 2.6) * (1 if sy > py else -1)))
            arrow(ax, p0, p1,
                  color=PALETTE["critical"] if critical else PALETTE["normal"],
                  lw=2.3 if critical else 1.2,
                  ls="solid" if critical else (0, (5, 3)))

    # start / finish markers
    ax.plot([3.0, 3.0], [40.0, 88.0], color=PALETTE["grid"], lw=1.0,
            linestyle=(0, (4, 3)))
    ax.text(3.0, 38.0, "start", fontsize=7.4, ha="center", color=PALETTE["muted"],
            style="italic")
    ax.plot([150.0, 150.0], [40.0, 88.0], color=PALETTE["grid"], lw=1.0,
            linestyle=(0, (4, 3)))
    ax.text(150.0, 38.0, f"finish {total:.2f} d", fontsize=7.4, ha="center",
            color=PALETTE["muted"], style="italic")

    # legend
    lx, ly = 4.0, 22.0
    ax.add_patch(
        FancyBboxPatch((lx - 1.0, ly - 12.0), 62.0, 19.0,
                       boxstyle="round,pad=0,rounding_size=1.6",
                       facecolor="#f7f9fb", edgecolor=PALETTE["grid"], linewidth=1.0)
    )
    ax.text(lx, ly + 5.0, "Legend", fontsize=8.2, fontweight="bold",
            color=PALETTE["ink"], zorder=5)
    ax.add_patch(Rectangle((lx, ly + 0.4), 8.0, 3.4, facecolor="#fdeceb",
                           edgecolor=PALETTE["critical"], linewidth=1.8, zorder=4))
    ax.text(lx + 9.4, ly + 2.1, "on the critical path (slack = 0)", fontsize=7.2,
            va="center", color=PALETTE["ink"], zorder=5)
    ax.add_patch(Rectangle((lx, ly - 4.4), 8.0, 3.4, facecolor="#f4f6f8",
                           edgecolor=PALETTE["normal"], linewidth=1.1, zorder=4))
    ax.text(lx + 9.4, ly - 2.7, "has float (slack > 0)", fontsize=7.2,
            va="center", color=PALETTE["ink"], zorder=5)
    ax.plot([lx, lx + 8.0], [ly - 8.0, ly - 8.0], color=PALETTE["critical"],
            lw=2.3, zorder=4)
    ax.text(lx + 9.4, ly - 8.0, "critical-path link", fontsize=7.2, va="center",
            color=PALETTE["ink"], zorder=5)
    ax.text(lx + 30.0, ly + 2.1, "te = (O + 4M + P) / 6", fontsize=7.2,
            va="center", color=PALETTE["ink"], zorder=5)
    ax.text(lx + 30.0, ly - 2.7, "ES, EF in working days from project start",
            fontsize=7.2, va="center", color=PALETTE["ink"], zorder=5)
    ax.text(lx + 30.0, ly - 8.0,
            "slack = LS - ES; variance = ((P - O) / 6)^2", fontsize=7.2,
            va="center", color=PALETTE["ink"], zorder=5)

    audit_overflow(fig, ax, "pert")
    return save(fig, "pert-chart.png")


# --------------------------------------------------------------------------- #
# 6. Gantt chart
# --------------------------------------------------------------------------- #

#: Per CHANGELOG.md every phase is complete as of 2026-11-14.
COMPLETED = {"A", "B", "C", "D", "E", "F", "G", "H", "I", "J"}

MILESTONES = [
    ("M1", "design frozen", "B"),
    ("M2", "rules + parser green", "C"),
    ("M3", "provider layer green", "E"),
    ("M4", "posting + benchmark green", "G"),
    ("M5", "test suite green", "I"),
    ("M6", "report and release", "J"),
]


def build_gantt() -> Path:
    """16-week bars from the PERT schedule, with milestones and completion state."""
    by_id = schedule(ACTIVITIES)
    path = critical_path(by_id)
    on_path = {a.ident for a in path}
    total = sum(a.expected for a in path)

    fig = plt.figure(figsize=(15, 9.6))
    _reset_tracking()
    ax = fig.add_axes([0.235, 0.215, 0.735, 0.635])
    ax.set_xlim(0.0, PLAN_WEEKS)
    rows = [a.ident for a in ACTIVITIES]
    ax.set_ylim(-0.75, len(rows) - 0.30)

    crit_weeks = total / DAYS_PER_WEEK
    ax.add_patch(Rectangle((crit_weeks, -0.75), PLAN_WEEKS - crit_weeks,
                           len(rows) + 0.45, facecolor=PALETTE["buffer"],
                           edgecolor="none", alpha=0.6, zorder=0))
    ax.text((crit_weeks + PLAN_WEEKS) / 2, len(rows) - 0.42,
            f"plan buffer\n{PLAN_WEEKS - crit_weeks:.2f} wk",
            ha="center", va="top", fontsize=7.6, color="#8a6d3b",
            fontweight="bold", linespacing=1.15, zorder=6)

    for week in range(0, int(PLAN_WEEKS) + 1):
        ax.axvline(week, color=PALETTE["grid"], lw=0.8, zorder=1)
    for i in range(len(rows)):
        ax.axhline(i - 0.5, color="#eef1f4", lw=0.7, zorder=1)

    for i, aid in enumerate(rows):
        a = by_id[aid]
        start = a.es / DAYS_PER_WEEK
        end = a.ef / DAYS_PER_WEEK
        critical = aid in on_path
        # planned baseline: the full-height outline
        ax.add_patch(
            Rectangle((start, i - 0.31), end - start, 0.62,
                      facecolor=PALETTE["bar_plan"],
                      edgecolor=PALETTE["critical"] if critical else PALETTE["normal"],
                      linewidth=1.6 if critical else 1.0,
                      linestyle=(0, (3, 2)), zorder=3)
        )
        # completed overlay: the solid inner bar, so both states stay visible
        if aid in COMPLETED:
            ax.add_patch(
                Rectangle((start, i - 0.20), end - start, 0.40,
                          facecolor=PALETTE["bar_done"], edgecolor="none",
                          alpha=0.95, zorder=4)
            )
            ax.text(end + 0.12, i, "\u2713", fontsize=9.0, va="center",
                    ha="left", color=PALETTE["bar_done"], fontweight="bold",
                    zorder=6)

    for label, caption, aid in MILESTONES:
        a = by_id[aid]
        x = a.ef / DAYS_PER_WEEK
        y = rows.index(aid) + 0.50
        ax.plot([x], [y], marker="D", markersize=6.2, color=PALETTE["milestone"],
                markeredgecolor="white", markeredgewidth=1.0, zorder=7)
        ax.annotate(f"{label} {caption}", (x, y), xytext=(0, 6),
                    textcoords="offset points", ha="center", fontsize=6.4,
                    color="#8a6d3b", zorder=7,
                    bbox=dict(boxstyle="round,pad=0.10", fc="white", ec="none",
                              alpha=0.88))

    ax.set_yticks(range(len(rows)))
    labels = [f"{by_id[r].ident}   {by_id[r].name}" for r in rows]
    ax.set_yticklabels(labels, fontsize=7.6)
    for tick, aid in zip(ax.get_yticklabels(), rows):
        if aid in on_path:
            tick.set_color(PALETTE["critical"])
            tick.set_fontweight("bold")
    ax.set_xticks([w + 0.5 for w in range(int(PLAN_WEEKS))])
    ax.set_xticklabels([f"W{w + 1}" for w in range(int(PLAN_WEEKS))], fontsize=7.8)
    ax.set_xlabel("Project week — a bar runs from ES/5 to EF/5 in week units "
                  "(5 working days per week)",
                  fontsize=8.0, color=PALETTE["muted"], labelpad=7)
    ax.tick_params(axis="x", length=0, colors=PALETTE["muted"])
    ax.tick_params(axis="y", length=0)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(PALETTE["grid"])

    fig.text(
        0.5, 0.955,
        "Gantt chart — the 16-week plan, derived from the PERT schedule",
        ha="center", va="center", fontsize=13.5, fontweight="bold",
        color=PALETTE["ink"],
    )
    fig.text(
        0.5, 0.915,
        f"Critical path {'-'.join(a.ident for a in path)} = {total:.2f} working days "
        f"= {crit_weeks:.2f} weeks; weeks {crit_weeks:.2f}-{PLAN_WEEKS:.0f} carry no activity",
        ha="center", va="center", fontsize=8.6, color=PALETTE["muted"],
        style="italic",
    )

    fig.text(
        0.235, 0.145,
        "Every bar is complete: CHANGELOG.md records all six phases delivered on "
        "2026-11-13/14, so the outlined baseline is the plan and the solid inner bar "
        "is the recorded outcome.",
        fontsize=7.6, color=PALETTE["muted"], style="italic",
    )

    handles = [
        Rectangle((0, 0), 1, 1, facecolor=PALETTE["bar_plan"],
                  edgecolor=PALETTE["normal"], linestyle=(0, (3, 2)), linewidth=1.0),
        Rectangle((0, 0), 1, 1, facecolor=PALETTE["bar_plan"],
                  edgecolor=PALETTE["critical"], linestyle=(0, (3, 2)), linewidth=1.6),
        Rectangle((0, 0), 1, 1, facecolor=PALETTE["bar_done"], edgecolor="none"),
        Rectangle((0, 0), 1, 1, facecolor=PALETTE["buffer"], edgecolor="none",
                  alpha=0.6),
        plt.Line2D([], [], marker="D", linestyle="none", markersize=6.2,
                   color=PALETTE["milestone"], markeredgecolor="white"),
    ]
    labels = [
        "Planned baseline (PERT ES to EF)",
        "Planned baseline, on the critical path",
        "Complete per CHANGELOG.md (2026-11-14)",
        "Plan buffer — no activity scheduled",
        "Milestone M1-M6",
    ]
    leg = fig.legend(handles, labels, loc="lower center", ncol=5, frameon=False,
                     fontsize=7.8, bbox_to_anchor=(0.5, 0.045),
                     columnspacing=1.8, handlelength=1.8)
    for txt in leg.get_texts():
        txt.set_color(PALETTE["ink"])

    path_out = OUT_DIR / "gantt-chart.png"
    fig.savefig(path_out, dpi=DPI, facecolor="white", edgecolor="none",
                metadata={"Software": None, "Creation Time": None})
    plt.close(fig)
    print(f"  gantt: {len(rows)} activities, {len(MILESTONES)} milestones")
    return path_out


def aid_on(a: Activity, on_path: set[str]) -> bool:
    """Convenience predicate used by the Gantt loop."""
    return a.ident in on_path


# --------------------------------------------------------------------------- #
# planning.md
# --------------------------------------------------------------------------- #


def _n(value: float, places: int = 2) -> str:
    """Format a number, folding -0.00 into 0.00."""
    if abs(value) < 5e-3:
        value = 0.0
    return f"{value:.{places}f}"


def write_planning(by_id: dict[str, Activity], path: list[Activity]) -> Path:
    """Emit planning.md with the PERT table, the arithmetic and the assumptions."""
    total = sum(a.expected for a in path)
    variance = sum(a.variance for a in path)
    sd = variance ** 0.5
    crit_weeks = total / DAYS_PER_WEEK
    paths = all_paths(by_id)

    lines: list[str] = []
    add = lines.append

    add("# Project planning — PERT, critical path and the 16-week Gantt")
    add("")
    add("This file is generated by `docs/diagrams/make_behavioural.py`. Every number in")
    add("it is computed by that script at run time — the three-point estimates in the")
    add("table below are the only inputs, and the forward pass, backward pass, slack and")
    add("critical path are all derived from them. Re-running the script reproduces this")
    add("file byte for byte.")
    add("")
    add("## 1. Method")
    add("")
    add("Three-point (PERT) estimation over ten activities that match the delivered")
    add("modules: `app/rules.py`, `app/parser.py`, `app/engine.py` +")
    add("`app/openai_compat_provider.py`, `app/main.py`, `app/github_client.py`,")
    add("`benchmarks/`, `tests/` and the documentation pack.")
    add("")
    add("* Expected time: `te = (O + 4M + P) / 6`")
    add("* Variance of one activity: `var = ((P - O) / 6)^2`")
    add("* Forward pass: `ES = max(EF of predecessors)`, `EF = ES + te`")
    add("* Backward pass: `LF = min(LS of successors)`, `LS = LF - te`")
    add("* Total float: `slack = LS - ES`; an activity with zero slack is critical")
    add("* Project duration: `max(EF)` over every activity")
    add("")
    add(f"All times are **working days**, at {DAYS_PER_WEEK:.0f} days per week, which puts")
    add(f"the {PLAN_WEEKS:.0f}-week frame of `docs/learning/PACE.md` at")
    add(f"{PLAN_WEEKS * DAYS_PER_WEEK:.0f} working days.")
    add("")
    add("## 2. PERT table")
    add("")
    add("| ID | Activity | Predecessors | O | M | P | te = (O+4M+P)/6 | Variance | ES | EF | LS | LF | Slack | Critical |")
    add("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |")
    for a in ACTIVITIES:
        preds = ", ".join(a.preds) if a.preds else "—"
        add(
            f"| {a.ident} | {a.name} | {preds} | {a.optimistic:g} | {a.likely:g} | "
            f"{a.pessimistic:g} | {_n(a.expected)} | {_n(a.variance, 3)} | {_n(a.es)} | "
            f"{_n(a.ef)} | {_n(a.ls)} | {_n(a.lf)} | {_n(a.slack)} | "
            f"{'yes' if a.critical else 'no'} |"
        )
    add("")
    add("Standard deviation of each activity, `(P - O) / 6`, is the square root of its")
    add("variance column; the network's standard deviation is the square root of the")
    add("critical path's variance sum (section 4).")
    add("")
    add("## 3. Every path through the network")
    add("")
    add("| Rank | Path | Expected duration (days) | Weeks |")
    add("| ---: | --- | ---: | ---: |")
    for i, (trail, dur) in enumerate(paths, start=1):
        add(f"| {i} | {' - '.join(trail)} | {dur:.2f} | {dur / DAYS_PER_WEEK:.2f} |")
    add("")
    add("## 4. Critical path")
    add("")
    add(f"**Critical path: {' - '.join(a.ident for a in path)}**")
    add("")
    add("| Step | Activity | te (days) | Cumulative (days) | Cumulative (weeks) |")
    add("| ---: | --- | ---: | ---: | ---: |")
    running = 0.0
    for i, a in enumerate(path, start=1):
        running += a.expected
        add(f"| {i} | {a.ident} — {a.name} | {a.expected:.2f} | {running:.2f} | "
            f"{running / DAYS_PER_WEEK:.2f} |")
    add("")
    add(f"* **Total expected duration: {total:.2f} working days** "
        f"(= {total / DAYS_PER_WEEK:.2f} weeks at {DAYS_PER_WEEK:.0f} days per week).")
    add(f"* Sum of critical-path variances: {variance:.3f} day², so the standard "
        f"deviation is **{sd:.2f} days**.")
    add(f"* One standard deviation above the mean: {total + sd:.2f} days "
        f"({(total + sd) / DAYS_PER_WEEK:.2f} weeks).")
    add(f"* The {PLAN_WEEKS:.0f}-week frame holds {PLAN_WEEKS * DAYS_PER_WEEK:.0f} working "
        f"days, so the plan carries **{PLAN_WEEKS * DAYS_PER_WEEK - total:.2f} days "
        f"({(PLAN_WEEKS * DAYS_PER_WEEK - total) / DAYS_PER_WEEK:.2f} weeks) of buffer** "
        f"beyond the critical path.")
    add(f"* Activities with float: "
        f"{', '.join(f'{a.ident} ({a.slack:.2f} d)' for a in ACTIVITIES if not a.critical)}.")
    add("")
    add(f"`E` (provider layer) is the longest single activity at {_n(by_id['E'].expected)}")
    add("days and it is on the critical path, which is why")
    add("`docs/learning/PACE.md` protects weeks 5-7 and 11-12 from compression. `F`")
    add(f"(API surface) has {by_id['F'].slack:.2f} days of float because `G` waits on `E`,")
    add(f"and `D` (parser) has {by_id['D'].slack:.2f} days because `C` is the longer of the two")
    add("branches out of `B`.")
    add("")
    add("## 5. Gantt assumptions")
    add("")
    add("* The chart spans 16 weeks, the frame set by `docs/learning/PACE.md`.")
    add(f"* One week is {DAYS_PER_WEEK:.0f} working days; a bar runs from `ES / 5` to")
    add("  `EF / 5` in week units, so a bar's right edge is the activity's earliest")
    add("  finish, not a calendar date.")
    add("* Activities are drawn in the order of the table, which is a topological order,")
    add("  so a successor never appears above its predecessor's start.")
    add("* Bars on the critical path are outlined in red; bars with float are outlined")
    add("  grey. The shaded band from the critical-path finish to week 16 is plan buffer")
    add("  and carries no activity — `PACE.md` keeps week 8 empty on purpose, and this")
    add("  chart shows the same idea as one contiguous tail.")
    add("* Milestones M1-M6 sit at the earliest finish of the activity that closes them:")
    add("  M1 design frozen (B), M2 rules and parser green (C), M3 provider layer green")
    add("  (E), M4 posting and benchmark green (G), M5 test suite green (I), M6 report")
    add("  and release (J).")
    add("* Completion state: the solid fill marks an activity that `CHANGELOG.md`")
    add("  records as delivered. Every activity carries it, because the changelog records")
    add("  all six phases complete on 2026-11-13/14 — the build ran as one continuous")
    add("  session, far inside the 16-week frame. Requirements (A) and design (B) are not")
    add("  logged as separate phases in the changelog; they are shown complete because")
    add("  Phase 1 could not have been built without them.")
    add("")
    add("## 6. Plan versus record")
    add("")
    add("The 16-week schedule in this file and in `gantt-chart.png` is **a plan, not a")
    add("record of what happened**. It states how long each activity was expected to")
    add("take, which activities could slip without moving the end date, and where the")
    add("buffer sits. Actual completion is recorded in `CHANGELOG.md`, which is the only")
    add("authority on what was delivered and when: it logs the six phases, the test count")
    add("at the end of each, and the dates. Where the two disagree, the changelog wins —")
    add("the plan is the estimate made before the work, and the estimates above were")
    add("written to describe the shape of the work, not to match a stopwatch. The")
    add("schedule should therefore be read as a statement about dependency and float,")
    add("and the changelog as the statement about outcome.")
    add("")
    add("## 7. What each figure is drawn from")
    add("")
    add("| Figure | File | Grounded in |")
    add("| --- | --- | --- |")
    add("| `use-case-diagram.png` | `docs/diagrams/use-case-diagram.png` | `app/main.py` endpoints, `app/cli.py` surfaces, `app/engine.py` provider choice, `ARCHITECTURE.md` §2-§5 |")
    add("| `activity-diagram.png` | `docs/diagrams/activity-diagram.png` | `app/main.py` (`_verify_signature`, the 422/401/200-ignored paths, `_build_response`, `_persist_review`, `_publish_review`), `app/parser.py`, `app/engine.py` `select_provider`, `app/openai_compat_provider.py` `review_diff_live` repair retry, `app/db.py` `store_review` and `store_pr_post`, `app/github_client.py` `post_review` |")
    add("| `sequence-diagram.png` | `docs/diagrams/sequence-diagram.png` | `app/engine.py` `review()`, `app/openai_compat_provider.py` `review_with_fallback`, `app/mock_provider.py`, `app/parser.py` `anchor_findings`, `app/github_client.py` `post_review` |")
    add("| `state-diagram.png` | `docs/diagrams/state-diagram.png` | `app/github_client.py` `_publish` and `post_review` (marker check, 422 demotion, 429 retry, typed errors) |")
    add("| `pert-chart.png` | `docs/diagrams/pert-chart.png` | the estimates in section 2 of this file |")
    add("| `gantt-chart.png` | `docs/diagrams/gantt-chart.png` | the ES/EF columns of section 2, plus `CHANGELOG.md` for the completion state |")
    add("")
    add("Two honesty notes on the figures:")
    add("")
    add("1. **Reviews are persisted.** Every surface — `/review`, `/test-review` and")
    add("   `/webhook` — funnels through `_build_response` in `app/main.py`, which calls")
    add("   `_persist_review` and therefore `Database.store_review` in `app/db.py`: the")
    add("   SQLite store whose DDL is `SCHEMA_SQL`, six tables, drawn as Figure 4.")
    add("   Storage is best-effort by design: `_persist_review` and `_persist_pr_post`")
    add("   swallow every failure, log once at WARNING on `reviewer.db`, and leave the")
    add("   response exactly as it would have been; a blank `DATABASE_PATH` switches")
    add("   history off entirely. The `Review store` lifeline in the sequence diagram is")
    add("   that store, and a posting outcome is stored separately by")
    add("   `Database.store_pr_post`.")
    add("2. The webhook always answers GitHub with HTTP 200, even when the post failed —")
    add("   the locked Phase 5 decision, stated in the `app/main.py` module docstring.")
    add("   The state diagram therefore has `Failed` as a terminal *posting* state, not")
    add("   as an HTTP error.")
    add("")

    out = OUT_DIR / "planning.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def main() -> None:
    """Build all six figures and planning.md, then print a checksum table."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    produced: list[Path] = []
    for builder in (build_use_case, build_activity, build_sequence, build_state,
                    build_pert, build_gantt):
        produced.append(builder())

    by_id = schedule(ACTIVITIES)
    path = critical_path(by_id)
    produced.append(write_planning(by_id, path))

    print("")
    print(f"{'file':<26}{'bytes':>9}  md5")
    for p in produced:
        digest = hashlib.md5(p.read_bytes()).hexdigest()
        print(f"{p.name:<26}{p.stat().st_size:>9}  {digest}")

    total = sum(a.expected for a in path)
    print("")
    print(f"critical path: {' - '.join(a.ident for a in path)}")
    print(f"duration:      {total:.2f} working days = {total / DAYS_PER_WEEK:.2f} weeks")


if __name__ == "__main__":
    main()
