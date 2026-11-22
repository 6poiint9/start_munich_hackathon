"""Gap closing: every gap gets a plan with owner, price and time.

The loop is general. It calls all generators, keeps the options that can
still arrive in time, and builds a plan until confirmed options cover the
need. A gap without enough options is reported openly as `unclosable`
(docs/lueckenschluss.md §5 to §8).
"""

import datetime
from typing import Any
import zoneinfo

from lineguard import approvals
from lineguard import clock
from lineguard import db
from lineguard import runtime
from lineguard.coverage import core
from lineguard.coverage import options as options_module
from lineguard.policy import engine

_LOCKED = ("approved", "in_execution", "confirmed", "delivered", "failed")
_ESCALATE_BEFORE = datetime.timedelta(minutes=30)
_FREE_ACTIONS = ("status_request", "count_request", "quote_request")
_REQUESTS = ("status_request", "pickup", "quote_request")
# Actions that secure goods of an order. They stay on the table when the
# goods come after the due date, but they close nothing of the gap then.
_SECURES_ORDER = ("confirm_terms",)
_OPTION_DATA = ("asks_earlier", "po_number", "condition", "incoterm", "contract_ref", "request_qty",
                "shipment_ref", "conflict", "cost_unknown")


def _number(value: float) -> str:
    return f"{value:,.0f}"


def _iso(moment: datetime.datetime | None) -> str | None:
    return clock.iso(moment) if moment else None


def _local(rt: runtime.Runtime, moment: datetime.datetime) -> str:
    """A moment in the time zone of the site, for text that a person reads."""
    return moment.astimezone(zoneinfo.ZoneInfo(rt.pack.timezone)).strftime("%d %b %H:%M")


def _still_usable(rt: runtime.Runtime, state: core.State, gap: dict[str, Any], arrives: datetime.datetime, qty_per: dict[str, float]) -> float:
    """Parts of a late delivery that can still pass the line before the due date.

    Goods after the latest useful arrival do not close the whole gap, but
    every hour of line time that is left still saves units.
    """
    due = clock.parse(gap["due_at"]) if gap.get("due_at") else state.next_due
    if due is None:
        return 0.0
    start = arrives + datetime.timedelta(hours=rt.pack.coverage.default_handling_hours)
    usable = 0.0
    for product_id, per in qty_per.items():
        product = state.products.get(product_id)
        if product is None or not product.rate_per_hour or not per:
            continue
        hours = (core.shift_hours(state.shifts, start, due) if state.shifts
                 else max((due - start).total_seconds() / 3600, 0.0))
        usable += hours * product.rate_per_hour * per
    return usable


