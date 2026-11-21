"""Builds a runtime on a temporary database for tests."""

import pathlib

from lineguard import db
from lineguard import pack as pack_module
from lineguard import pipeline
from lineguard import runtime
from lineguard.connectors import blob
from lineguard.connectors import source

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEMO_PACK = ROOT / "tests" / "fixtures" / "packs" / "demo_bikes"
DEMO_NOW = "2027-03-01T08:00:00+01:00"
SOONY_PACK = ROOT / "packs" / "soony_gh6"
SOONY_SNAPSHOT = ROOT / "tests" / "fixtures" / "soony"
SOONY_NOW = "2026-11-21T22:45:00+01:00"


def make_runtime(tmp_path: pathlib.Path, pack_path: pathlib.Path, conn=None) -> runtime.Runtime:
    pack = pack_module.load(pack_path)
    conn = conn or db.connect(pack.workspace, tmp_path / f"{pack.workspace}.sqlite")
    store = blob.LocalBlobStore(tmp_path / "data" / pack.workspace)
    return runtime.Runtime(conn=conn, pack=pack, blob=store)


def demo_runtime(tmp_path, monkeypatch, conn=None) -> runtime.Runtime:
    """demo_bikes after wave 1, at the fixed test clock."""
    monkeypatch.setenv("LINEGUARD_NOW", DEMO_NOW)
    rt = make_runtime(tmp_path, DEMO_PACK, conn)
    pipeline.import_wave_one(rt, source.from_pack(rt.pack))
    return rt


def soony_runtime(tmp_path, monkeypatch, conn=None) -> runtime.Runtime:
    """The frozen customer snapshot after wave 1."""
    monkeypatch.setenv("LINEGUARD_NOW", SOONY_NOW)
    rt = make_runtime(tmp_path, SOONY_PACK, conn)
    pipeline.import_wave_one(rt, source.LocalFolderSource(SOONY_SNAPSHOT))
    return rt
