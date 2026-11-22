import datetime
import email.message

from fastapi import testclient
import pytest

from lineguard import approvals
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
    assert "€4,500" in decision["explanation"]
    # The person sees the exact mail before the click. It is not sent yet.
    drafts = _rows(rt, "emails")
    assert [(m["status"], m["commits_money"], m["routine"]) for m in drafts] == [("draft", 1, 0)]


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
    assert "latest useful arrival" in option["infeasible_reason"]
    case = _rows(rt, "cases", "kind = 'gap'")[0]
    assert case["state"] == "unclosable"
    assert _rows(rt, "gaps", "is_current = 1")[0]["residual_qty"] == 50


def test_unclosable_alert_is_immediate_idempotent_and_safe_to_acknowledge(tmp_path, monkeypatch):
    rt, client = _setup(tmp_path, monkeypatch)
    rt.conn.execute(
        "UPDATE facts SET data = json_set(data, '$.lead_time_hours', 2000) "
        "WHERE workspace_id = ? AND fact_type = 'offer'", (rt.ws,))
    db.emit(rt.conn, rt.ws, "tick")
    pipeline.drain(rt)

    alerts = _rows(rt, "decisions", "dedupe_key LIKE 'unclosable:%'")
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["approver_role"] == "category_lead"
    assert alert["recommended_option"] is None
    assert "does not confirm a later delivery date or cost" in alert["explanation"]
    snapshot = client.get("/state").json()
    assert snapshot["approvals"][0]["kind"] == "unclosable_gap"
    detail = client.get(f"/cases/{alert['case_id']}").json()
    assert next(d for d in detail["decisions"] if d["id"] == alert["id"])["kind"] == "unclosable_gap"
    mail_before = _rows(rt, "emails")

    db.emit(rt.conn, rt.ws, "tick")
    pipeline.drain(rt)
    assert len(_rows(rt, "decisions", "dedupe_key LIKE 'unclosable:%'")) == 1
    response = client.post(f"/decisions/{alert['id']}/approve",
                           headers={"X-Lineguard-User": "P1"})
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["decided_by"] == "P1"
    assert _rows(rt, "cases", "kind = 'gap'")[0]["state"] == "unclosable"
    assert _rows(rt, "emails") == mail_before


def test_unclosable_alert_expires_when_a_plan_becomes_possible(tmp_path, monkeypatch):
    rt, client = _setup(tmp_path, monkeypatch)
    rt.conn.execute(
        "UPDATE facts SET data = json_set(data, '$.lead_time_hours', 2000) "
        "WHERE workspace_id = ? AND fact_type = 'offer'", (rt.ws,))
    db.emit(rt.conn, rt.ws, "tick")
    pipeline.drain(rt)
    alert = _rows(rt, "decisions", "dedupe_key LIKE 'unclosable:%'")[0]
    rt.conn.execute(
        "UPDATE facts SET data = json_set(data, '$.lead_time_hours', 24) "
        "WHERE workspace_id = ? AND fact_type = 'offer'", (rt.ws,))
    db.emit(rt.conn, rt.ws, "tick")
    pipeline.drain(rt)

    assert db.one(rt.conn, rt.ws,
                  "SELECT status FROM decisions WHERE workspace_id = ? AND id = ?",
                  (alert["id"],))["status"] == "expired"
    assert _rows(rt, "cases", "kind = 'gap'")[0]["state"] == "plan_proposed"
    assert client.post(f"/decisions/{alert['id']}/approve",
                       headers={"X-Lineguard-User": "P2"}).json()["status"] == "expired"


def test_known_person_approves_and_sends_exactly_one_mail(tmp_path, monkeypatch):
    rt, client = _setup(tmp_path, monkeypatch)
    decision_id = _rows(rt, "decisions")[0]["id"]

    assert client.post(f"/decisions/{decision_id}/approve").status_code == 401
    unknown = client.post(f"/decisions/{decision_id}/approve",
                          headers={"X-Lineguard-User": "nobody"})
    first = client.post(f"/decisions/{decision_id}/approve",
                        headers={"X-Lineguard-User": "P3"})
    second = client.post(f"/decisions/{decision_id}/approve",
                         headers={"X-Lineguard-User": "P3"})

    assert unknown.status_code == 403
    assert (first.status_code, first.json()["status"]) == (200, "approved")
    assert second.json()["status"] == "approved"
    mails = _rows(rt, "emails", "direction = 'out' AND commits_money = 1")
    assert len(mails) == 1
    assert mails[0]["status"] == "dry_run"
    assert mails[0]["to_addr"] == "jan@rahmenbau.example"
    assert mails[0]["approved_by"] == "P3"
    assert mails[0]["subject"].startswith("[RAD]")
    assert _rows(rt, "cases", "kind = 'gap'")[0]["state"] == "in_execution"


