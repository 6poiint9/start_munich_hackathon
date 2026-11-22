"""A supplier holds finished goods until a condition is confirmed in writing."""

import email.message

from fastapi import testclient

from lineguard import db
from lineguard import main
from lineguard import pipeline
from lineguard.agents import action
from lineguard.agents import watcher
from lineguard.connectors import mail
from lineguard.connectors import source
from lineguard.coverage import core
from tests import fakes
from tests import helpers

_MAIL = helpers.ROOT / "tests" / "fixtures" / "mails" / "bedingung_lieferant.txt"
_CONDITION = "Supplier releases the goods after written confirmation of delivery EXW works."
_CONFIRMED = "Delivery EXW under RV-7"
_FACT = {
    "fact_type": "supplier_condition", "po_number": "BE-2001",
    "component_id": "RAHMEN-01", "qty": 60, "value_text": _CONDITION,
    "confidence": 0.95,
    "data": {"condition_kind": "incoterm_confirmation", "incoterm": "EXW",
             "contract_ref": "RV-7", "transit_hours_after_release": 24,
             "alternatives": ["own forwarder"]}}


def _rows(rt, table, where="1 = 1"):
    return db.rows(rt.conn, rt.ws,
                   f"SELECT * FROM {table} WHERE workspace_id = ? AND {where} ORDER BY id")


