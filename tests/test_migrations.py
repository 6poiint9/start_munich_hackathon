import pathlib

from lineguard import clock
from lineguard import db

MIGRATIONS = pathlib.Path(db.__file__).parent / "migrations"


def test_empty_database_gets_highest_version(conn):
    highest = max(int(f.stem.split("_")[0]) for f in MIGRATIONS.glob("[0-9]*.py"))
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    assert row["v"] == highest


def test_second_run_changes_nothing(conn):
    before = conn.execute("SELECT * FROM schema_version").fetchall()
    assert db.migrate(conn) == before[-1]["version"]
    assert conn.execute("SELECT * FROM schema_version").fetchall() == before


def test_every_table_has_workspace_id(conn):
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT IN ('schema_version') AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    assert len(tables) >= 20
    for table in tables:
        columns = [c["name"] for c in conn.execute(f"PRAGMA table_info({table['name']})")]
        assert "workspace_id" in columns, table["name"]


def test_clock_can_be_fixed(monkeypatch):
    monkeypatch.setenv(clock.NOW_ENV, "2026-11-21T13:00:00+01:00")
    assert clock.iso() == "2026-11-21T12:00:00Z"
    monkeypatch.delenv(clock.NOW_ENV)
    assert clock.now().tzinfo is not None
