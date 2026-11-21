"""Reads tables into rows with core field names, without an LLM.

Rules are in docs/import-und-routen.md §3. The order for mapping a column:
`columns` of the route, then the alias list of the core. A customer value
(a column name of one customer, an id format) comes from the route.
"""

from collections.abc import Iterable, Mapping
import csv
import io
import json
import re
from typing import Any
import zoneinfo

import openpyxl

from lineguard import pack as pack_module
from lineguard import timeutil

ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")

# Core field -> spellings. Generic words and the field names of the ERP
# vendor. These hold for every customer of that ERP.
ALIASES: dict[str, tuple[str, ...]] = {
    "product_id": ("product_id", "product", "parent_id"),
    "component_id": ("component_id", "material_id", "material", "matnr",
                     "child_id", "part"),
    "supplier_id": ("supplier_id", "lifnr", "vendor"),
    "po_number": ("po_number", "ebeln"),
    "po_line": ("po_line", "ebelp"),
    "qty": ("qty", "quantity", "menge", "qty_received"),
    "qty_ordered": ("qty_ordered",),
    "unit_price": ("unit_price", "netpr"),
    "site_id": ("site_id", "site", "plant", "werks"),
    "batch": ("batch", "charg"),
    "order_date": ("order_date", "bedat"),
    "requested_date": ("requested_date", "eindt"),
    "actual_delivery_date": ("actual_delivery_date", "wedat"),
    "buyer": ("buyer", "ernam"),
    "ref": ("ref", "gr_number"),
    "doc_date": ("doc_date", "gr_date"),
    "as_of": ("as_of", "snapshot_date"),
}

NUMBER_FIELDS = frozenset({
    "qty", "qty_ordered", "qty_per", "qty_per_new", "unit_price", "units",
    "demand_units", "demand_preordered", "packed", "still_to_pack",
    "rate_per_hour", "transit_days", "weight_kg", "packages",
    "lead_time_hours", "lead_time_days",
})
DATE_FIELDS = frozenset({
    "as_of", "eta", "etd", "valid_until", "doc_date", "due_at", "last_count",
    "order_date", "requested_date", "actual_delivery_date", "updated_at",
})
FREE_TEXT_FIELDS = ("note", "remark", "notes", "text")

_THOUSANDS_DOT = re.compile(r"-?\d{1,3}(\.\d{3})+")


class TableError(Exception):
    """A table cannot be read or lacks a required field."""


def normalize_name(name: object) -> str:
    """Lowercases a column name and keeps only letters and digits."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def parse_number(value: object) -> float | None:
    """Parses '554.000', '1.234,5', '1,234.5', '640,000' and '1,5200'."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "").replace("\u00a0", "")
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif _THOUSANDS_DOT.fullmatch(text):
        text = text.replace(".", "")
    elif "," in text:
        head, _, tail = text.rpartition(",")
        if len(tail) == 3:
            text = text.replace(",", "")
        else:
            text = f"{head.replace(',', '')}.{tail}"
    try:
        return float(text)
    except ValueError:
        return None


def decode(data: bytes) -> str:
    """Decodes text with the first encoding that fits."""
    for encoding in ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise TableError("Unknown text encoding")


def read_csv(data: bytes) -> list[dict[str, str]]:
    """Reads a CSV file. Detects the encoding and the delimiter."""
    text = decode(data)
    sample = "\n".join(text.splitlines()[:20])
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return [dict(row) for row in reader]


