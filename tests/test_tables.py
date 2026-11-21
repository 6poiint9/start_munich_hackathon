import pytest

from lineguard import pack as pack_module
from lineguard import timeutil
from lineguard.agents.reader import tables


@pytest.mark.parametrize(("text", "expected"), [
    ("554.000", 554000.0), ("1.234,5", 1234.5), ("1,234.5", 1234.5),
    ("640,000", 640000.0), ("1,5200", 1.52), ("-9500", -9500.0),
    ("42,00", 42.0), (" 7 ", 7.0), ("", None), ("n/a", None), (12, 12.0),
])
def test_parse_number(text, expected):
    assert tables.parse_number(text) == expected


def test_date_order_is_decided_per_column():
    assert timeutil.is_day_first(["11/06/2024", "10/29/2024"]) is False
    assert timeutil.is_day_first(["20.02.2027", "01.03.2027"]) is True
    assert timeutil.is_day_first(["01.02.2027"]) is True
    assert timeutil.is_day_first(["01/02/2027"]) is False
    assert timeutil.normalize("10/29/2024", day_first=False) == "2024-10-29"
    assert timeutil.normalize("20.02.2027", day_first=True) == "2027-02-20"


def test_csv_with_semicolon_vendor_names_and_route_rules():
    route = pack_module.Route(
        match="x", parser="table", kind="purchase_orders",
        columns={"ZZCONF": "eta"}, normalize={"supplier_id": "SUP-{:04d}"})
    data = ("EBELN;EBELP;LIFNR;MATNR;MENGE;ZZCONF\n"
            "4500000001;10;10;PART-1;1.500;10/29/2024\n").encode("cp1252")

    rows = tables.load_table(route, "erp/legacy.csv", data)

    assert rows == [{
        "po_number": "4500000001", "po_line": "10", "supplier_id": "SUP-0010",
        "component_id": "PART-1", "qty": 1500.0, "eta": "2024-10-29"}]


def test_split_and_path_fields():
    route = pack_module.Route(
        match="x", parser="table", kind="shipments",
        split={"po_numbers": "|"}, path_fields={"supplier_id": r"sup/(S\d+)_"})
    rows = tables.load_table(route, "sup/S7_x/a.csv",
                             b"ref,po_numbers\nSH1,P1|P2\n")
    assert rows[0]["po_numbers"] == ["P1", "P2"]
    assert rows[0]["supplier_id"] == "S7"


def test_json_paths():
    route = pack_module.Route(
        match="x", parser="json", kind="suppliers", as_of="exportedAt",
        columns={"supplier.id": "supplier_id", "supplier.contact.email": "email"})
    data = (b'{"exportedAt": "2027-01-02T10:00:00+01:00", "supplier": '
            b'{"id": "S1", "contact": {"email": "a@b.example"}}}')
    rows, as_of = tables.load_json(route, "s.json", data)
    assert rows[0]["supplier_id"] == "S1"
    assert rows[0]["email"] == "a@b.example"
    assert as_of == "2027-01-02T10:00:00+01:00"


def test_report_title_gives_as_of():
    import datetime
    import zoneinfo
    anchor = datetime.datetime(2026, 11, 22, 20, 0,
                               tzinfo=zoneinfo.ZoneInfo("Europe/Berlin"))
    assert timeutil.from_title("Status · Saturday 13:00 · X", anchor) == (
        "2026-11-21T13:00:00+01:00")
    assert timeutil.from_title("plan · status 2026-11-20 18:00", anchor) == (
        "2026-11-20T18:00:00+01:00")
    assert timeutil.from_title("after receipts 2026-11-21, late shift", anchor) == (
        "2026-11-21")
    assert timeutil.from_title("no time here", anchor) is None


def test_glob_patterns():
    pack = pack_module.load("tests/fixtures/packs/demo_bikes")
    assert pack.route_for("bestand.csv").kind == "stock"
    assert pack.route_for("x/unknown.pdf").parser == "document"
    regex = pack_module._glob_regex("a/**/*.{jpg,png}")
    assert regex.fullmatch("a/b/c/x.png")
    assert regex.fullmatch("a/x.jpg")
    assert not regex.fullmatch("a/x.pdf")


def test_missing_required_field_stops_with_clear_message(tmp_path):
    (tmp_path / "pack.yaml").write_text("workspace: x\ncustomer: y\n")
    with pytest.raises(pack_module.PackError, match="deadline"):
        pack_module.load(tmp_path)
