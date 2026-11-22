"""Builds the JSON views for the page: the state and one case.

The header numbers are never stored. `/state` computes them from the
facts each time it is read (docs/skalierung.md N2).
"""

import datetime
from typing import Any

from lineguard import clock
from lineguard import config
from lineguard import db
from lineguard import runtime
from lineguard.coverage import core
from lineguard.policy import engine

_PLANNED_STATES = ("approved", "in_execution", "confirmed")
_FACT_LABELS = {
    "stock_qty": "Bestand laut ERP", "gr_qty": "Wareneingang gebucht",
    "po_line": "Bestellposition", "delivery_note_qty": "Menge auf dem Lieferschein",
    "delivery_note_weight_kg": "Gewicht auf dem Lieferschein",
    "delivery_note_packages": "Packstücke auf dem Lieferschein",
    "inspection_result": "Prüfergebnis", "released_rev": "Freigegebene Revision",
    "artwork_rev": "Revision der Bestellung", "shipment": "Sendung",
    "planned_inbound": "Zulauf laut Planung", "inbound_qty": "Zulauf mit Beleg",
    "offer": "Angebot", "not_stocked": "Nicht lagergeführt", "note": "Bemerkung",
    "counted_qty": "Gezählte Menge", "gr_exception_qty": "Abweichung laut Bemerkung",
    "validity": "Gültigkeit", "release_status": "Lieferanten-Freigabe",
    "supplier_condition": "Bedingung des Lieferanten", "demand": "Bedarf", "packed_qty": "Gepackt", "policy_rule": "Regel",
}


def _iso(moment: datetime.datetime | None) -> str | None:
    return clock.iso(moment) if moment else None


def people(rt: runtime.Runtime) -> list[dict[str, Any]]:
    """Persons with the roles they hold now, for 'Angemeldet als'."""
    return sorted(engine.persons(rt).values(), key=lambda p: str(p["name"]))


def _case_summary(row: dict[str, Any], gaps: dict[int, dict[str, Any]], pending: dict[int, dict[str, int]]) -> dict[str, Any]:
    gap = gaps.get(row["id"], {})
    return {
        "id": row["id"], "kind": row["kind"], "rule": row["rule"],
        "title": row["title"], "impact": row["impact"], "state": row["state"],
        "rank": row["rank"], "component_id": row["component_id"],
        "product_id": row["product_id"], "supplier_id": row["supplier_id"],
        "po_number": row["po_number"], "due_at": row["due_at"],
        "act_by": row["act_by"] or gap.get("act_by"),
        "breaks_at": gap.get("breaks_at"), "owner_role": row["owner_role"],
        "gap_qty": gap.get("gap_qty"), "units_at_risk": gap.get("units_at_risk"),
        "residual_qty": gap.get("residual_qty"),
        "pending": pending.get(row["id"], {"decisions": 0, "corrections": 0, "emails": 0}),
        "updated_at": row["updated_at"],
    }


def _pending(rt: runtime.Runtime) -> dict[int, dict[str, int]]:
    counts: dict[int, dict[str, int]] = {}

    def add(sql: str, name: str) -> None:
        for row in db.rows(rt.conn, rt.ws, sql):
            if row["case_id"] is not None:
                counts.setdefault(row["case_id"], {"decisions": 0, "corrections": 0, "emails": 0})[name] = row["n"]
    add("SELECT case_id, COUNT(*) AS n FROM decisions WHERE workspace_id = ? "
        "AND status = 'open' GROUP BY case_id", "decisions")
    add("SELECT f.case_id AS case_id, COUNT(*) AS n FROM corrections c JOIN "
        "booking_findings f ON f.id = c.finding_id WHERE c.workspace_id = ? "
        "AND c.status = 'proposed' GROUP BY f.case_id", "corrections")
    add("SELECT case_id, COUNT(*) AS n FROM emails WHERE workspace_id = ? "
        "AND status = 'draft' GROUP BY case_id", "emails")
    return counts


def _units_by_state(product: core.ProductState, cases: list[dict[str, Any]]) -> dict[str, float]:
    secured = min(product.still_to_pack, product.buildable.get("secured", 0.0))
    rest = product.still_to_pack - secured
    own = [c for c in cases if c["kind"] == "gap" and c["product_id"] == product.product_id
           and c["state"] not in ("closed", "dismissed")]
    unclosable = min(rest, sum(
        (c.get("residual_qty") or c.get("units_at_risk") or 0)
        for c in own if c["state"] == "unclosable"))
    planned = 0.0
    if own and all(c["state"] in _PLANNED_STATES for c in own):
        planned = rest - unclosable
    return {"secured": secured, "planned": planned,
            "open": max(rest - planned - unclosable, 0.0), "unclosable": unclosable}


