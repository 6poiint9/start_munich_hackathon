"""Stock Truth: the real coverage per part and product, as plain code.

No LLM takes part in any number. The calculation is a function of the
current facts, so it can run again at any time (architecture.md §2.3,
docs/dauerbetrieb.md §4, docs/lueckenschluss.md §2).

Two levels are computed with the same function:
    system   what the planning of the customer believes: stock as booked,
             every planned inbound before the deadline
    secured  stock minus proven deductions, inbound only with proof of
             rank 1 or 2 that arrives in time
"""

import dataclasses
import datetime
import math
from typing import Any

from lineguard import clock
from lineguard import db
from lineguard import runtime
from lineguard import timeutil

_OPEN_FINDINGS = ("proposed", "needs_count")
_DONE_SHIPMENT = ("delivered", "received", "cancelled")


@dataclasses.dataclass
class Line:
    """Units of one product that must be ready at one moment."""

    product_id: str
    demand_class: str
    units: float
    due_at: datetime.datetime
    open_units: float = 0.0
    buildable: dict[str, float] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class Block:
    """A quantity that is in the book stock but must not be counted."""

    reason: str
    qty: float
    text: str
    fact_ids: list[int] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Inbound:
    """Goods on the way to the site for one part."""

    component_id: str
    qty: float
    arrives_at: datetime.datetime | None
    rank: int
    ref: str | None
    status: str | None
    supplier_id: str | None
    po_number: str | None
    fact_ids: list[int]
    secured: bool = False


@dataclasses.dataclass
class ComponentState:
    """The computed state of one part of the bill of materials."""

    component_id: str
    description: str = ""
    stocked: bool = True
    carrier_component_id: str | None = None
    need: float = 0.0
    erp_stock: float = 0.0
    stock_as_of: str | None = None
    stock_time: datetime.datetime | None = None
    batches: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    used_since_snapshot: float = 0.0
    blocks: list[Block] = dataclasses.field(default_factory=list)
    usable: float = 0.0
    inbound: list[Inbound] = dataclasses.field(default_factory=list)
    inbound_secured: float = 0.0
    inbound_system: float = 0.0
    gap_qty: float = 0.0
    gap_system: float = 0.0
    short_lines: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    breaks_at: datetime.datetime | None = None
    latest_useful_arrival: datetime.datetime | None = None
    last_count: str | None = None
    batch_unknown: bool = False
    evidence_fact_ids: list[int] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class ProductState:
    """The computed state of one finished product."""

    product_id: str
    description: str = ""
    demand: float = 0.0
    packed: float = 0.0
    packed_as_of: datetime.datetime | None = None
    still_to_pack: float = 0.0
    rate_per_hour: float | None = None
    hours_left: float | None = None
    buildable: dict[str, float] = dataclasses.field(default_factory=dict)
    coverage: dict[str, float] = dataclasses.field(default_factory=dict)
    limiting_component: str | None = None


@dataclasses.dataclass
class State:
    """The result of one calculation for the whole workspace."""

    at: datetime.datetime
    next_due: datetime.datetime | None
    products: dict[str, ProductState]
    components: dict[str, ComponentState]
    lines: list[Line]
    shifts: list[tuple[datetime.datetime, datetime.datetime]]


def current_facts(rt: runtime.Runtime, fact_type: str) -> list[dict[str, Any]]:
    """Facts that count: current file version, not removed, not suspect."""
    found = db.rows(
        rt.conn, rt.ws,
        "SELECT f.* FROM facts f LEFT JOIN files x ON x.id = f.source_file_id "
        "WHERE f.workspace_id = ? AND f.fact_type = ? "
        "AND f.superseded_by IS NULL AND f.source_removed = 0 "
        "AND f.suspicious = 0 AND f.needs_review = 0 "
        "AND (x.id IS NULL OR x.is_current = 1) ORDER BY f.id",
        (fact_type,))
    for fact in found:
        fact["data"] = db.loads(fact["data"], {})
    return found


def _when(rt: runtime.Runtime, text: str | None) -> datetime.datetime | None:
    return timeutil.to_datetime(text, rt.pack.timezone)


