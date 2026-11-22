"""Booking check: finds wrong goods receipts when they are booked.

Plain code, no LLM. Each receipt is compared with independent sources:
order, delivery note, weight, packages, history and the remark of the
booking (docs/buchungspruefung.md). A new check is one function plus one
entry in `CHECKS`.
"""

from collections.abc import Callable
import dataclasses
import statistics
from typing import Any

from lineguard import clock
from lineguard import db
from lineguard import runtime
from lineguard.coverage import core

_MATCH_TOLERANCE = 0.02
_MIN_HISTORY = 3
_MAX_SPREAD = 0.15
_SHIFT_FACTORS = (10.0, 100.0, 0.1, 0.01)
_HARD_CHECKS = ("gr_vs_po", "gr_vs_delivery_note", "duplicate", "unreferenced",
                "gr_note_exception")
_SOFT_CHECKS = ("gr_vs_weight", "gr_vs_packages", "gr_vs_history")
_KEEP_STATUS = ("dismissed", "corrected")


@dataclasses.dataclass
class Result:
    """The outcome of one check for one receipt."""

    status: str  # pass, fail or no_data
    value: float | None = None
    fact_ids: list[int] = dataclasses.field(default_factory=list)
    source: str | None = None  # document that backs `value` as a quantity

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "value": self.value,
                "fact_ids": self.fact_ids}


@dataclasses.dataclass
class Context:
    """Facts grouped once for all receipts of a run."""

    rt: runtime.Runtime
    receipts: list[dict[str, Any]]
    ordered: dict[tuple[str, str], tuple[float, list[int]]]
    by_position: dict[tuple[str, str], list[dict[str, Any]]]
    by_note: dict[str, list[dict[str, Any]]]
    note_qty: dict[str, list[dict[str, Any]]]
    note_weight: dict[str, dict[str, Any]]
    note_packages: dict[str, dict[str, Any]]
    exceptions: dict[str, list[dict[str, Any]]]
    components: set[str]
    unit_weight: dict[str, float]
    per_package: dict[str, float]
    single_part_notes: set[str]


def _close(left: float, right: float) -> bool:
    return abs(left - right) <= _MATCH_TOLERANCE * max(abs(left), abs(right), 1.0)


def _position(fact: dict[str, Any]) -> tuple[str, str]:
    return (str(fact.get("po_number") or ""), str(fact.get("po_line") or ""))


def build_context(rt: runtime.Runtime) -> Context:
    """Loads and groups the facts that the checks compare."""
    receipts = core.current_facts(rt, "gr_qty")
    ordered: dict[tuple[str, str], tuple[float, list[int]]] = {}
    for fact in core.current_facts(rt, "po_line"):
        qty, ids = ordered.get(_position(fact), (0.0, []))
        ordered[_position(fact)] = (qty + (fact["qty"] or 0), [*ids, fact["id"]])
    by_position: dict[tuple[str, str], list[dict[str, Any]]] = {}
    by_note: dict[str, list[dict[str, Any]]] = {}
    for receipt in receipts:
        by_position.setdefault(_position(receipt), []).append(receipt)
        if receipt.get("value_text"):
            by_note.setdefault(receipt["value_text"], []).append(receipt)
        if _position(receipt) not in ordered and receipt.get("value_num"):
            ordered[_position(receipt)] = (receipt["value_num"], [receipt["id"]])
    note_qty: dict[str, list[dict[str, Any]]] = {}
    for fact in core.current_facts(rt, "delivery_note_qty"):
        note_qty.setdefault(fact["ref"], []).append(fact)
    note_weight = {f["ref"]: f for f in core.current_facts(rt, "delivery_note_weight_kg")}
    note_packages = {f["ref"]: f for f in core.current_facts(rt, "delivery_note_packages")}
    exceptions: dict[str, list[dict[str, Any]]] = {}
    for fact in core.current_facts(rt, "gr_exception_qty"):
        exceptions.setdefault(str(fact.get("ref") or ""), []).append(fact)
    components = {
        r["component_id"] for r in db.rows(
            rt.conn, rt.ws,
            "SELECT component_id FROM components WHERE workspace_id = ?")}
    weights: dict[str, list[float]] = {}
    packages: dict[str, list[float]] = {}
    single_part_notes = set()
    for note, facts in note_qty.items():
        qty = sum(f["qty"] or 0 for f in facts)
        parts = {f["component_id"] for f in facts if f["component_id"]}
        # Weight and packages cover the whole note. They say something
        # about one part only when the note holds one part.
        if qty <= 0 or len(parts) != 1 or len(facts) != 1:
            continue
        single_part_notes.add(note)
        part = parts.pop()
        if note in note_weight and note_weight[note]["value_num"]:
            weights.setdefault(part, []).append(note_weight[note]["value_num"] / qty)
        if note in note_packages and note_packages[note]["value_num"]:
            packages.setdefault(part, []).append(qty / note_packages[note]["value_num"])
    return Context(
        rt, receipts, ordered, by_position, by_note, note_qty, note_weight,
        note_packages, exceptions, components,
        _stable_medians(weights), _stable_medians(packages), single_part_notes)


