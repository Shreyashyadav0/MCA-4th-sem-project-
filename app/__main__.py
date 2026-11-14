"""Allow ``python -m app <file>`` as an alias for ``python reviewer.py <file>``."""

from __future__ import annotations

from app.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