def _newest(facts: list[dict[str, Any]], rt: runtime.Runtime) -> dict[str, Any] | None:
    """The fact with the best rank, and among those the newest as-of."""
    def key(fact: dict[str, Any]) -> tuple[int, float]:
        moment = _when(rt, fact.get("as_of"))
        return (-fact["source_rank"], moment.timestamp() if moment else 0.0)
    return max(facts, key=key) if facts else None


# ---------- demand ----------


def demand_lines(rt: runtime.Runtime) -> list[Line]:
    """Builds the demand lines: facts first, then the pack.

    A product with only a total gets one line at the pack deadline. A fact
    of the class 'preordered' splits the total into two lines.
    """
    by_product: dict[str, list[dict[str, Any]]] = {}
    for fact in current_facts(rt, "demand"):
        by_product.setdefault(fact["product_id"], []).append(fact)
    order = rt.pack.priority_order
    lines: list[Line] = []
    for product, facts in by_product.items():
        dated = [f for f in facts if f.get("eta") and f["value_text"] != "total"]
        if dated:
            for fact in dated:
                lines.append(Line(product, fact["value_text"], fact["qty"],
                                  _when(rt, fact["eta"]) or rt.pack.deadline))
            continue
        total = _newest([f for f in facts if f["value_text"] == "total"], rt)
        if total is None:
            continue
        first = _newest([f for f in facts if f["value_text"] == order[0]], rt)
        first_units = min(first["qty"], total["qty"]) if first else 0.0
        if first_units > 0:
            lines.append(Line(product, order[0], first_units, rt.pack.deadline))
        if total["qty"] - first_units > 0:
            lines.append(Line(product, order[-1], total["qty"] - first_units,
                              rt.pack.deadline))
    known = {line.product_id for line in lines}
    for item in rt.pack.demand:
        if item.product not in known:
            lines.append(Line(item.product, item.demand_class, item.units,
                              item.due_at or rt.pack.deadline))

    def sort_key(line: Line) -> tuple[datetime.datetime, int]:
        position = order.index(line.demand_class) if line.demand_class in order else len(order)
        return (line.due_at, position)
    return sorted(lines, key=sort_key)


# ---------- packed units and capacity ----------


def _packed_history(rt: runtime.Runtime, product_ids: set[str]) -> dict[str, list[tuple[datetime.datetime, float, float | None]]]:
    history: dict[str, list[tuple[datetime.datetime, float, float | None]]] = {}
    for row in db.rows(rt.conn, rt.ws,
                       "SELECT * FROM build_status WHERE workspace_id = ?"):
        moment = _when(rt, row["as_of"])
        if moment and row["product_id"] in product_ids:
            history.setdefault(row["product_id"], []).append(
                (moment, row["packed"], row["rate_per_hour"]))
    for fact in current_facts(rt, "stock_qty"):
        moment = _when(rt, fact.get("as_of"))
        if moment and fact["component_id"] in product_ids:
            history.setdefault(fact["component_id"], []).append(
                (moment, fact["qty"], None))
    for entries in history.values():
        entries.sort(key=lambda entry: entry[0])
    return history


def _shifts(rt: runtime.Runtime) -> list[tuple[datetime.datetime, datetime.datetime]]:
    windows = set()
    for fact in current_facts(rt, "shift"):
        start, end = _when(rt, fact["eta"]), _when(rt, fact["valid_until"])
        if start and end and end > start:
            windows.add((start, end))
    return sorted(windows)


def shift_hours(shifts: list[tuple[datetime.datetime, datetime.datetime]], start: datetime.datetime, end: datetime.datetime) -> float:
    """Working hours between two moments."""
    hours = 0.0
    for shift_start, shift_end in shifts:
        begin, finish = max(shift_start, start), min(shift_end, end)
        if finish > begin:
            hours += (finish - begin).total_seconds() / 3600
    return hours


