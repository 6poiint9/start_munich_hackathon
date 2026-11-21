import datetime
import email.message

from fastapi import testclient

from lineguard import clock
from lineguard import db
from lineguard import main
from lineguard import pipeline
from lineguard.agents import action
from lineguard.connectors import mail
from tests import fakes
from tests import helpers


def _rows(rt, table, where="1 = 1"):
    return db.rows(rt.conn, rt.ws,
                   f"SELECT * FROM {table} WHERE workspace_id = ? AND {where} ORDER BY id")


def _setup(tmp_path, monkeypatch):
    monkeypatch.setenv("LINEGUARD_DATA", str(tmp_path / "data"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    rt = helpers.demo_runtime(tmp_path, monkeypatch, conn=db.connect("demo_bikes"))
    rt.mailer = mail.Mailer("DRY_RUN", "einkauf@radwerk.example", "", "Radwerk Einkauf",
                            tmp_path / "inbox")
    return rt, testclient.TestClient(main.create_app(rt.pack))


def test_every_blocking_gap_has_a_plan_with_decision(tmp_path, monkeypatch):
    rt, _ = _setup(tmp_path, monkeypatch)

    gap_cases = _rows(rt, "cases", "kind = 'gap'")
    options = _rows(rt, "options")
    decisions = _rows(rt, "decisions")

    assert [c["state"] for c in gap_cases] == ["plan_proposed"]
    assert [(o["kind"], o["qty_gain"], o["cost_eur"], o["role_in_plan"], o["feasible"])
            for o in options] == [("accept_offer", 100, 4500, "primary", 1)]
    decision = decisions[0]
    assert decision["status"] == "open"
    assert decision["approver_role"] == "buyer"
    assert decision["approver_name"] == "Anna Beispiel"
    assert "4.500 €" in decision["explanation"]


def test_option_after_latest_useful_arrival_is_not_feasible(tmp_path, monkeypatch):
    rt, _ = _setup(tmp_path, monkeypatch)
    rt.conn.execute(
        "UPDATE facts SET data = json_set(data, '$.lead_time_hours', 2000) "
        "WHERE workspace_id = ? AND fact_type = 'offer'", (rt.ws,))
    rt.conn.execute("DELETE FROM decisions WHERE workspace_id = ?", (rt.ws,))
    db.emit(rt.conn, rt.ws, "tick")

    pipeline.drain(rt)

    option = _rows(rt, "options")[0]
    assert option["feasible"] == 0
    assert option["role_in_plan"] == "none"
    assert "spätesten nützlichen Ankunft" in option["infeasible_reason"]
    case = _rows(rt, "cases", "kind = 'gap'")[0]
    assert case["state"] == "unclosable"
    assert _rows(rt, "gaps", "is_current = 1")[0]["residual_qty"] == 50


def test_approval_needs_the_role_and_sends_exactly_one_mail(tmp_path, monkeypatch):
    rt, client = _setup(tmp_path, monkeypatch)
    decision_id = _rows(rt, "decisions")[0]["id"]

    assert client.post(f"/decisions/{decision_id}/approve").status_code == 401
    wrong = client.post(f"/decisions/{decision_id}/approve",
                        headers={"X-Lineguard-User": "P3"})
    first = client.post(f"/decisions/{decision_id}/approve",
                        headers={"X-Lineguard-User": "P1"})
    second = client.post(f"/decisions/{decision_id}/approve",
                         headers={"X-Lineguard-User": "P1"})

    assert wrong.status_code == 403
    assert (first.status_code, first.json()["status"]) == (200, "approved")
    assert second.json()["status"] == "approved"
    mails = _rows(rt, "emails", "direction = 'out' AND commits_money = 1")
    assert len(mails) == 1
    assert mails[0]["status"] == "dry_run"
    assert mails[0]["to_addr"] == "jan@rahmenbau.example"
    assert mails[0]["approved_by"] == "P1"
    assert mails[0]["subject"].startswith("[RAD]")
    assert _rows(rt, "cases", "kind = 'gap'")[0]["state"] == "in_execution"


def test_reply_confirms_option_and_closes_gap(tmp_path, monkeypatch):
    rt, client = _setup(tmp_path, monkeypatch)
    decision_id = _rows(rt, "decisions")[0]["id"]
    client.post(f"/decisions/{decision_id}/approve", headers={"X-Lineguard-User": "P1"})
    sent = _rows(rt, "emails", "direction = 'out' AND commits_money = 1")[0]
    reply = email.message.EmailMessage()
    reply["From"] = "Jan Muster <jan@rahmenbau.example>"
    reply["Subject"] = "AW: Bestellung"
    reply["Message-ID"] = "<reply-1@rahmenbau.example>"
    reply["In-Reply-To"] = sent["message_id"]
    reply.set_content("Bestaetigt: 100 Rahmen, Ankunft 04.03.2027 10:00.")
    reply.add_attachment(b"Lieferavis 100 Stueck", maintype="text", subtype="plain",
                         filename="avis.txt")
    rt.llm = fakes.FakeLlm(lambda purpose, prompt: {"doc_class": "supplier_mail", "facts": [
        {"fact_type": "inbound_qty", "component_id": "RAHMEN-01", "qty": 100,
         "eta": "2027-03-04T10:00:00+01:00", "confidence": 0.95}]}
        if "body.txt" in prompt else {"facts": []})

    assert action.receive(rt, reply) is not None
    assert action.receive(rt, reply) is None
    pipeline.drain(rt)

    incoming = _rows(rt, "emails", "direction = 'in'")
    assert incoming[0]["case_id"] == sent["case_id"]
    files = _rows(rt, "files", "path LIKE 'mail/%'")
    assert sorted(f["path"].split("/")[-1] for f in files) == ["avis.txt", "body.txt"]
    assert files[0]["path"].startswith("mail/LIEF-A/")
    fact = _rows(rt, "facts", "fact_type = 'inbound_qty'")[0]
    assert (fact["source_rank"], fact["supplier_id"]) == (2, "LIEF-A")
    assert _rows(rt, "gaps", "is_current = 1") == []
    assert _rows(rt, "cases", "kind = 'gap'")[0]["state"] == "closed"
    assert _rows(rt, "options")[0]["status"] == "confirmed"
    header = client.get("/state").json()["products"][0]
    assert header["coverage_secured"] == 1.0


def test_open_decision_escalates_before_it_is_due(tmp_path, monkeypatch):
    rt, _ = _setup(tmp_path, monkeypatch)
    decision = _rows(rt, "decisions")[0]
    due = clock.parse(decision["deadline"])
    monkeypatch.setenv("LINEGUARD_NOW", (due - datetime.timedelta(minutes=10)).isoformat())
    db.emit(rt.conn, rt.ws, "tick")

    pipeline.drain(rt)

    after = _rows(rt, "decisions")[0]
    assert after["approver_role"] == "category_lead"
    assert after["approver_name"] == "Bernd Muster"
    assert after["escalation_level"] == 1


def test_rejected_decision_reopens_the_case(tmp_path, monkeypatch):
    rt, client = _setup(tmp_path, monkeypatch)
    decision_id = _rows(rt, "decisions")[0]["id"]
    response = client.post(f"/decisions/{decision_id}/reject",
                           headers={"X-Lineguard-User": "P1"}, json={"reason": "zu teuer"})
    pipeline.drain(rt)
    assert response.json()["status"] == "rejected"
    assert _rows(rt, "cases", "kind = 'gap'")[0]["state"] == "unclosable"
    assert _rows(rt, "emails", "commits_money = 1") == []
