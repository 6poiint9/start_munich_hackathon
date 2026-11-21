"""Answers the core question: will we make the launch, and what breaks first?

The forecast runs two scenarios side by side:

- "plan" repeats what Soony's own launch plan believes: ERP stock as it is,
  every planned inbound with an ETA before the launch, no revision checks.
- "realistic" corrects this: it removes the parts used since the stock
  snapshot, blocks parts with a revision that must not be packed, adds the
  last leg from port or airport to Hamburg, and does not trust silent
  shipments.

The gap between the two scenarios is the answer to "The system says we are
fine. My gut says we are not."
"""

import dataclasses
import re

import pandas as pd

from soony_tower import model
from soony_tower import settings


@dataclasses.dataclass
class Inbound:
    shipment_id: str
    supplier_id: str | None
    material_id: str
    quantity: float | None
    quantity_source: str
    mode: str
    status: str
    eta: pd.Timestamp | None
    arrival_at_dc: pd.Timestamp | None
    in_time: bool
    silent_hours: float | None
    is_silent: bool
    reference: str
    source: str


@dataclasses.dataclass
class ComponentLine:
    material_id: str
    description: str
    need: float
    erp_stock: float
    used_since_snapshot: float
    on_hand: float
    revision_blocked: bool
    revision_note: str
    embedded_in: str | None
    inbound_plan: float
    inbound_realistic: float
    available_plan: float
    available_realistic: float


@dataclasses.dataclass
class ProductLine:
    product_id: str
    name: str
    day_one_qty: float
    packed: float
    packed_as_of: pd.Timestamp
    packed_source: str
    remaining: float
    rate_per_hour: float | None
    hours_left: float
    capacity: float | None
    by_parts_plan: float
    by_parts_realistic: float
    forecast_plan: float
    forecast_realistic: float
    limiting_factor: str


@dataclasses.dataclass
class Forecast:
    at: pd.Timestamp
    deadline: pd.Timestamp
    products: list[ProductLine]
    components: list[ComponentLine]
    inbound: list[Inbound]
    snapshot_as_of: pd.Timestamp | None


def _latest_packed(data: model.LaunchData, product_id: str) -> model.PackedCount:
    counts = [c for c in data.packed_counts if c.product_id == product_id]
    return max(counts, key=lambda c: c.as_of)


def _packed_at(data: model.LaunchData, product_id: str,
               moment: pd.Timestamp) -> float:
    counts = [c for c in data.packed_counts
              if c.product_id == product_id and c.as_of <= moment]
    return max(counts, key=lambda c: c.as_of).packed if counts else 0.0


def _shift_hours(data: model.LaunchData, start: pd.Timestamp) -> float:
    hours = 0.0
    for shift in data.shifts:
        begin = max(shift.start, start)
        if shift.end > begin:
            hours += (shift.end - begin).total_seconds() / 3600
    return hours


def _last_leg_days(data: model.LaunchData, origin: str, site: str) -> float:
    routes = data.routes
    match = routes[(routes["origin"] == origin) & (routes["destination"] == site)]
    if not match.empty:
        return float(match["transit_days"].min())
    return 0.0 if origin == site else settings.DEFAULT_LAST_LEG_DAYS


def _embedded_parts(data: model.LaunchData) -> dict[str, str]:
    """Finds parts a supplier fits into another part (not stocked alone)."""
    embedded = {}
    parts = data.supplier_parts
    for _, row in parts.iterrows():
        note = str(row.get("note") or "")
        host = re.search(r"into (CMP-[A-Z]+-\d+)", note)
        if host and "not ordered" in note.lower():
            embedded[row["material_id"]] = host[1]
    return embedded