def moment_after_hours(shifts: list[tuple[datetime.datetime, datetime.datetime]], start: datetime.datetime, hours: float) -> datetime.datetime | None:
    """The moment at which this many working hours have passed."""
    left = hours
    for shift_start, shift_end in shifts:
        begin = max(shift_start, start)
        if shift_end <= begin:
            continue
        available = (shift_end - begin).total_seconds() / 3600
        if left <= available:
            return begin + datetime.timedelta(hours=left)
        left -= available
    return None


# ---------- stock ----------


def _stock(rt: runtime.Runtime, state: State, bom: dict[str, dict[str, float]], history: dict[str, list[tuple[datetime.datetime, float, float | None]]]) -> None:
    groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for fact in current_facts(rt, "stock_qty"):
        if fact["component_id"] in state.components:
            groups.setdefault(fact["component_id"], {}).setdefault(
                fact.get("as_of") or "", []).append(fact)
    for component_id, by_as_of in groups.items():
        component = state.components[component_id]
        newest_as_of = max(by_as_of, key=lambda text: (_when(rt, text) or state.at).timestamp() if text else 0.0)
        newest = by_as_of[newest_as_of]
        component.erp_stock = sum(f["qty"] for f in newest)
        component.stock_as_of = newest_as_of or None
        component.evidence_fact_ids = [f["id"] for f in newest]
        counts = [f["data"].get("last_count") for f in newest if f["data"].get("last_count")]
        component.last_count = max(counts) if counts else None
        snapshot = _when(rt, newest_as_of)
        component.stock_time = snapshot
        if snapshot:
            component.used_since_snapshot = _used_since(
                snapshot, component_id, state, bom, history)
        with_batches = [
            (text, facts) for text, facts in by_as_of.items()
            if any(f.get("batch") for f in facts)]
        component.batch_unknown = not any(f.get("batch") for f in newest) and bool(with_batches)
        if with_batches:
            _, batch_facts = max(
                with_batches, key=lambda item: (_when(rt, item[0]) or state.at).timestamp())
            component.batches = [f for f in batch_facts if f.get("batch")]


def _used_since(snapshot: datetime.datetime, component_id: str, state: State, bom: dict[str, dict[str, float]], history: dict[str, list[tuple[datetime.datetime, float, float | None]]]) -> float:
    used = 0.0
    for product_id, product in state.products.items():
        qty_per = bom.get(product_id, {}).get(component_id)
        entries = history.get(product_id, [])
        if not qty_per or not entries:
            continue
        before = [packed for moment, packed, _ in entries if moment <= snapshot]
        if before and product.packed > before[-1]:
            used += (product.packed - before[-1]) * qty_per
    return used


def _blocks(rt: runtime.Runtime, state: State) -> None:
    """Collects proven deductions from the book stock per part."""
    findings = db.rows(
        rt.conn, rt.ws,
        "SELECT * FROM booking_findings WHERE workspace_id = ? "
        f"AND status IN ({', '.join('?' for _ in _OPEN_FINDINGS)})",
        _OPEN_FINDINGS)
    for finding in findings:
        component = state.components.get(finding["component_id"] or "")
        delta = (finding["booked_qty"] or 0) - (finding["proposed_qty"] or 0)
        if component and delta > 0:
            component.blocks.append(Block(
                "booking_finding", delta,
                f"Wareneingang {finding['gr_number']}: {finding['booked_qty']:,.0f} gebucht, "
                f"{finding['proposed_qty']:,.0f} belegt".replace(",", "."),
                [finding["gr_fact_id"]] if finding["gr_fact_id"] else []))
    for fact in current_facts(rt, "inspection_result"):
        component = state.components.get(fact["component_id"] or "")
        if component and fact["value_text"] == "fail" and fact.get("qty"):
            component.blocks.append(Block(
                "inspection_failed", fact["qty"],
                f"Charge {fact.get('batch') or '?'}: Prüfung nicht bestanden",
                [fact["id"]]))
    _revision_blocks(rt, state)


def released_rules(rt: runtime.Runtime) -> dict[str, dict[str, Any]]:
    """Per part: the released revision and whether old stock may be used."""
    rules: dict[str, dict[str, Any]] = {}
    for fact in current_facts(rt, "released_rev"):
        if fact.get("rev") and fact["component_id"]:
            rules[fact["component_id"]] = {
                "rev": fact["rev"], "fact_id": fact["id"],
                "use_up_old": bool(fact["data"].get("use_up_old_rev")),
                "text": fact["data"].get("reason") or "",
                "change_id": fact["data"].get("change_id"),
            }
    return rules