def _stable_medians(samples: dict[str, list[float]]) -> dict[str, float]:
    """The median per part, only where the samples agree with each other.

    Notes from different suppliers use different packaging. A reference
    with a wide spread would raise false alarms, so it is dropped.
    """
    medians = {}
    for part, values in samples.items():
        if len(values) < _MIN_HISTORY:
            continue
        median = statistics.median(values)
        spread = statistics.median(abs(v - median) for v in values)
        if median > 0 and spread / median <= _MAX_SPREAD:
            medians[part] = median
    return medians


# ---------- checks ----------


def gr_vs_po(ctx: Context, receipt: dict[str, Any]) -> Result:
    """Sum of all receipts of the order position against the ordered qty."""
    found = ctx.ordered.get(_position(receipt))
    if not found or not found[0]:
        return Result("no_data")
    ordered, fact_ids = found
    limit = ordered * (1 + ctx.rt.pack.booking_check.over_tolerance)
    siblings = ctx.by_position[_position(receipt)]
    total = sum(r["qty"] or 0 for r in siblings)
    largest = max(siblings, key=lambda r: r["qty"] or 0)
    over = total > limit and ((receipt["qty"] or 0) > limit or receipt["id"] == largest["id"])
    return Result("fail" if over else "pass", ordered, fact_ids, "order")


def gr_vs_delivery_note(ctx: Context, receipt: dict[str, Any]) -> Result:
    """Booked quantity against the quantity on the delivery note."""
    note = receipt.get("value_text")
    lines = ctx.note_qty.get(note or "", [])
    if not lines:
        return Result("no_data")
    booked = [r["qty"] or 0 for r in ctx.by_note.get(note, [receipt])]
    noted = [f["qty"] or 0 for f in lines]
    fact_ids = [f["id"] for f in lines]
    if _close(sum(booked), sum(noted)):
        return Result("pass", receipt["qty"], fact_ids, f"note:{note}")
    same_part = [f["qty"] or 0 for f in lines
                 if f["component_id"] == receipt["component_id"]]
    value = sum(same_part) if same_part else sum(noted)
    if len(booked) > 1 and any(_close(receipt["qty"] or 0, q) for q in noted):
        return Result("pass", receipt["qty"], fact_ids, f"note:{note}")
    return Result("fail", value, fact_ids, f"note:{note}")


def gr_vs_weight(ctx: Context, receipt: dict[str, Any]) -> Result:
    """Weight on the delivery note against booked quantity times unit weight."""
    weight = ctx.note_weight.get(receipt.get("value_text") or "")
    unit = ctx.unit_weight.get(receipt.get("component_id") or "")
    if receipt.get("value_text") not in ctx.single_part_notes:
        return Result("no_data")
    if not weight or not weight["value_num"] or not unit or not receipt["qty"]:
        return Result("no_data")
    implied = weight["value_num"] / unit
    low, high = ctx.rt.pack.booking_check.weight_ratio_range
    ratio = implied / receipt["qty"]
    return Result("pass" if low <= ratio <= high else "fail", implied,
                  [weight["id"]], f"weight:{receipt['value_text']}")


