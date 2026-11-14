"""Guards for the generated ER figure: it must not drift from ``SCHEMA_SQL``.

``docs/diagrams/make_diagrams.py`` draws ``er-diagram.png`` from the column list it
reads out of :data:`app.db.SCHEMA_SQL`. Nothing in the build enforces that: a column
whose definition wraps onto a second line, or one written with a lower-case type, is
simply not drawn, and the figure then contradicts the database the service creates.

Three assertions close that hole, and they fail at different points on purpose:

1. :func:`test_er_columns_match_a_freshly_created_database` compares the generator's
   column list with ``PRAGMA table_info`` on a database built by the real
   ``Database.init_schema()``. This is the assertion that catches a parser that has
   stopped understanding the DDL. It needs no matplotlib, so it runs in CI, which
   installs only ``requirements.lock``.
2. :func:`test_er_figure_content_is_pinned` pins the exact text the figure will carry
   in :data:`ER_COLUMNS_SHA256`. Any schema edit that changes the figure — a new
   column, a new ``UNIQUE``, a widened type — changes this digest and fails here even
   if nobody regenerated the PNG.
3. :func:`test_er_png_is_newer_than_the_schema_or_regenerates_identically` compares the
   committed PNG with ``app/db.py``: a PNG older than the DDL must either be stale
   documentation or must regenerate byte-for-byte identically. Regenerating needs
   matplotlib, so this one is skipped where matplotlib is absent — by then assertion
   2 has already covered the content.

When a schema change is deliberate: re-run ``python docs/diagrams/make_diagrams.py``,
confirm the figure, and update :data:`ER_COLUMNS_SHA256` in the same commit.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent
DIAGRAMS = ROOT / "docs" / "diagrams"
GENERATOR = DIAGRAMS / "make_diagrams.py"
ER_PNG = DIAGRAMS / "er-diagram.png"
DB_SOURCE = ROOT / "app" / "db.py"

#: The six tables the report prescribes, in the order the DDL declares them.
EXPECTED_TABLES = ("roles", "users", "reviews", "findings", "pr_posts", "benchmark_runs")

#: sha256 of ``json.dumps(_er_columns(), sort_keys=True)``. Regenerate the figure and
#: update this value whenever the schema changes on purpose.
ER_COLUMNS_SHA256 = "3b9d52c09faa2d3e63524350eb454013e1c009e66762e5dda1bdf2d05e79e362"


@pytest.fixture(scope="module")
def generator() -> ModuleType:
    """Load ``docs/diagrams/make_diagrams.py`` as a module, matplotlib or not.

    The module guards its matplotlib import, so this works on a machine that can
    only read the schema. ``sys.modules`` is populated before execution because the
    module defines dataclasses, which look themselves up by module name.

    Returns:
        The imported generator module.
    """
    name = "make_diagrams_under_test"
    spec = importlib.util.spec_from_file_location(name, GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec.loader.exec_module(module)
    return module


def _column_names(lines: list[str]) -> list[str]:
    """Read the column names back out of the display lines the figure draws.

    Args:
        lines: One display line per column, as ``_er_columns()`` returns them.

    Returns:
        The column name of each line, in order — the first whitespace-separated
        token, which is exactly what a reader of the PNG sees.
    """
    return [line.split()[0] for line in lines]


def _digest(payload: dict[str, list[str]]) -> str:
    """Stable sha256 of the figure's content.

    Args:
        payload: The mapping ``_er_columns()`` returns.

    Returns:
        The hex digest of its canonical JSON form.
    """
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _pragma_columns(path: Path, table: str) -> list[str]:
    """Column names of ``table``, straight from SQLite.

    Args:
        path: The database file.
        table: Table name.

    Returns:
        Column names in ``cid`` order.
    """
    with sqlite3.connect(path) as connection:
        rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    return [row[1] for row in rows]


def test_er_columns_match_a_freshly_created_database(
    generator: ModuleType, tmp_path: Path
) -> None:
    """The drawn columns must be the columns ``init_schema()`` actually creates."""
    from app.db import Database

    drawn = generator._er_columns()

    assert tuple(drawn) == EXPECTED_TABLES, (
        "the ER figure must show exactly the six prescribed tables; "
        f"the generator returned {tuple(drawn)!r}"
    )

    database = Database(tmp_path / "er.db")
    database.init_schema()
    database.close()

    with sqlite3.connect(tmp_path / "er.db") as connection:
        created = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
    assert sorted(created) == sorted(EXPECTED_TABLES), (
        f"SCHEMA_SQL created {sorted(created)!r}, not the six prescribed tables"
    )

    for table in EXPECTED_TABLES:
        expected = _pragma_columns(tmp_path / "er.db", table)
        actual = _column_names(drawn[table])
        assert actual == expected, (
            f"the ER figure's {table} box is out of step with SCHEMA_SQL: "
            f"drawn {actual!r}, created {expected!r}. "
            "docs/diagrams/make_diagrams.py::_parse_schema_columns is dropping or "
            "inventing a column."
        )
        assert all(actual), f"{table} has a blank column line in the figure"


def test_er_figure_content_is_pinned(generator: ModuleType) -> None:
    """Any change to what the figure draws changes the pinned digest."""
    drawn = generator._er_columns()
    digest = _digest(drawn)

    assert digest == ER_COLUMNS_SHA256, (
        "the ER figure no longer matches the pinned schema content.\n"
        f"  expected sha256 {ER_COLUMNS_SHA256}\n"
        f"  actual   sha256 {digest}\n"
        "If the schema change is intended, run "
        "`python docs/diagrams/make_diagrams.py`, check the figure, and update "
        "ER_COLUMNS_SHA256 in tests/test_diagram_generator.py."
    )


def test_er_png_is_newer_than_the_schema_or_regenerates_identically(
    generator: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A PNG older than the DDL must be a stale-looking but identical figure."""
    assert ER_PNG.is_file(), f"the ER figure is missing: {ER_PNG.name}"

    png_mtime = ER_PNG.stat().st_mtime
    schema_mtime = DB_SOURCE.stat().st_mtime

    if png_mtime >= schema_mtime:
        return  # the figure is at least as new as the schema it is drawn from

    # A fresh git checkout stamps every file with the checkout time, so mtimes carry no
    # ordering information in CI or in any other clone. Only trust them when the gap is
    # large enough to be a real edit rather than the same checkout.
    if abs(schema_mtime - png_mtime) < 5.0:
        pytest.skip(
            "file mtimes are within five seconds of each other, which is what a fresh "
            "checkout looks like; the pinned digest still guards the figure's content"
        )

    pytest.importorskip(
        "matplotlib",
        reason="regenerating the figure needs matplotlib; the pinned digest still "
        "guards its content",
    )

    monkeypatch.setattr(generator, "HERE", tmp_path)
    regenerated = generator.er_diagram()

    assert regenerated.parent == tmp_path, "the generator wrote outside the temp dir"
    assert regenerated.stat().st_size > 20_000, "the regenerated figure is empty"

    on_disk = hashlib.sha256(ER_PNG.read_bytes()).hexdigest()
    fresh = hashlib.sha256(regenerated.read_bytes()).hexdigest()
    assert fresh == on_disk, (
        "app/db.py is newer than er-diagram.png and regenerating the figure produces "
        "a different image, so the committed PNG is out of date.\n"
        f"  committed  {on_disk}\n"
        f"  regenerated {fresh}\n"
        "Run `python docs/diagrams/make_diagrams.py` and commit the new PNG."
    )