def _effective_bom(data: model.LaunchData, at: pd.Timestamp) -> pd.DataFrame:
    bom = data.bom[data.bom["product_id"].isin(settings.LAUNCH_PRODUCTS)].copy()
    bom["revision_blocked"] = False
    bom["revision_note"] = ""
    for _, change in data.bom_changes.iterrows():
        effective = change.get("effective_from")
        if pd.notna(effective) and effective > at:
            continue
        mask = ((bom["product_id"] == change["product_id"]) &
                (bom["child_id"] == change["child_id"]))
        if pd.notna(change.get("qty_per_new")):
            bom.loc[mask, "qty_per"] = float(change["qty_per_new"])
        if str(change.get("use_up_old_rev", "")).upper().startswith("N"):
            bom.loc[mask, "revision_blocked"] = True
            bom.loc[mask, "revision_note"] = (
                f"{change['change_id']}: rev {change['rev_old']} must not be "
                f"packed, needs rev {change['rev_new']}. Stock shows no "
                f"revision. ({change['reason']})")
    return bom


def _inbound(data: model.LaunchData, at: pd.Timestamp,
             deadline: pd.Timestamp) -> list[Inbound]:
    planned = data.planned_inbound
    pos = data.purchase_orders
    # Silence is measured against the newest update in the same feed. If the
    # whole feed is old, that is one problem (see risks.py), not 25.
    feed_latest = data.shipments["updated_at"].max()
    usable_by = deadline - pd.Timedelta(hours=settings.RECEIVING_HOURS)
    result = []
    for _, ship in data.shipments.iterrows():
        materials = [m for m in str(ship.get("material_ids") or "").split("|") if m]
        plan_rows = planned[planned["reference"].astype(str) == str(ship["reference"])]
        if not materials and not plan_rows.empty:
            materials = plan_rows["material_id"].dropna().tolist()
        po_numbers = [p.strip() for p in str(ship.get("po_numbers") or "").split("|")
                      if p.strip() and p.strip() != "nan"]
        mode = str(ship.get("mode") or "")
        status = str(ship.get("status") or "")
        updated = ship.get("updated_at")
        silent_hours = ((feed_latest - updated).total_seconds() / 3600
                        if pd.notna(updated) else None)
        limit = settings.SILENT_AFTER_HOURS.get(mode, 24.0)
        is_silent = (silent_hours is not None and silent_hours > limit and
                     status not in ("booked", "delivered"))
        eta = ship.get("eta")
        eta = eta.tz_convert(settings.TIMEZONE) if pd.notna(eta) else None
        leg = _last_leg_days(data, str(ship.get("destination")),
                             str(ship.get("dest_site")))
        if eta is None:
            arrival = None
        elif status == "arrived_port":
            arrival = max(at, eta) + pd.Timedelta(days=settings.PORT_PICKUP_DAYS)
        elif status in ("in_delivery", "delivered"):
            arrival = eta
        else:
            arrival = eta + pd.Timedelta(days=leg)
        for material in materials:
            quantity, quantity_source = None, "unknown"
            match = plan_rows[plan_rows["material_id"] == material]
            if not match.empty:
                quantity = float(match["quantity"].sum())
                quantity_source = match["_source"].iloc[0]
            elif len(po_numbers) == 1:
                lines = pos[(pos["po_number"] == po_numbers[0]) &
                            (pos["material_id"] == material) &
                            (pos["status"] == "open")]
                if not lines.empty:
                    quantity = float(lines["quantity"].sum())
                    quantity_source = "open PO quantity"
            result.append(Inbound(
                shipment_id=ship["shipment_id"],
                supplier_id=ship.get("supplier_id"),
                material_id=material, quantity=quantity,
                quantity_source=quantity_source, mode=mode, status=status,
                eta=eta, arrival_at_dc=arrival,
                in_time=arrival is not None and arrival <= usable_by,
                silent_hours=silent_hours, is_silent=is_silent,
                reference=str(ship["reference"]),
                source="open_shipments.csv"))
    return result


def _allocate(remaining: dict[str, float], bom: pd.DataFrame,
              available: dict[str, float], embedded: dict[str, str]) -> dict[str, float]:
    """Gives shared parts to editions in priority order."""
    stock = dict(available)
    packable = {}
    for product_id in settings.EDITION_PRIORITY:
        rows = bom[(bom["product_id"] == product_id) &
                   (~bom["child_id"].isin(embedded))]
        limit = remaining[product_id]
        for _, row in rows.iterrows():
            limit = min(limit, max(stock.get(row["child_id"], 0.0), 0.0) / row["qty_per"])
        limit = float(int(limit))
        for _, row in rows.iterrows():
            stock[row["child_id"]] = stock.get(row["child_id"], 0.0) - limit * row["qty_per"]
        packable[product_id] = limit
    return packable


