"""Reads messy tabular files into tables with known column names.

The portal warns that column names, delimiters, encodings and date formats
differ between files and can change over time. This module does not trust any
of them. It detects the encoding and the delimiter, maps column names through
an alias list, and parses dates and numbers in several formats.

If a required column cannot be mapped, the reader raises SchemaError. The
caller can then ask a language model to propose a mapping (see agents.py).
"""

import csv
import io
import pathlib
import re

import pandas as pd

ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")

# Canonical field name -> known spellings. Spellings are compared after
# normalization (lowercase, only letters and digits).
ALIASES: dict[str, tuple[str, ...]] = {
        "po_number": ("po_number", "ebeln", "po", "bestellnummer", "po_no"),
        "po_line": ("po_line", "ebelp", "item", "line"),
        "supplier_id": ("supplier_id", "lifnr", "supplier", "vendor"),
        "material_id": ("material_id", "matnr", "material", "component_id",
                                        "part"),
        "plant": ("plant", "werks", "site"),
        "quantity": ("quantity", "menge", "qty", "quantity_pc"),
        "unit_price": ("unit_price", "netpr", "price"),
        "order_date": ("order_date", "bedat"),
        "requested_date": ("requested_date", "eindt"),
        "promised_date": ("promised_date", "zzconf", "confirmed_date"),
        "actual_delivery_date": ("actual_delivery_date", "wedat"),
        "status": ("status", "zzstat"),
        "buyer": ("buyer", "ernam"),
        "snapshot_date": ("snapshot_date", "date"),
        "batch": ("batch", "charg"),
        "safety_stock": ("safety_stock",),
        "last_count": ("last_count",),
        "shipment_id": ("shipment_id", "shipment"),
        "carrier_id": ("carrier_id", "carrier"),
        "mode": ("mode",),
        "reference": ("reference", "container_awb", "containerawb"),
        "po_numbers": ("po_numbers", "pos"),
        "material_ids": ("material_ids", "materials"),
        "route_id": ("route_id",),
        "origin": ("origin", "from"),
        "destination": ("destination", "to"),
        "etd": ("etd",),
        "eta": ("eta",),
        "updated_at": ("updated_at", "last_update"),
        "note": ("note", "comment", "remark"),
        "product_id": ("product_id", "product", "parent_id"),
        "child_id": ("child_id",),
        "qty_per": ("qty_per",),
        "units_packed": ("units_packed", "packed_units"),
        "line": ("line",),
        "gr_date": ("gr_date",),
        "qty_received": ("qty_received",),
        "qty_ordered": ("qty_ordered",),
        "delivery_note": ("delivery_note",),
}


class SchemaError(Exception):
    """A required column could not be found in a file."""

    def __init__(self, path: pathlib.Path, missing: list[str],
                              columns: list[str]):
        super().__init__(f"{path.name}: cannot map {missing} from {columns}")
        self.path = path
        self.missing = missing
        self.columns = columns


def normalize(name: str) -> str:
    """Lowercases a column name and removes everything but letters/digits."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _read_text(path: pathlib.Path) -> str:
    raw = path.read_bytes()
    for encoding in ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"{path}: unknown text encoding")


def _sniff_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:20])
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def read_raw(path: pathlib.Path) -> pd.DataFrame:
    """Reads a CSV or the first sheet of an Excel file as strings."""
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path, dtype=str)
    text = _read_text(path)
    return pd.read_csv(io.StringIO(text), sep=_sniff_delimiter(text), dtype=str,
                                          keep_default_na=False, na_values=[""])


def map_columns(
        frame: pd.DataFrame,
        extra_aliases: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Renames known columns to canonical names. Keeps unknown columns."""
    lookup = {}
    for canonical, spellings in ALIASES.items():
        for spelling in spellings:
            lookup.setdefault(normalize(spelling), canonical)
    for source, canonical in (extra_aliases or {}).items():
        lookup[normalize(source)] = canonical
    renamed = {}
    for column in frame.columns:
        canonical = lookup.get(normalize(column))
        if canonical and canonical not in renamed.values():
            renamed[column] = canonical
    return frame.rename(columns=renamed)


def parse_number(value: object) -> float | None:
    """Parses '1.234,5', '1,234.5', '1234' and '-9500' into a float."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().replace(" ", "").replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", text):
        # "554.000" is a German thousands separator, not 554.0.
        text = text.replace(".", "")
    elif "," in text:
        head, _, tail = text.rpartition(",")
        # "1,5200" is a decimal comma. "640,000" is a thousands separator.
        text = (head.replace(",", "") + "." + tail if len(tail) != 3 else
                        text.replace(",", ""))
    try:
        return float(text)
    except ValueError:
        return None


def parse_dates(series: pd.Series) -> pd.Series:
    """Parses a column of dates. Detects day-first vs month-first per column."""
    values = series.dropna().astype(str).str.strip()
    slash = values[values.str.match(r"^\d{1,2}[/.]\d{1,2}[/.]\d{2,4}")]
    dayfirst = False
    if not slash.empty:
        firsts = slash.str.extract(r"^(\d{1,2})[/.](\d{1,2})").astype(int)
        if (firsts[0] > 12).any():
            dayfirst = True
        elif not (firsts[1] > 12).any():
            # Ambiguous. A dot is German (day first), a slash is US (month first).
            dayfirst = slash.str.contains(r"\.").any()
    return pd.to_datetime(series, errors="coerce", dayfirst=dayfirst,
                                                utc=True, format="mixed")


def load(
        path: pathlib.Path,
        required: list[str],
        dates: tuple[str, ...] = (),
        numbers: tuple[str, ...] = (),
        extra_aliases: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Loads a file, maps columns and parses typed columns."""
    frame = map_columns(read_raw(path), extra_aliases)
    missing = [name for name in required if name not in frame.columns]
    if missing:
        raise SchemaError(path, missing, [str(c) for c in frame.columns])
    for name in dates:
        if name in frame.columns:
            frame[name] = parse_dates(frame[name])
    for name in numbers:
        if name in frame.columns:
            frame[name] = frame[name].map(parse_number)
    frame["_source"] = str(path)
    return frame