def _upsert_option(rt: runtime.Runtime, state: core.State, case: dict[str, Any], gap: dict[str, Any], option: dict[str, Any], component: core.ComponentState, qty_per: dict[str, float]) -> dict[str, Any]:
    arrives = option.get("arrives_at")
    valid_until = option.get("valid_until")
    reason = None
    note = None
    # A question or a pickup asks for the arrival that is needed. Its
    # current date is the thing to change, so it does not rule the option out.
    is_request = option.get("action_kind") in _REQUESTS
    secures = option.get("action_kind") in _SECURES_ORDER
    planned_qty = option["qty_gain"]
    after_deadline = False
    if arrives is None and secures:
        after_deadline = True
        note = "The arrival is open. The quantity counts only when the supplier names a date."
        option = {**option, "qty_gain": 0.0}
    elif arrives is None:
        reason = None if is_request else "Arrival unknown"
    elif is_request:
        reason = None
    elif component.latest_useful_arrival and arrives > component.latest_useful_arrival:
        usable = min(option["qty_gain"], _still_usable(rt, state, gap, arrives, qty_per))
        if usable >= 1:
            note = (f"Arrives late: of {_number(option['qty_gain'])} pieces, "
                    f"{_number(usable)} still pass the line in time")
            option = {**option, "qty_gain": float(int(usable)),
                      "title": f"{option['title']} (late, {_number(usable)} usable)"}
        elif secures:
            after_deadline = True
            note = (f"Arrives after the deadline (arrival {_local(rt, arrives)}). Secures "
                    f"{_number(planned_qty)} pieces for the delivery after it, and does not close the shortage.")
            option = {**option, "qty_gain": 0.0}
        else:
            reason = (f"Arrival {clock.iso(arrives)} is after the latest "
                      f"useful arrival {clock.iso(component.latest_useful_arrival)}")
    if valid_until and valid_until <= clock.now():
        reason = "The offer expired"
    units = {product: option["qty_gain"] / per for product, per in qty_per.items() if per}
    columns = {
        "case_id": case["id"], "gap_id": gap["id"], "kind": option["kind"],
        "title": option["title"], "qty_gain": option["qty_gain"],
        "units_gained": units, "arrives_at": _iso(arrives),
        "cost_eur": option["cost_eur"], "confidence": option["confidence"],
        "valid_until": _iso(valid_until), "feasible": int(reason is None),
        "infeasible_reason": reason, "needs_roles": option.get("needs_roles") or [],
        "evidence_fact_ids": option["evidence_fact_ids"],
        "supplier_id": option.get("supplier_id"),
        "action_kind": option.get("action_kind"),
        "data": {"note": note, "after_deadline": after_deadline,
                 "planned_qty": planned_qty,
                 **{k: v for k, v in option.items() if k in _OPTION_DATA}},
        "updated_at": clock.iso(),
    }
    existing = db.one(
        rt.conn, rt.ws,
        "SELECT * FROM options WHERE workspace_id = ? AND dedupe_key = ?",
        (option["dedupe_key"],))
    if existing is None:
        option_id = db.insert(rt.conn, "options", rt.ws,
                              dedupe_key=option["dedupe_key"], **columns)
        db.emit(rt.conn, rt.ws, "option.created", {"option_id": option_id},
                priority=3, dedupe_key=f"option.created:{option_id}")
        return {"id": option_id, "status": "candidate", "role_in_plan": "none", **columns}
    if existing["status"] not in _LOCKED:
        db.update(rt.conn, "options", rt.ws, existing["id"], **columns)
    else:
        columns = {k: existing[k] for k in columns} | {
            "needs_roles": db.loads(existing["needs_roles"], [])}
    return {"id": existing["id"], "status": existing["status"],
            "role_in_plan": existing["role_in_plan"], **columns}


def _plan(rt: runtime.Runtime, need: float, found: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float, float]:
    """Picks options until confirmed ones cover the need.

    Returns:
        The plan, the confirmed quantity and the unconfirmed quantity.
    """
    threshold = rt.pack.coverage.confirm_threshold
    usable = [o for o in found if o["feasible"] and o["status"] != "failed"]
    usable.sort(key=lambda o: (
        o["confidence"] < threshold,
        o["cost_eur"] / o["qty_gain"] if o["qty_gain"] else 0.0,
        -o["confidence"], o["arrives_at"] or "9999"))
    plan, firm, soft = [], 0.0, 0.0
    for option in usable:
        if firm >= need:
            break
        plan.append(option)
        if option["confidence"] >= threshold:
            firm += option["qty_gain"]
        else:
            soft += option["qty_gain"]
    return plan, firm, soft


