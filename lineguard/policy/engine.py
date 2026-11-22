"""Approval rules as data, evaluated by code. No prompt decides here.

The rules come from `approval_policy.yaml` of the pack. Persons and their
roles are facts from the newest organisation chart of the customer
(docs/kern-und-kundenpaket.md §3, docs/betrieb-und-wartung.md W1).
"""

import datetime
from typing import Any

from lineguard import clock
from lineguard import runtime
from lineguard.coverage import core


class NotAllowedError(Exception):
    """The person does not hold a role that this approval needs."""

    def __init__(self, roles: list[str]):
        super().__init__(f"Diese Freigabe braucht die Rolle {' oder '.join(roles)}")
        self.roles = roles


def _rules(rt: runtime.Runtime, applies_to: str) -> list[dict[str, Any]]:
    return [rule for rule in rt.pack.approval_policy.get("rules", [])
            if rule.get("applies_to") == applies_to]


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def route(rt: runtime.Runtime, decision_type: str, value_eur: float = 0.0, flags: list[str] | None = None) -> list[str]:
    """Returns the roles that must approve, all of them.

    Args:
        decision_type: The `applies_to` of the main rule, for example
            `purchase_order` or `erp_correction`.
        value_eur: The cost of the decision.
        flags: More `applies_to` values whose `add_role` is added, for
            example `inbound_delivery` or `unreleased_part`.
    """
    roles: list[str] = []
    for rule in _rules(rt, decision_type):
        if "tiers" in rule:
            for tier in rule["tiers"]:
                if "lt_eur" not in tier or value_eur < tier["lt_eur"]:
                    roles.extend(_as_list(tier["role"]))
                    break
        elif "limit_eur_per_month_per_category" in rule:
            below = value_eur <= rule["limit_eur_per_month_per_category"]
            roles.extend(_as_list(rule["below"] if below else rule["above"]))
        else:
            roles.extend(_as_list(rule.get("role")))
            roles.extend(_as_list(rule.get("add_role")))
    for flag in flags or []:
        for rule in _rules(rt, flag):
            roles.extend(_as_list(rule.get("add_role")))
    if not roles:
        roles = [fallback_role(rt)]
    return list(dict.fromkeys(roles))


def has_rule(rt: runtime.Runtime, applies_to: str) -> bool:
    """True when the pack holds a rule for this decision type."""
    return bool(_rules(rt, applies_to))


def fallback_role(rt: runtime.Runtime) -> str:
    """The role that decides when a rule or a person is missing."""
    for rule in rt.pack.approval_policy.get("rules", []):
        if rule.get("fallback_role"):
            return rule["fallback_role"]
    escalation = rt.pack.approval_policy.get("escalation") or ["owner"]
    return escalation[-1]


def next_role(rt: runtime.Runtime, role: str) -> str | None:
    """The next role in the escalation chain."""
    chain = rt.pack.approval_policy.get("escalation") or []
    if role in chain and chain.index(role) + 1 < len(chain):
        return chain[chain.index(role) + 1]
    return None


def persons(rt: runtime.Runtime, at: datetime.datetime | None = None) -> dict[str, dict[str, Any]]:
    """All persons with the roles they hold at this moment."""
    at = at or clock.now()
    found: dict[str, dict[str, Any]] = {}
    facts = core.current_facts(rt, "person_role")
    # Several charts can exist. The one with the newest date wins as a whole.
    charts = {(f.get("doc_date") or "", f["source_file_id"] or 0) for f in facts
              if f["extracted_by"] != "parser"}
    newest = max(charts)[1] if charts else None
    for fact in facts:
        if fact["extracted_by"] != "parser" and fact["source_file_id"] != newest:
            continue
        data = fact["data"]
        if data.get("vacant") or str(fact["ref"]).upper() == "VACANT":
            continue
        valid_from = core.timeutil.to_datetime(
            data.get("valid_from"), rt.pack.timezone, end_of_day=False)
        if valid_from and valid_from > at:
            continue
        person = found.setdefault(fact["ref"], {
            "person_id": fact["ref"], "name": data.get("name") or fact["ref"],
            "roles": [], "categories": []})
        if fact["value_text"] not in person["roles"]:
            person["roles"].append(fact["value_text"])
        for text in (data.get("category"), data.get("title")):
            if text:
                person["categories"].append(str(text))
    return found


def resolve_person(rt: runtime.Runtime, role: str, category: str | None = None, at: datetime.datetime | None = None, preferred: list[str] | None = None) -> dict[str, Any] | None:
    """The person who holds a role now.

    Order: a holder among the preferred names (for example the usual
    buyer of the part), then a holder whose title or category names the
    category. If holders exist but none fits the category, the position
    for this category is vacant, and the fallback role of the policy
    decides. Without a category, the first holder is returned.
    """
    holders = [p for p in persons(rt, at).values() if role in p["roles"]]
    for name in preferred or []:
        for person in holders:
            if person["name"] == name:
                return person
    if category and holders:
        matching = [p for p in holders if any(
            category.lower() in c.lower() for c in p["categories"])]
        if matching:
            return matching[0]
        if any(p["categories"] for p in holders) and len(holders) > 1:
            holders = []
    if holders:
        return holders[0]
    fallback = fallback_role(rt)
    if role != fallback:
        return resolve_person(rt, fallback, None, at)
    return None


def require_role(rt: runtime.Runtime, person_id: str, needs_roles: list[str], at: datetime.datetime | None = None) -> dict[str, Any]:
    """Checks that the person holds one of the roles at this moment.

    A person with the fallback role may act for a role that nobody holds.

    Raises:
        NotAllowedError: The person holds none of the roles.
    """
    known = persons(rt, at)
    person = known.get(person_id)
    if person is None:
        raise NotAllowedError(needs_roles)
    if set(person["roles"]) & set(needs_roles):
        return person
    vacant = [r for r in needs_roles
              if not any(r in other["roles"] for other in known.values())]
    if vacant and fallback_role(rt) in person["roles"]:
        return person
    raise NotAllowedError(needs_roles)
