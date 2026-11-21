"""Database access: connection, migrations, the event queue and helpers.

Agents reach the database only through this module. Every function takes
the workspace as an argument, so two customers in one database never meet
(docs/skalierung.md N3). `claim_next` is the only code that moves an event to
'processing' (docs/skalierung.md N2).
"""

from collections.abc import Iterable, Mapping, Sequence
import datetime
import importlib
import json
import pathlib
import sqlite3
from typing import Any

from lineguard import clock
from lineguard import config

LOG_ONLY_EVENTS = frozenset({
    "option.created", "decision.created", "decision.escalated",
    "decision.approved", "gap.unclosable", "finding.created",
    "correction.proposed", "correction.verified", "action.created",
    "email.drafted", "email.sent", "email.received",
})
_MIGRATIONS_DIR = pathlib.Path(__file__).parent / "migrations"
_SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL
)"""


def database_path(workspace: str) -> pathlib.Path:
    """Resolves DATABASE_URL, or the default file of the workspace."""
    url = config.get("DATABASE_URL")
    if not url:
        return config.data_dir(workspace) / "lineguard.sqlite"
    if not url.startswith("sqlite:///"):
        raise ValueError(
            f"DATABASE_URL '{url}' is not supported yet. Use sqlite:///path."
        )
    return pathlib.Path(url.removeprefix("sqlite:///"))


def connect(workspace: str, path: pathlib.Path | None = None) -> sqlite3.Connection:
    """Opens the database of a workspace and applies missing migrations."""
    path = path or database_path(workspace)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(path), isolation_level=None, check_same_thread=False, timeout=5.0
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    """Applies every migration file above the stored version, in order.

    Returns:
        The highest applied version.
    """
    conn.execute(_SCHEMA_VERSION_TABLE)
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    current = row["v"] or 0
    for file in sorted(_MIGRATIONS_DIR.glob("[0-9]*.py")):
        version = int(file.stem.split("_")[0])
        if version <= current:
            continue
        module = importlib.import_module(f"lineguard.migrations.{file.stem}")
        module.up(conn)
        conn.execute(
            "INSERT INTO schema_version (version, name, applied_at) "
            "VALUES (?, ?, ?)",
            (version, file.stem, clock.iso()),
        )
        current = version
    return current


# ---------- generic helpers ----------


def insert(conn: sqlite3.Connection, table: str, ws: str, **columns: Any) -> int:
    """Inserts one row and returns its id."""
    columns = {"workspace_id": ws, **columns}
    names = ", ".join(columns)
    marks = ", ".join("?" for _ in columns)
    cursor = conn.execute(
        f"INSERT INTO {table} ({names}) VALUES ({marks})",
        [_to_db(value) for value in columns.values()],
    )
    return int(cursor.lastrowid or 0)


def update(conn: sqlite3.Connection, table: str, ws: str, row_id: int, **columns: Any) -> None:
    """Updates columns of one row by id."""
    assignments = ", ".join(f"{name} = ?" for name in columns)
    conn.execute(
        f"UPDATE {table} SET {assignments} WHERE workspace_id = ? AND id = ?",
        [*(_to_db(value) for value in columns.values()), ws, row_id],
    )


def rows(conn: sqlite3.Connection, ws: str, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    """Runs a SELECT that filters on the workspace.

    The statement must contain `workspace_id = ?` as its first placeholder.
    """
    if "workspace_id = ?" not in sql:
        raise ValueError("Every query must filter on workspace_id = ?")
    return [dict(row) for row in conn.execute(sql, [ws, *params])]


def one(conn: sqlite3.Connection, ws: str, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
    found = rows(conn, ws, sql, params)
    return found[0] if found else None


def _to_db(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, datetime.datetime):
        return clock.iso(value)
    return value


def loads(value: str | None, default: Any = None) -> Any:
    """Parses a JSON column."""
    return json.loads(value) if value else default


# ---------- event queue ----------


def emit(
    conn: sqlite3.Connection,
    ws: str,
    event_type: str,
    payload: Mapping[str, Any] | None = None,
    *,
    priority: int = 2,
    dedupe_key: str | None = None,
    coalesce_key: str | None = None,
    partition_key: str | None = None,
) -> int | None:
    """Adds an event. Returns None when a key says the event exists already.

    `dedupe_key` is unique forever. `coalesce_key` is unique among pending
    events only, so ten new facts for one part cause one recalculation.
    """
    now = clock.iso()
    # An event without a handler is a log entry. It is stored as done, so
    # it never counts as waiting work.
    status = "done" if event_type in LOG_ONLY_EVENTS else "pending"
    try:
        return insert(
            conn, "events", ws,
            type=event_type, priority=priority, payload=dict(payload or {}),
            dedupe_key=dedupe_key, coalesce_key=coalesce_key,
            partition_key=partition_key, available_at=now, created_at=now,
            status=status,
        )
    except sqlite3.IntegrityError:
        return None


def claim_next(
    conn: sqlite3.Connection,
    ws: str,
    worker_id: str,
    types: Iterable[str],
    lease_seconds: int | None = None,
    max_priority: int | None = None,
) -> dict[str, Any] | None:
    """Takes the next pending event for a worker, or returns None.

    An event with an expired lease becomes pending again first. Two events
    with the same partition_key never run at the same time.
    """
    types = list(types)
    if not types:
        return None
    lease = lease_seconds or config.get_int("LEASE_SECONDS", 300)
    now = clock.now()
    now_text = clock.iso(now)
    until = clock.iso(now + datetime.timedelta(seconds=lease))
    marks = ", ".join("?" for _ in types)
    conn.execute(
        "UPDATE events SET status = 'pending', locked_by = NULL "
        "WHERE workspace_id = ? AND status = 'processing' AND locked_until < ?",
        (ws, now_text),
    )
    row = conn.execute(
        f"""
        UPDATE events SET status = 'processing', locked_by = ?,
               locked_until = ?, attempts = attempts + 1
        WHERE id = (
            SELECT id FROM events
            WHERE workspace_id = ? AND status = 'pending'
              AND available_at <= ? AND type IN ({marks})
              AND priority <= ?
              AND (partition_key IS NULL OR partition_key NOT IN (
                   SELECT partition_key FROM events
                   WHERE workspace_id = ? AND status = 'processing'
                     AND partition_key IS NOT NULL))
            ORDER BY priority, id LIMIT 1)
        RETURNING *
        """,
        (worker_id, until, ws, now_text, *types, max_priority or 9, ws),
    ).fetchone()
    if row is None:
        return None
    event = dict(row)
    event["payload"] = loads(event["payload"], {})
    return event


def finish(conn: sqlite3.Connection, ws: str, event: Mapping[str, Any], handler: str, error: str | None = None) -> None:
    """Marks an event done, or schedules a retry after a failure.

    After three failed attempts the event stays 'failed' and shows up in the
    problem list of the page (architecture.md §6.2).
    """
    if error is None:
        update(conn, "events", ws, event["id"], status="done",
               handled_by=handler, finished_at=clock.iso(), locked_by=None)
        return
    attempts = int(event.get("attempts") or 1)
    if attempts >= 3:
        update(conn, "events", ws, event["id"], status="failed",
               handled_by=handler, error=error, locked_by=None)
        return
    retry_at = clock.now() + datetime.timedelta(minutes=2**attempts)
    update(conn, "events", ws, event["id"], status="pending",
           available_at=clock.iso(retry_at), error=error, locked_by=None)
