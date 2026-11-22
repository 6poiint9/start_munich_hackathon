"""Watchers: rules that open a case without a gap.

They keep Lineguard useful after a deadline: an open order with a
revision that is not released, a contract or release that runs out
(docs/dauerbetrieb.md §5). Each watcher reads only facts. A new watcher is
one function plus one entry in `WATCHERS`.
"""

from collections.abc import Callable
import datetime
from typing import Any

from lineguard import clock
from lineguard import db
from lineguard import runtime
from lineguard.coverage import core
from lineguard.policy import engine

_OPEN_ORDER = ("open", "confirmed", "awaiting_approval", "in_transit")


def _number(value: float) -> str:
    return f"{value:,.0f}"


def _case(rule: str, subject: str, title: str, act_by: datetime.datetime | None, owner_role: str, fact_ids: list[int], **link: Any) -> dict[str, Any]:
    return {"rule": rule, "dedupe_key": f"watch:{rule}:{subject}", "title": title,
            "act_by": clock.iso(act_by) if act_by else None,
            "owner_role": owner_role, "evidence_fact_ids": fact_ids, **link}


def revision_mismatch_open_po(rt: runtime.Runtime, now: datetime.datetime) -> list[dict[str, Any]]:
    """An open order position asks for a revision that is not released."""
    del now
    released = {
        row["component_id"]: row["released_rev"] for row in db.rows(
            rt.conn, rt.ws,
            "SELECT component_id, released_rev FROM components "
            "WHERE workspace_id = ? AND released_rev IS NOT NULL")}
    for component_id, rule in core.released_rules(rt).items():
        released[component_id] = rule["rev"]
    confirmed = {
        (f["po_number"], f["component_id"]): f
        for f in core.current_facts(rt, "artwork_rev") if f.get("po_number")}
    notice = datetime.timedelta(days=rt.pack.watch.default_notice_days)
    cases = []
    for order in core.current_facts(rt, "po_line"):
        component_id = order["component_id"]
        if str(order.get("value_text") or "").lower() not in _OPEN_ORDER:
            continue
        proof = confirmed.get((order["po_number"], component_id))
        rev = proof["rev"] if proof else order.get("rev")
        if not rev or component_id not in released or rev == released[component_id]:
            continue
        eta = core.timeutil.to_datetime(order.get("eta"), rt.pack.timezone)
        cases.append(_case(
            "revision_mismatch_open_po", f"{order['po_number']}:{order.get('po_line') or ''}",
            f"Purchase order {order['po_number']}: {_number(order['qty'] or 0)} pieces "
            f"{component_id} in revision {rev}, released is {released[component_id]}",
            eta - notice if eta else None,
            engine.route(rt, "purchase_order", (order["qty"] or 0) * (order["value_num"] or 0))[0],
            [order["id"], *([proof["id"]] if proof else [])],
            component_id=component_id, supplier_id=order.get("supplier_id"),
            po_number=order["po_number"]))
    return cases


def validity_expiring(rt: runtime.Runtime, now: datetime.datetime) -> list[dict[str, Any]]:
    """A contract or a supplier release is over or ends within the horizon."""
    horizon = now + datetime.timedelta(days=rt.pack.coverage.horizon_days)
    owner = engine.route(rt, "supplier_release")[0]
    cases = []
    newest: dict[tuple[str, str, str], dict[str, Any]] = {}
    for fact_type in ("validity", "release_status"):
        for fact in core.current_facts(rt, fact_type):
            key = (fact_type, fact.get("supplier_id") or "", fact.get("value_text") or "")
            if not fact.get("valid_until"):
                continue
            # Two sources can name two end dates. The earlier one is the risk.
            if key not in newest or fact["valid_until"] < newest[key]["valid_until"]:
                newest[key] = fact
    for (fact_type, supplier, text), fact in newest.items():
        until = core.timeutil.to_datetime(fact.get("valid_until"), rt.pack.timezone)
        days = fact["data"].get("notice_days") or rt.pack.watch.default_notice_days
        if until is None or not supplier:
            continue
        if until - datetime.timedelta(days=float(days)) > horizon:
            continue
        what = "Supplier release" if fact_type == "release_status" else "Contract"
        state = "expired on" if until <= now else "expires on"
        cases.append(_case(
            "validity_expiring", f"{fact_type}:{supplier}:{text}",
            f"{what} {supplier} ({text}) {state} {until.date().isoformat()}",
            until - datetime.timedelta(days=float(days)), owner, [fact["id"]],
            supplier_id=supplier, component_id=fact.get("component_id")))
    return cases


def feed_stale(rt: runtime.Runtime, now: datetime.datetime) -> list[dict[str, Any]]:
    """Opens one case per shipment feed whose latest update is too old."""
    files = {row["id"]: row["path"] for row in db.rows(
        rt.conn, rt.ws,
        "SELECT id, path FROM files WHERE workspace_id = ? AND is_current = 1")}
    latest: dict[int, tuple[datetime.datetime, int]] = {}
    for fact in core.current_facts(rt, "shipment"):
        file_id = fact["source_file_id"]
        updated = core.timeutil.to_datetime(fact["data"].get("updated_at"), rt.pack.timezone)
        if file_id not in files or updated is None:
            continue
        if file_id not in latest or updated > latest[file_id][0]:
            latest[file_id] = (updated, fact["id"])
    limit = datetime.timedelta(hours=rt.pack.watch.feed_stale_hours)
    return [
        _case("feed_stale", files[file_id],
              f"Shipment feed {files[file_id]} has not updated since {clock.iso(updated)}",
              updated + limit, "erp_owner", [fact_id])
        for file_id, (updated, fact_id) in latest.items()
        if updated + limit <= now
    ]


Watcher = Callable[[runtime.Runtime, datetime.datetime], list[dict[str, Any]]]

WATCHERS: list[Watcher] = [revision_mismatch_open_po, validity_expiring, feed_stale]


def run_watchers(rt: runtime.Runtime) -> int:
    """Runs all watchers and stores one case per hit. Returns the count.

    A second run creates no second case. A case whose reason is gone is
    closed.
    """
    now = clock.now()
    horizon = now + datetime.timedelta(days=rt.pack.coverage.horizon_days)
    seen = set()
    for watcher in WATCHERS:
        for found in watcher(rt, now):
            seen.add(found["dedupe_key"])
            act_by = clock.parse(found["act_by"]) if found["act_by"] else None
            # A case moves to the list 'Jetzt' when it is time to act.
            found["impact"] = ("deadline_blocker" if act_by and act_by <= horizon
                               and act_by <= now else "after_deadline")
            existing = db.one(
                rt.conn, rt.ws,
                "SELECT * FROM cases WHERE workspace_id = ? AND dedupe_key = ?",
                (found["dedupe_key"],))
            if existing:
                if existing["state"] != "dismissed":
                    if existing["state"] == "closed":
                        found["state"] = "open"
                    db.update(rt.conn, "cases", rt.ws, existing["id"],
                              updated_at=clock.iso(), **{
                                  k: v for k, v in found.items() if k != "dedupe_key"})
            else:
                db.insert(rt.conn, "cases", rt.ws, kind="watch",
                          created_at=clock.iso(), updated_at=clock.iso(), **found)
    for row in db.rows(
            rt.conn, rt.ws,
            "SELECT * FROM cases WHERE workspace_id = ? AND kind = 'watch' "
            "AND state NOT IN ('closed', 'dismissed')"):
        if row["dedupe_key"] not in seen:
            db.update(rt.conn, "cases", rt.ws, row["id"], state="closed",
                      updated_at=clock.iso())
    return len(seen)
