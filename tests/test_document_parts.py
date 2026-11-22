"""Tests for complete document processing without a network."""

from lineguard import db
from lineguard import llm
from lineguard import pipeline
from lineguard.agents import watcher
from lineguard.agents.reader import documents
from lineguard.connectors import source
from lineguard.tools import content
from tests import fakes
from tests import helpers


def _read_file(tmp_path, monkeypatch, text, answer):
    monkeypatch.setenv("LINEGUARD_NOW", helpers.DEMO_NOW)
    rt = helpers.make_runtime(tmp_path, helpers.DEMO_PACK)
    rt.llm = fakes.FakeLlm(answer)
    folder = tmp_path / "source"
    folder.mkdir()
    (folder / "test.txt").write_text(text)
    watcher.sync(rt, source.LocalFolderSource(folder))
    pipeline.drain(rt, ["reader"])
    return rt


def test_long_text_reads_every_part(tmp_path, monkeypatch):
    def answer(_purpose, prompt):
        return {"facts": [{"fact_type": "info",
                           "value_text": "last" if "END-MARKER" in prompt else "first"}]}

    rt = _read_file(tmp_path, monkeypatch,
                    "a" * content.MAX_TEXT_CHARS + "END-MARKER", answer)
    facts = db.rows(rt.conn, rt.ws,
                    "SELECT * FROM facts WHERE workspace_id = ? ORDER BY id")
    assert [fact["value_text"] for fact in facts] == ["first", "last"]
    assert len(rt.llm.calls) == 2
    assert "part 2" in facts[1]["source_locator"]


def test_late_suspicious_part_marks_all_facts(tmp_path, monkeypatch):
    def answer(_purpose, prompt):
        return {"suspicious": "END-MARKER" in prompt,
                "facts": [{"fact_type": "info", "value_text": "test"}]}

    rt = _read_file(tmp_path, monkeypatch,
                    "a" * content.MAX_TEXT_CHARS + "END-MARKER", answer)
    facts = db.rows(rt.conn, rt.ws,
                    "SELECT * FROM facts WHERE workspace_id = ? AND fact_type = 'info'")
    assert facts
    assert all(fact["suspicious"] for fact in facts)


def test_failed_later_part_stores_no_partial_facts(tmp_path, monkeypatch):
    def answer(_purpose, prompt):
        if "END-MARKER" in prompt:
            raise llm.LlmError("test failure")
        return {"facts": [{"fact_type": "info", "value_text": "first"}]}

    rt = _read_file(tmp_path, monkeypatch,
                    "a" * content.MAX_TEXT_CHARS + "END-MARKER", answer)
    assert not db.rows(rt.conn, rt.ws, "SELECT * FROM facts WHERE workspace_id = ?")
    file = db.one(rt.conn, rt.ws, "SELECT * FROM files WHERE workspace_id = ?")
    assert file["parse_status"] == "manual"
    assert file["parse_error"] == "test failure"


def test_pdf_reads_scans_after_page_three_and_mixed_text(monkeypatch):
    monkeypatch.setattr(content, "_pdf_text",
                        lambda _data: "x" * 60 + "\f\f\f\f\f")
    seen = []

    def render(_data, pages):
        seen.extend(pages)
        return [(str(page).encode(), "image/png") for page in pages]

    monkeypatch.setattr(content, "_pdf_pages", render)
    parts = content.extract_parts("mixed.pdf", b"pdf")
    assert seen == [2, 3, 4, 5]
    assert parts[0] == ("page 1", "x" * 60, [])
    assert parts[-1] == ("page 5", "", [(b"5", "image/png")])


def _notes_runtime(tmp_path, monkeypatch, answer):
    monkeypatch.setenv("LINEGUARD_NOW", helpers.DEMO_NOW)
    rt = helpers.make_runtime(tmp_path, helpers.DEMO_PACK)
    rt.llm = fakes.FakeLlm(answer)
    file_id = db.insert(rt.conn, "files", rt.ws, path="notes.csv", sha256="test",
                        version=1, first_seen_at="2027-03-01T00:00:00Z")
    for index in range(121):
        db.insert(rt.conn, "facts", rt.ws, fact_type="note",
                  source_file_id=file_id, value_text=f"note-{index}",
                  created_at="2027-03-01T00:00:00Z")
    return rt, file_id


def test_all_table_notes_are_processed(tmp_path, monkeypatch):
    rt, file_id = _notes_runtime(tmp_path, monkeypatch, lambda _purpose, prompt: {
        "facts": [{"fact_type": "info",
                   "value_text": "last" if "note-120" in prompt else "first"}]})
    documents.read_notes(rt, {"payload": {"file_id": file_id}})
    facts = db.rows(rt.conn, rt.ws,
                    "SELECT * FROM facts WHERE workspace_id = ? AND fact_type = 'info'")
    assert [fact["value_text"] for fact in facts] == ["first", "last"]
    assert len(rt.llm.calls) == 2


def test_failed_note_batch_keeps_previous_results(tmp_path, monkeypatch):
    def answer(_purpose, prompt):
        if "note-120" in prompt:
            raise llm.LlmError("test failure")
        return {"facts": [{"fact_type": "info", "value_text": "new"}]}

    rt, file_id = _notes_runtime(tmp_path, monkeypatch, answer)
    db.insert(rt.conn, "facts", rt.ws, fact_type="info", source_file_id=file_id,
              value_text="old", extracted_by="llm_note",
              created_at="2027-03-01T00:00:00Z")
    documents.read_notes(rt, {"payload": {"file_id": file_id}})
    facts = db.rows(rt.conn, rt.ws,
                    "SELECT * FROM facts WHERE workspace_id = ? AND fact_type = 'info'")
    assert [fact["value_text"] for fact in facts] == ["old"]


def test_suspicious_note_batch_marks_all_results(tmp_path, monkeypatch):
    rt, file_id = _notes_runtime(tmp_path, monkeypatch, lambda _purpose, prompt: {
        "suspicious": "note-120" in prompt,
        "facts": [{"fact_type": "info", "value_text": "result"}]})
    documents.read_notes(rt, {"payload": {"file_id": file_id}})
    facts = db.rows(rt.conn, rt.ws,
                    "SELECT * FROM facts WHERE workspace_id = ? "
                    "AND fact_type = 'info' AND value_text = 'result'")
    assert len(facts) == 2
    assert all(fact["suspicious"] for fact in facts)