def run(data: model.LaunchData, at: pd.Timestamp | None = None) -> Forecast:
    """Computes the launch forecast at the given moment (default: now)."""
    at = at or model.now()
    deadline = data.shifts[-1].end
    bom = _effective_bom(data, at)
    embedded = _embedded_parts(data)
    stock_dates = data.stock["snapshot_date"].dropna()
    snapshot_as_of = (stock_dates.max().tz_convert(settings.TIMEZONE)
                      if not stock_dates.empty else None)

    products, remaining, used_since = [], {}, {}
    product_rows = data.products.set_index("product_id")
    for product_id in settings.LAUNCH_PRODUCTS:
        latest = _latest_packed(data, product_id)
        remaining[product_id] = max(
            product_rows.loc[product_id, "day_one_qty"] - latest.packed, 0.0)
        at_snapshot = (_packed_at(data, product_id, snapshot_as_of)
                       if snapshot_as_of is not None else latest.packed)
        used_since[product_id] = max(latest.packed - at_snapshot, 0.0)

    inbound = _inbound(data, at, deadline)
    planned = data.planned_inbound

    components = []
    available_plan, available_real = {}, {}
    descriptions = data.components.set_index("material_id")["description"].to_dict()
    for material_id, rows in bom.groupby("child_id"):
        need = sum(remaining[r.product_id] * r.qty_per for r in rows.itertuples())
        used = sum(used_since[r.product_id] * r.qty_per for r in rows.itertuples())
        erp = float(data.stock.loc[data.stock["material_id"] == material_id,
                                   "quantity"].sum())
        on_hand = max(erp - used, 0.0)
        blocked = bool(rows["revision_blocked"].any())
        plan_in = float(planned.loc[(planned["material_id"] == material_id) &
                                    (planned["eta"] <= deadline), "quantity"].sum())
        real_in = sum(i.quantity or 0.0 for i in inbound
                      if i.material_id == material_id and i.in_time and not i.is_silent)
        available_plan[material_id] = erp + plan_in
        available_real[material_id] = (0.0 if blocked else on_hand) + real_in
        components.append(ComponentLine(
            material_id=material_id,
            description=descriptions.get(material_id, material_id),
            need=need, erp_stock=erp, used_since_snapshot=used,
            on_hand=on_hand, revision_blocked=blocked,
            revision_note="; ".join(n for n in rows["revision_note"] if n),
            embedded_in=embedded.get(material_id),
            inbound_plan=plan_in, inbound_realistic=real_in,
            available_plan=available_plan[material_id],
            available_realistic=available_real[material_id]))

    by_plan = _allocate(remaining, bom, available_plan, embedded)
    by_real = _allocate(remaining, bom, available_real, embedded)

    for product_id in settings.LAUNCH_PRODUCTS:
        latest = _latest_packed(data, product_id)
        rate = data.rates_per_hour.get(product_id, (None,))[0]
        # The packed count is valid at its as_of time. The line keeps packing
        # after that, so the hours count from as_of, not from now.
        hours = _shift_hours(data, latest.as_of)
        capacity = rate * hours if rate else None
        candidates = {"parts": by_real[product_id], "time": capacity or float("inf")}
        limiting = min(candidates, key=candidates.get)
        forecast_real = min(by_real[product_id], capacity or float("inf"))
        products.append(ProductLine(
            product_id=product_id,
            name=str(product_rows.loc[product_id, "name"]),
            day_one_qty=float(product_rows.loc[product_id, "day_one_qty"]),
            packed=latest.packed, packed_as_of=latest.as_of,
            packed_source=latest.source, remaining=remaining[product_id],
            rate_per_hour=rate, hours_left=hours, capacity=capacity,
            by_parts_plan=by_plan[product_id],
            by_parts_realistic=by_real[product_id],
            forecast_plan=min(by_plan[product_id], remaining[product_id]),
            forecast_realistic=forecast_real,
            limiting_factor=(limiting if forecast_real < remaining[product_id]
                             else "none")))

    return Forecast(at, deadline, products, components, inbound, snapshot_as_of)
