from lineguard import commands
from lineguard import db
from lineguard import pipeline
from lineguard.agents import stock_truth
from lineguard.coverage import core
from lineguard.coverage import watch
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
    assert "revision B, released is C" in revision["title"]
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


def test_watch_case_reopens_when_the_problem_returns(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)
    original = next(c for c in _watch_cases(rt) if c["rule"] == "revision_mismatch_open_po")
    rt.conn.execute(
        "UPDATE facts SET rev = 'C' WHERE workspace_id = ? AND fact_type = 'po_line' "
        "AND po_number = ?", (rt.ws, original["po_number"]))
    watch.run_watchers(rt)
    assert next(c for c in _watch_cases(rt) if c["id"] == original["id"])["state"] == "closed"

    rt.conn.execute(
        "UPDATE facts SET rev = 'B' WHERE workspace_id = ? AND fact_type = 'po_line' "
        "AND po_number = ?", (rt.ws, original["po_number"]))
    watch.run_watchers(rt)
    reopened = [c for c in _watch_cases(rt) if c["id"] == original["id"]]
    assert len(reopened) == 1
    assert reopened[0]["state"] == "open"


def test_stale_feed_is_one_case_and_closes_after_an_update(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)
    file_id = db.insert(rt.conn, "files", rt.ws, path="shipments.csv",
                        sha256="test", version=1, first_seen_at="2027-03-01T00:00:00Z")
    for ref, updated in (("one", "2027-02-27T00:00:00Z"),
                         ("two", "2027-02-28T00:00:00Z")):
        db.insert(rt.conn, "facts", rt.ws, fact_type="shipment", ref=ref,
                  source_file_id=file_id, created_at="2027-03-01T00:00:00Z",
                  data={"updated_at": updated})

    watch.run_watchers(rt)
    watch.run_watchers(rt)
    stale = [case for case in _watch_cases(rt) if case["rule"] == "feed_stale"]
    assert len(stale) == 1
    assert (stale[0]["owner_role"], stale[0]["impact"], stale[0]["state"]) == (
        "erp_owner", "deadline_blocker", "open")

    rt.conn.execute(
        "UPDATE facts SET data = json_set(data, '$.updated_at', '2027-03-01T07:00:00Z') "
        "WHERE workspace_id = ? AND source_file_id = ? AND ref = 'two'", (rt.ws, file_id))
    watch.run_watchers(rt)
    assert next(case for case in _watch_cases(rt) if case["id"] == stale[0]["id"])["state"] == "closed"


def test_feed_without_update_time_does_not_invent_a_stale_date(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)
    file_id = db.insert(rt.conn, "files", rt.ws, path="missing-time.csv",
                        sha256="test", version=1, first_seen_at="2027-03-01T00:00:00Z")
    db.insert(rt.conn, "facts", rt.ws, fact_type="shipment", ref="one",
              source_file_id=file_id, created_at="2027-03-01T00:00:00Z", data={})

    watch.run_watchers(rt)

    assert not [case for case in _watch_cases(rt) if case["rule"] == "feed_stale"]


def test_tick_recomputes_expired_demand_without_new_files(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)
    assert db.rows(rt.conn, rt.ws,
                   "SELECT * FROM gaps WHERE workspace_id = ? AND is_current = 1")
    assert not db.rows(rt.conn, rt.ws,
                       "SELECT * FROM events WHERE workspace_id = ? "
                       "AND status = 'pending' AND type = 'facts.updated'")
    monkeypatch.setenv("LINEGUARD_NOW", "2027-04-01T08:00:00+02:00")
    commands._tick(rt)
    commands._tick(rt)

    pipeline.drain(rt, ["stock_truth", "decision"])

    assert db.rows(rt.conn, rt.ws,
                   "SELECT * FROM gaps WHERE workspace_id = ? AND is_current = 1") == []
    assert any(c["rule"] == "validity_expiring" for c in _watch_cases(rt))
    ticks = db.rows(rt.conn, rt.ws,
                    "SELECT * FROM events WHERE workspace_id = ? AND type = 'tick.stock'")
    assert len(ticks) == 1
    assert ticks[0]["status"] == "done"


def test_tick_does_not_run_decisions_before_a_failed_refresh(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)

    def fail_refresh(_rt, _event):
        raise ValueError("Refresh failed")

    monkeypatch.setattr(stock_truth, "recompute", fail_refresh)
    commands._tick(rt)
    pipeline.drain(rt, ["stock_truth", "decision"])

    assert not db.rows(rt.conn, rt.ws,
                       "SELECT * FROM events WHERE workspace_id = ? AND type = 'tick'")
    refresh = db.one(rt.conn, rt.ws,
                     "SELECT * FROM events WHERE workspace_id = ? AND type = 'tick.stock'")
    assert refresh["status"] == "pending"
    assert "Refresh failed" in refresh["error"]


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