def gr_vs_packages(ctx: Context, receipt: dict[str, Any]) -> Result:
    """Packages on the delivery note against the usual quantity per package."""
    packages = ctx.note_packages.get(receipt.get("value_text") or "")
    usual = ctx.per_package.get(receipt.get("component_id") or "")
    if receipt.get("value_text") not in ctx.single_part_notes:
        return Result("no_data")
    if not packages or not packages["value_num"] or not usual or not receipt["qty"]:
        return Result("no_data")
    implied = packages["value_num"] * usual
    low, high = ctx.rt.pack.booking_check.weight_ratio_range
    ratio = implied / receipt["qty"]
    return Result("pass" if low <= ratio <= high else "fail", implied,
                  [packages["id"]], f"packages:{receipt['value_text']}")


def gr_vs_history(ctx: Context, receipt: dict[str, Any]) -> Result:
    """Booked quantity against earlier receipts of the part from the supplier."""
    earlier = [
        r["qty"] for r in ctx.receipts
        if r["id"] != receipt["id"] and r["qty"]
        and r["component_id"] == receipt["component_id"]
        and r["supplier_id"] == receipt["supplier_id"]]
    if len(earlier) < _MIN_HISTORY or not receipt["qty"]:
        return Result("no_data")
    median = statistics.median(earlier)
    odd = receipt["qty"] > 5 * median or receipt["qty"] < median / 5
    return Result("fail" if odd else "pass", median)


def duplicate(ctx: Context, receipt: dict[str, Any]) -> Result:
    """Same delivery note, same order position, same quantity."""
    if not receipt.get("value_text"):
        return Result("no_data")
    twins = [
        r for r in ctx.by_note.get(receipt["value_text"], [])
        if r["id"] < receipt["id"] and _position(r) == _position(receipt)
        and r["qty"] == receipt["qty"]]
    return Result("fail" if twins else "pass", 0.0 if twins else None,
                  [r["id"] for r in twins])


def unreferenced(ctx: Context, receipt: dict[str, Any]) -> Result:
    """Receipt without order number or with an unknown part."""
    if not ctx.components:
        return Result("no_data")  # The master data is not loaded yet.
    missing = not receipt.get("po_number") or receipt.get("component_id") not in ctx.components
    return Result("fail" if missing else "pass")


def gr_note_exception(ctx: Context, receipt: dict[str, Any]) -> Result:
    """The remark of the booking names a quantity that is not the booked part."""
    found = [f for f in ctx.exceptions.get(str(receipt.get("ref") or ""), [])
             if (f["qty"] or 0) > 0]
    if not found:
        return Result("no_data")
    affected = sum(f["qty"] or 0 for f in found)
    return Result("fail", (receipt["qty"] or 0) - affected,
                  [f["id"] for f in found], f"remark:{receipt['ref']}")


Check = Callable[[Context, dict[str, Any]], Result]

CHECKS: dict[str, Check] = {
    "gr_vs_po": gr_vs_po,
    "gr_vs_delivery_note": gr_vs_delivery_note,
    "gr_vs_weight": gr_vs_weight,
    "gr_vs_packages": gr_vs_packages,
    "gr_vs_history": gr_vs_history,
    "duplicate": duplicate,
    "unreferenced": unreferenced,
    "gr_note_exception": gr_note_exception,
}


# ---------- finding ----------


