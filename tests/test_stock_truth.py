"""Expected numbers for the frozen customer snapshot (Sat 21 Nov, 22:45).

These numbers live only here, never in the core.
"""

import pytest

from lineguard.coverage import core
from tests import helpers

pytestmark = pytest.mark.customer_data


@pytest.fixture
def state(tmp_path, monkeypatch):
    rt = helpers.soony_runtime(tmp_path, monkeypatch)
    return core.compute(rt)


def test_still_to_pack_comes_from_newest_status(state):
    assert state.products["FG-GH6-STD"].still_to_pack == 38000
    assert state.products["FG-GH6-CE"].still_to_pack == 11700
    assert state.products["FG-GH6-STD"].demand == 640000


def test_need_and_stock_of_all_parts(state):
    need = {c.component_id: c.need for c in state.components.values()}
    assert need["CMP-GAM-001"] == 49700
    assert need["CMP-GAM-003"] == 38000
    assert need["CMP-GAM-008"] == 11700
    assert state.components["CMP-GAM-008"].erp_stock == 77800
    assert state.components["CMP-GAM-004"].erp_stock == 116000


def test_gaps_that_need_only_tables(state):
    assert state.components["CMP-GAM-003"].gap_qty == -32000
    assert state.components["CMP-GAM-001"].gap_qty == -6800
    cards = state.components["CMP-GAM-001"]
    assert [s["class"] for s in cards.short_lines] == ["open_sale"]


def test_received_goods_do_not_count_twice(state):
    sleeves = state.components["CMP-GAM-004"]
    assert all(i.po_number != "4500318775" for i in sleeves.inbound)
    cards = [i for i in state.components["CMP-GAM-001"].inbound
             if i.po_number == "4500318735"]
    assert [i.qty for i in cards] == [20000]


def test_system_says_fine(state):
    assert state.products["FG-GH6-STD"].coverage["system"] == 1.0
    assert state.products["FG-GH6-STD"].coverage["secured"] < 1.0
