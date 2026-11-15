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

    for path in sorted(SITE.glob("content/part-*/lesson-*.js")):
        text = path.read_text(encoding="utf-8")
        i = text.rindex("window.LESSONS.push(") + len("window.LESSONS.push(")
        lesson = json.loads(text[i:].rstrip()[:-2].rstrip())
        for n, q in enumerate(lesson["quiz"]):
            total += 1
            spread[q["answer"]] += 1
            lens = [len(o) for o in q["options"]]
            key = lens[q["answer"]]
            others = [l for j, l in enumerate(lens) if j != q["answer"]]
            if key > max(others):
                longest += 1
                offenders.append("%s q%d: key %d, next %d (+%d)" % (
                    lesson["id"], n, key, max(others), key - max(others)))
            if max(lens) - min(lens) <= 3:
                clustered += 1
                offenders.append("%s q%d: all four within %d chars" % (
                    lesson["id"], n, max(lens) - min(lens)))

    print("\n".join(offenders[:20]))
    print("\nquestions: %d | key is unique longest: %d | all four within 3 chars: %d"
          % (total, longest, clustered))
    print("answer index spread: %s" % spread)
    return 0 if not longest and not clustered else 1


if __name__ == "__main__":
    raise SystemExit(main())