def test_routine_question_and_binding_order_are_separate_without_network(tmp_path, monkeypatch):
    rt, client = _setup(tmp_path, monkeypatch)
    rt.pack.auto_approve.action_kinds = ["status_request", "order"]

    def network_forbidden(*_args, **_kwargs):
        raise AssertionError("Mail test attempted to use the network")

    monkeypatch.setattr(mail.smtplib, "SMTP_SSL", network_forbidden)
    monkeypatch.setattr(mail.imaplib, "IMAP4_SSL", network_forbidden)
    case = _rows(rt, "cases", "kind = 'gap'")[0]
    option_id = db.insert(
        rt.conn, "options", rt.ws, case_id=case["id"], kind="expedite_inbound",
        title="Ask about delivery", qty_gain=20, supplier_id="LIEF-A",
        action_kind="status_request", data={"po_number": "BE-2001"},
        dedupe_key="test:routine", updated_at=clock.iso())
    event = {"payload": {"option_id": option_id}}

    action.handle_requested(rt, event)
    action.handle_requested(rt, event)
    question = _rows(rt, "emails", "routine = 1 AND direction = 'out'")
    order = _rows(rt, "emails", "commits_money = 1 AND direction = 'out'")
    assert len(question) == 1
    assert (question[0]["status"], question[0]["approved_by"]) == ("dry_run", "auto_approve")
    assert len(order) == 1
    assert order[0]["status"] == "draft"

    decision_id = _rows(rt, "decisions")[0]["id"]
    response = client.post(f"/decisions/{decision_id}/approve",
                           headers={"X-Lineguard-User": "P1"})
    assert response.status_code == 200
    assert _rows(rt, "emails", "commits_money = 1")[0]["status"] == "dry_run"
    assert _rows(rt, "emails", "commits_money = 1")[0]["approved_by"] == "P1"
    assert len(_rows(rt, "emails", "status = 'sent'")) == 0


def test_alternative_supplier_quote_does_not_count_as_available_stock(tmp_path, monkeypatch):
    rt, _ = _setup(tmp_path, monkeypatch)
    rt.conn.execute("UPDATE facts SET valid_until = '2027-02-28T00:00:00Z' "
                    "WHERE workspace_id = ? AND fact_type = 'offer'", (rt.ws,))
    db.insert(rt.conn, "contacts", rt.ws, supplier_id="ALT", name="Alternative",
              email="alternative@example.invalid", language="en")
    db.insert(rt.conn, "facts", rt.ws, fact_type="supplier_part",
              component_id="RAHMEN-01", supplier_id="ALT", source_rank=3,
              created_at=clock.iso())
    db.emit(rt.conn, rt.ws, "tick")
    pipeline.drain(rt)

    option = _rows(rt, "options", "kind = 'alt_source' AND supplier_id = 'ALT'")[0]
    assert option["qty_gain"] == 0
    assert db.loads(option["data"])["request_qty"] == 50
    quote = _rows(rt, "emails", "to_addr = 'alternative@example.invalid'")
    assert len(quote) == 1
    assert (quote[0]["status"], quote[0]["routine"], quote[0]["commits_money"]) == (
        "draft", 0, 0)
    assert "not an order" in quote[0]["body"]
    assert "quantity: 50" in quote[0]["body"]
    assert _rows(rt, "gaps", "is_current = 1")[0]["gap_qty"] == -50

    db.emit(rt.conn, rt.ws, "tick")
    pipeline.drain(rt)
    assert len(_rows(rt, "emails", "to_addr = 'alternative@example.invalid'")) == 1
    rt.conn.execute("UPDATE facts SET valid_until = '2027-03-10T00:00:00Z' "
                    "WHERE workspace_id = ? AND fact_type = 'offer'", (rt.ws,))
    db.emit(rt.conn, rt.ws, "tick")
    pipeline.drain(rt)
    assert _rows(rt, "options", f"id = {option['id']}")[0]["status"] == "expired"
    assert _rows(rt, "emails", "to_addr = 'alternative@example.invalid'")[0]["status"] == "discarded"
    rt.conn.execute("UPDATE facts SET valid_until = '2027-02-28T00:00:00Z' "
                    "WHERE workspace_id = ? AND fact_type = 'offer'", (rt.ws,))
    db.emit(rt.conn, rt.ws, "tick")
    pipeline.drain(rt)
    assert [row["status"] for row in _rows(
        rt, "emails", "to_addr = 'alternative@example.invalid'")] == ["discarded", "draft"]
    approvals.on_gap_closed(rt, {"payload": {"case_id": _rows(
        rt, "cases", "kind = 'gap'")[0]["id"]}})
    assert [row["status"] for row in _rows(
        rt, "emails", "to_addr = 'alternative@example.invalid'")] == ["discarded", "discarded"]


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


