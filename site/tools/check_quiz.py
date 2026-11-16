#!/usr/bin/env python3
"""Report quiz questions whose shape gives the answer away.

Two defects, both measurable:
  * the correct option is the unique longest string;
  * all four options are within 3 characters of each other, so length says
    nothing and the question is a coin toss between four equal-length claims.

    python site/tools/check_quiz.py
"""

from __future__ import annotations

import json
import pathlib
import sys

SITE = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    total = longest = clustered = 0
    spread = {0: 0, 1: 0, 2: 0, 3: 0}
    offenders: list[str] = []
    worklist: list[tuple] = []
    # A site-wide spread can look healthy while one part puts every key at the
    # same index: Part 10 shipped 30 of 30 at index 0 that way. Count per part.
    per_part: dict[int, dict[int, int]] = {}

    for path in sorted(SITE.glob("content/part-*/lesson-*.js")):
        text = path.read_text(encoding="utf-8")
        i = text.rindex("window.LESSONS.push(") + len("window.LESSONS.push(")
        lesson = json.loads(text[i:].rstrip()[:-2].rstrip())
        part_no = int(lesson["id"].split(".")[0])
        part_spread = per_part.setdefault(part_no, {0: 0, 1: 0, 2: 0, 3: 0})
        for n, q in enumerate(lesson["quiz"]):
            total += 1
            spread[q["answer"]] += 1
            part_spread[q["answer"]] += 1
            lens = [len(o) for o in q["options"]]
            key = lens[q["answer"]]
            others = [l for j, l in enumerate(lens) if j != q["answer"]]
            if key > max(others):
                longest += 1
                offenders.append("%s q%d: key %d, next %d (+%d)" % (
                    lesson["id"], n, key, max(others), key - max(others)))
                worklist.append((lesson["id"], n, key, max(others), key - max(others),
                                 q["options"][q["answer"]][:44]))
            if max(lens) - min(lens) <= 3:
                clustered += 1
                offenders.append("%s q%d: all four within %d chars" % (
                    lesson["id"], n, max(lens) - min(lens)))

    if longest or clustered:
        print("id      q  key  max  gap   the key")
        print("-" * 72)
        for line in sorted(worklist, key=lambda r: -r[4]):
            print("%-6s %2d %4d %4d %4d   %s" % line)

    print("\nquestions: %d | key is unique longest: %d | all four within 3 chars: %d"
          % (total, longest, clustered))
    print("answer index spread: %s" % spread)

    # One index holding more than half a part's keys, in a part with five or more
    # questions, is a positional tell the site-wide figure hides.
    skewed: list[str] = []
    for part_no in sorted(per_part):
        counts = per_part[part_no]
        n_q = sum(counts.values())
        if n_q < 5:
            continue
        idx, hits = max(counts.items(), key=lambda kv: kv[1])
        if hits * 2 > n_q:
            skewed.append("part %d: index %d holds %d of %d keys (%.0f%%)"
                          % (part_no, idx, hits, n_q, 100.0 * hits / n_q))
    if skewed:
        print("\nper-part spread is skewed:")
        for line in skewed:
            print("  " + line)
    if worklist:
        gaps = [r[4] for r in worklist]
        print("gap: median %.1f, mean %.1f, max %d, <=8: %d, >8: %d"
              % (sorted(gaps)[len(gaps) // 2], sum(gaps) / len(gaps), max(gaps),
                 sum(1 for g in gaps if g <= 8), sum(1 for g in gaps if g > 8)))
    return 0 if not longest and not clustered and not skewed else 1


if __name__ == "__main__":
    raise SystemExit(main())
