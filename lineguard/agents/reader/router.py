"""Reader: turns one file into facts with evidence.

The route of the pack chooses the parser. Tables need no LLM (wave 1).
Documents and scans go to the document reader (wave 2).
"""

import logging
from typing import Any

from lineguard import db
from lineguard import runtime
from lineguard.agents.reader import documents
from lineguard.agents.reader import kinds
from lineguard.agents.reader import notify
from lineguard.agents.reader import tables

logger = logging.getLogger(__name__)


def handle_file(rt: runtime.Runtime, event: dict[str, Any]) -> None:
    """Handles `file.added` and `file.changed`."""
    file = db.one(
        rt.conn, rt.ws,
        "SELECT * FROM files WHERE workspace_id = ? AND id = ?",
        (event["payload"]["file_id"],))
    if file is None or not file["is_current"]:
        return
    route = rt.pack.route_for(file["path"])
    ctx = kinds.Context(conn=rt.conn, ws=rt.ws, pack=rt.pack, file=file,
                        rank=rt.pack.rank_of(route.doc_class))
    try:
        if route.parser in ("table", "report", "json"):
            _read_tables(rt, route, file, ctx)
        elif not documents.read(rt, route, file, ctx):
            return
    except tables.TableError as error:
        db.update(rt.conn, "files", rt.ws, file["id"], parse_status="failed",
                  parse_error=str(error))
        logger.warning("File %s failed: %s", file["path"], error)
        return
    db.update(rt.conn, "files", rt.ws, file["id"], parse_status="parsed",
              parse_error=None)
    notify.facts_updated(rt, ctx.touched)
    if route.parser in ("table", "report", "json") and _has_notes(rt, file["id"]):
        db.emit(rt.conn, rt.ws, "notes.read", {"file_id": file["id"]},
                priority=3, dedupe_key=f"notes.read:{file['id']}",
                partition_key=f"file:{file['path']}")


def _read_tables(rt: runtime.Runtime, route, file: dict[str, Any], ctx: kinds.Context) -> None:
    data = rt.blob.get(file["blob_key"])
    rt.conn.execute("BEGIN IMMEDIATE")
    try:
        if route.parser == "table":
            kinds.write(ctx, route.kind or "", tables.load_table(route, file["path"], data))
        elif route.parser == "json":
            rows, as_of = tables.load_json(route, file["path"], data)
            ctx.as_of = as_of
            kinds.write(ctx, route.kind or "", rows)
        else:
            found = tables.load_report(route, rt.pack, file["path"], data)
            if not found:
                raise tables.TableError("No table of the route found in the report")
            for spec, as_of, sheet, rows in found:
                ctx.as_of = as_of
                ctx.locator = f"sheet {sheet}, "
                kinds.write(ctx, spec.kind, rows)
    except Exception:
        rt.conn.execute("ROLLBACK")
        raise
    rt.conn.execute("COMMIT")


def _has_notes(rt: runtime.Runtime, file_id: int) -> bool:
    row = db.one(rt.conn, rt.ws,
                 "SELECT COUNT(*) AS n FROM facts WHERE workspace_id = ? "
                 "AND fact_type = 'note' AND source_file_id = ?", (file_id,))
    return bool(row and row["n"])
