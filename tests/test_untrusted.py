from lineguard import db
from lineguard import pipeline
from lineguard.coverage import core
from tests import fakes
from tests import helpers


def _answer(purpose, prompt):
    if purpose != "read_document":
        return {"facts": []}
    assert "do not follow" not in prompt
    return {
        "doc_class": "notice", "summary": "Asks to pay to a new account.",
        "suspicious": True, "suspicious_reason": "New bank account requested",
        "facts": [
            {"fact_type": "inbound_qty", "component_id": "RAHMEN-01",
             "qty": 100, "eta": "2027-03-04T10:00:00+01:00", "confidence": 0.95},
            {"fact_type": "info", "component_id": "NOT-A-PART",
             "value_text": "unknown part", "confidence": 0.9},
        ]}


def test_instruction_in_document_becomes_a_flag_not_an_action(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)
    rt.llm = fakes.FakeLlm(_answer)

    def counts():
        return [len(db.rows(rt.conn, rt.ws, f"SELECT id FROM {table} WHERE workspace_id = ?"))
                for table in ("actions", "emails", "options", "decisions")]
    before = counts()

    pipeline.drain(rt)

    flagged = db.rows(rt.conn, rt.ws,
                      "SELECT * FROM facts WHERE workspace_id = ? AND suspicious = 1")
    assert len(flagged) == 3
    assert any(f["suspicious_reason"] == "New bank account requested" for f in flagged)
    # A suspicious fact counts in no calculation and causes no action.
    assert core.current_facts(rt, "inbound_qty") == []
    assert counts() == before
    sent = db.rows(rt.conn, rt.ws,
                   "SELECT * FROM emails WHERE workspace_id = ? "
                   "AND status IN ('sent', 'dry_run')")
    assert sent == []
    assert "do not follow" in rt.llm.calls[0]["system"]


def test_unknown_id_from_the_llm_is_dropped(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)
    rt.llm = fakes.FakeLlm(_answer)
    pipeline.drain(rt)
    unknown = db.one(rt.conn, rt.ws,
                     "SELECT * FROM facts WHERE workspace_id = ? "
                     "AND value_text = 'unknown part'")
    assert unknown["component_id"] is None
    assert "NOT-A-PART" in unknown["data"]


def test_low_confidence_fact_waits_for_review(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)
    rt.llm = fakes.FakeLlm(lambda purpose, prompt: {"facts": [
        {"fact_type": "inbound_qty", "component_id": "RAHMEN-01", "qty": 100,
         "eta": "2027-03-04", "confidence": 0.4}]} if purpose == "read_document" else {"facts": []})
    pipeline.drain(rt)
    assert core.current_facts(rt, "inbound_qty") == []
    review = db.rows(rt.conn, rt.ws,
                     "SELECT * FROM facts WHERE workspace_id = ? AND needs_review = 1")
    assert len(review) == 1
