"""Implementations of the command line commands."""

import argparse
import contextlib
import logging
import pathlib
import sqlite3

import uvicorn

from lineguard import config
from lineguard import db
from lineguard import llm as llm_module
from lineguard import orchestrator
from lineguard import pack as pack_module
from lineguard import pipeline
from lineguard import runtime
from lineguard.agents import action
from lineguard.agents import watcher
from lineguard.connectors import blob as blob_module
from lineguard.connectors import source as source_module

logger = logging.getLogger(__name__)


def runtime_factory(pack: pack_module.PackConfig, with_llm: bool = True):
    """Returns a function that opens a new runtime with its own connection.

    The LLM client and the blob store are shared by all workers.
    """
    client = llm_module.from_env() if with_llm else None
    store = blob_module.LocalBlobStore(config.data_dir(pack.workspace))

    def make_runtime() -> runtime.Runtime:
        return runtime.Runtime(conn=db.connect(pack.workspace), pack=pack,
                               blob=store, llm=client)
    return make_runtime


def run(args: argparse.Namespace) -> int:
    """Dispatches one parsed command."""
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    handlers = {"init": _init, "import": _import, "run": _run,
                "recompute": _recompute, "reread": _reread,
                "send-logged": _send_logged, "demo-save": _demo_save,
                "demo-reset": _demo_reset}
    handler = handlers.get(args.command)
    if handler is None:
        print(f"Command '{args.command}' is not built yet.")
        return 2
    return handler(args)


def _init(_: argparse.Namespace) -> int:
    pack = pack_module.load()
    with contextlib.closing(db.connect(pack.workspace)) as conn:
        version = db.migrate(conn)
    print(f"Workspace '{pack.workspace}': schema version {version}")
    return 0


def import_all(pack: pack_module.PackConfig, with_llm: bool) -> dict[str, int]:
    """Syncs the source, reads tables (wave 1), then documents (wave 2)."""
    make_runtime = runtime_factory(pack, with_llm)
    rt = make_runtime()
    with contextlib.closing(rt.conn):
        changes = pipeline.import_wave_one(rt, source_module.from_pack(pack))
        _tick(rt)
    handled = 0
    if with_llm and rt.llm is not None:
        handled = orchestrator.run_until_empty(make_runtime)
    return {"changes": len(changes), "wave_two_events": handled}


def _import(args: argparse.Namespace) -> int:
    pack = pack_module.load()
    result = import_all(pack, with_llm=not args.no_llm)
    print(f"Workspace '{pack.workspace}': {result['changes']} file changes, "
          f"{result['wave_two_events']} events in wave 2")
    return 0


def _recompute(_: argparse.Namespace) -> int:
    """Computes the state again from the stored facts and runs the agents."""
    pack = pack_module.load()
    make_runtime = runtime_factory(pack)
    rt = make_runtime()
    with contextlib.closing(rt.conn):
        db.emit(rt.conn, rt.ws, "facts.updated", {"component_id": "*"},
                priority=1, coalesce_key="facts.updated:*", partition_key="coverage")
        _tick(rt)
        handled = pipeline.drain(rt)
    print(f"Workspace '{pack.workspace}': {handled} events handled")
    return 0


def _reread(args: argparse.Namespace) -> int:
    """Reads files again whose path contains the text, with the current prompt."""
    pack = pack_module.load()
    make_runtime = runtime_factory(pack)
    rt = make_runtime()
    with contextlib.closing(rt.conn):
        files = db.rows(
            rt.conn, rt.ws,
            "SELECT * FROM files WHERE workspace_id = ? AND is_current = 1 "
            "AND path LIKE ?", (f"%{args.text}%",))
        for file in files:
            rt.conn.execute(
                "DELETE FROM facts WHERE workspace_id = ? AND source_file_id = ?",
                (rt.ws, file["id"]))
            db.update(rt.conn, "files", rt.ws, file["id"], parse_status="new")
            db.emit(rt.conn, rt.ws, "file.changed",
                    {"file_id": file["id"], "path": file["path"]}, priority=2,
                    partition_key=f"file:{file['path']}")
        _tick(rt)
        handled = pipeline.drain(rt)
    print(f"Workspace '{pack.workspace}': {len(files)} files read again, "
          f"{handled} events handled")
    return 0


