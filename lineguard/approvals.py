"""What happens when a person clicks: approve, reject, request a count.

Every function gets the person who clicked. The API checks the role
before it calls these functions (docs/betrieb-und-wartung.md W1).
"""

from typing import Any

from lineguard import clock
from lineguard import db
from lineguard import runtime
from lineguard.agents import action
from lineguard.connectors import erp_writer as erp_writer_module


class StateError(Exception):
    """The object is not in a state that allows this action."""


def _correction(rt: runtime.Runtime, correction_id: int) -> dict[str, Any]:
    row = db.one(
        rt.conn, rt.ws,
        "SELECT c.*, f.case_id, f.gr_number, f.component_id FROM corrections c "
        "JOIN booking_findings f ON f.id = c.finding_id "
        "WHERE c.workspace_id = ? AND c.id = ?", (correction_id,))
    if row is None:
        raise KeyError(correction_id)
    row["payload"] = db.loads(row["payload"], {})
    return row


def approve_correction(rt: runtime.Runtime, correction_id: int, person: dict[str, Any]) -> dict[str, Any]:
    """Approves a correction and hands it to the ERP writer.

    A second click on the same correction changes nothing.
    """
    correction = _correction(rt, correction_id)
    if correction["status"] != "proposed":
        return correction
    now = clock.iso()
    correction.update(approved_by=person["person_id"], approved_at=now)
    writer = rt.erp_writer or erp_writer_module.from_pack(
        rt.pack.erp_writer.mode, rt.ws)
    result = writer.apply(correction)
    db.update(rt.conn, "corrections", rt.ws, correction_id,
              status=result["status"], approved_by=person["person_id"],
              approved_at=now, writer=writer.name,
              external_ref=result["external_ref"])
    if result.get("new"):
        payload = correction["payload"]
        db.insert(
            rt.conn, "emails", rt.ws, case_id=correction["case_id"],
            direction="out", to_addr=person["name"],
            subject=f"Korrektur Wareneingang {payload['gr_number']}",
            body=(f"Freigegebene Korrektur für Wareneingang {payload['gr_number']}: "
                  f"{payload['booked_qty']:g} gebucht, {payload['proposed_qty']:g} belegt. "
                  f"Buchung: Storno des Belegs und neuer Wareneingang mit "
                  f"{payload['proposed_qty']:g}.\nDatei: {result['external_ref']}"),
            language="de", status="dry_run", routine=1,
            reason="Übergabe der Korrektur an den ERP-Verantwortlichen",
            approved_by=person["person_id"], created_at=now)
    db.emit(rt.conn, rt.ws, "correction.approved",
            {"correction_id": correction_id, "case_id": correction["case_id"]},
            dedupe_key=f"correction.approved:{correction_id}")
    return _correction(rt, correction_id)


def reject_correction(rt: runtime.Runtime, correction_id: int, person: dict[str, Any], reason: str) -> dict[str, Any]:
    """Rejects a correction. Stock Truth counts the ERP quantity again."""
    correction = _correction(rt, correction_id)
    if correction["status"] != "proposed":
        raise StateError(f"Korrektur ist schon {correction['status']}")
    now = clock.iso()
    db.update(rt.conn, "corrections", rt.ws, correction_id, status="rejected",
              reject_reason=reason, approved_by=person["person_id"],
              approved_at=now)
    db.update(rt.conn, "booking_findings", rt.ws, correction["finding_id"],
              status="dismissed")
    db.update(rt.conn, "cases", rt.ws, correction["case_id"],
              state="dismissed", updated_at=now)
    db.insert(rt.conn, "facts", rt.ws, fact_type="info",
              ref=correction["gr_number"], component_id=correction["component_id"],
              value_text=f"Korrektur abgelehnt: {reason}", source_rank=1,
              extracted_by="human", source_locator=person["person_id"],
              created_at=now)
    db.emit(rt.conn, rt.ws, "correction.rejected",
            {"correction_id": correction_id, "case_id": correction["case_id"]},
            dedupe_key=f"correction.rejected:{correction_id}")
    return _correction(rt, correction_id)


def request_count(rt: runtime.Runtime, correction_id: int, person: dict[str, Any]) -> dict[str, Any]:
    """Asks the site for a physical count before the correction is decided."""
    correction = _correction(rt, correction_id)
    key = f"{correction['case_id']}:count_request:{correction['component_id']}"
    existing = db.one(
        rt.conn, rt.ws,
        "SELECT * FROM actions WHERE workspace_id = ? AND idempotency_key = ?",
        (key,))
    if existing is None:
        action_id = db.insert(
            rt.conn, "actions", rt.ws, case_id=correction["case_id"],
            type="count_request", kind="count_request", target="site_lead",
            status="approved", idempotency_key=key, created_at=clock.iso(),
            result={"component_id": correction["component_id"],
                    "gr_number": correction["gr_number"],
                    "requested_by": person["person_id"],
                    "text": f"Bitte Teil {correction['component_id']} aus "
                            f"Wareneingang {correction['gr_number']} zählen."})
        db.emit(rt.conn, rt.ws, "action.created",
                {"action_id": action_id, "case_id": correction["case_id"]},
                dedupe_key=f"action.created:{action_id}")
    return _correction(rt, correction_id)


def _decision(rt: runtime.Runtime, decision_id: int) -> dict[str, Any]:
    row = db.one(rt.conn, rt.ws,
                 "SELECT * FROM decisions WHERE workspace_id = ? AND id = ?",
                 (decision_id,))
    if row is None:
        raise KeyError(decision_id)
    row["options"] = db.loads(row["options"], [])
    row["needs_roles"] = db.loads(row["needs_roles"], [])
    return row


