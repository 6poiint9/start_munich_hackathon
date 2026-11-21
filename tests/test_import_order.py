from lineguard import db
from tests import helpers


def test_wave_one_gives_gaps_without_llm(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)

    gaps = db.rows(rt.conn, rt.ws,
                   "SELECT * FROM gaps WHERE workspace_id = ? AND is_current = 1")
    calls = db.rows(rt.conn, rt.ws, "SELECT * FROM llm_calls WHERE workspace_id = ?")
    failed = db.rows(rt.conn, rt.ws,
                     "SELECT path, parse_error FROM files WHERE workspace_id = ? "
                     "AND parse_status = 'failed'")
    documents = db.rows(rt.conn, rt.ws,
                        "SELECT * FROM events WHERE workspace_id = ? "
                        "AND status = 'pending' AND type = 'file.added'")

    assert failed == []
    assert calls == []
    assert len(documents) == 1, "the text document waits for wave 2"
    # The booking check runs without LLM: it finds the wrong receipt, and
    # the frame gap shows up.
    assert [(g["component_id"], g["gap_qty"]) for g in gaps] == [("RAHMEN-01", -50)]


def test_every_file_meets_a_route(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)
    files = db.rows(rt.conn, rt.ws, "SELECT * FROM files WHERE workspace_id = ?")
    assert len(files) == 14
    assert all(f["parser"] for f in files)


def test_second_sync_changes_nothing(tmp_path, monkeypatch):
    from lineguard.agents import watcher
    from lineguard.connectors import source
    rt = helpers.demo_runtime(tmp_path, monkeypatch)
    assert watcher.sync(rt, source.from_pack(rt.pack)) == []
