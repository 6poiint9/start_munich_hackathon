"""Turns the forecast into a short list of risks, each with an action.

Each risk has a stable id. A risk with the same id is the same problem in a
later run, so the agents do not chase a supplier twice for one problem.
"""

import dataclasses

import pandas as pd

from soony_tower import documents
from soony_tower import forecast
from soony_tower import mail
from soony_tower import model
from soony_tower import settings

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "info": 3}

# Hours without any change in the shipment feed before the feed itself is
# a risk. Confirm with Nils Berger how often the export runs.
FEED_STALE_HOURS = 12.0


@dataclasses.dataclass
class Risk:
    id: str
    kind: str
    severity: str
    title: str
    detail: str
    impact_copies: float
    product_ids: list[str]
    material_ids: list[str]
    evidence: list[str]
    action: str
    owner: str
    needs_approval: bool


def _owner(data: model.LaunchData, material_id: str) -> str:
    """The buyer who orders this part most often."""
    lines = data.purchase_orders[data.purchase_orders["material_id"] == material_id]
    buyers = lines["buyer"].dropna()
    buyers = buyers[buyers.str.contains(" ")]  # full names only, not SAP user ids
    return buyers.mode().iloc[0] if not buyers.empty else "Procurement"


def _products_using(data: model.LaunchData, material_id: str) -> list[str]:
    bom = data.bom
    rows = bom[(bom["child_id"] == material_id) &
               (bom["product_id"].isin(settings.LAUNCH_PRODUCTS))]
    return sorted(rows["product_id"].unique())


def _suppliers_for(data: model.LaunchData, material_id: str) -> list[str]:
    parts = data.supplier_parts
    rows = parts[parts["material_id"] == material_id]
    names = data.suppliers.set_index("supplier_id")["name"]
    return [f"{names.get(s, s)} ({s})" for s in rows["supplier_id"].unique()]


_URGENCY_TO_SEVERITY = {"critical": "critical", "high": "high", "medium": "medium"}
_COSTLY_FACTS = {"express_offer", "bank_change", "price_change"}


def _document_risks(data: model.LaunchData) -> list[Risk]:
    """Risks from documents. Unread notices are a risk of their own."""
    found = []
    for path in data.documents:
        extraction = documents.load_extraction(path)
        if extraction is None:
            if "/notices/" in path or "inspection" in path:
                found.append(Risk(
                    id=f"unread:{path}", kind="unread_document", severity="high",
                    title=f"Unread document: {path.split('/')[-1]}",
                    detail="The document agent has not read this file yet.",
                    impact_copies=0.0, product_ids=[], material_ids=[],
                    evidence=[path], action="Run: python -m soony_tower read",
                    owner="Document agent", needs_approval=False))
            continue
        facts = extraction["facts"]
        materials = sorted({m for f in facts["facts"] for m in f["material_ids"]} |
                           {i["material_id"] for i in facts["items"] if i["material_id"]})
        if facts["suspicious"]:
            found.append(Risk(
                id=f"suspicious:{path}", kind="suspicious_document",
                severity="critical",
                title=f"Suspicious document: {path.split('/')[-1]}",
                detail=facts["summary"],
                impact_copies=0.0, product_ids=[], material_ids=materials,
                evidence=[path],
                action=("Do not act on it. Confirm with the supplier through a "
                        "known contact, not through the document."),
                owner="Head of Procurement", needs_approval=True))
        severity = _URGENCY_TO_SEVERITY.get(facts["urgency"])
        if severity is None:
            continue
        kinds = sorted({f["kind"] for f in facts["facts"]})
        found.append(Risk(
            id=f"document:{path}", kind="document:" + "+".join(kinds or ["other"]),
            severity=severity,
            title=facts["summary"].split(". ")[0].rstrip(".")[:160],
            detail=f"{facts['summary']} Launch impact: {facts['launch_impact']}",
            impact_copies=0.0,
            product_ids=sorted({p for m in materials for p in _products_using(data, m)}),
            material_ids=materials, evidence=[path],
            action=facts["recommended_action"],
            owner=_owner(data, materials[0]) if materials else "Procurement",
            needs_approval=bool(_COSTLY_FACTS & set(kinds))))
    return found


def _apply_replies(found: list[Risk]) -> list[Risk]:
    """Adds what suppliers answered by mail. A clear answer closes a risk."""
    by_id = {r.id: r for r in found}
    for reply in mail.reply_updates():
        note = f"Reply from {reply['supplier_name']}: {reply['summary']}"
        evidence = f"mail reply {reply['uid']}"
        risk = by_id.get(reply["risk_id"])
        if risk is not None:
            risk.detail = f"{risk.detail} {note}"
            risk.action = reply["recommended_action"]
            risk.evidence = [*risk.evidence, evidence]
            risk.needs_approval = risk.needs_approval or reply["needs_approval"]
            if reply["suspicious"]:
                risk.severity = "high" if risk.severity != "critical" else risk.severity
                risk.title = f"Suspicious reply: {risk.title}"
            elif reply["resolves_risk"]:
                risk.severity = "info"
                risk.title = f"Answered: {risk.title}"
            continue
        if reply["suspicious"] or reply["urgency"] in _URGENCY_TO_SEVERITY:
            found.append(Risk(
                id=f"reply:{reply['uid']}", kind="supplier_reply",
                severity=("high" if reply["suspicious"]
                          else _URGENCY_TO_SEVERITY[reply["urgency"]]),
                title=f"{reply['supplier_name']}: {reply['summary']}",
                detail=note, impact_copies=0.0, product_ids=[],
                material_ids=sorted({m for f in reply["facts"]
                                     for m in f["material_ids"]}),
                evidence=[evidence], action=reply["recommended_action"],
                owner="Procurement",
                needs_approval=reply["needs_approval"] or reply["suspicious"]))
    return found