def _decide(rt: runtime.Runtime, case: dict[str, Any], gap: dict[str, Any], component: core.ComponentState, plan: list[dict[str, Any]], state: core.State, rate: float | None) -> None:
    """One open decision per case for the options that need a person."""
    paid = [o for o in plan if o.get("action_kind") not in _FREE_ACTIONS
            and o["status"] in ("candidate", "proposed")]
    if not paid:
        return
    recommended = paid[0]
    roles = recommended["needs_roles"] or [engine.fallback_role(rt)]
    lead = datetime.timedelta(0)
    arrives = clock.parse(recommended["arrives_at"]) if recommended["arrives_at"] else None
    if arrives:
        lead = max(arrives - state.at, datetime.timedelta(0))
    deadline = None
    if component.breaks_at:
        deadline = component.breaks_at - lead
    if (deadline is None or deadline < state.at) and component.latest_useful_arrival:
        deadline = component.latest_useful_arrival - lead
    category = _category(rt, component.component_id)
    person = engine.resolve_person(
        rt, roles[0], category, preferred=_usual_buyers(rt, component.component_id))
    if person and roles[0] not in person["roles"]:
        # Nobody holds the role for this category. The fallback role decides.
        roles = [*roles, engine.fallback_role(rt)]
    label = rt.pack.labels.get("units", "units")
    waiting = f" Each hour of standstill costs {_number(rate)} {label}." if rate else ""
    details = recommended.get("data") or {}
    if isinstance(details, str):
        details = db.loads(details, {})
    price = (". The cost is not known yet" if details.get("cost_unknown")
             else f" for €{_number(recommended['cost_eur'])}")
    remarks = [details.get("conflict")]
    if details.get("after_deadline"):
        remarks.append((details.get("note") or "").rstrip("."))
    extra = "".join(f" {text}." for text in remarks if text)
    explanation = (
        f"{_number(-gap['gap_qty'])} pieces of {component.description} are short. "
        f"Recommendation: {recommended['title']}{price}.{extra}"
        f"{waiting}")
    key = f"case:{case['id']}"
    existing = db.one(
        rt.conn, rt.ws,
        "SELECT * FROM decisions WHERE workspace_id = ? AND dedupe_key = ?", (key,))
    columns = {
        "title": f"{component.description}: close the shortage",
        "options": [o["id"] for o in paid], "recommended_option": recommended["id"],
        "explanation": explanation, "needs_roles": roles, "approver_role": roles[0],
        "approver_name": person["name"] if person else None,
        "policy_ref": rt.pack.approval_policy.get("source"),
        "deadline": _iso(deadline),
    }
    if existing is None:
        decision_id = db.insert(
            rt.conn, "decisions", rt.ws, case_id=case["id"], gap_id=gap["id"],
            dedupe_key=key, created_at=clock.iso(), **columns)
        db.emit(rt.conn, rt.ws, "decision.created", {"decision_id": decision_id},
                priority=3, dedupe_key=f"decision.created:{decision_id}")
    elif existing["status"] == "open":
        if existing["escalation_level"]:
            columns.pop("approver_role")
            columns.pop("approver_name")
            columns.pop("needs_roles")
        db.update(rt.conn, "decisions", rt.ws, existing["id"], **columns)
        decision_id = existing["id"]
    else:
        return
    for option in paid:
        db.update(rt.conn, "options", rt.ws, option["id"], status="proposed",
                  decision_id=decision_id)
    # The mail of the recommended option is written now, so the person
    # sees the exact text before the click. It is sent only after approval.
    if recommended.get("supplier_id"):
        db.emit(rt.conn, rt.ws, "action.requested",
                {"option_id": recommended["id"], "case_id": case["id"]},
                partition_key=f"case:{case['id']}",
                dedupe_key=f"action.requested:{recommended['id']}")


def _category(rt: runtime.Runtime, component_id: str) -> str | None:
    row = db.one(rt.conn, rt.ws,
                 "SELECT category FROM components WHERE workspace_id = ? "
                 "AND component_id = ?", (component_id,))
    return row["category"] if row else None


def _usual_buyers(rt: runtime.Runtime, component_id: str) -> list[str]:
    """Names of the buyers on the orders of this part, most frequent first."""
    counts: dict[str, int] = {}
    for fact in core.current_facts(rt, "po_line"):
        buyer = fact["data"].get("buyer")
        if fact["component_id"] == component_id and buyer and " " in str(buyer):
            counts[buyer] = counts.get(buyer, 0) + 1
    return sorted(counts, key=counts.get, reverse=True)