def _field_lookup(route_columns: Mapping[str, str]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for field, spellings in ALIASES.items():
        for spelling in spellings:
            lookup.setdefault(normalize_name(spelling), field)
    for column, field in route_columns.items():
        lookup[normalize_name(column)] = field
    return lookup


def map_rows(
    raw_rows: Iterable[Mapping[str, Any]],
    route: pack_module.Route,
    columns: Mapping[str, str] | None = None,
    file_path: str = "",
) -> list[dict[str, Any]]:
    """Renames columns to core fields and parses numbers and dates.

    Unknown columns keep their own name, so no value of the file is lost.
    """
    route_columns = {**route.columns, **(columns or {})}
    lookup = _field_lookup(route_columns)
    mapped_rows = []
    for raw in raw_rows:
        mapped: dict[str, Any] = {}
        for column, value in raw.items():
            if column is None:
                continue
            field = lookup.get(normalize_name(column), str(column))
            if field not in mapped or mapped[field] in (None, ""):
                mapped[field] = value.strip() if isinstance(value, str) else value
        mapped_rows.append(mapped)
    _apply_route_rules(mapped_rows, route, file_path)
    _parse_typed(mapped_rows)
    return mapped_rows


def _apply_route_rules(rows: list[dict[str, Any]], route: pack_module.Route, file_path: str) -> None:
    path_values = {}
    for field, pattern in route.path_fields.items():
        match = re.search(pattern, file_path)
        if match:
            path_values[field] = match[1]
    for row in rows:
        for field, value in path_values.items():
            if not row.get(field):
                row[field] = value
        for field, template in route.normalize.items():
            digits = re.sub(r"\D", "", str(row.get(field) or ""))
            if digits and str(row[field]).strip().isdigit():
                row[field] = template.format(int(digits))
        for field, separator in route.split.items():
            value = row.get(field)
            if isinstance(value, str):
                row[field] = [p.strip() for p in value.split(separator) if p.strip()]
        for field, replacements in route.values.items():
            if row.get(field) in replacements:
                row[field] = replacements[row[field]]


def _parse_typed(rows: list[dict[str, Any]]) -> None:
    day_first = {}
    for field in DATE_FIELDS:
        values = [str(r[field]) for r in rows if isinstance(r.get(field), str)]
        day_first[field] = timeutil.is_day_first(values)
    for row in rows:
        for field in NUMBER_FIELDS & row.keys():
            row[field] = parse_number(row[field])
        for field in DATE_FIELDS & row.keys():
            row[field] = timeutil.normalize(row[field], day_first[field])


def load_table(route: pack_module.Route, file_path: str, data: bytes) -> list[dict[str, Any]]:
    """Reads a CSV file for `parser: table`."""
    return map_rows(read_csv(data), route, file_path=file_path)


def load_json(route: pack_module.Route, file_path: str, data: bytes) -> tuple[list[dict[str, Any]], str | None]:
    """Reads a JSON file for `parser: json`.

    Nested keys become paths with dots. `records` names the list of rows,
    without it the document is one row.

    Returns:
        The mapped rows and the as-of text, if the route names its key.
    """
    document = json.loads(decode(data))
    records = document
    if route.records:
        for key in route.records.split("."):
            records = records[key]
    if not isinstance(records, list):
        records = [records]
    as_of = None
    if route.as_of and isinstance(document, dict):
        as_of = timeutil.normalize(document.get(route.as_of))
    rows = map_rows([_flatten(r) for r in records], route, file_path=file_path)
    return rows, as_of


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(value, dict):
        return {prefix: value}
    flat: dict[str, Any] = {}
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(item, dict):
            flat.update(_flatten(item, path))
        else:
            flat[path] = item
    return flat


def load_report(
    route: pack_module.Route,
    pack: pack_module.PackConfig,
    file_path: str,
    data: bytes,
) -> list[tuple[pack_module.TableSpec, str | None, str, list[dict[str, Any]]]]:
    """Reads an Excel report with several tables for `parser: report`.

    Each table is found through its header row: the first row that holds
    all words of `header`. The as-of moment comes from the title cell of
    the sheet.

    Returns:
        One entry per found table: its spec, as-of text, sheet name, rows.
    """
    workbook = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    anchor = pack.deadline.astimezone(zoneinfo.ZoneInfo(pack.timezone))
    found = []
    for sheet in workbook.worksheets:
        grid = [list(row) for row in sheet.iter_rows(values_only=True)]
        as_of = None
        if route.as_of == "title" and grid:
            title = next((str(c) for c in grid[0] if c is not None), "")
            as_of = timeutil.from_title(title, anchor)
        for spec in route.tables:
            if spec.sheet and spec.sheet != sheet.title:
                continue
            raw_rows = _table_below_header(grid, spec.header)
            if raw_rows:
                rows = map_rows(raw_rows, route, spec.columns, file_path)
                found.append((spec, as_of, sheet.title, rows))
    workbook.close()
    return found


def _table_below_header(grid: list[list[Any]], header: list[str]) -> list[dict[str, Any]]:
    wanted = {normalize_name(word) for word in header}
    for index, row in enumerate(grid):
        cells = {normalize_name(c) for c in row if c is not None}
        if not wanted <= cells:
            continue
        names = [str(c) if c is not None else None for c in row]
        table = []
        for values in grid[index + 1:]:
            if all(v is None for v in values):
                break
            table.append({n: v for n, v in zip(names, values, strict=False) if n})
        return table
    return []