def approvals(rt: runtime.Runtime) -> list[dict[str, Any]]:
    """Everything that waits for a click of a person, most urgent first."""
    found = []
    for row in db.rows(
            rt.conn, rt.ws,
            "SELECT d.*, o.kind AS option_kind, o.title AS option_title, "
            "o.cost_eur, o.supplier_id, o.data AS option_data, o.arrives_at "
            "FROM decisions d LEFT JOIN options o ON o.id = d.recommended_option "
            "WHERE d.workspace_id = ? AND d.status = 'open'"):
        data = db.loads(row["option_data"], {})
        mail = db.one(
            rt.conn, rt.ws,
            "SELECT e.id, e.to_addr, e.subject, e.body, e.language, e.commits_money "
            "FROM emails e JOIN actions a ON a.id = e.action_id "
            "WHERE e.workspace_id = ? AND a.option_id = ? AND e.status = 'draft'",
            (row["recommended_option"],))
        found.append({
            "id": f"decision:{row['id']}", "type": "decision", "object_id": row["id"],
            "case_id": row["case_id"], "kind": row["option_kind"],
            "title": row["option_title"] or row["title"], "summary": row["explanation"],
            "needs_roles": db.loads(row["needs_roles"], []),
            "approver_name": row["approver_name"], "deadline": row["deadline"],
            "cost_eur": row["cost_eur"], "cost_unknown": bool(data.get("cost_unknown")),
            "commits_money": bool(mail and mail["commits_money"]) or bool(row["cost_eur"]),
            "supplier_id": row["supplier_id"], "arrives_at": row["arrives_at"],
            "condition": data.get("condition"), "conflict": data.get("conflict"),
            "note": data.get("note"), "after_deadline": bool(data.get("after_deadline")),
            "email": mail, "created_at": row["created_at"],
        })
    for row in db.rows(
            rt.conn, rt.ws,
            "SELECT c.*, f.case_id, f.gr_number, f.component_id FROM corrections c "
            "JOIN booking_findings f ON f.id = c.finding_id "
            "WHERE c.workspace_id = ? AND c.status = 'proposed'"):
        payload = db.loads(row["payload"], {})
        person = engine.resolve_person(rt, row["approver_role"])
        found.append({
            "id": f"correction:{row['id']}", "type": "correction", "object_id": row["id"],
            "case_id": row["case_id"], "kind": "erp_correction",
            "title": f"Wareneingang {row['gr_number']} korrigieren",
            "summary": (f"Gebucht sind {payload.get('booked_qty', 0):g} Stück "
                        f"{row['component_id']}, belegt sind "
                        f"{payload.get('proposed_qty', 0):g}."),
            "needs_roles": [row["approver_role"]],
            "approver_name": person["name"] if person else None, "deadline": None,
            "cost_eur": 0.0, "cost_unknown": False, "commits_money": False,
            "supplier_id": None, "arrives_at": None, "condition": None,
            "conflict": None, "note": None, "after_deadline": False, "email": None,
            "created_at": row["created_at"],
        })
    found.sort(key=lambda item: (item["deadline"] or "9999", item["created_at"] or ""))
    return found


def _recent_approvals(rt: runtime.Runtime) -> list[dict[str, Any]]:
    """The last clicks with their effect, newest first."""
    names = {key: value["name"] for key, value in engine.persons(rt).items()}
    found = []
    for row in db.rows(
            rt.conn, rt.ws,
            "SELECT d.id, d.case_id, d.status, d.decided_by, d.decided_at, "
            "o.title AS option_title, d.title, "
            "(SELECT e.status FROM emails e JOIN actions a ON a.id = e.action_id "
            " WHERE a.option_id = d.recommended_option AND e.direction = 'out' "
            " ORDER BY e.id DESC LIMIT 1) AS mail_status, "
            "(SELECT e.to_addr FROM emails e JOIN actions a ON a.id = e.action_id "
            " WHERE a.option_id = d.recommended_option AND e.direction = 'out' "
            " ORDER BY e.id DESC LIMIT 1) AS mail_to "
            "FROM decisions d LEFT JOIN options o ON o.id = d.recommended_option "
            "WHERE d.workspace_id = ? AND d.status IN ('approved', 'rejected') "
            "ORDER BY d.decided_at DESC LIMIT 5"):
        found.append({
            "id": f"decision:{row['id']}", "type": "decision", "case_id": row["case_id"],
            "title": row["option_title"] or row["title"], "status": row["status"],
            "decided_by": names.get(row["decided_by"], row["decided_by"]),
            "decided_at": row["decided_at"], "mail_status": row["mail_status"],
            "mail_to": row["mail_to"]})
    for row in db.rows(
            rt.conn, rt.ws,
            "SELECT c.id, c.status, c.approved_by, c.approved_at, f.case_id, "
            "f.gr_number FROM corrections c JOIN booking_findings f "
            "ON f.id = c.finding_id WHERE c.workspace_id = ? "
            "AND c.status != 'proposed' AND c.approved_at IS NOT NULL "
            "ORDER BY c.approved_at DESC LIMIT 5"):
        found.append({
            "id": f"correction:{row['id']}", "type": "correction",
            "case_id": row["case_id"],
            "title": f"Wareneingang {row['gr_number']} korrigieren",
            "status": row["status"],
            "decided_by": names.get(row["approved_by"], row["approved_by"]),
            "decided_at": row["approved_at"], "mail_status": None, "mail_to": None})
    found.sort(key=lambda item: item["decided_at"] or "", reverse=True)
    return found[:5]


