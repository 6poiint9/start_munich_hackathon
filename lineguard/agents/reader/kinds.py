"""Writes mapped table rows as facts and master data, one writer per kind.

The kinds and their required fields are listed in
docs/import-und-routen.md §1. A new kind is one function plus one entry in
`KINDS`.
"""

from collections.abc import Callable, Mapping
import dataclasses
import datetime
import re
import sqlite3
from typing import Any
import zoneinfo

from lineguard import clock
from lineguard import db
from lineguard import pack as pack_module
from lineguard import timeutil
from lineguard.agents.reader import tables

_WINDOW = re.compile(r"(\d{1,2}):(\d{2})\D+(\d{1,2}):(\d{2})")


@dataclasses.dataclass
class Context:
    """Everything a writer needs to store the rows of one table."""

    conn: sqlite3.Connection
    ws: str
    pack: pack_module.PackConfig
    file: Mapping[str, Any]
    rank: int
    as_of: str | None = None
    locator: str = ""
    touched: set[str] = dataclasses.field(default_factory=set)
    fact_count: int = 0

    def fact(self, fact_type: str, row_number: int, **columns: Any) -> int:
        """Stores one fact with its evidence: file, place and rank."""
        columns = {k: v for k, v in columns.items() if v not in (None, "")}
        component = columns.get("component_id")
        if component:
            self.touched.add(str(component))
        columns.setdefault("as_of", self.as_of)
        columns.setdefault(
            "source_locator", f"{self.locator}row {row_number}".strip())
        self.fact_count += 1
        return db.insert(
            self.conn, "facts", self.ws, fact_type=fact_type,
            source_file_id=self.file["id"], source_rank=self.rank,
            created_at=clock.iso(), **columns,
        )


def _extra(row: Mapping[str, Any], *used: str) -> dict[str, Any]:
    """The fields of a row that have no fact column of their own."""
    return {k: v for k, v in row.items() if k not in used and v not in (None, "")}


def _notes(ctx: Context, number: int, row: Mapping[str, Any], **link: Any) -> None:
    """Keeps free text as a fact. Wave 2 reads it with the LLM."""
    for field in tables.FREE_TEXT_FIELDS:
        text = row.get(field)
        if isinstance(text, str) and text.strip():
            ctx.fact("note", number, value_text=text.strip(),
                     source_locator=f"{ctx.locator}row {number}, column {field}",
                     **link)