def _revision_blocks(rt: runtime.Runtime, state: State) -> None:
    rules = released_rules(rt)
    if not rules:
        return
    po_by_batch = {
        f["ref"]: f for f in current_facts(rt, "gr_qty") if f.get("ref")}
    rev_by_po: dict[str, dict[str, Any]] = {}
    for fact in current_facts(rt, "artwork_rev"):
        if fact.get("po_number") and fact.get("rev"):
            rev_by_po[f"{fact['po_number']}:{fact.get('component_id') or ''}"] = fact
            rev_by_po.setdefault(f"{fact['po_number']}:", fact)
    for component_id, rule in rules.items():
        component = state.components.get(component_id)
        if component is None or rule["use_up_old"]:
            continue
        for batch in component.batches:
            receipt = po_by_batch.get(batch["batch"])
            if receipt is None:
                continue
            rev_fact = (rev_by_po.get(f"{receipt['po_number']}:{component_id}")
                        or rev_by_po.get(f"{receipt['po_number']}:"))
            if rev_fact and rev_fact["rev"] != rule["rev"]:
                component.blocks.append(Block(
                    "wrong_revision", batch["qty"],
                    f"Charge {batch['batch']}: Revision {rev_fact['rev']}, "
                    f"freigegeben ist {rule['rev']}",
                    [rev_fact["id"], rule["fact_id"], batch["id"]]))


# ---------- inbound ----------


def _transit_hours(rt: runtime.Runtime, origin: str | None, facts: list[dict[str, Any]]) -> float:
    for fact in facts:
        if fact["value_text"] == origin and fact["ref"] == rt.pack.site:
            return float(fact["value_num"] or 0) * 24
    return 0.0


def _inbound(rt: runtime.Runtime, state: State) -> None:
    ordered: dict[tuple[str, str], float] = {}
    for fact in current_facts(rt, "po_line"):
        key = (fact["po_number"], fact["component_id"])
        ordered[key] = ordered.get(key, 0.0) + (fact["qty"] or 0)
    for fact in current_facts(rt, "gr_qty"):
        key = (fact["po_number"], fact["component_id"])
        if key in ordered:
            ordered[key] -= fact["qty"] or 0
    planned = current_facts(rt, "planned_inbound")
    transits = current_facts(rt, "transit")

    for fact in planned:
        component = state.components.get(fact["component_id"])
        eta = _when(rt, fact.get("eta"))
        if component and eta and state.next_due and eta <= state.next_due:
            component.inbound_system += fact["qty"] or 0

    best: dict[str, dict[str, Any]] = {}
    for fact in current_facts(rt, "shipment"):
        known = best.get(fact["ref"])
        if known is None or fact["source_rank"] < known["source_rank"]:
            best[fact["ref"]] = fact
    for fact in best.values():
        data = fact["data"]
        status = str(fact.get("value_text") or "").lower().replace(" ", "_")
        if status in _DONE_SHIPMENT:
            continue
        po_numbers = data.get("po_numbers") or []
        eta = _when(rt, fact.get("eta"))
        arrives = None
        if eta:
            # A shipment that waits at the port can leave now at the earliest.
            start = max(eta, state.at) if status == "arrived_port" else eta
            arrives = start + datetime.timedelta(
                hours=_transit_hours(rt, data.get("destination"), transits))
        for component_id in data.get("material_ids") or []:
            component = state.components.get(component_id)
            if component is None:
                continue
            plan = [p for p in planned if p.get("ref") == data.get("reference")
                    and p["component_id"] == component_id]
            open_qty = sum(max(ordered.get((po, component_id), 0.0), 0.0)
                           for po in po_numbers)
            has_po = any((po, component_id) in ordered for po in po_numbers)
            if plan:
                qty = sum(p["qty"] or 0 for p in plan)
            elif len(po_numbers) == 1 and has_po:
                qty = open_qty
            else:
                continue
            if has_po:
                qty = min(qty, open_qty)
            if qty <= 0:
                continue
            component.inbound.append(Inbound(
                component_id, qty, arrives, fact["source_rank"], fact["ref"],
                status, fact.get("supplier_id"),
                po_numbers[0] if po_numbers else None,
                [fact["id"], *(p["id"] for p in plan)]))

    for fact in current_facts(rt, "inbound_qty"):
        component = state.components.get(fact["component_id"] or "")
        if component is None or not fact.get("qty"):
            continue
        eta = _when(rt, fact.get("eta"))
        component.inbound.append(Inbound(
            component.component_id, fact["qty"], eta,
            fact["source_rank"], fact.get("ref"), fact.get("value_text"),
            fact.get("supplier_id"), fact.get("po_number"), [fact["id"]]))


