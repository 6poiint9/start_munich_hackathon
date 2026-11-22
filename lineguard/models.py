"""Schemas for what the LLM returns. Every answer is validated here."""

from typing import Any

import pydantic

FACT_TYPES = (
    "delivery_note_qty", "delivery_note_weight_kg", "delivery_note_packages",
    "inspection_result", "shipped_qty", "inbound_qty", "artwork_rev", "offer",
    "order_confirmed", "supplier_condition",
    "not_stocked", "gr_exception_qty", "release_status", "validity",
    "person_role", "policy_rule", "counted_qty", "info",
)


class FactOut(pydantic.BaseModel):
    """One statement that the reader found in a document."""

    model_config = pydantic.ConfigDict(extra="ignore")

    fact_type: str
    component_id: str | None = None
    supplier_part: str | None = None
    supplier_id: str | None = None
    po_number: str | None = None
    po_line: str | None = None
    batch: str | None = None
    rev: str | None = None
    ref: str | None = None
    qty: float | None = None
    value_num: float | None = None
    value_text: str | None = None
    eta: str | None = None
    valid_until: str | None = None
    locator: str | None = None
    confidence: float = 0.8
    data: dict[str, Any] = {}

    @pydantic.field_validator("fact_type")
    @classmethod
    def _known_type(cls, value: str) -> str:
        if value not in FACT_TYPES:
            raise ValueError(f"unknown fact_type '{value}'")
        return value

    @pydantic.field_validator("po_number", "po_line", "batch", "rev", "ref",
                              "component_id", "supplier_id", mode="before")
    @classmethod
    def _as_text(cls, value: Any) -> Any:
        return None if value is None else str(value).strip() or None


class DocumentOut(pydantic.BaseModel):
    """The answer of the reader for one document."""

    model_config = pydantic.ConfigDict(extra="ignore")

    doc_class: str | None = None
    language: str | None = None
    doc_date: str | None = None
    summary: str = ""
    suspicious: bool = False
    suspicious_reason: str | None = None
    facts: list[FactOut] = []


class EmailDraftOut(pydantic.BaseModel):
    """A supplier mail written by the LLM. A human approves it."""

    model_config = pydantic.ConfigDict(extra="ignore")

    subject: str
    body: str
    language: str = "en"
    commits_money: bool = False
