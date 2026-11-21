from lineguard.coverage import core
from tests import helpers


def test_two_due_dates_earlier_one_is_served_first(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)

    state = core.compute(rt)

    first, second = state.lines
    assert (first.demand_class, first.open_units) == ("preordered", 300)
    assert (second.demand_class, second.open_units) == ("open_sale", 300)
    frame = state.components["RAHMEN-01"]
    assert frame.usable == 550
    assert frame.gap_qty == -50
    assert [s["class"] for s in frame.short_lines] == ["open_sale"]
    assert first.buildable["secured"] == 300
    assert second.buildable["secured"] == 250
    product = state.products["BIKE-CITY"]
    assert product.coverage["system"] == 1.0
    assert round(product.coverage["secured"], 4) == round(650 / 700, 4)


def test_no_open_demand_date_gives_no_gap(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)
    monkeypatch.setenv("LINEGUARD_NOW", "2027-04-01T08:00:00+02:00")
    state = core.compute(rt)
    assert state.lines == []
    assert state.next_due is None
    assert all(c.gap_qty == 0 for c in state.components.values())