# ---------- main calculation ----------


def compute(rt: runtime.Runtime, now: datetime.datetime | None = None) -> State:
    """Computes coverage, gaps and line stops from the current facts."""
    now = now or clock.now()
    all_lines = demand_lines(rt)
    lines = [line for line in all_lines if line.due_at > now]
    product_ids = {line.product_id for line in all_lines}
    descriptions = {
        row["product_id"]: row["description"] for row in db.rows(
            rt.conn, rt.ws, "SELECT * FROM products WHERE workspace_id = ?")}
    state = State(now, lines[0].due_at if lines else None, {}, {}, lines, _shifts(rt))
    history = _packed_history(rt, product_ids)

    for product_id in product_ids:
        product = ProductState(product_id, descriptions.get(product_id) or product_id)
        product.demand = sum(line.units for line in all_lines if line.product_id == product_id)
        entries = history.get(product_id, [])
        if entries:
            product.packed_as_of, product.packed, _ = entries[-1]
            rates = [rate for _, _, rate in entries if rate]
            product.rate_per_hour = rates[-1] if rates else None
        product.still_to_pack = max(product.demand - product.packed, 0.0)
        state.products[product_id] = product
        packed_left = product.packed
        for line in all_lines:
            if line.product_id != product_id:
                continue
            covered = min(line.units, packed_left)
            packed_left -= covered
            line.open_units = line.units - covered
        if product.rate_per_hour and state.shifts and state.next_due:
            # still_to_pack counts from the status moment, so do the hours.
            start = product.packed_as_of or now
            product.hours_left = shift_hours(state.shifts, start, state.next_due)

    bom: dict[str, dict[str, float]] = {}
    for row in db.rows(rt.conn, rt.ws,
                       "SELECT * FROM bom_lines WHERE workspace_id = ?"):
        if row["product_id"] in product_ids:
            bom.setdefault(row["product_id"], {})[row["component_id"]] = row["qty_per"]
    component_rows = {
        row["component_id"]: row for row in db.rows(
            rt.conn, rt.ws, "SELECT * FROM components WHERE workspace_id = ?")}
    for parts in bom.values():
        for component_id in parts:
            row = component_rows.get(component_id, {})
            state.components.setdefault(component_id, ComponentState(
                component_id, row.get("description") or component_id))
    for fact in current_facts(rt, "not_stocked"):
        component = state.components.get(fact["component_id"] or "")
        if component:
            component.stocked = False
            component.carrier_component_id = fact.get("value_text")
            component.evidence_fact_ids.append(fact["id"])

    _stock(rt, state, bom, history)
    _blocks(rt, state)
    _inbound(rt, state)
    for component in state.components.values():
        stock_now = max(component.erp_stock - component.used_since_snapshot, 0.0)
        blocked = min(sum(b.qty for b in component.blocks), stock_now)
        component.usable = stock_now - blocked
    _allocate(rt, state, bom, "system")
    _allocate(rt, state, bom, "secured")
    _line_stops(state, bom)
    return state