def state(rt: runtime.Runtime, at: datetime.datetime | None = None) -> dict[str, Any]:
    """The page state: header, cases 'Jetzt' and 'Danach', counters."""
    computed = core.compute(rt, at)
    top_n = config.get_int("STATE_TOP_N", 50)
    gaps = {
        g["case_id"]: g for g in db.rows(
            rt.conn, rt.ws,
            "SELECT * FROM gaps WHERE workspace_id = ? AND is_current = 1")}
    pending = _pending(rt)
    cases = [
        _case_summary(c, gaps, pending) for c in db.rows(
            rt.conn, rt.ws,
            "SELECT * FROM cases WHERE workspace_id = ? "
            "AND state NOT IN ('closed', 'dismissed') "
            "ORDER BY COALESCE(rank, 999), COALESCE(act_by, due_at, '9999'), id")]
    now_cases = [c for c in cases if c["impact"] == "deadline_blocker"]
    later_cases = sorted(
        (c for c in cases if c["impact"] == "after_deadline"),
        key=lambda c: c["act_by"] or c["due_at"] or "9999")
    files = db.one(
        rt.conn, rt.ws,
        "SELECT COUNT(*) AS total, SUM(parse_status = 'parsed') AS read, "
        "SUM(parse_status = 'failed') AS failed, "
        "SUM(parse_status = 'manual') AS manual "
        "FROM files WHERE workspace_id = ? AND is_current = 1") or {}
    stops = [c for c in computed.components.values() if c.breaks_at and c.stocked]
    first_stop = min(stops, key=lambda c: c.breaks_at) if stops else None
    findings = db.one(
        rt.conn, rt.ws,
        "SELECT COUNT(*) AS n FROM booking_findings WHERE workspace_id = ?") or {}
    receipts = len(core.current_facts(rt, "gr_qty"))
    products = []
    for product in sorted(computed.products.values(), key=lambda p: p.product_id):
        products.append({
            "product_id": product.product_id, "description": product.description,
            "demand": product.demand, "packed": product.packed,
            "packed_as_of": _iso(product.packed_as_of),
            "still_to_pack": product.still_to_pack,
            "rate_per_hour": product.rate_per_hour, "hours_left": product.hours_left,
            "coverage_system": product.coverage.get("system"),
            "coverage_secured": product.coverage.get("secured"),
            "units": _units_by_state(product, cases),
            "limiting_component": product.limiting_component,
        })
    return {
        "workspace": rt.ws, "customer": rt.pack.customer, "labels": rt.pack.labels,
        "at": _iso(computed.at), "next_due": _iso(computed.next_due),
        "timezone": rt.pack.timezone,
        "import": {"files_total": files.get("total") or 0,
                   "files_read": files.get("read") or 0,
                   "failed": files.get("failed") or 0,
                   "manual": files.get("manual") or 0},
        "products": products,
        "first_stop": {
            "component_id": first_stop.component_id,
            "description": first_stop.description,
            "breaks_at": _iso(first_stop.breaks_at)} if first_stop else None,
        "cases_now": now_cases[:top_n], "cases_later": later_cases[:top_n],
        "counters": {
            "now_total": len(now_cases), "later_total": len(later_cases),
            "open_decisions": sum(c["pending"]["decisions"] for c in cases),
            "open_corrections": sum(c["pending"]["corrections"] for c in cases),
            "open_emails": sum(c["pending"]["emails"] for c in cases)},
        "booking_review": {"receipts_checked": receipts, "findings": findings.get("n") or 0},
        "problems": db.rows(
            rt.conn, rt.ws,
            "SELECT id AS event_id, type, error FROM events "
            "WHERE workspace_id = ? AND status = 'failed' ORDER BY id DESC LIMIT 20"),
        "approvals": approvals(rt), "approvals_done": _recent_approvals(rt),
        "people": people(rt),
        "mail_mode": config.get("MAIL_MODE", "DRY_RUN"),
    }