def _propose(results: dict[str, Result]) -> tuple[float | None, int]:
    """The quantity that most independent sources support, and how many."""
    references = [
        (r.value, r.source) for name, r in results.items()
        if r.source and r.value is not None and r.status in ("pass", "fail")
        and name != "gr_note_exception"]
    best: tuple[float | None, int] = (None, 0)
    for value, _ in references:
        sources = {source for other, source in references if _close(value, other)}
        if len(sources) > best[1]:
            best = (value, len(sources))
    return best


def _cause(results: dict[str, Result], booked: float, proposed: float | None, per_package: float | None) -> str:
    if results["duplicate"].status == "fail":
        return "duplicate_booking"
    if results["unreferenced"].status == "fail":
        return "unreferenced_receipt"
    if proposed:
        ratio = booked / proposed
        if any(_close(ratio, factor) for factor in _SHIFT_FACTORS):
            return "decimal_shift"
        if per_package and (_close(ratio, per_package) or _close(1 / ratio, per_package)):
            return "unit_mismatch"
    if results["gr_note_exception"].status == "fail":
        return "content_mismatch"
    return "quantity_mismatch"


def check_receipt(ctx: Context, receipt: dict[str, Any]) -> dict[str, Any] | None:
    """Runs all checks for one receipt.

    Returns:
        The finding as a dict, or None when the booking looks right.
    """
    results = {name: check(ctx, receipt) for name, check in CHECKS.items()}
    hard = [n for n in _HARD_CHECKS if results[n].status == "fail"]
    soft = [n for n in _SOFT_CHECKS if results[n].status == "fail"]
    if not hard and len(soft) < 2:
        return None
    booked = receipt["qty"] or 0.0
    proposed, agreeing = _propose(results)
    if proposed is not None and _close(proposed, booked):
        proposed, agreeing = None, 0
    exception = results["gr_note_exception"]
    if proposed is None and exception.status == "fail":
        proposed, agreeing = exception.value, 1
    cause = _cause(results, booked, proposed,
                   ctx.per_package.get(receipt.get("component_id") or ""))
    if results["duplicate"].status == "fail":
        proposed, agreeing = 0.0, 2
    enough = agreeing >= ctx.rt.pack.booking_check.min_agreeing_sources
    status = "proposed" if enough and proposed is not None else "needs_count"
    if proposed is None:
        proposed = booked
    return {
        "gr_fact_id": receipt["id"], "gr_number": receipt["ref"],
        "component_id": receipt.get("component_id"),
        "supplier_id": receipt.get("supplier_id"),
        "po_number": receipt.get("po_number"), "po_line": receipt.get("po_line"),
        "booked_qty": booked, "proposed_qty": proposed,
        "delta_qty": proposed - booked, "cause": cause,
        "checks": {name: result.as_dict() for name, result in results.items()},
        "agreeing_sources": agreeing,
        "confidence": min(1.0, 0.5 + 0.2 * agreeing),
        "status": status, "booked_at": receipt.get("doc_date"),
    }


def _number(value: float) -> str:
    return f"{value:,.0f}"


def _upsert_case(rt: runtime.Runtime, finding: dict[str, Any], in_demand: bool) -> int:
    now = clock.iso()
    title = (f"Goods receipt {finding['gr_number']}: {_number(finding['booked_qty'])} "
             f"booked, documents show {_number(finding['proposed_qty'])}")
    if finding["cause"] == "unreferenced_receipt":
        title = f"Goods receipt {finding['gr_number']}: no purchase order or an unknown part"
    elif not finding["delta_qty"]:
        title = (f"Goods receipt {finding['gr_number']}: weight and packages "
                 "do not fit the quantity, stock count needed")
    key = f"finding::{finding['gr_number']}"
    impact = "deadline_blocker" if in_demand and finding["delta_qty"] else "after_deadline"
    columns = {
        "title": title, "impact": impact, "owner_role": "erp_owner",
        "component_id": finding["component_id"],
        "supplier_id": finding["supplier_id"], "po_number": finding["po_number"],
        "evidence_fact_ids": [finding["gr_fact_id"]], "updated_at": now,
    }
    existing = db.one(
        rt.conn, rt.ws,
        "SELECT * FROM cases WHERE workspace_id = ? AND dedupe_key = ?", (key,))
    if existing:
        db.update(rt.conn, "cases", rt.ws, existing["id"], **columns)
        return existing["id"]
    return db.insert(rt.conn, "cases", rt.ws, kind="booking_finding",
                     rule=finding["cause"], dedupe_key=key, created_at=now,
                     **columns)


