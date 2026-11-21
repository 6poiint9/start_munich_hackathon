"""The objects every agent handler gets: database, pack and ports."""

import dataclasses
import sqlite3
from typing import Any

from lineguard import config
from lineguard import db
from lineguard import pack as pack_module
from lineguard.connectors import blob as blob_module


@dataclasses.dataclass
class Runtime:
    """One workspace with its database, pack and connectors."""

    conn: sqlite3.Connection
    pack: pack_module.PackConfig
    blob: blob_module.LocalBlobStore
    llm: Any = None
    mailer: Any = None
    erp_writer: Any = None

    @property
    def ws(self) -> str:
        return self.pack.workspace


def open_runtime(pack: pack_module.PackConfig | None = None) -> Runtime:
    """Opens the workspace of the configured pack."""
    pack = pack or pack_module.load()
    conn = db.connect(pack.workspace)
    blob = blob_module.LocalBlobStore(config.data_dir(pack.workspace))
    return Runtime(conn=conn, pack=pack, blob=blob)