def _send_logged(_: argparse.Namespace) -> int:
    """Sends the mails that DRY_RUN only wrote to the log.

    Use it after a switch to MAIL_MODE=LIVE. Only approved mails are sent:
    routine questions and mails that a person approved. Drafts stay drafts.
    """
    pack = pack_module.load()
    rt = runtime_factory(pack, with_llm=False)()
    with contextlib.closing(rt.conn):
        if action.mailer(rt).mode != "LIVE":
            print("MAIL_MODE is not LIVE. Nothing sent.")
            return 1
        logged = db.rows(
            rt.conn, rt.ws,
            "SELECT * FROM emails WHERE workspace_id = ? AND direction = 'out' "
            "AND status = 'dry_run' AND to_addr LIKE '%@%' ORDER BY id")
        seen = set()
        for row in logged:
            key = (row["to_addr"], row["po_ref"], row["case_id"])
            if key in seen:
                db.update(rt.conn, "emails", rt.ws, row["id"], status="discarded",
                          reason="Doppelt: gleiche Frage an denselben Empfänger")
                continue
            seen.add(key)
            db.update(rt.conn, "emails", rt.ws, row["id"], status="approved")
            sent = action.send(rt, row["id"], row["approved_by"] or "auto_approve")
            print(f"{sent['status']}: {row['to_addr']} | {row['subject']}")
    return 0


def _snapshot_path(workspace: str) -> pathlib.Path:
    return config.data_dir(workspace) / "demo" / "demo_start.sqlite"


def _copy_database(source: pathlib.Path, target: pathlib.Path) -> None:
    """Copies a database with the SQLite backup API, safe with open readers."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.closing(sqlite3.connect(source)) as origin:
        with contextlib.closing(sqlite3.connect(target)) as copy:
            origin.backup(copy)


def _demo_save(_: argparse.Namespace) -> int:
    """Stores the current state as the demo start state."""
    pack = pack_module.load()
    _copy_database(db.database_path(pack.workspace), _snapshot_path(pack.workspace))
    print(f"Saved the demo start state to {_snapshot_path(pack.workspace)}")
    return 0


def _demo_reset(_: argparse.Namespace) -> int:
    """Restores the demo start state. Stop `lineguard run` before."""
    pack = pack_module.load()
    snapshot = _snapshot_path(pack.workspace)
    if not snapshot.is_file():
        print(f"No snapshot at {snapshot}. Run 'python -m lineguard demo-save' first.")
        return 1
    target = db.database_path(pack.workspace)
    for suffix in ("", "-wal", "-shm"):
        pathlib.Path(f"{target}{suffix}").unlink(missing_ok=True)
    _copy_database(snapshot, target)
    with contextlib.closing(db.connect(pack.workspace)) as conn:
        version = db.migrate(conn)
    print(f"Workspace '{pack.workspace}' is at the demo start state, schema {version}")
    return 0


def _poll_source(rt: runtime.Runtime) -> None:
    changes = watcher.sync(rt, source_module.from_pack(rt.pack))
    if changes:
        logger.info("Source: %d changes", len(changes))


def _tick(rt: runtime.Runtime) -> None:
    db.emit(rt.conn, rt.ws, "tick", coalesce_key="tick", priority=3)
    db.emit(rt.conn, rt.ws, "tick.action", coalesce_key="tick.action", priority=3)


def _run(args: argparse.Namespace) -> int:
    from lineguard import main as main_module  # pylint: disable=import-outside-toplevel

    pack = pack_module.load()
    # Migrate once before the threads start. On an empty database, threads
    # that migrate at the same time create the same tables twice and die.
    with contextlib.closing(db.connect(pack.workspace)):
        pass
    make_runtime = runtime_factory(pack)
    workers = orchestrator.Orchestrator(make_runtime)
    if not args.no_agents:
        workers.every(float(pack.sources[0].poll_seconds), _poll_source)
        workers.every(60.0, _tick)
        workers.start()
    try:
        uvicorn.run(main_module.create_app(pack, llm=llm_module.from_env()),
                    host=args.host, port=args.port)
    finally:
        workers.stop()
    return 0
