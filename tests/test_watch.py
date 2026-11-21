from lineguard import db
from lineguard.agents import stock_truth
from lineguard.coverage import core
from tests import helpers


def _watch_cases(rt):
    return db.rows(rt.conn, rt.ws,
                   "SELECT * FROM cases WHERE workspace_id = ? AND kind = 'watch' "
                   "ORDER BY rule")


def test_open_order_with_old_revision_and_expiring_contract(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)

    cases = _watch_cases(rt)

    assert [c["rule"] for c in cases] == ["revision_mismatch_open_po", "validity_expiring"]
    revision, contract = cases
    assert revision["po_number"] == "BE-2004"
    assert "Revision B, freigegeben ist C" in revision["title"]
    assert revision["owner_role"] == "buyer"
    assert revision["act_by"] == "2027-03-06T22:59:00Z"
    assert contract["supplier_id"] == "LIEF-B"
    assert contract["act_by"] is not None
    # The order has time. The contract is past its notice date: act now.
    assert revision["impact"] == "after_deadline"
    assert contract["impact"] == "deadline_blocker"


def test_second_run_creates_no_second_case(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)
    stock_truth.recompute(rt)
    assert len(_watch_cases(rt)) == 2


def test_after_the_last_due_date_the_core_still_works(tmp_path, monkeypatch):
    from fastapi import testclient

    from lineguard import main
    monkeypatch.setenv("LINEGUARD_DATA", str(tmp_path / "data"))
    rt = helpers.demo_runtime(tmp_path, monkeypatch, conn=db.connect("demo_bikes"))
    monkeypatch.setenv("LINEGUARD_NOW", "2027-04-01T08:00:00+02:00")

    stock_truth.recompute(rt)
    body = testclient.TestClient(main.create_app(rt.pack)).get("/state").json()

    assert body["next_due"] is None
    assert core.compute(rt).lines == []
    assert db.rows(rt.conn, rt.ws,
                   "SELECT * FROM gaps WHERE workspace_id = ? AND is_current = 1") == []
    # The booking check and the watchers run without a demand date.
    assert body["booking_review"]["findings"] == 1
    assert len(body["cases_later"]) + len(body["cases_now"]) >= 2
