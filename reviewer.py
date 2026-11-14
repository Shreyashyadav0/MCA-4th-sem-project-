#!/usr/bin/env python3
"""Phase 1 entry point: ``python reviewer.py <file> [--offline] [--json]``.

All logic lives in the ``app`` package; this file only anchors the CLI at the
project root so the command in the README is the one people type.
"""

from __future__ import annotations

from app.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
