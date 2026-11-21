"""Stock Truth agent: recomputes the state and stores gaps and cases.

Runs on `facts.updated` and on every event that changes what counts as
stock. The numbers come from `coverage.core`, this module only stores
them and tells the other agents what changed.
"""

import datetime
from typing import Any

from lineguard import clock
from lineguard import db
from lineguard import runtime
from lineguard.coverage import core


def _number(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def _rank(rt: runtime.Runtime, component: core.ComponentState) -> tuple[int, float]:
    order = rt.pack.priority_order
    classes = [order.index(s["class"]) if s["class"] in order else len(order)
               for s in component.short_lines]
    breaks = component.breaks_at.timestamp() if component.breaks_at else float("inf")
    return (min(classes) if classes else len(order), breaks)


def recompute(rt: runtime.Runtime, event: dict[str, Any] | None = None) -> core.State:
    """Computes the state, stores it and emits `gap.changed` where needed."""
    del event  # The calculation always covers the whole workspace.
    state = core.compute(rt)
    now = clock.iso()
    rt.conn.execute("BEGIN")
    try:
        _store_products(rt, state)
        _store_components(rt, state, now)
        _store_demand(rt)
        _store_gaps(rt, state, now)
    except Exception:
        rt.conn.execute("ROLLBACK")
        raise
    rt.conn.execute("COMMIT")
    return state


def _store_products(rt: runtime.Runtime, state: core.State) -> None:
    for product in state.products.values():
        rt.conn.execute(
            "UPDATE products SET demand_units = ?, packed = ?, "
            "still_to_pack = ?, rate_per_hour = ? "
            "WHERE workspace_id = ? AND product_id = ?",
            (product.demand, product.packed, product.still_to_pack,
             product.rate_per_hour, rt.ws, product.product_id))


def _store_components(rt: runtime.Runtime, state: core.State, now: str) -> None:
    for component in state.components.values():
        status = "ok"
        if component.gap_qty < 0:
            status = "break"
        elif component.need and component.usable - component.need < component.need * rt.pack.coverage.thin_margin:
            status = "risk"
        rt.conn.execute(
            "UPDATE components SET need_remaining = ?, erp_stock = ?, "
            "usable_stock = ?, inbound_ok = ?, gap_qty = ?, status = ?, "
            "stocked = ?, carrier_component_id = ?, updated_at = ? "
            "WHERE workspace_id = ? AND component_id = ?",
            (component.need, component.erp_stock, component.usable,
             component.inbound_secured, component.gap_qty, status,
             int(component.stocked), component.carrier_component_id, now,
             rt.ws, component.component_id))


def _store_demand(rt: runtime.Runtime) -> None:
    rt.conn.execute("DELETE FROM demand_lines WHERE workspace_id = ?", (rt.ws,))
    for line in core.demand_lines(rt):
        rt.conn.execute(
            "INSERT OR REPLACE INTO demand_lines (workspace_id, product_id, "
            "class, units, due_at, source) VALUES (?, ?, ?, ?, ?, 'facts')",
            (rt.ws, line.product_id, line.demand_class, line.units,
             clock.iso(line.due_at)))


def _store_gaps(rt: runtime.Runtime, state: core.State, now: str) -> None:
    current = {
        row["component_id"]: row for row in db.rows(
            rt.conn, rt.ws,
            "SELECT * FROM gaps WHERE workspace_id = ? AND is_current = 1")}
    short = sorted(
        (c for c in state.components.values() if c.gap_qty < 0),
        key=lambda c: _rank(rt, c))
    for position, component in enumerate(short, 1):
        old = current.pop(component.component_id, None)
        case_id = _upsert_case(rt, component, position, now)
        detail = _gap_detail(component)
        if old and abs(old["gap_qty"] - component.gap_qty) < 0.5:
            db.update(rt.conn, "gaps", rt.ws, old["id"], rank=position,
                      breaks_at=_iso(component.breaks_at), detail=detail,
                      evidence_fact_ids=_evidence(component), case_id=case_id)
            continue
        if old:
            db.update(rt.conn, "gaps", rt.ws, old["id"], is_current=0)
        first = component.short_lines[0]
        gap_id = db.insert(
            rt.conn, "gaps", rt.ws, case_id=case_id,
            component_id=component.component_id, product_id=first["product_id"],
            site_id=rt.pack.site, due_at=first["due_at"],
            gap_qty=component.gap_qty,
            units_at_risk=sum(s["units_at_risk"] for s in component.short_lines),
            breaks_at=_iso(component.breaks_at), rank=position,
            evidence_fact_ids=_evidence(component), detail=detail,
            version=(old["version"] + 1) if old else 1, created_at=now)
        db.emit(rt.conn, rt.ws, "gap.changed",
                {"gap_id": gap_id, "case_id": case_id,
                 "component_id": component.component_id},
                priority=1, partition_key=f"component:{component.component_id}",
                dedupe_key=f"gap.changed:{gap_id}")
    for component_id, old in current.items():
        db.update(rt.conn, "gaps", rt.ws, old["id"], is_current=0)
        rt.conn.execute(
            "UPDATE cases SET state = 'closed', updated_at = ? "
            "WHERE workspace_id = ? AND id = ? AND state NOT IN ('closed', 'dismissed')",
            (now, rt.ws, old["case_id"]))
        db.emit(rt.conn, rt.ws, "gap.closed",
                {"gap_id": old["id"], "case_id": old["case_id"],
                 "component_id": component_id},
                dedupe_key=f"gap.closed:{old['id']}")


def _iso(moment: datetime.datetime | None) -> str | None:
    return clock.iso(moment) if moment else None


def _evidence(component: core.ComponentState) -> list[int]:
    ids = list(component.evidence_fact_ids)
    for block in component.blocks:
        ids.extend(block.fact_ids)
    for inbound in component.inbound:
        ids.extend(inbound.fact_ids)
    return sorted(set(ids))


def _gap_detail(component: core.ComponentState) -> dict[str, Any]:
    return {
        "erp_stock": component.erp_stock,
        "stock_as_of": component.stock_as_of,
        "used_since_snapshot": component.used_since_snapshot,
        "usable": component.usable, "need": component.need,
        "inbound_secured": component.inbound_secured,
        "gap_system": component.gap_system,
        "batch_unknown": component.batch_unknown,
        "latest_useful_arrival": _iso(component.latest_useful_arrival),
        "blocks": [{"reason": b.reason, "qty": b.qty, "text": b.text,
                    "fact_ids": b.fact_ids} for b in component.blocks],
        "short_lines": component.short_lines,
        "inbound": [{"qty": i.qty, "arrives_at": _iso(i.arrives_at),
                     "rank": i.rank, "ref": i.ref, "status": i.status,
                     "secured": i.secured, "po_number": i.po_number,
                     "supplier_id": i.supplier_id, "fact_ids": i.fact_ids}
                    for i in component.inbound],
    }


def _upsert_case(rt: runtime.Runtime, component: core.ComponentState, position: int, now: str) -> int:
    first = component.short_lines[0]
    units = sum(s["units_at_risk"] for s in component.short_lines)
    label = rt.pack.labels.get("units", "Stück")
    title = (f"{component.description}: {_number(-component.gap_qty)} fehlen, "
             f"{_number(units)} {label} in Gefahr")
    key = f"gap::{component.component_id}"
    existing = db.one(
        rt.conn, rt.ws,
        "SELECT * FROM cases WHERE workspace_id = ? AND dedupe_key = ?", (key,))
    columns = {
        "title": title, "impact": "deadline_blocker",
        "due_at": first["due_at"], "product_id": first["product_id"],
        "rank": position, "evidence_fact_ids": _evidence(component),
        "detail": _gap_detail(component), "updated_at": now,
    }
    if existing:
        if existing["state"] in ("closed", "dismissed"):
            columns["state"] = "open"
        db.update(rt.conn, "cases", rt.ws, existing["id"], **columns)
        return existing["id"]
    return db.insert(rt.conn, "cases", rt.ws, kind="gap",
                     component_id=component.component_id, dedupe_key=key,
                     created_at=now, **columns)
