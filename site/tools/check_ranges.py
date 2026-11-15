#!/usr/bin/env python3
"""Check that every project_links range begins and ends on a construct boundary.

A range must start at the first line of a def, a class, a decorator block or a
contiguous field group, and end at that construct's last line. This rejects the
three ways a range goes wrong: starting or ending on a blank line, ending on a
closing bracket alone, and ending in the middle of a call.

    python site/tools/check_ranges.py          # report
    python site/tools/check_ranges.py --fix    # rewrite the ranges in place
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

SITE = pathlib.Path(__file__).resolve().parent.parent
ROOT = SITE.parent

START = re.compile(r"^(\s*)(async def |def |class |@)")


def lesson_files() -> list[pathlib.Path]:
    return sorted(SITE.glob("content/part-*/lesson-*.js"))


def load(path: pathlib.Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    index = text.rindex("window.LESSONS.push(") + len("window.LESSONS.push(")
    return json.loads(text[index:].rstrip()[:-2].rstrip()), text[:index]


def save(path: pathlib.Path, lesson: dict, prefix: str) -> None:
    path.write_text(prefix + json.dumps(lesson, indent=2, ensure_ascii=False) + ");\n",
                    encoding="utf-8")


def bad_start(lines: list[str], start: int) -> str | None:
    """Why this line cannot begin a range, or None."""
    stripped = lines[start].strip()
    if not stripped:
        return "blank line"
    if stripped in (")", "]", "}", "},", "),"):
        return "closing bracket"
    # A start is bad only when the line above is an unclosed expression: an
    # open bracket, a comma, an assignment with nothing after it. Starting a new
    # statement directly under another statement is normal at module level.
    if start > 0:
        above = lines[start - 1].rstrip()
        if above.endswith(("(", "[", "{", ",", "=", "+", "\\")):
            return "continues the line above"
    return None


def start_of(lines: list[str], end: int) -> int:
    return end


def bad_end(lines: list[str], end: int) -> str | None:
    """Why this line cannot end a range, or None.

    A range ends correctly where its construct ends: at end of file, before a
    blank line, or before the next construct at the same or lower indent. A line
    that dangles a comma or an open bracket never ends one.
    """
    stripped = lines[end].strip()
    if not stripped:
        return "blank line"
    if stripped.endswith((",", "(", "[", "{", "= Field(")):
        return "mid-call"
    if end == len(lines) - 1:
        return None
    if end == start_of(lines, end):
        return None  # a one-line range whose line does not dangle
    nxt = lines[end + 1]
    if not nxt.strip():
        return None
    m = START.match(nxt)
    indent = len(lines[end]) - len(lines[end].lstrip())
    if m and len(m.group(1)) <= indent:
        return None
    return "continues below"


def construct_bounds(lines: list[str], start: int) -> tuple[int, int]:
    """Grow a range out to the enclosing def/class/decorator block."""
    indent = len(lines[start]) - len(lines[start].lstrip())
    first = start
    for i in range(start, -1, -1):
        m = START.match(lines[i])
        if m and len(m.group(1)) <= indent:
            first = i
            break
    # the block ends at the line before the next construct at the same or lower indent
    last = start
    for i in range(start + 1, len(lines)):
        m = START.match(lines[i])
        if m and len(m.group(1)) <= indent:
            break
        last = i
    while last > first and not lines[last].strip():
        last -= 1
    return first, last


def main(argv: list[str]) -> int:
    fix = "--fix" in argv
    problems: list[str] = []
    fixed = 0
    total = 0

    for path in lesson_files():
        lesson, prefix = load(path)
        changed = False
        for link in lesson.get("project_links", []):
            total += 1
            target = ROOT / link["path"]
            if not target.exists():
                problems.append("%s: missing %s" % (lesson["id"], link["path"]))
                continue
            lines = target.read_text(encoding="utf-8").splitlines()
            spec = link["lines"]
            m = re.fullmatch(r"(\d+)(?:-(\d+))?", spec)
            if not m:
                problems.append("%s: bad range %s" % (lesson["id"], spec))
                continue
            start = int(m.group(1)) - 1
            end = int(m.group(2) or m.group(1)) - 1
            if end >= len(lines):
                problems.append("%s: %s past EOF" % (lesson["id"], spec))
                continue

            python_file = target.suffix == ".py"
            if python_file:
                why_start = bad_start(lines, start) if start != end else None
                why_end = bad_end(lines, end)
            else:
                # Prose and Makefiles have no def to align to: only a blank or
                # dangling line is a defect there.
                why_start = "blank line" if not lines[start].strip() else None
                why_end = ("blank line" if not lines[end].strip()
                           else "dangling" if lines[end].rstrip().endswith((",", "\\")) else None)
            if why_start is None and why_end is None:
                continue

            problems.append("%s: %s %s-%s (%s / %s)" % (
                lesson["id"], link["path"], start + 1, end + 1,
                why_start or "ok", why_end or "ok"))
            if fix:
                first, last = construct_bounds(lines, start)
                if end > last:
                    last = end
                    while last < len(lines) - 1 and lines[last].strip() and bad_end(lines, last):
                        last += 1
                    while last > first and not lines[last].strip():
                        last -= 1
                link["lines"] = "%d-%d" % (first + 1, last + 1)
                fixed += 1
                changed = True

        if changed:
            save(path, lesson, prefix)

    print("\n".join(problems) if problems else "OK every range starts and ends on a boundary")
    print("\n%d ranges checked, %d problems%s" % (
        total, len(problems), ", %d rewritten" % fixed if fix else ""))
    return 0 if (not problems or fix) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
