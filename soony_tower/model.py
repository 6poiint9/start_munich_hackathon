"""Builds one consistent picture of the launch from all portal files.

No value from the data is written into this code. File names are found with
glob patterns, columns with the alias list in tables.py, and the layout of
the Excel reports with a header search. If Soony drops a new version of a
file, the next build picks it up.
"""

import dataclasses
import pathlib
import re

import pandas as pd

from soony_tower import portal
from soony_tower import settings
from soony_tower import tables

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday",
            "saturday", "sunday")


@dataclasses.dataclass
class PackedCount:
    """Copies already packed for one product, as stated by one source."""

    product_id: str
    packed: float
    as_of: pd.Timestamp
    source: str


@dataclasses.dataclass
class Shift:
    start: pd.Timestamp
    end: pd.Timestamp


@dataclasses.dataclass
class LaunchData:
    """All parsed inputs. Every frame keeps a _source column."""

    products: pd.DataFrame
    components: pd.DataFrame
    bom: pd.DataFrame
    bom_changes: pd.DataFrame
    stock: pd.DataFrame
    purchase_orders: pd.DataFrame
    shipments: pd.DataFrame
    planned_inbound: pd.DataFrame
    routes: pd.DataFrame
    suppliers: pd.DataFrame
    supplier_parts: pd.DataFrame
    packout_log: pd.DataFrame
    packed_counts: list[PackedCount]
    rates_per_hour: dict[str, tuple[float, str, pd.Timestamp]]
    shifts: list[Shift]
    documents: list[str]
    notes: list[tuple[str, str]]
    problems: list[str]


def _files(pattern: str) -> list[pathlib.Path]:
    return sorted(portal.CURRENT_DIR.glob(pattern))