def decision_roles(rt: runtime.Runtime, decision_id: int) -> list[str]:
    """The roles of which one must approve this decision."""
    return _decision(rt, decision_id)["needs_roles"]


def approve_decision(rt: runtime.Runtime, decision_id: int, person: dict[str, Any], option_id: int | None = None) -> dict[str, Any]:
    """Approves one option of a decision and sends its mail, exactly once."""
    decision = _decision(rt, decision_id)
    if decision["status"] != "open":
        return decision
    chosen = option_id or decision["recommended_option"]
    if chosen not in decision["options"]:
        raise StateError("Diese Option gehört nicht zu der Entscheidung")
    now = clock.iso()
    db.update(rt.conn, "decisions", rt.ws, decision_id, status="approved",
              decided_by=person["person_id"], decided_at=now,
              recommended_option=chosen)
    db.update(rt.conn, "options", rt.ws, chosen, status="approved",
              decision_id=decision_id)
    if decision["case_id"]:
        db.update(rt.conn, "cases", rt.ws, decision["case_id"], state="approved",
                  updated_at=now)
    draft = db.one(
        rt.conn, rt.ws,
        "SELECT e.id FROM emails e JOIN actions a ON a.id = e.action_id "
        "WHERE e.workspace_id = ? AND a.option_id = ? AND e.status = 'draft'",
        (chosen,))
    if draft:
        action.send(rt, draft["id"], person["person_id"])
    else:
        action.handle_requested(rt, {"payload": {
            "option_id": chosen, "approved_by": person["person_id"]}})
    db.update(rt.conn, "options", rt.ws, chosen, status="in_execution")
    db.emit(rt.conn, rt.ws, "decision.approved", {"decision_id": decision_id},
            priority=3, dedupe_key=f"decision.approved:{decision_id}")
    return _decision(rt, decision_id)


def reject_decision(rt: runtime.Runtime, decision_id: int, person: dict[str, Any], reason: str) -> dict[str, Any]:
    """Rejects a decision. The loop looks for another way."""
    decision = _decision(rt, decision_id)
    if decision["status"] != "open":
        raise StateError(f"Entscheidung ist schon {decision['status']}")
    now = clock.iso()
    db.update(rt.conn, "decisions", rt.ws, decision_id, status="rejected",
              decided_by=person["person_id"], decided_at=now, reject_reason=reason,
              dedupe_key=f"{decision['dedupe_key']}:rejected:{decision_id}")
    for option_id in decision["options"]:
        db.update(rt.conn, "options", rt.ws, option_id, status="failed",
                  infeasible_reason=f"Abgelehnt: {reason}")
        rt.conn.execute(
            "UPDATE emails SET status = 'discarded' WHERE workspace_id = ? "
            "AND status = 'draft' AND action_id IN (SELECT id FROM actions "
            "WHERE workspace_id = ? AND option_id = ?)", (rt.ws, rt.ws, option_id))
    if decision["case_id"]:
        db.update(rt.conn, "cases", rt.ws, decision["case_id"], state="open",
                  updated_at=now)
    db.emit(rt.conn, rt.ws, "decision.rejected", {"decision_id": decision_id},
            dedupe_key=f"decision.rejected:{decision_id}")
    return _decision(rt, decision_id)


def _email(rt: runtime.Runtime, email_id: int) -> dict[str, Any]:
    row = db.one(
        rt.conn, rt.ws,
        "SELECT e.*, a.decision_id, a.option_id FROM emails e LEFT JOIN actions a "
        "ON a.id = e.action_id WHERE e.workspace_id = ? AND e.id = ?", (email_id,))
    if row is None:
        raise KeyError(email_id)
    return row


def email_roles(rt: runtime.Runtime, email_id: int) -> list[str] | None:
    """Roles needed to send a draft. None means any known person."""
    row = _email(rt, email_id)
    if not row["option_id"]:
        return None
    option = db.one(rt.conn, rt.ws,
                    "SELECT needs_roles FROM options WHERE workspace_id = ? AND id = ?",
                    (row["option_id"],))
    return db.loads(option["needs_roles"], []) or None if option else None


def approve_email(rt: runtime.Runtime, email_id: int, person: dict[str, Any], subject: str | None = None, body: str | None = None) -> dict[str, Any]:
    """Sends a draft. A draft of a decision approves that decision too."""
    row = _email(rt, email_id)
    if row["status"] != "draft":
        return row
    if subject or body:
        db.update(rt.conn, "emails", rt.ws, email_id,
                  subject=subject or row["subject"], body=body or row["body"])
    if row["decision_id"] and row["option_id"]:
        approve_decision(rt, row["decision_id"], person, row["option_id"])
    action.send(rt, email_id, person["person_id"])
    return _email(rt, email_id)


def discard_email(rt: runtime.Runtime, email_id: int, person: dict[str, Any]) -> dict[str, Any]:
    row = _email(rt, email_id)
    if row["status"] != "draft":
        raise StateError(f"Mail ist schon {row['status']}")
    db.update(rt.conn, "emails", rt.ws, email_id, status="discarded",
              approved_by=person["person_id"])
    return _email(rt, email_id)


def on_gap_closed(rt: runtime.Runtime, event: dict[str, Any]) -> None:
    """A closed gap confirms the options that were in execution."""
    rt.conn.execute(
        "UPDATE options SET status = 'confirmed', updated_at = ? "
        "WHERE workspace_id = ? AND case_id = ? AND status = 'in_execution'",
        (clock.iso(), rt.ws, event["payload"].get("case_id")))