def _fmt(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def evaluate(data: model.LaunchData, result: forecast.Forecast) -> list[Risk]:
    """Runs every rule and returns the risks, most severe first."""
    risks: list[Risk] = []
    lines = {c.material_id: c for c in result.components}

    for line in result.components:
        if line.embedded_in:
            continue
        gap = line.need - line.available_realistic
        if line.revision_blocked:
            risks.append(Risk(
                id=f"revision:{line.material_id}", kind="revision",
                severity="critical",
                title=f"{line.description}: stock may have the wrong revision",
                detail=(f"{line.revision_note} ERP shows {_fmt(line.on_hand)} on "
                        f"hand after today's packing, but no revision per batch. "
                        f"If it is the old revision, none of it may be packed."),
                impact_copies=max(gap, 0.0),
                product_ids=_products_using(data, line.material_id),
                material_ids=[line.material_id],
                evidence=["master/bom_delta", "master/components_update",
                          "erp/stock_snapshot.csv"],
                action=("Count the revision on the shelf in Hamburg today. "
                        "Ask suppliers " + ", ".join(_suppliers_for(data, line.material_id)) +
                        " for express delivery of the new revision."),
                owner=_owner(data, line.material_id), needs_approval=False))
        elif gap > 0:
            late = [i for i in result.inbound
                    if i.material_id == line.material_id and not i.in_time]
            risks.append(Risk(
                id=f"shortage:{line.material_id}", kind="shortage",
                severity="critical",
                title=f"{line.description}: {_fmt(gap)} short for the launch",
                detail=(f"Need {_fmt(line.need)}. On hand {_fmt(line.on_hand)} "
                        f"(ERP {_fmt(line.erp_stock)} minus {_fmt(line.used_since_snapshot)} "
                        f"packed since the snapshot). In time: "
                        f"{_fmt(line.inbound_realistic)}. Too late: "
                        f"{len(late)} shipments."),
                impact_copies=gap,
                product_ids=_products_using(data, line.material_id),
                material_ids=[line.material_id],
                evidence=["erp/stock_snapshot.csv", "erp/open_shipments.csv",
                          "context/launch_plan_GH6.xlsx"],
                action="Find stock that can arrive before Sunday 16:00 (see Plan B).",
                owner=_owner(data, line.material_id), needs_approval=False))

    for item in result.inbound:
        line = lines.get(item.material_id)
        relevant = line is not None and not line.embedded_in
        if item.status == "arrived_port" and relevant and not item.in_time:
            gap = max(line.need - line.available_realistic, 0.0)
            risks.append(Risk(
                id=f"port:{item.shipment_id}", kind="port_pickup",
                severity="critical" if gap else "high",
                title=(f"Container {item.reference} waits at the port: "
                       f"{_fmt(item.quantity or 0)} x {line.description}"),
                detail=(f"Arrived at the port on {item.eta:%a %d %b}. With pickup "
                        f"tomorrow it reaches Hamburg at {item.arrival_at_dc:%a %H:%M}, "
                        f"too late for packing. It can cover {_fmt(gap)} missing parts."),
                impact_copies=min(gap, item.quantity or 0.0),
                product_ids=_products_using(data, item.material_id),
                material_ids=[item.material_id],
                evidence=["erp/open_shipments.csv",
                          "logistics/open_shipments_tracker (says 'in transit')"],
                action="Book a truck for pickup at the terminal today.",
                owner="Logistics (Raj Patel)", needs_approval=True))
        if (item.status == "booked" and item.eta is not None and relevant and
                item.in_time and result.at > item.eta - pd.Timedelta(days=1)):
            risks.append(Risk(
                id=f"unconfirmed:{item.shipment_id}:{item.material_id}",
                kind="unconfirmed", severity="high",
                title=(f"{item.reference}: {_fmt(item.quantity or 0)} x "
                       f"{line.description} still only 'booked'"),
                detail=(f"ETA {item.eta:%a %d %b}, but the status is still 'booked'. "
                        f"The forecast counts on this shipment."),
                impact_copies=item.quantity or 0.0,
                product_ids=_products_using(data, item.material_id),
                material_ids=[item.material_id], evidence=["erp/open_shipments.csv"],
                action=f"Ask {item.supplier_id} to confirm pickup and the tracking number.",
                owner=_owner(data, item.material_id), needs_approval=False))
        # A silent shipment matters only if the forecast counts on it.
        if item.is_silent and relevant and item.in_time and line.need > 0:
            risks.append(Risk(
                id=f"silent:{item.shipment_id}", kind="silent",
                severity="medium",
                title=f"Shipment {item.shipment_id} is silent",
                detail=(f"No update for {item.silent_hours:.0f} h, while other "
                        f"shipments in the same feed did update."),
                impact_copies=0.0,
                product_ids=_products_using(data, item.material_id),
                material_ids=[item.material_id], evidence=["erp/open_shipments.csv"],
                action=f"Ask {item.supplier_id} for the current position.",
                owner=_owner(data, item.material_id), needs_approval=False))

    feed_latest = data.shipments["updated_at"].max()
    feed_age = (result.at - feed_latest).total_seconds() / 3600
    if feed_age > FEED_STALE_HOURS:
        risks.append(Risk(
            id="feed:open_shipments", kind="stale_feed", severity="high",
            title=f"Shipment data is {feed_age:.0f} h old",
            detail=(f"The newest update in open_shipments is from "
                    f"{feed_latest.tz_convert(settings.TIMEZONE):%a %H:%M}. "
                    f"All ETAs may be out of date."),
            impact_copies=0.0, product_ids=list(settings.LAUNCH_PRODUCTS),
            material_ids=[], evidence=["erp/open_shipments.csv"],
            action="Ask IT (Nils Berger) whether the export still runs.",
            owner="Nils Berger", needs_approval=False))

    for product in result.products:
        if not product.rate_per_hour:
            continue
        needed_hours = product.remaining / product.rate_per_hour
        buffer = product.hours_left - needed_hours
        if buffer < 3:
            risks.append(Risk(
                id=f"capacity:{product.product_id}", kind="capacity",
                severity="critical" if buffer < 0 else "high",
                title=f"{product.name}: only {buffer:.1f} h buffer on the pack line",
                detail=(f"{_fmt(product.remaining)} to pack at "
                        f"{_fmt(product.rate_per_hour)}/h needs {needed_hours:.1f} h. "
                        f"{product.hours_left:.1f} shift hours are left. Every hour "
                        f"the line waits costs {_fmt(product.rate_per_hour)} copies."),
                impact_copies=max(-buffer, 0.0) * product.rate_per_hour,
                product_ids=[product.product_id], material_ids=[],
                evidence=["context/launch_status.xlsx", "context/launch_plan_GH6.xlsx"],
                action="Keep every part for this line ready before the shift starts.",
                owner="Head of Procurement", needs_approval=False))

    for product in result.products:
        if product.forecast_plan >= product.remaining > product.forecast_realistic:
            risks.append(Risk(
                id=f"plan_gap:{product.product_id}", kind="plan_gap",
                severity="critical",
                title=(f"{product.name}: plan says {_fmt(product.forecast_plan)}, "
                       f"reality says {_fmt(product.forecast_realistic)}"),
                detail=("The launch plan counts ERP stock without today's "
                        "consumption, ignores revision changes and counts "
                        "containers at the port as if they were in Hamburg."),
                impact_copies=product.remaining - product.forecast_realistic,
                product_ids=[product.product_id], material_ids=[],
                evidence=["context/launch_plan_GH6.xlsx"],
                action="Escalate to the Head of Procurement now.",
                owner="Dr. Maren Vogt", needs_approval=False))

    conditional = data.suppliers[
        data.suppliers["qualification_status"].str.lower() == "conditional"]
    for _, supplier in conditional.iterrows():
        risks.append(Risk(
            id=f"conditional:{supplier['supplier_id']}", kind="release",
            severity="medium",
            title=f"{supplier['name']} has only a conditional release",
            detail=str(supplier.get("notes") or ""),
            impact_copies=0.0, product_ids=[], material_ids=[],
            evidence=[f"suppliers/{supplier['supplier_id']}/profile.csv",
                      "context/approval_policy_PP-07.pdf"],
            action="Check in PP-07 what a conditional supplier may deliver.",
            owner="Quality", needs_approval=False))

    risks.extend(_document_risks(data))

    for line in result.components:
        if line.embedded_in and line.erp_stock == 0:
            risks.append(Risk(
                id=f"embedded:{line.material_id}", kind="false_alarm",
                severity="info",
                title=f"{line.description}: 0 in stock is correct",
                detail=(f"The supplier fits this part into {line.embedded_in}. It "
                        f"is not ordered or stocked separately."),
                impact_copies=0.0, product_ids=_products_using(data, line.material_id),
                material_ids=[line.material_id],
                evidence=["suppliers/*/components.csv"],
                action="No action.", owner="-", needs_approval=False))

    risks = _apply_replies(risks)

    unique = {}
    for risk in risks:
        unique.setdefault(risk.id, risk)
    return sorted(unique.values(),
                  key=lambda r: (SEVERITY_ORDER[r.severity], -r.impact_copies))