def _products(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        ctx.conn.execute(
            "INSERT INTO products (workspace_id, product_id, description) "
            "VALUES (?, ?, ?) ON CONFLICT DO UPDATE SET "
            "description = excluded.description",
            (ctx.ws, row["product_id"], row.get("description")),
        )
        if row.get("demand_units"):
            ctx.fact("demand", number, product_id=row["product_id"],
                     qty=row["demand_units"], value_text="total")


def _components(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        ctx.conn.execute(
            "INSERT INTO components (workspace_id, component_id, description,"
            " category, released_rev) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT DO UPDATE SET description = excluded.description, "
            "category = excluded.category, "
            "released_rev = COALESCE(excluded.released_rev, released_rev)",
            (ctx.ws, row["component_id"], row.get("description"),
             row.get("category"), row.get("released_rev")),
        )
        ctx.touched.add(row["component_id"])


def _bom(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        ctx.conn.execute(
            "INSERT INTO bom_lines (workspace_id, product_id, component_id, "
            "qty_per, valid_from, valid_to) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT DO UPDATE SET qty_per = excluded.qty_per",
            (ctx.ws, row["product_id"], row["component_id"],
             row["qty_per"], row.get("valid_from"), row.get("valid_to")),
        )
        ctx.touched.add(row["component_id"])


def _bom_change(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        use_up = str(row.get("use_up_old_rev") or "").upper().startswith("Y")
        ctx.fact(
            "released_rev", number, component_id=row["component_id"],
            product_id=row.get("product_id"), rev=row.get("rev"),
            value_text=row.get("rev_old"), doc_date=row.get("doc_date"),
            data={"use_up_old_rev": use_up, **_extra(
                row, "component_id", "product_id", "rev", "rev_old",
                "doc_date", "use_up_old_rev")},
        )
        if row.get("rev"):
            ctx.conn.execute(
                "UPDATE components SET released_rev = ? "
                "WHERE workspace_id = ? AND component_id = ?",
                (row["rev"], ctx.ws, row["component_id"]),
            )
        new_qty = row.get("qty_per_new")
        if new_qty and row.get("product_id"):
            ctx.conn.execute(
                "UPDATE bom_lines SET qty_per = ? WHERE workspace_id = ? "
                "AND product_id = ? AND component_id = ?",
                (new_qty, ctx.ws, row["product_id"], row["component_id"]),
            )


def _master_update(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        link = {"component_id": row.get("component_id"),
                "supplier_id": row.get("supplier_id")}
        ctx.fact("master_update", number, value_text=row.get("field"),
                 data=_extra(row, "component_id", "supplier_id", "field"),
                 **link)
        if row.get("field") == "released_rev" and row.get("new"):
            ctx.conn.execute(
                "UPDATE components SET released_rev = ? "
                "WHERE workspace_id = ? AND component_id = ?",
                (row["new"], ctx.ws, row["component_id"]),
            )
        _notes(ctx, number, row, **link)


def _demand(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        ctx.fact("demand", number, product_id=row["product_id"],
                 qty=row["units"], eta=row.get("due_at"),
                 value_text=row.get("demand_class") or "total")


def _stock(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        if row.get("qty") is None:
            continue
        ctx.fact("stock_qty", number, component_id=row["component_id"],
                 batch=row.get("batch"), qty=row["qty"],
                 site_id=row.get("site_id"), as_of=row.get("as_of") or ctx.as_of,
                 data=_extra(row, "component_id", "batch", "qty", "site_id", "as_of"))


def _goods_receipts(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        link = {"ref": row.get("ref"), "po_number": row.get("po_number"),
                "po_line": row.get("po_line"),
                "supplier_id": row.get("supplier_id"),
                "component_id": row.get("component_id")}
        ctx.fact("gr_qty", number, qty=row.get("qty"),
                 value_num=row.get("qty_ordered"), doc_date=row.get("doc_date"),
                 site_id=row.get("site_id"), value_text=row.get("delivery_note"),
                 data=_extra(row, *link, "qty", "qty_ordered", "doc_date", "site_id"),
                 **link)
        _notes(ctx, number, row, **link)


def _delivery_notes(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        link = {"ref": row["ref"], "component_id": row.get("component_id"),
                "doc_date": row.get("doc_date")}
        ctx.fact("delivery_note_qty", number, qty=row.get("qty"), **link)
        if row.get("weight_kg") is not None:
            ctx.fact("delivery_note_weight_kg", number,
                     value_num=row["weight_kg"], **link)
        if row.get("packages") is not None:
            ctx.fact("delivery_note_packages", number,
                     value_num=row["packages"], **link)


def _purchase_orders(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        link = {"po_number": str(row["po_number"]), "po_line": row.get("po_line"),
                "supplier_id": row.get("supplier_id"),
                "component_id": row.get("component_id")}
        ctx.fact("po_line", number, qty=row.get("qty"),
                 value_num=row.get("unit_price"), eta=row.get("eta"),
                 rev=row.get("rev"), value_text=row.get("status"),
                 doc_date=row.get("order_date"),
                 data=_extra(row, *link, "qty", "unit_price", "eta", "rev",
                             "status", "order_date"),
                 **link)
        _notes(ctx, number, row, **link)


def _shipments(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        if not row.get("ref"):
            continue
        ctx.fact("shipment", number, ref=row["ref"],
                 supplier_id=row.get("supplier_id"), eta=row.get("eta"),
                 value_text=row.get("status"),
                 data=_extra(row, "ref", "supplier_id", "eta", "status"))
        _notes(ctx, number, row, ref=row["ref"],
               supplier_id=row.get("supplier_id"))


def _planned_inbound(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        ctx.fact("planned_inbound", number, component_id=row["component_id"],
                 qty=row.get("qty"), eta=row.get("eta"), ref=row.get("ref"),
                 value_text=row.get("status"),
                 data=_extra(row, "component_id", "qty", "eta", "ref", "status"))


def _build_status(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        product = row.get("product_id")
        packed = tables.parse_number(row.get("packed"))
        if not product or packed is None or not ctx.as_of:
            continue
        ctx.conn.execute(
            "INSERT OR REPLACE INTO build_status (workspace_id, as_of, "
            "product_id, packed, still_to_pack, rate_per_hour, source_file_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ctx.ws, ctx.as_of, product, packed, row.get("still_to_pack"),
             row.get("rate_per_hour"), ctx.file["id"]),
        )
        ctx.fact("packed_qty", number, product_id=product, qty=packed,
                 value_num=row.get("rate_per_hour"))
        if row.get("demand_units"):
            ctx.fact("demand", number, product_id=product,
                     qty=row["demand_units"], value_text="total")
        if row.get("demand_preordered"):
            ctx.fact("demand", number, product_id=product,
                     qty=row["demand_preordered"], value_text="preordered")
        ctx.touched.add("*")


def _build_log(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        ctx.fact("build_log", number, product_id=row.get("product_id"),
                 qty=row.get("qty"), doc_date=row.get("doc_date"),
                 data=_extra(row, "product_id", "qty", "doc_date"))


def _shifts(ctx: Context, rows: list[dict[str, Any]]) -> None:
    zone = zoneinfo.ZoneInfo(ctx.pack.timezone)
    anchor = ctx.pack.deadline.astimezone(zone)
    for number, row in enumerate(rows, 2):
        window = _WINDOW.search(str(row.get("window") or ""))
        day_text = str(row.get("day") or "")
        day = timeutil.weekday_before(day_text, anchor)
        if day is None and timeutil.normalize(day_text):
            day = datetime.date.fromisoformat(timeutil.normalize(day_text)[:10])
        if not window or day is None:
            continue
        start = datetime.datetime.combine(
            day, datetime.time(int(window[1]), int(window[2])), zone)
        end = datetime.datetime.combine(
            day, datetime.time(int(window[3]), int(window[4])), zone)
        ctx.fact("shift", number, eta=start.isoformat(),
                 valid_until=end.isoformat(), value_text=day_text,
                 data=_extra(row, "day", "window"))
        ctx.touched.add("*")


def _routes(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        ctx.fact("transit", number, value_text=row.get("origin"),
                 ref=row.get("destination"), value_num=row.get("transit_days"),
                 data=_extra(row, "origin", "destination", "transit_days"))


def _suppliers(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        supplier = row.get("supplier_id")
        if not supplier:
            continue
        as_of = ctx.as_of or ""
        if row.get("email"):
            ctx.conn.execute(
                "INSERT INTO contacts (workspace_id, supplier_id, name, "
                "contact_name, email, language, source_file_id, as_of) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO UPDATE SET "
                "name = excluded.name, contact_name = excluded.contact_name, "
                "email = excluded.email, language = excluded.language, "
                "source_file_id = excluded.source_file_id, "
                "as_of = excluded.as_of WHERE excluded.as_of >= contacts.as_of",
                (ctx.ws, supplier, row.get("name"), row.get("contact_name"),
                 row["email"], row.get("language"), ctx.file["id"], as_of),
            )
        if row.get("release_status"):
            ctx.fact("release_status", number, supplier_id=supplier,
                     value_text=row["release_status"],
                     valid_until=timeutil.normalize(row.get("valid_until")),
                     data={"status": row.get("status")})
        _notes(ctx, number, row, supplier_id=supplier)


def _supplier_parts(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        link = {"supplier_id": row.get("supplier_id"),
                "component_id": row.get("component_id")}
        ctx.fact("supplier_part", number, value_num=row.get("unit_price"),
                 data=_extra(row, *link, "unit_price"), **link)
        _notes(ctx, number, row, **link)


def _offers(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        ctx.fact("offer", number, supplier_id=row.get("supplier_id"),
                 component_id=row["component_id"], qty=row.get("qty"),
                 value_num=row.get("unit_price"),
                 valid_until=row.get("valid_until"),
                 data=_extra(row, "supplier_id", "component_id", "qty",
                             "unit_price", "valid_until"))


def _validity(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        ctx.fact("validity", number, supplier_id=row.get("supplier_id"),
                 component_id=row.get("component_id"),
                 value_text=row.get("subject"),
                 valid_until=row["valid_until"])


def _person_roles(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        ctx.fact("person_role", number, ref=row["person_id"],
                 value_text=row["role"],
                 data=_extra(row, "person_id", "role"))


def _notes_table(ctx: Context, rows: list[dict[str, Any]]) -> None:
    for number, row in enumerate(rows, 2):
        _notes(ctx, number, row)


def _reference(_: Context, __: list[dict[str, Any]]) -> None:
    """Reference tables (ports, sites) need no facts today."""


Writer = Callable[[Context, list[dict[str, Any]]], None]

# kind -> (required fields, writer)
KINDS: dict[str, tuple[tuple[str, ...], Writer]] = {
    "products": (("product_id",), _products),
    "components": (("component_id",), _components),
    "bom": (("product_id", "component_id", "qty_per"), _bom),
    "bom_change": (("component_id",), _bom_change),
    "master_update": (("field",), _master_update),
    "demand": (("product_id", "units"), _demand),
    "stock": (("component_id", "qty"), _stock),
    "goods_receipts": (("ref", "component_id", "qty"), _goods_receipts),
    "delivery_notes": (("ref", "qty"), _delivery_notes),
    "purchase_orders": (("po_number", "component_id", "qty"), _purchase_orders),
    "shipments": (("ref",), _shipments),
    "planned_inbound": (("component_id", "qty"), _planned_inbound),
    "build_status": (("product_id", "packed"), _build_status),
    "build_log": (("product_id", "qty"), _build_log),
    "shifts": (("day", "window"), _shifts),
    "routes": (("origin", "destination"), _routes),
    "suppliers": (("supplier_id",), _suppliers),
    "supplier_parts": (("component_id",), _supplier_parts),
    "offers": (("component_id", "qty"), _offers),
    "validity": (("valid_until",), _validity),
    "person_roles": (("person_id", "role"), _person_roles),
    "notes": ((), _notes_table),
    "reference": ((), _reference),
}


def write(ctx: Context, kind: str, rows: list[dict[str, Any]]) -> None:
    """Checks the required fields and stores the rows of one table.

    Raises:
        tables.TableError: The kind is unknown or a required field is
            missing in every row.
    """
    if kind not in KINDS:
        raise tables.TableError(f"Unknown table kind '{kind}'")
    required, writer = KINDS[kind]
    if rows:
        missing = [f for f in required if all(r.get(f) in (None, "") for r in rows)]
        if missing:
            raise tables.TableError(
                f"Kind '{kind}' lacks the required fields {missing}. "
                f"Columns found: {sorted(rows[0])}"
            )
    usable = [r for r in rows if all(r.get(f) not in (None, "") for f in required)]
    writer(ctx, usable)
