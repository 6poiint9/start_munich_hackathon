import datetime

import pytest

from lineguard import clock
from lineguard import db
from lineguard import pipeline
from lineguard import views
from lineguard.coverage import core
from tests import helpers


def _short(product, demand_class, units, parts):
    return {
        "product_id": product,
        "class": demand_class,
        "due_at": "2027-03-05T00:00:00+00:00",
        "gap_qty": -parts,
        "units_at_risk": units,
    }


def test_shared_part_residual_follows_priority_and_part_quantities():
    lines = [_short("first", "preordered", 10, 20),
             _short("second", "open_sale", 20, 20)]

    assert core.residual_by_line(lines, 25) == [3, 20]
    assert core.residual_by_line(lines, 0) == [0, 0]
    assert core.residual_by_line(lines, 100) == [10, 20]


def test_shared_shortage_counts_each_product_and_overlapping_parts_once():
    now = datetime.datetime(2027, 3, 1, tzinfo=datetime.UTC)
    first = core.ProductState("first", demand=100, still_to_pack=100,
                              buildable={"secured": 90})
    second = core.ProductState("second", demand=100, still_to_pack=100,
                               buildable={"secured": 80})
    shared = core.ComponentState(
        "shared", gap_qty=-40,
        short_lines=[_short("first", "preordered", 10, 20),
                     _short("second", "open_sale", 20, 20)])
    other = core.ComponentState(
        "other", gap_qty=-10, short_lines=[_short("second", "open_sale", 10, 10)])
    state = core.State(now, now, {"first": first, "second": second},
                       {"shared": shared, "other": other}, [], [])
    cases = [
        {"id": 1, "kind": "gap", "component_id": "shared", "state": "unclosable"},
        {"id": 2, "kind": "gap", "component_id": "other", "state": "unclosable"},
    ]
    gaps = {1: {"detail": '{"residual_parts": 25}'},
            2: {"detail": '{"residual_parts": 10}'}}

    first_units = views._units_by_state(first, state, cases, gaps)
    second_units = views._units_by_state(second, state, cases, gaps)

    assert first_units == {"secured": 90, "planned": 0, "open": 7, "unclosable": 3}
    assert second_units == {"secured": 80, "planned": 0, "open": 0, "unclosable": 20}
    assert sum(first_units.values()) == pytest.approx(first.still_to_pack)
    assert sum(second_units.values()) == pytest.approx(second.still_to_pack)


def test_capacity_shortfall_is_not_treated_as_an_approved_plan():
    now = datetime.datetime(2027, 3, 1, tzinfo=datetime.UTC)
    product = core.ProductState("first", demand=100, still_to_pack=100,
                                buildable={"secured": 80})
    component = core.ComponentState(
        "part", gap_qty=-10, short_lines=[_short("first", "preordered", 10, 10)])
    state = core.State(now, now, {"first": product}, {"part": component}, [], [])
    cases = [{"id": 1, "kind": "gap", "component_id": "part", "state": "approved"}]

    assert views._units_by_state(product, state, cases, {1: {"detail": "{}"}}) == {
        "secured": 80, "planned": 10, "open": 10, "unclosable": 0,
    }


def test_same_class_and_date_keep_distinct_demand_lines():
    now = datetime.datetime(2027, 3, 1, tzinfo=datetime.UTC)
    product = core.ProductState("first", demand=20, still_to_pack=20,
                                buildable={"secured": 10})
    first = {**_short("first", "preordered", 5, 5), "line_index": 0}
    second = {**_short("first", "preordered", 5, 5), "line_index": 1}
    component = core.ComponentState("part", gap_qty=-10, short_lines=[first, second])
    state = core.State(now, now, {"first": product}, {"part": component}, [], [])
    cases = [{"id": 1, "kind": "gap", "component_id": "part", "state": "unclosable"}]

    assert views._units_by_state(product, state, cases, {1: {"detail": "{}"}}) == {
        "secured": 10, "planned": 0, "open": 0, "unclosable": 10,
    }


def test_partial_component_shortage_counts_a_whole_product():
    lines = [_short("first", "preordered", 1, 1)]
    assert core.residual_by_line(lines, 0.5) == [1]


def test_partial_coverage_uses_bom_ratio_before_rounding():
    lines = [{**_short("first", "preordered", 2, 3), "qty_per": 2}]
    assert core.residual_by_line(lines, 2) == [1]


def test_pipeline_allocates_shared_parts_across_products(tmp_path, monkeypatch):
    monkeypatch.setenv("LINEGUARD_NOW", helpers.DEMO_NOW)
    monkeypatch.setenv("MAIL_MODE", "DRY_RUN")
    rt = helpers.make_runtime(tmp_path, helpers.DEMO_PACK)
    db.insert(rt.conn, "components", rt.ws, component_id="PART", description="Part")
    for product, ratio, demand_class, units in (
            ("FIRST", 2, "preordered", 5),
            ("SECOND", 1, "open_sale", 10)):
        db.insert(rt.conn, "products", rt.ws, product_id=product, description=product)
        db.insert(rt.conn, "bom_lines", rt.ws, product_id=product,
                  component_id="PART", qty_per=ratio)
        db.insert(rt.conn, "facts", rt.ws, fact_type="demand", product_id=product,
                  value_text=demand_class, qty=units, eta="2027-03-05T16:00:00+01:00",
                  created_at=clock.iso())
    db.insert(rt.conn, "facts", rt.ws, fact_type="stock_qty", component_id="PART",
              qty=9, as_of="2027-03-01T08:00:00+01:00", created_at=clock.iso())
    db.emit(rt.conn, rt.ws, "facts.updated")

    pipeline.drain(rt)

    snapshot = views.state(rt)
    products = {item["product_id"]: item for item in snapshot["products"]}
    assert products["FIRST"]["units"] == {
        "secured": 4, "planned": 0, "open": 0, "unclosable": 1,
    }
    assert products["SECOND"]["units"] == {
        "secured": 0, "planned": 0, "open": 0, "unclosable": 10,
    }
    gap = db.one(rt.conn, rt.ws, "SELECT * FROM gaps WHERE workspace_id = ? AND is_current = 1")
    assert gap["gap_qty"] == -11
    assert gap["residual_qty"] == 11
    assert not db.rows(rt.conn, rt.ws,
                       "SELECT * FROM events WHERE workspace_id = ? AND status = 'failed'")