def test_any_known_person_can_approve_email_after_escalation(tmp_path, monkeypatch):
    rt, client = _setup(tmp_path, monkeypatch)
    decision = _rows(rt, "decisions")[0]
    email_id = _rows(rt, "emails", "status = 'draft'")[0]["id"]
    db.update(rt.conn, "decisions", rt.ws, decision["id"],
              approver_role="category_lead", needs_roles=["category_lead"],
              escalation_level=1)

    assert client.post(f"/emails/{email_id}/approve").status_code == 401
    assert client.post(f"/emails/{email_id}/approve",
                       headers={"X-Lineguard-User": "nobody"}).status_code == 403
    assert client.post(f"/emails/{email_id}/discard",
                       headers={"X-Lineguard-User": "P1"}).status_code == 403
    accepted = client.post(f"/emails/{email_id}/approve",
                           headers={"X-Lineguard-User": "P1"})
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "dry_run"
    assert accepted.json()["approved_by"] == "P1"


@pytest.mark.parametrize("route", ["decision", "email"])
def test_mail_failure_is_reported_without_automatic_retry(tmp_path, monkeypatch, route):
    rt, client = _setup(tmp_path, monkeypatch)
    decision_id = _rows(rt, "decisions")[0]["id"]
    email_id = _rows(rt, "emails", "status = 'draft'")[0]["id"]
    attempts = []

    def fail_send(*_args, **_kwargs):
        attempts.append(1)
        raise mail.MailError("SMTP connection failed")

    monkeypatch.setattr(mail.Mailer, "send", fail_send)
    path = (f"/decisions/{decision_id}/approve" if route == "decision"
            else f"/emails/{email_id}/approve")
    headers = {"X-Lineguard-User": "P1"}
    response = client.post(path, headers=headers)
    again = client.post(path, headers=headers)

    assert response.status_code == 502
    assert "Check the mailbox" in response.json()["detail"]
    assert again.status_code == 409
    assert attempts == [1]
    assert _rows(rt, "decisions")[0]["status"] == "approved"
    assert _rows(rt, "emails")[0]["status"] == "failed"


@pytest.mark.parametrize("change", [
    {"feasible": 0},
    {"role_in_plan": "none"},
    {"valid_until": "2027-02-28T00:00:00Z"},
])
def test_unavailable_option_cannot_be_approved_through_decision_or_email(tmp_path, monkeypatch, change):
    rt, client = _setup(tmp_path, monkeypatch)
    decision = _rows(rt, "decisions")[0]
    option = _rows(rt, "options")[0]
    email_id = _rows(rt, "emails", "status = 'draft'")[0]["id"]
    db.update(rt.conn, "options", rt.ws, option["id"], **change)

    decision_result = client.post(f"/decisions/{decision['id']}/approve",
                                  headers={"X-Lineguard-User": "P1"})
    email_result = client.post(f"/emails/{email_id}/approve",
                               headers={"X-Lineguard-User": "P1"})

    assert decision_result.status_code == 409
    assert email_result.status_code == 409
    assert _rows(rt, "decisions")[0]["status"] == "open"
    assert _rows(rt, "emails")[0]["status"] == "draft"


def test_rejected_decision_reopens_the_case(tmp_path, monkeypatch):
    rt, client = _setup(tmp_path, monkeypatch)
    decision_id = _rows(rt, "decisions")[0]["id"]
    response = client.post(f"/decisions/{decision_id}/reject",
                           headers={"X-Lineguard-User": "P1"}, json={"reason": "zu teuer"})
    pipeline.drain(rt)
    assert response.json()["status"] == "rejected"
    assert _rows(rt, "cases", "kind = 'gap'")[0]["state"] == "unclosable"
    assert [m["status"] for m in _rows(rt, "emails", "commits_money = 1")] == ["discarded"]
