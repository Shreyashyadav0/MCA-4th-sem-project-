"""Offline benchmark harness for the AI code reviewer.

Nothing in this package imports ``app.main`` or ``app.cli``: the harness measures
the review engine, not the HTTP surface. Labels under ``benchmarks/golden`` are
human-authored; the harness never generates or auto-labels them.
"""

__all__: list[str] = []
