import time

from lineguard import db
from lineguard import orchestrator
from lineguard import pack as pack_module
from lineguard import runtime
from lineguard.agents import watcher
from lineguard.connectors import blob
from lineguard.connectors import source
from tests import fakes
from tests import helpers


def _answer(purpose, prompt):
    del purpose
    name = prompt.split("File path: ")[1].split("\n")[0]
    return {"doc_class": "notice", "summary": name, "facts": [
        {"fact_type": "info", "value_text": name, "confidence": 0.9}]}


def test_forty_documents_are_read_in_parallel(tmp_path, monkeypatch):
    monkeypatch.setenv("READER_CONCURRENCY", "8")
    folder = tmp_path / "source"
    folder.mkdir()
    for index in range(40):
        (folder / f"doc_{index:02d}.txt").write_text(f"document {index}")
    pack = pack_module.load(helpers.DEMO_PACK)
    path = tmp_path / "t.sqlite"
    llm = fakes.FakeLlm(_answer, delay=1.0)
    store = blob.LocalBlobStore(tmp_path / "blobs")

    def make_runtime():
        return runtime.Runtime(conn=db.connect(pack.workspace, path), pack=pack,
                               blob=store, llm=llm)

    rt = make_runtime()
    watcher.sync(rt, source.LocalFolderSource(folder))
    started = time.monotonic()
    orchestrator.run_until_empty(make_runtime, ["reader"])
    elapsed = time.monotonic() - started

    facts = db.rows(rt.conn, rt.ws,
                    "SELECT source_file_id, COUNT(*) AS n FROM facts "
                    "WHERE workspace_id = ? GROUP BY source_file_id")
    assert elapsed < 10
    assert len(llm.calls) == 40
    assert len(facts) == 40
    assert all(row["n"] == 1 for row in facts)