def _setup(tmp_path, monkeypatch, suspicious=False, extra_facts=()):
    """demo_bikes without a usable offer, plus the reply of the supplier."""
    monkeypatch.setenv("LINEGUARD_DATA", str(tmp_path / "data"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    rt = helpers.demo_runtime(tmp_path, monkeypatch, conn=db.connect("demo_bikes"))
    rt.mailer = mail.Mailer("DRY_RUN", "einkauf@radwerk.example", "", "Radwerk Einkauf",
                            tmp_path / "inbox")
    rt.conn.execute("DELETE FROM facts WHERE workspace_id = ? AND fact_type = 'offer'",
                    (rt.ws,))
    rt.conn.execute("DELETE FROM decisions WHERE workspace_id = ?", (rt.ws,))
    answer = {"doc_class": "supplier_mail", "suspicious": suspicious,
              "suspicious_reason": "New bank account requested" if suspicious else None,
              "facts": [_FACT, *extra_facts]}
    rt.llm = fakes.FakeLlm(
        lambda purpose, prompt: answer if "body.txt" in prompt else {"facts": []})
    reply = email.message.EmailMessage()
    reply["From"] = "Jan Muster <jan@rahmenbau.example>"
    reply["Subject"] = "AW: [RAD][PO BE-2001] Status RAHMEN-01"
    reply["Message-ID"] = "<condition-1@rahmenbau.example>"
    reply.set_content(_MAIL.read_text(encoding="utf-8"))
    action.receive(rt, reply)
    pipeline.drain(rt)
    # The decision loop runs on the tick, as in live operation.
    db.emit(rt.conn, rt.ws, "tick")
    pipeline.drain(rt)
    return rt, testclient.TestClient(main.create_app(rt.pack))


def test_condition_becomes_an_option_with_the_roles_of_the_pack(tmp_path, monkeypatch):
    rt, client = _setup(tmp_path, monkeypatch)

    option = _rows(rt, "options", "kind = 'confirm_terms'")[0]
    data = db.loads(option["data"])
    assert (option["qty_gain"], option["feasible"], option["role_in_plan"]) == (60, 1, "primary")
    assert option["arrives_at"].startswith("2027-03-02T07:00")
    assert db.loads(option["needs_roles"]) == ["category_lead"]
    assert (option["supplier_id"], data["po_number"]) == ("LIEF-A", "BE-2001")
    assert data["condition"] == _CONFIRMED
    assert data["cost_unknown"] is True

    waiting = client.get("/state").json()["approvals"]
    entry = next(a for a in waiting if a["kind"] == "confirm_terms")
    assert entry["type"] == "decision"
    assert entry["needs_roles"][0] == "category_lead"
    assert entry["approver_name"] == "Bernd Muster"
    assert entry["commits_money"] is True
    assert entry["condition"] == _CONFIRMED
    assert entry["email"]["to_addr"] == "jan@rahmenbau.example"


def test_draft_binds_the_company_and_waits_for_a_person(tmp_path, monkeypatch):
    rt, _ = _setup(tmp_path, monkeypatch)

    drafts = _rows(rt, "emails", "direction = 'out' AND status != 'discarded'")
    assert [(m["status"], m["commits_money"], m["routine"]) for m in drafts] == [("draft", 1, 0)]
    # The condition in the mail comes from the fields of the fact.
    assert _CONFIRMED in drafts[0]["body"]
    assert drafts[0]["to_addr"] == "jan@rahmenbau.example"
    assert drafts[0]["in_reply_to"] == "<condition-1@rahmenbau.example>"
    assert _rows(rt, "emails", "status IN ('sent', 'dry_run')") == []


def test_only_a_person_with_the_role_sends_the_confirmation(tmp_path, monkeypatch):
    rt, client = _setup(tmp_path, monkeypatch)
    decision_id = _rows(rt, "decisions", "status = 'open'")[0]["id"]

    assert client.post(f"/decisions/{decision_id}/approve").status_code == 401
    unknown = client.post(f"/decisions/{decision_id}/approve",
                          headers={"X-Lineguard-User": "nobody"})
    assert unknown.status_code == 403
    wrong = client.post(f"/decisions/{decision_id}/approve",
                        headers={"X-Lineguard-User": "P1"})
    assert wrong.status_code == 403
    assert _rows(rt, "emails", "status IN ('sent', 'dry_run')") == []

    right = client.post(f"/decisions/{decision_id}/approve",
                        headers={"X-Lineguard-User": "P2"})
    again = client.post(f"/decisions/{decision_id}/approve",
                        headers={"X-Lineguard-User": "P2"})

    assert (right.status_code, right.json()["status"]) == (200, "approved")
    assert again.json()["status"] == "approved"
    sent = _rows(rt, "emails", "direction = 'out' AND status != 'discarded'")
    assert [(m["status"], m["approved_by"]) for m in sent] == [("dry_run", "P2")]
    state = client.get("/state").json()
    assert [a for a in state["approvals"] if a["kind"] == "confirm_terms"] == []
    done = state["approvals_done"][0]
    assert (done["status"], done["decided_by"], done["mail_status"]) == (
        "approved", "Bernd Muster", "dry_run")
    assert _rows(rt, "cases", "kind = 'gap'")[0]["state"] == "in_execution"


def test_no_status_question_for_an_order_that_waits_for_confirmation(tmp_path, monkeypatch):
    held = {"fact_type": "inbound_qty", "component_id": "RAHMEN-01", "qty": 60,
            "po_number": "BE-2001", "ref": "AWB-1", "confidence": 0.95}
    rt, _ = _setup(tmp_path, monkeypatch, extra_facts=[held])

    assert _rows(rt, "options", "kind = 'expedite_inbound'") == []
    assert _rows(rt, "emails", "direction = 'out' AND routine = 1") == []


def test_condition_after_the_due_date_stays_a_decision_but_closes_nothing(tmp_path, monkeypatch):
    rt, client = _setup(tmp_path, monkeypatch)
    rt.conn.execute(
        "UPDATE facts SET data = json_set(data, '$.transit_hours_after_release', 2000) "
        "WHERE workspace_id = ? AND fact_type = 'supplier_condition'", (rt.ws,))
    db.emit(rt.conn, rt.ws, "tick")
    pipeline.drain(rt)

    option = _rows(rt, "options", "kind = 'confirm_terms'")[0]
    data = db.loads(option["data"])
    assert (option["qty_gain"], option["feasible"]) == (0, 1)
    assert (data["after_deadline"], data["planned_qty"]) == (True, 60)
    assert _rows(rt, "cases", "kind = 'gap'")[0]["state"] == "unclosable"
    entry = next(a for a in client.get("/state").json()["approvals"]
                 if a["kind"] == "confirm_terms")
    assert entry["after_deadline"] is True


def test_sync_with_the_source_keeps_the_replies_of_suppliers(tmp_path, monkeypatch):
    rt, _ = _setup(tmp_path, monkeypatch)

    changes = watcher.sync(rt, source.from_pack(rt.pack))

    assert changes == []
    assert [f["is_current"] for f in _rows(rt, "files", "path LIKE 'mail/%'")] == [1]
    assert len(core.current_facts(rt, "supplier_condition")) == 1


def test_suspicious_condition_gives_no_option(tmp_path, monkeypatch):
    rt, _ = _setup(tmp_path, monkeypatch, suspicious=True)

    assert _rows(rt, "facts", "fact_type = 'supplier_condition'")[0]["suspicious"] == 1
    assert _rows(rt, "options", "kind = 'confirm_terms'") == []
    assert _rows(rt, "emails", "direction = 'out' AND commits_money = 1 "
                 "AND status != 'discarded'") == []
