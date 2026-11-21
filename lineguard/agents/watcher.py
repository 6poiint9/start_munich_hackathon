"""Watcher: finds new, replaced and removed files in the source.

No LLM. Every version of a file is kept. A replaced file gets priority 1,
because it usually changes a quantity or a date (architecture.md §2.1).
"""

from typing import Any

from lineguard import clock
from lineguard import db
from lineguard import runtime
from lineguard.connectors import source as source_module

TABLE_PARSERS = ("table", "report", "json")


def sync(rt: runtime.Runtime, source: source_module.SourceConnector) -> list[dict[str, Any]]:
    """Compares the source with the known files and stores the changes.

    Returns:
        One entry per change with `kind` (added, changed, removed), `path`
        and `file_id`.
    """
    current = {
        row["path"]: row for row in db.rows(
            rt.conn, rt.ws,
            "SELECT * FROM files WHERE workspace_id = ? AND is_current = 1")
    }
    changes = []
    for remote in source.list():
        old = current.pop(remote.path, None)
        if old and old["sha256"] == remote.sha256:
            continue
        data = source.download(remote)
        changes.append(_store_version(rt, remote, data, old))
    for path, old in current.items():
        db.update(rt.conn, "files", rt.ws, old["id"], is_current=0,
                  replaced_at=clock.iso())
        rt.conn.execute(
            "UPDATE facts SET source_removed = 1 "
            "WHERE workspace_id = ? AND source_file_id = ?", (rt.ws, old["id"]))
        db.emit(rt.conn, rt.ws, "file.removed", {"file_id": old["id"], "path": path},
                priority=2, dedupe_key=f"file.removed:{path}:{old['sha256']}")
        changes.append({"kind": "removed", "path": path, "file_id": old["id"]})
    return changes


def _store_version(rt: runtime.Runtime, remote: source_module.SourceFile, data: bytes, old: dict[str, Any] | None) -> dict[str, Any]:
    route = rt.pack.route_for(remote.path)
    key = f"versions/{remote.sha256[:12]}/{remote.path}"
    rt.blob.put(key, data)
    rt.blob.put(f"live/{remote.path}", data)
    # Tables are wave 1 and get priority 1. Documents are wave 2: the
    # priority of their route (1 to 3) moves down by one, so a document
    # never runs before a table (docs/skalierung.md N1).
    if route.parser in TABLE_PARSERS:
        priority = 1
    else:
        priority = 2 if old else (route.priority or 3) + 1
    file_id = db.insert(
        rt.conn, "files", rt.ws, path=remote.path, sha256=remote.sha256,
        version=(old["version"] + 1) if old else 1, bytes=len(data),
        blob_key=key, doc_class=route.doc_class, parser=route.parser,
        kind=route.kind, priority=priority, first_seen_at=clock.iso(),
    )
    if old:
        db.update(rt.conn, "files", rt.ws, old["id"], is_current=0,
                  replaced_at=clock.iso())
        rt.conn.execute(
            "UPDATE facts SET superseded_by = ? WHERE workspace_id = ? "
            "AND source_file_id = ? AND superseded_by IS NULL",
            (file_id, rt.ws, old["id"]))
    kind = "changed" if old else "added"
    db.emit(
        rt.conn, rt.ws, f"file.{kind}",
        {"file_id": file_id, "path": remote.path,
         "previous_file_id": old["id"] if old else None},
        priority=priority,
        dedupe_key=f"file.{kind}:{remote.path}:{remote.sha256}",
        partition_key=f"file:{remote.path}",
    )
    return {"kind": kind, "path": remote.path, "file_id": file_id}
