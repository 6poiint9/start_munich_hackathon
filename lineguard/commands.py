"""Implementations of the command line commands."""

import argparse
import contextlib
import logging

import uvicorn

from lineguard import config
from lineguard import db
from lineguard import llm as llm_module
from lineguard import orchestrator
from lineguard import pack as pack_module
from lineguard import pipeline
from lineguard import runtime
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
    handlers = {"init": _init, "import": _import, "run": _run}
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
    make_runtime = runtime_factory(pack)
    workers = orchestrator.Orchestrator(make_runtime)
    if not args.no_agents:
        workers.every(float(pack.sources[0].poll_seconds), _poll_source)
        workers.every(60.0, _tick)
        workers.start()
    try:
        uvicorn.run(main_module.create_app(pack), host="127.0.0.1", port=args.port)
    finally:
        workers.stop()
    return 0
