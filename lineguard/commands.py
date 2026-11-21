"""Implementations of the command line commands."""

import argparse

from lineguard import db
from lineguard import pack as pack_module


def run(args: argparse.Namespace) -> int:
    """Dispatches one parsed command."""
    handlers = {"init": _init}
    handler = handlers.get(args.command)
    if handler is None:
        print(f"Command '{args.command}' is not built yet.")
        return 2
    return handler(args)


def _init(_: argparse.Namespace) -> int:
    pack = pack_module.load()
    with_conn = db.connect(pack.workspace)
    version = db.migrate(with_conn)
    with_conn.close()
    print(f"Workspace '{pack.workspace}': schema version {version}")
    return 0