def _concat(frames: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [f for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _load_all(pattern: str, problems: list[str], **kwargs) -> pd.DataFrame:
    frames = []
    for path in _files(pattern):
        try:
            frames.append(tables.load(path, **kwargs))
        except tables.SchemaError as error:
            problems.append(str(error))
    return _concat(frames)


def _supplier_id(value: object) -> str | None:
    """Turns '19', 'SUP-19' or 'SUP-0019' into 'SUP-0019'."""
    if value is None or pd.isna(value):
        return None
    digits = re.sub(r"\D", "", str(value))
    return f"SUP-{int(digits):04d}" if digits else str(value)


def _find_header(raw: pd.DataFrame, required: list[str]) -> pd.DataFrame:
    """Finds the header row of a report-style sheet and returns the table."""
    wanted = {tables.normalize(name) for name in required}
    for index, row in raw.iterrows():
        cells = {tables.normalize(v) for v in row.tolist() if pd.notna(v)}
        if wanted <= cells:
            table = raw.iloc[index + 1:].copy()
            table.columns = [str(v) if pd.notna(v) else f"col{i}"
                             for i, v in enumerate(row.tolist())]
            return table.dropna(how="all")
    return pd.DataFrame()


def _launch_date(products: pd.DataFrame) -> pd.Timestamp:
    launch = products[products["product_id"].isin(settings.LAUNCH_PRODUCTS)]
    return pd.Timestamp(launch["launch_date"].dropna().max())


def _as_of_from_title(title: str, launch_date: pd.Timestamp) -> pd.Timestamp | None:
    """Reads 'status 2026-11-20 18:00' or 'Saturday 13:00' from a title."""
    tz = settings.TIMEZONE
    time_match = re.search(r"(\d{1,2}):(\d{2})", title)
    hour, minute = (int(time_match[1]), int(time_match[2])) if time_match else (0, 0)
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", title)
    if date_match:
        day = pd.Timestamp(date_match[1])
    else:
        names = [d for d in WEEKDAYS if d in title.lower()]
        if not names:
            return None
        offset = (launch_date.weekday() - WEEKDAYS.index(names[0])) % 7
        day = launch_date.normalize() - pd.Timedelta(days=offset)
    return day.replace(hour=hour, minute=minute).tz_localize(tz)


def _read_context_reports(launch_date, packed, rates, shifts, notes,
                          inbound_frames):
    """Reads the Excel launch plan and launch status reports."""
    for path in _files("soony/context/*.xlsx"):
        sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object)
        title = ""
        for sheet_name, raw in sheets.items():
            if raw.empty:
                continue
            first = raw.iloc[0, 0]
            if not title and isinstance(first, str):
                title = first
            as_of = _as_of_from_title(title, launch_date)

            editions = _find_header(raw, ["Product", "Packed"])
            if not editions.empty and as_of is not None:
                editions = tables.map_columns(editions)
                for _, row in editions.iterrows():
                    count = tables.parse_number(row.get("Packed"))
                    if count is not None and pd.notna(row.get("product_id")):
                        packed.append(PackedCount(row["product_id"], count, as_of,
                                                  f"{path.name} / {sheet_name}"))
                    rate = tables.parse_number(row.get("Rate per hour"))
                    previous = rates.get(row["product_id"])
                    if rate and (previous is None or previous[2] <= as_of):
                        rates[row["product_id"]] = (rate, path.name, as_of)

            inbound = _find_header(raw, ["Part", "Quantity", "ETA"])
            if not inbound.empty:
                inbound = tables.map_columns(inbound)
                inbound["_source"] = f"{path.name} / {sheet_name}"
                inbound_frames.append(inbound)

            shift_table = _find_header(raw, ["Day", "Shift"])
            if not shift_table.empty:
                for _, row in shift_table.iterrows():
                    day, window = str(row.get("Day", "")), str(row.get("Shift", ""))
                    times = re.findall(r"(\d{1,2}):(\d{2})", window)
                    names = [d for d in WEEKDAYS if d in day.lower()]
                    if len(times) == 2 and names:
                        offset = (launch_date.weekday() - WEEKDAYS.index(names[0])) % 7
                        date = launch_date.normalize() - pd.Timedelta(days=offset)
                        start = date.replace(hour=int(times[0][0]), minute=int(times[0][1]))
                        end = date.replace(hour=int(times[1][0]), minute=int(times[1][1]))
                        shifts.append(Shift(start.tz_localize(settings.TIMEZONE),
                                            end.tz_localize(settings.TIMEZONE)))

            note_table = _find_header(raw, ["Note"])
            if not note_table.empty:
                for value in note_table.iloc[:, 0].dropna():
                    notes.append((str(value), f"{path.name} / {sheet_name}"))


def build() -> LaunchData:
    """Reads every known file from data/current and returns LaunchData."""
    problems: list[str] = []
    products = _load_all("soony/master/products*.csv", problems,
                         required=["product_id"], numbers=("day_one_qty",))
    products["launch_date"] = pd.to_datetime(products["launch_date"], errors="coerce")
    launch_date = _launch_date(products)

    components = _load_all("soony/master/components.csv", problems,
                           required=["material_id"])
    for update in _files("soony/master/components_update_*.csv"):
        changes = tables.load(update, required=["material_id"])
        for _, change in changes.iterrows():
            mask = components["material_id"] == change["material_id"]
            components.loc[mask, change["field"]] = change["new"]

    bom = _load_all("soony/master/bom.csv", problems,
                    required=["product_id", "child_id", "qty_per"],
                    numbers=("qty_per",))
    bom_changes = _load_all("soony/master/bom_delta_*.csv", problems,
                            required=["product_id", "child_id"],
                            dates=("effective_from",))

    stock = _load_all("soony/erp/stock_snapshot*.csv", problems,
                      required=["material_id", "quantity"],
                      numbers=("quantity", "safety_stock"),
                      dates=("snapshot_date", "last_count"))

    purchase_orders = _load_all("soony/erp/purchase_orders*.csv", problems,
                                required=["po_number", "material_id", "quantity"],
                                numbers=("quantity", "unit_price"),
                                dates=("order_date", "requested_date",
                                       "promised_date", "actual_delivery_date"))
    purchase_orders["supplier_id"] = purchase_orders["supplier_id"].map(_supplier_id)
    purchase_orders["po_number"] = purchase_orders["po_number"].astype(str).str.strip()

    shipments = _load_all("soony/erp/open_shipments*.csv", problems,
                          required=["shipment_id", "eta"],
                          dates=("etd", "eta", "updated_at"))
    routes = _load_all("soony/master/routes*.csv", problems,
                       required=["route_id"], numbers=("transit_days",))
    suppliers = _load_all("suppliers/*/profile.csv", problems,
                          required=["supplier_id"])
    supplier_parts = []
    for path in _files("suppliers/*/components.csv"):
        frame = tables.load(path, required=["material_id"])
        frame["supplier_id"] = _supplier_id(path.parent.name.split("_")[0])
        supplier_parts.append(frame)
    packout_log = _load_all("soony/erp/packout_log*.csv", problems,
                            required=["product_id", "units_packed"],
                            numbers=("units_packed",), dates=("date",))

    packed: list[PackedCount] = []
    fg_stock = stock[stock["material_id"].isin(settings.LAUNCH_PRODUCTS)]
    for _, row in fg_stock.iterrows():
        as_of = row["snapshot_date"].tz_convert(settings.TIMEZONE)
        packed.append(PackedCount(row["material_id"], row["quantity"], as_of,
                                  pathlib.Path(row["_source"]).name))
    rates: dict[str, tuple[float, str, pd.Timestamp]] = {}
    shifts: list[Shift] = []
    notes: list[tuple[str, str]] = []
    inbound_frames: list[pd.DataFrame] = []
    _read_context_reports(launch_date, packed, rates, shifts, notes, inbound_frames)
    planned_inbound = _concat(inbound_frames)
    if not planned_inbound.empty:
        planned_inbound["quantity"] = planned_inbound["quantity"].map(tables.parse_number)
        planned_inbound["eta"] = tables.parse_dates(planned_inbound["eta"])

    documents = [str(p.relative_to(portal.CURRENT_DIR)).replace("\\", "/")
                 for p in portal.CURRENT_DIR.rglob("*")
                 if p.suffix.lower() in (".pdf", ".docx", ".png", ".jpg")]

    return LaunchData(products, components, bom, bom_changes, stock,
                      purchase_orders, shipments, planned_inbound, routes,
                      suppliers, _concat(supplier_parts), packout_log, packed,
                      rates, sorted(shifts, key=lambda s: s.start), documents,
                      notes, problems)


def now() -> pd.Timestamp:
    # Server clocks often run in UTC, so ask for Berlin time directly.
    return pd.Timestamp.now(tz=settings.TIMEZONE)