def _request_actions(rt: runtime.Runtime, case: dict[str, Any], found: list[dict[str, Any]]) -> None:
    """Free questions go out at once, all in parallel."""
    for option in found:
        if option.get("action_kind") not in _FREE_ACTIONS or option["status"] != "candidate":
            continue
        status = "proposed" if option["action_kind"] == "quote_request" else "in_execution"
        db.update(rt.conn, "options", rt.ws, option["id"], status=status)
        db.emit(rt.conn, rt.ws, "action.requested",
                {"option_id": option["id"], "case_id": case["id"]},
                partition_key=f"case:{case['id']}",
                dedupe_key=f"action.requested:{option['id']}")


def close_gaps(rt: runtime.Runtime, event: dict[str, Any] | None = None) -> None:
    """Runs the loop for every current gap that blocks a demand date."""
    del event
    state = core.compute(rt)
    bom = {}
    for row in db.rows(rt.conn, rt.ws, "SELECT * FROM bom_lines WHERE workspace_id = ?"):
        bom.setdefault(row["component_id"], {})[row["product_id"]] = row["qty_per"]
    gaps = db.rows(
        rt.conn, rt.ws,
        "SELECT * FROM gaps WHERE workspace_id = ? AND is_current = 1 "
        "AND gap_qty < 0 ORDER BY rank")
    rt.conn.execute("BEGIN IMMEDIATE")
    try:
        for gap in gaps:
            component = state.components.get(gap["component_id"])
            case = db.one(rt.conn, rt.ws,
                          "SELECT * FROM cases WHERE workspace_id = ? AND id = ?",
                          (gap["case_id"],))
            if component is None or case is None or case["impact"] != "deadline_blocker":
                continue
            _close_one(rt, state, gap, case, component, bom.get(gap["component_id"], {}))
        _escalate(rt, state)
    except Exception:
        rt.conn.execute("ROLLBACK")
        raise
    rt.conn.execute("COMMIT")


def _close_one(rt: runtime.Runtime, state: core.State, gap: dict[str, Any], case: dict[str, Any], component: core.ComponentState, qty_per: dict[str, float]) -> None:
    need = -gap["gap_qty"]
    found = []
    for generator in options_module.GENERATORS:
        if generator is options_module.standard.alt_source:
            continue
        for option in generator(rt, state, component):
            found.append(_upsert_option(rt, state, case, gap, option, component, qty_per))
    _, firm, soft = _plan(rt, need, found)
    if firm + soft < need:
        for option in options_module.standard.alt_source(rt, state, component):
            found.append(_upsert_option(rt, state, case, gap, option, component, qty_per))
    _expire_stale(rt, case, {o["id"] for o in found})
    plan, firm, soft = _plan(rt, need, found)
    roles = {}
    covered = 0.0
    for option in plan:
        roles[option["id"]] = "primary" if covered < need else "backup"
        covered += option["qty_gain"]
    for option in found:
        if option["status"] not in _LOCKED:
            db.update(rt.conn, "options", rt.ws, option["id"],
                      role_in_plan=roles.get(option["id"], "none"))
    rates = [state.products[p].rate_per_hour for p in qty_per
             if p in state.products and state.products[p].rate_per_hour]
    _request_actions(rt, case, [o for o in found if o["feasible"]])
    _decide(rt, case, gap, component, plan, state, max(rates) if rates else None)
    residual = max(need - firm - soft, 0.0)
    new_state = case["state"]
    if residual > 0:
        new_state = "unclosable"
        db.emit(rt.conn, rt.ws, "gap.unclosable",
                {"gap_id": gap["id"], "residual_qty": residual},
                priority=3, dedupe_key=f"gap.unclosable:{gap['id']}:{residual:g}")
        _alert_unclosable(rt, gap, case, component, residual)
    elif case["state"] in ("open", "unclosable"):
        new_state = "plan_proposed"
    if residual <= 0:
        approvals.retire_unclosable_decisions(rt, case["id"])
    units = sum(core.residual_by_line(component.short_lines, residual))
    detail = db.loads(gap["detail"], {})
    detail["residual_parts"] = residual
    db.update(rt.conn, "gaps", rt.ws, gap["id"], residual_qty=units,
              detail=detail, act_by=_iso(component.latest_useful_arrival))
    if new_state != case["state"]:
        db.update(rt.conn, "cases", rt.ws, case["id"], state=new_state,
                  updated_at=clock.iso())


