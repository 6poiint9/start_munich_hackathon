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
              approved_at=now, writer="proposal_file" if result.get("fallback") else writer.name,
              external_ref=result["external_ref"])
    if result.get("new"):
        payload = correction["payload"]
        db.insert(
            rt.conn, "emails", rt.ws, case_id=correction["case_id"],
            direction="out", to_addr=person["name"],
            subject=f"Correction of goods receipt {payload['gr_number']}",
            body=(f"Approved correction of goods receipt {payload['gr_number']}: "
                  f"{payload['booked_qty']:g} booked, documents show {payload['proposed_qty']:g}. "
                  f"Booking: cancel the receipt and book a new goods receipt with "
                  f"{payload['proposed_qty']:g}.\nFile: {result['external_ref']}"),
            language="en", status="dry_run", routine=1,
            reason="Handover of the correction to the ERP owner",
            approved_by=person["person_id"], created_at=now)
    db.emit(rt.conn, rt.ws, "correction.approved",
            {"correction_id": correction_id, "case_id": correction["case_id"]},
            dedupe_key=f"correction.approved:{correction_id}")
    return _correction(rt, correction_id)


def reject_correction(rt: runtime.Runtime, correction_id: int, person: dict[str, Any], reason: str) -> dict[str, Any]:
    """Rejects a correction. Stock Truth counts the ERP quantity again."""
    correction = _correction(rt, correction_id)
    if correction["status"] != "proposed":
        raise StateError(f"The correction is already {correction['status']}")
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
              value_text=f"Correction rejected: {reason}", source_rank=1,
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
                    "text": f"Please count part {correction['component_id']} from "
                            f"goods receipt {correction['gr_number']}."})
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


def retire_unclosable_decisions(rt: runtime.Runtime, case_id: int, keep: str = "",
                               gap_id: int | None = None) -> None:
    """Expires open shortage alerts and preserves their history."""
    rt.conn.execute(
        "UPDATE decisions SET status = CASE WHEN status = 'open' THEN 'expired' ELSE status END, "
        "dedupe_key = 'unclosable:retired:' || id "
        "WHERE workspace_id = ? AND case_id = ? AND dedupe_key LIKE 'unclosable:%' "
        "AND dedupe_key NOT LIKE 'unclosable:retired:%' AND dedupe_key != ? "
        "AND (? IS NULL OR gap_id = ?)",
        (rt.ws, case_id, keep, gap_id, gap_id))


def approve_decision(rt: runtime.Runtime, decision_id: int, person: dict[str, Any], option_id: int | None = None) -> dict[str, Any]:
    """Approves one option of a decision and sends its mail, exactly once."""
    decision = _decision(rt, decision_id)
    if decision["status"] != "open":
        return decision
    if decision["dedupe_key"].startswith("unclosable:"):
        if option_id is not None:
            raise StateError("This alert has no delivery option")
        gap = db.one(
            rt.conn, rt.ws,
            "SELECT g.id FROM gaps g JOIN cases c "
            "ON c.id = g.case_id AND c.workspace_id = g.workspace_id "
            "WHERE g.workspace_id = ? AND g.id = ? AND g.is_current = 1 "
            "AND c.state = 'unclosable'", (decision["gap_id"],))
        if gap is None:
            raise StateError("This shortage alert is no longer current")
        db.update(rt.conn, "decisions", rt.ws, decision_id, status="approved",
                  decided_by=person["person_id"], decided_at=clock.iso())
        db.emit(rt.conn, rt.ws, "decision.approved", {"decision_id": decision_id},
                priority=3, dedupe_key=f"decision.approved:{decision_id}")
        return _decision(rt, decision_id)
    chosen = option_id or decision["recommended_option"]
    if chosen not in decision["options"]:
        raise StateError("This option does not belong to the decision")
    option = db.one(
        rt.conn, rt.ws,
        "SELECT o.*, g.is_current, c.state AS case_state FROM options o "
        "JOIN gaps g ON g.id = o.gap_id AND g.workspace_id = o.workspace_id "
        "JOIN cases c ON c.id = o.case_id AND c.workspace_id = o.workspace_id "
        "WHERE o.workspace_id = ? AND o.id = ? AND o.decision_id = ?",
        (chosen, decision_id))
    if option is None or not option["is_current"] or option["case_state"] in ("closed", "dismissed"):
        raise StateError("This option is no longer available")
    if (option["status"] != "proposed" or not option["feasible"]
            or option["role_in_plan"] not in ("primary", "backup")):
        raise StateError("This option is no longer available")
    if option["valid_until"] and clock.parse(option["valid_until"]) <= clock.now():
        raise StateError("This option is no longer available")
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
        raise StateError(f"The decision is already {decision['status']}")
    if decision["dedupe_key"].startswith("unclosable:"):
        raise StateError("This shortage alert can only be acknowledged")
    now = clock.iso()
    db.update(rt.conn, "decisions", rt.ws, decision_id, status="rejected",
              decided_by=person["person_id"], decided_at=now, reject_reason=reason,
              dedupe_key=f"{decision['dedupe_key']}:rejected:{decision_id}")
    for option_id in decision["options"]:
        db.update(rt.conn, "options", rt.ws, option_id, status="failed",
                  infeasible_reason=f"Rejected: {reason}")
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
    if row["decision_id"]:
        return decision_roles(rt, row["decision_id"])
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
        decision = approve_decision(rt, row["decision_id"], person, row["option_id"])
        if decision["status"] != "approved" or decision["recommended_option"] != row["option_id"]:
            raise StateError("This decision no longer permits the email")
    action.send(rt, email_id, person["person_id"])
    return _email(rt, email_id)


def discard_email(rt: runtime.Runtime, email_id: int, person: dict[str, Any]) -> dict[str, Any]:
    row = _email(rt, email_id)
    if row["status"] != "draft":
        raise StateError(f"The mail is already {row['status']}")
    db.update(rt.conn, "emails", rt.ws, email_id, status="discarded",
              approved_by=person["person_id"])
    return _email(rt, email_id)


def on_gap_closed(rt: runtime.Runtime, event: dict[str, Any]) -> None:
    """A closed gap confirms the options that were in execution."""
    case_id = event["payload"].get("case_id")
    if case_id is not None:
        retire_unclosable_decisions(rt, case_id, gap_id=event["payload"].get("gap_id"))
        rt.conn.execute(
            "UPDATE emails SET status = 'discarded' WHERE workspace_id = ? "
            "AND case_id = ? AND status = 'draft' AND action_id IN "
            "(SELECT id FROM actions WHERE workspace_id = ? AND kind = 'quote_request')",
            (rt.ws, case_id, rt.ws))
        rt.conn.execute(
            "UPDATE options SET status = 'expired', feasible = 0, role_in_plan = 'none', "
            "dedupe_key = dedupe_key || ':expired:' || id, "
            "infeasible_reason = 'The shortage is closed' "
            "WHERE workspace_id = ? AND case_id = ? AND kind = 'alt_source' "
            "AND status IN ('candidate', 'proposed')", (rt.ws, case_id))
    rt.conn.execute(
        "UPDATE options SET status = 'confirmed', updated_at = ? "
        "WHERE workspace_id = ? AND case_id = ? AND status = 'in_execution'",
        (clock.iso(), rt.ws, case_id))
