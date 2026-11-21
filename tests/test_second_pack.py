"""The same core serves a second customer, and two customers stay apart."""

import pytest

from lineguard import db
from tests import helpers


def test_core_finds_error_gap_and_decision_for_the_invented_customer(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)

    def rows(table):
        return db.rows(rt.conn, rt.ws, f"SELECT * FROM {table} WHERE workspace_id = ?")
    assert [f["cause"] for f in rows("booking_findings")] == ["decimal_shift"]
    assert [g["gap_qty"] for g in rows("gaps") if g["is_current"]] == [-50]
    assert len(rows("decisions")) == 1
    assert len(rows("options")) >= 1


def test_changed_threshold_in_the_pack_changes_the_result(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)
    from lineguard.agents import stock_truth
    # With a tolerance of 1000 % the receipt of ten times the order passes
    # check 1. The delivery note still disagrees, so the finding stays.
    rt.pack.booking_check.over_tolerance = 10.0
    stock_truth.recompute(rt)
    import json
    finding = db.one(rt.conn, rt.ws,
                     "SELECT * FROM booking_findings WHERE workspace_id = ?")
    assert json.loads(finding["checks"])["gr_vs_po"]["status"] == "pass"


@pytest.mark.customer_data
def test_two_workspaces_in_one_database_do_not_touch(tmp_path, monkeypatch):
    shared = db.connect("shared", tmp_path / "shared.sqlite")
    soony = helpers.soony_runtime(tmp_path, monkeypatch, conn=shared)
    demo = helpers.demo_runtime(tmp_path, monkeypatch, conn=shared)

    def gaps(rt):
        return sorted((g["component_id"], g["gap_qty"]) for g in db.rows(
            rt.conn, rt.ws,
            "SELECT * FROM gaps WHERE workspace_id = ? AND is_current = 1"))
    assert gaps(demo) == [("RAHMEN-01", -50)]
    assert ("CMP-GAM-003", -32000) in gaps(soony)
    assert all(not part.startswith("RAHMEN") for part, _ in gaps(soony))
