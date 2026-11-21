"""The standard ways to close a gap. Each generator reads only facts.

A generator returns options as dicts. It knows fact types and master
data, but no part, no supplier and no case of a customer
(docs/lueckenschluss.md §4). A new way is one function plus one entry in
`GENERATORS` of the package.
"""

import datetime
from typing import Any

from lineguard import runtime
from lineguard.coverage import core
from lineguard.policy import engine

_CONFIDENCE_DOCUMENT = 0.9
_CONFIDENCE_STATEMENT = 0.6
_CONFIDENCE_NO_ANSWER = 0.3
_HELD_STATUS = ("arrived_port", "arrived", "available")


def _number(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def _option(component: core.ComponentState, kind: str, source: Any, **values: Any) -> dict[str, Any]:
    return {"kind": kind, "dedupe_key": f"{component.component_id}:{kind}:{source}",
            "cost_eur": 0.0, "valid_until": None, "supplier_id": None,
            "evidence_fact_ids": [], **values}


def _list_price(rt: runtime.Runtime, supplier_id: str | None, component_id: str) -> float | None:
    for fact in core.current_facts(rt, "supplier_part"):
        if fact["supplier_id"] == supplier_id and fact["component_id"] == component_id:
            return fact["value_num"]
    return None


def accept_offer(rt: runtime.Runtime, state: core.State, component: core.ComponentState) -> list[dict[str, Any]]:
    """An offer that is still valid: order it."""
    options = []
    for fact in core.current_facts(rt, "offer"):
        valid_until = core.timeutil.to_datetime(fact.get("valid_until"), rt.pack.timezone)
        if fact["component_id"] != component.component_id or not fact.get("qty"):
            continue
        if valid_until and valid_until <= state.at:
            continue
        data = fact["data"]
        price = fact["value_num"] or _list_price(rt, fact["supplier_id"], component.component_id)
        cost = data.get("total") or (price or 0) * fact["qty"]
        # Without a stated lead time the arrival is unknown, and the offer
        # cannot be part of a plan.
        parts = [data.get(key) for key in ("ready_hours", "transport_hours", "lead_time_hours")]
        hours = sum(float(part) for part in parts if part)
        arrives = state.at + datetime.timedelta(hours=hours) if hours else None
        options.append(_option(
            component, "accept_offer", fact["id"],
            title=f"Angebot annehmen: {_number(fact['qty'])} Stück bestellen",
            qty_gain=fact["qty"], cost_eur=float(cost),
            arrives_at=arrives,
            confidence=_CONFIDENCE_DOCUMENT, valid_until=valid_until,
            supplier_id=fact["supplier_id"], action_kind="order",
            needs_roles=engine.route(rt, "purchase_order", float(cost), ["inbound_delivery"]),
            evidence_fact_ids=[fact["id"]]))
    return options


def release_held(rt: runtime.Runtime, state: core.State, component: core.ComponentState) -> list[dict[str, Any]]:
    """Goods that arrived somewhere but are not received: fetch them."""
    del state
    return [
        _option(component, "release_held", inbound.ref,
                title=f"Abholen: {_number(inbound.qty)} Stück liegen bereit ({inbound.ref})",
                qty_gain=inbound.qty, arrives_at=inbound.arrives_at,
                confidence=_CONFIDENCE_STATEMENT, supplier_id=inbound.supplier_id,
                action_kind="pickup", asks_earlier=True, po_number=inbound.po_number,
                needs_roles=engine.route(rt, "inbound_delivery"),
                evidence_fact_ids=inbound.fact_ids)
        for inbound in component.inbound
        if not inbound.secured and (inbound.status or "") in _HELD_STATUS]


def expedite_inbound(rt: runtime.Runtime, state: core.State, component: core.ComponentState) -> list[dict[str, Any]]:
    """Inbound without proof or too late: ask for an earlier arrival."""
    del rt
    options = []
    for inbound in component.inbound:
        if inbound.secured or (inbound.status or "") in _HELD_STATUS:
            continue
        late = (component.latest_useful_arrival is not None and inbound.arrives_at is not None
                and inbound.arrives_at > component.latest_useful_arrival)
        horizon = state.next_due + datetime.timedelta(days=7) if state.next_due else None
        if horizon and inbound.arrives_at and inbound.arrives_at > horizon:
            continue
        options.append(_option(
            component, "expedite_inbound", inbound.ref or inbound.po_number,
            title=(f"Nachfragen: {_number(inbound.qty)} Stück "
                   f"{'früher liefern' if late else 'bestätigen'} ({inbound.ref or inbound.po_number})"),
            qty_gain=inbound.qty, arrives_at=inbound.arrives_at,
            confidence=_CONFIDENCE_NO_ANSWER, supplier_id=inbound.supplier_id,
            action_kind="status_request", needs_roles=[],
            asks_earlier=late, po_number=inbound.po_number,
            evidence_fact_ids=inbound.fact_ids))
    return options


def rework_sort(rt: runtime.Runtime, state: core.State, component: core.ComponentState) -> list[dict[str, Any]]:
    """A failed lot: sort it and use the good parts."""
    options = []
    facts = {f["id"]: f for f in core.current_facts(rt, "inspection_result")}
    for block in component.blocks:
        fact = facts.get(block.fact_ids[0]) if block.fact_ids else None
        if block.reason != "inspection_failed" or fact is None:
            continue
        sample = float(fact["data"].get("sample") or 0)
        defects = float(fact["data"].get("defects") or 0)
        good_share = 1 - defects / sample if sample else 0.5
        hours = rt.pack.coverage.default_handling_hours
        options.append(_option(
            component, "rework_sort", fact["id"],
            title=(f"Charge {fact.get('batch') or ''} sortieren: etwa "
                   f"{_number(block.qty * good_share)} gute Teile").replace("  ", " "),
            qty_gain=float(int(block.qty * good_share)),
            arrives_at=state.at + datetime.timedelta(hours=hours),
            confidence=_CONFIDENCE_STATEMENT, supplier_id=fact.get("supplier_id"),
            action_kind="sort",
            needs_roles=engine.route(rt, "supplier_release", 0.0, ["unreleased_part"]),
            evidence_fact_ids=[fact["id"]]))
    return options


GENERATORS = (accept_offer, release_held, expedite_inbound, rework_sort)