def evidence(rt: runtime.Runtime, fact_ids: list[int]) -> list[dict[str, Any]]:
    """Facts with file and place, for the evidence view."""
    if not fact_ids:
        return []
    marks = ", ".join("?" for _ in fact_ids)
    found = db.rows(
        rt.conn, rt.ws,
        "SELECT f.*, x.path AS file_path, x.version AS file_version FROM facts f "
        "LEFT JOIN files x ON x.id = f.source_file_id "
        f"WHERE f.workspace_id = ? AND f.id IN ({marks}) ORDER BY f.source_rank, f.id",
        fact_ids)
    return [{
        "fact_id": f["id"], "fact_type": f["fact_type"],
        "label": _FACT_LABELS.get(f["fact_type"], f["fact_type"]),
        "qty": f["qty"], "value_num": f["value_num"], "value_text": f["value_text"],
        "rev": f["rev"], "batch": f["batch"], "ref": f["ref"],
        "po_number": f["po_number"], "component_id": f["component_id"],
        "eta": f["eta"], "valid_until": f["valid_until"], "doc_date": f["doc_date"],
        "as_of": f["as_of"], "source_rank": f["source_rank"],
        "confidence": f["confidence"], "extracted_by": f["extracted_by"],
        "suspicious": bool(f["suspicious"]), "data": db.loads(f["data"], {}),
        "file": {"id": f["source_file_id"], "path": f["file_path"],
                 "version": f["file_version"]} if f["source_file_id"] else None,
        "locator": f["source_locator"],
    } for f in found]


def case(rt: runtime.Runtime, case_id: int) -> dict[str, Any] | None:
    """One case with evidence, finding, options, decisions and mails."""
    row = db.one(rt.conn, rt.ws,
                 "SELECT * FROM cases WHERE workspace_id = ? AND id = ?", (case_id,))
    if row is None:
        return None
    gaps = {
        g["case_id"]: g for g in db.rows(
            rt.conn, rt.ws,
            "SELECT * FROM gaps WHERE workspace_id = ? AND is_current = 1 "
            "AND case_id = ?", (case_id,))}
    summary = _case_summary(row, gaps, _pending(rt))
    summary["detail"] = db.loads(row["detail"], {})
    finding = db.one(
        rt.conn, rt.ws,
        "SELECT * FROM booking_findings WHERE workspace_id = ? AND case_id = ?",
        (case_id,))
    if finding is None and row["kind"] == "gap":
        # The correction card also shows in the gap that the finding causes.
        finding = db.one(
            rt.conn, rt.ws,
            "SELECT * FROM booking_findings WHERE workspace_id = ? "
            "AND component_id = ? AND status IN ('proposed', 'needs_count') "
            "ORDER BY ABS(delta_qty) DESC", (row["component_id"],))
    corrections = []
    fact_ids = list(db.loads(row["evidence_fact_ids"], []))
    if finding:
        finding["checks"] = db.loads(finding["checks"], {})
        for check in finding["checks"].values():
            fact_ids.extend(check.get("fact_ids") or [])
        corrections = db.rows(
            rt.conn, rt.ws,
            "SELECT * FROM corrections WHERE workspace_id = ? AND finding_id = ? "
            "ORDER BY id", (finding["id"],))
        for correction in corrections:
            correction["payload"] = db.loads(correction["payload"], {})
    options = db.rows(
        rt.conn, rt.ws,
        "SELECT * FROM options WHERE workspace_id = ? AND case_id = ? "
        "ORDER BY feasible DESC, role_in_plan = 'primary' DESC, cost_eur, id",
        (case_id,))
    for option in options:
        for key in ("units_gained", "needs_roles", "evidence_fact_ids"):
            option[key] = db.loads(option[key], [] if key != "units_gained" else {})
        fact_ids.extend(option["evidence_fact_ids"])
    decisions = db.rows(
        rt.conn, rt.ws,
        "SELECT * FROM decisions WHERE workspace_id = ? AND case_id = ? "
        "ORDER BY id DESC", (case_id,))
    for decision in decisions:
        decision["options"] = db.loads(decision["options"], [])
        decision["needs_roles"] = db.loads(decision["needs_roles"], [])
    return {
        "case": summary,
        "evidence": evidence(rt, sorted(set(int(i) for i in fact_ids if i))),
        "finding": finding, "corrections": corrections, "options": options,
        "decisions": decisions,
        "emails": db.rows(
            rt.conn, rt.ws,
            "SELECT * FROM emails WHERE workspace_id = ? AND case_id = ? "
            "ORDER BY id", (case_id,)),
        "actions": db.rows(
            rt.conn, rt.ws,
            "SELECT * FROM actions WHERE workspace_id = ? AND case_id = ? "
            "ORDER BY id", (case_id,)),
    }