def _alert_unclosable(rt: runtime.Runtime, gap: dict[str, Any], case: dict[str, Any],
                      component: core.ComponentState, residual: float) -> None:
    key = f"unclosable:{gap['id']}:{residual:g}"
    approvals.retire_unclosable_decisions(rt, case["id"], keep=key)
    existing = db.one(rt.conn, rt.ws,
                      "SELECT id FROM decisions WHERE workspace_id = ? AND dedupe_key = ?",
                      (key,))
    if existing:
        return
    chain = rt.pack.approval_policy.get("escalation") or []
    role = chain[-1] if chain else engine.fallback_role(rt)
    person = engine.resolve_person(rt, role)
    classes = sorted({line["class"] for line in component.short_lines if line.get("class")})
    affected = ", ".join(classes) if classes else "unknown"
    decision_id = db.insert(
        rt.conn, "decisions", rt.ws, case_id=case["id"], gap_id=gap["id"],
        title=f"{component.description}: shortage needs attention",
        options=[], recommended_option=None,
        explanation=(f"{_number(residual)} pieces remain without a known way to meet the deadline. "
                     f"Demand classes at risk: {affected}. "
                     "This alert does not confirm a later delivery date or cost. "
                     "Acknowledging this alert does not arrange a delivery or send an email."),
        approver_role=role, approver_name=person["name"] if person else None,
        needs_roles=[role], policy_ref=rt.pack.approval_policy.get("source"),
        deadline=clock.iso(), dedupe_key=key, created_at=clock.iso())
    db.emit(rt.conn, rt.ws, "decision.created", {"decision_id": decision_id},
            priority=3, dedupe_key=f"decision.created:{decision_id}")


def _expire_stale(rt: runtime.Runtime, case: dict[str, Any], current_ids: set[int]) -> None:
    """An option whose facts are gone expires, and its mail draft with it."""
    for row in db.rows(
            rt.conn, rt.ws,
            "SELECT id, status, kind, dedupe_key FROM options WHERE workspace_id = ? AND case_id = ?",
            (case["id"],)):
        if row["id"] in current_ids or row["status"] in (*_LOCKED, "expired"):
            continue
        changes = {"status": "expired", "feasible": 0, "role_in_plan": "none",
                   "infeasible_reason": "The document for this option is not valid any more"}
        if row["kind"] == "alt_source":
            changes["dedupe_key"] = f"{row['dedupe_key']}:expired:{row['id']}"
        db.update(rt.conn, "options", rt.ws, row["id"], **changes)
        rt.conn.execute(
            "UPDATE emails SET status = 'discarded' WHERE workspace_id = ? "
            "AND status = 'draft' AND action_id IN (SELECT id FROM actions "
            "WHERE workspace_id = ? AND option_id = ?)", (rt.ws, rt.ws, row["id"]))


def _escalate(rt: runtime.Runtime, state: core.State) -> None:
    """An open decision moves to the next role 30 minutes before it is due."""
    for decision in db.rows(
            rt.conn, rt.ws,
            "SELECT * FROM decisions WHERE workspace_id = ? AND status = 'open' "
            "AND deadline IS NOT NULL"):
        if clock.parse(decision["deadline"]) - _ESCALATE_BEFORE > state.at:
            continue
        following = engine.next_role(rt, decision["approver_role"])
        if following is None:
            continue
        person = engine.resolve_person(rt, following)
        db.update(rt.conn, "decisions", rt.ws, decision["id"],
                  approver_role=following, needs_roles=[following],
                  approver_name=person["name"] if person else None,
                  escalation_level=(decision["escalation_level"] or 0) + 1)
        db.emit(rt.conn, rt.ws, "decision.escalated",
                {"decision_id": decision["id"], "role": following}, priority=3,
                dedupe_key=f"decision.escalated:{decision['id']}:{following}")