def _latest_useful_arrival(rt: runtime.Runtime, state: State, line: Line, missing_units: float) -> datetime.datetime:
    """After this moment, goods cannot pass the line before the due date."""
    product = state.products[line.product_id]
    handling = datetime.timedelta(hours=rt.pack.coverage.default_handling_hours)
    if not product.rate_per_hour:
        return line.due_at - handling
    hours = missing_units / product.rate_per_hour
    moment = line.due_at
    for shift_start, shift_end in reversed(state.shifts):
        end = min(shift_end, line.due_at)
        if end <= shift_start:
            continue
        available = (end - shift_start).total_seconds() / 3600
        if hours <= available:
            return end - datetime.timedelta(hours=hours) - handling
        hours -= available
        moment = shift_start
    return moment - handling


def _allocate(rt: runtime.Runtime, state: State, bom: dict[str, dict[str, float]], level: str) -> None:
    """Gives stock and inbound to the demand lines in order of due date.

    A later demand never takes stock from an earlier one
    (docs/dauerbetrieb.md §4).
    """
    rest: dict[str, float] = {}
    unused: dict[str, list[Inbound]] = {}
    for component_id, component in state.components.items():
        if level == "system":
            rest[component_id] = component.erp_stock + component.inbound_system
        else:
            rest[component_id] = component.usable
            unused[component_id] = list(component.inbound)
            component.need = 0.0
            component.gap_qty = 0.0
    for line in state.lines:
        parts = bom.get(line.product_id, {})
        possible = line.open_units
        shortages = []
        for component_id, qty_per in parts.items():
            component = state.components[component_id]
            if not component.stocked:
                continue
            need = line.open_units * qty_per
            if level == "secured":
                component.need += need
                useful = _latest_useful_arrival(rt, state, line, 0.0)
                for inbound in list(unused[component_id]):
                    in_time = inbound.arrives_at is not None and inbound.arrives_at <= useful
                    if inbound.rank <= 2 and in_time:
                        inbound.secured = True
                        rest[component_id] += inbound.qty
                        component.inbound_secured += inbound.qty
                        unused[component_id].remove(inbound)
            gap = rest[component_id] - need
            possible = min(possible, math.floor(max(rest[component_id], 0.0) / qty_per))
            rest[component_id] = max(gap, 0.0)
            if gap < 0:
                shortages.append((component, gap, qty_per))
        for component, gap, qty_per in shortages:
            if level == "system":
                component.gap_system += gap
                continue
            component.gap_qty += gap
            missing_units = -gap / qty_per
            component.short_lines.append({
                "product_id": line.product_id, "class": line.demand_class,
                "due_at": line.due_at.isoformat(), "gap_qty": gap,
                "units_at_risk": missing_units,
            })
            useful = _latest_useful_arrival(rt, state, line, missing_units)
            if component.latest_useful_arrival is None or useful < component.latest_useful_arrival:
                component.latest_useful_arrival = useful
        line.buildable[level] = possible
    for product in state.products.values():
        own = [line for line in state.lines if line.product_id == product.product_id]
        buildable = sum(line.buildable.get(level, 0.0) for line in own)
        if product.rate_per_hour and product.hours_left is not None:
            buildable = min(buildable, product.rate_per_hour * product.hours_left)
        product.buildable[level] = buildable
        product.coverage[level] = (
            (product.packed + min(product.still_to_pack, buildable)) / product.demand
            if product.demand else 1.0)
        if level == "secured":
            short = [c for c in state.components.values()
                     if any(s["product_id"] == product.product_id for s in c.short_lines)]
            if short:
                worst = min(short, key=lambda c: c.gap_qty)
                product.limiting_component = worst.component_id


def _line_stops(state: State, bom: dict[str, dict[str, float]]) -> None:
    """The moment a part runs out at the current rate in the shift plan."""
    for component in state.components.values():
        if component.gap_qty >= 0 or not state.shifts:
            continue
        per_hour = 0.0
        # The stock is valid at its own moment. The line packs on from there.
        start = component.stock_time or state.at
        for product_id, product in state.products.items():
            qty_per = bom.get(product_id, {}).get(component.component_id)
            if qty_per and product.rate_per_hour and product.still_to_pack > 0:
                per_hour += product.rate_per_hour * qty_per
        if per_hour > 0:
            component.breaks_at = moment_after_hours(
                state.shifts, start, component.usable / per_hour)