def correction_payload(finding: dict[str, Any], site: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """The content of an ERP correction: reverse and book the right qty."""
    return {
        "kind": "gr_qty", "gr_number": finding["gr_number"],
        "po_number": finding["po_number"], "po_line": finding["po_line"],
        "material_id": finding["component_id"], "site": site,
        "booked_qty": finding["booked_qty"],
        "proposed_qty": finding["proposed_qty"],
        "delta_qty": finding["delta_qty"], "cause": finding["cause"],
        "evidence": evidence, "finding_id": finding["id"],
    }


def _store(rt: runtime.Runtime, finding: dict[str, Any], in_demand: bool) -> bool:
    """Stores a finding once per receipt. Returns True when it is new."""
    existing = db.one(
        rt.conn, rt.ws,
        "SELECT * FROM booking_findings WHERE workspace_id = ? "
        "AND idempotency_key = ?", (finding["gr_number"],))
    if existing and existing["status"] in _KEEP_STATUS:
        return False
    case_id = _upsert_case(rt, finding, in_demand)
    if existing:
        db.update(rt.conn, "booking_findings", rt.ws, existing["id"],
                  case_id=case_id, **finding)
        finding["id"] = existing["id"]
    else:
        finding["id"] = db.insert(
            rt.conn, "booking_findings", rt.ws, case_id=case_id,
            detected_at=clock.iso(), idempotency_key=finding["gr_number"],
            **finding)
        db.emit(rt.conn, rt.ws, "finding.created",
                {"finding_id": finding["id"], "case_id": case_id},
                dedupe_key=f"finding.created:{finding['id']}")
    if finding["status"] == "proposed":
        _propose_correction(rt, finding, case_id)
    else:
        _request_count(rt, finding, case_id)
    return existing is None


def _propose_correction(rt: runtime.Runtime, finding: dict[str, Any], case_id: int) -> None:
    key = f"{finding['gr_number']}:gr_qty:{finding['proposed_qty']:g}"
    fact_ids = [finding["gr_fact_id"]]
    for check in finding["checks"].values():
        fact_ids.extend(check["fact_ids"])
    evidence = [
        {"file": row["path"], "place": row["source_locator"],
         "value": row["qty"] if row["qty"] is not None else row["value_num"],
         "fact_type": row["fact_type"]}
        for row in db.rows(
            rt.conn, rt.ws,
            "SELECT f.fact_type, f.qty, f.value_num, f.source_locator, x.path "
            "FROM facts f LEFT JOIN files x ON x.id = f.source_file_id "
            f"WHERE f.workspace_id = ? AND f.id IN ({', '.join('?' for _ in fact_ids)})",
            fact_ids)]
    if db.one(rt.conn, rt.ws,
              "SELECT id FROM corrections WHERE workspace_id = ? "
              "AND idempotency_key = ?", (key,)):
        return
    rt.conn.execute(
        "UPDATE corrections SET status = 'rejected', reject_reason = "
        "'Replaced by a newer document' WHERE workspace_id = ? AND finding_id = ? "
        "AND status = 'proposed'", (rt.ws, finding["id"]))
    correction_id = db.insert(
        rt.conn, "corrections", rt.ws, finding_id=finding["id"], kind="gr_qty",
        payload=correction_payload(finding, rt.pack.site, evidence),
        approver_role="erp_owner", idempotency_key=key, created_at=clock.iso())
    db.emit(rt.conn, rt.ws, "correction.proposed",
            {"correction_id": correction_id, "case_id": case_id},
            dedupe_key=f"correction.proposed:{correction_id}")


def _request_count(rt: runtime.Runtime, finding: dict[str, Any], case_id: int) -> None:
    if finding["cause"] == "unreferenced_receipt":
        return
    key = f"{case_id}:count_request:{finding['component_id']}"
    if db.one(rt.conn, rt.ws,
              "SELECT id FROM actions WHERE workspace_id = ? AND idempotency_key = ?",
              (key,)):
        return
    action_id = db.insert(
        rt.conn, "actions", rt.ws, case_id=case_id, type="count_request",
        kind="count_request", target="site_lead", status="proposed",
        idempotency_key=key, created_at=clock.iso(),
        result={"component_id": finding["component_id"],
                "gr_number": finding["gr_number"],
                "text": f"Please count part {finding['component_id']} from goods receipt "
                        f"{finding['gr_number']}."})
    db.emit(rt.conn, rt.ws, "action.created",
            {"action_id": action_id, "case_id": case_id},
            dedupe_key=f"action.created:{action_id}")


def verify_corrections(rt: runtime.Runtime, ctx: Context) -> None:
    """A correction is done only when a later ERP export shows the new qty."""
    booked = {r["ref"]: r["qty"] for r in ctx.receipts}
    open_rows = db.rows(
        rt.conn, rt.ws,
        "SELECT c.*, f.gr_number, f.proposed_qty FROM corrections c "
        "JOIN booking_findings f ON f.id = c.finding_id "
        "WHERE c.workspace_id = ? AND c.status IN ('handed_over', 'posted')")
    for row in open_rows:
        current = booked.get(row["gr_number"])
        if current is not None and _close(current, row["proposed_qty"]):
            db.update(rt.conn, "corrections", rt.ws, row["id"],
                      status="verified", verified_at=clock.iso())
            db.update(rt.conn, "booking_findings", rt.ws, row["finding_id"],
                      status="corrected")
            rt.conn.execute(
                "UPDATE cases SET state = 'closed', updated_at = ? WHERE "
                "workspace_id = ? AND id = (SELECT case_id FROM booking_findings "
                "WHERE id = ?)", (clock.iso(), rt.ws, row["finding_id"]))
            db.emit(rt.conn, rt.ws, "correction.verified",
                    {"correction_id": row["id"]},
                    dedupe_key=f"correction.verified:{row['id']}")


def check_all(rt: runtime.Runtime) -> dict[str, int]:
    """Checks every current receipt (the look-back) and stores findings.

    Safe to run again: one finding per receipt, one correction per
    proposed quantity.
    """
    ctx = build_context(rt)
    products = {line.product_id for line in core.demand_lines(rt)}
    in_demand = {
        row["component_id"] for row in db.rows(
            rt.conn, rt.ws, "SELECT * FROM bom_lines WHERE workspace_id = ?")
        if row["product_id"] in products}
    new = 0
    seen = set()
    rt.conn.execute("BEGIN IMMEDIATE")
    try:
        verify_corrections(rt, ctx)
        for receipt in ctx.receipts:
            finding = check_receipt(ctx, receipt)
            if finding is None:
                continue
            seen.add(finding["gr_number"])
            new += _store(rt, finding, finding["component_id"] in in_demand)
        # A finding whose receipt now looks right is no longer open.
        for row in db.rows(
                rt.conn, rt.ws,
                "SELECT * FROM booking_findings WHERE workspace_id = ? "
                "AND status IN ('proposed', 'needs_count')"):
            if row["gr_number"] not in seen:
                db.update(rt.conn, "booking_findings", rt.ws, row["id"],
                          status="corrected")
                rt.conn.execute(
                    "UPDATE cases SET state = 'closed' WHERE workspace_id = ? "
                    "AND id = ?", (rt.ws, row["case_id"]))
    except Exception:
        rt.conn.execute("ROLLBACK")
        raise
    rt.conn.execute("COMMIT")
    return {"receipts": len(ctx.receipts), "findings": len(seen), "new": new}
