import json

import pytest

from lineguard import db
from lineguard.agents import stock_truth
from lineguard.connectors import erp_writer
from lineguard.coverage import booking_check
from tests import helpers


def _findings(rt):
    return db.rows(rt.conn, rt.ws,
                   "SELECT * FROM booking_findings WHERE workspace_id = ? ORDER BY id")


def test_factor_ten_error_is_found_with_two_sources(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)

    findings = _findings(rt)

    assert len(findings) == 1
    finding = findings[0]
    assert finding["gr_number"] == "WE-1001"
    assert finding["cause"] == "decimal_shift"
    assert (finding["booked_qty"], finding["proposed_qty"]) == (1000, 100)
    assert finding["agreeing_sources"] >= 2
    assert finding["status"] == "proposed"
    checks = json.loads(finding["checks"])
    assert checks["gr_vs_po"]["status"] == "fail"
    assert checks["gr_vs_delivery_note"]["status"] == "fail"
    case = db.one(rt.conn, rt.ws,
                  "SELECT * FROM cases WHERE workspace_id = ? AND id = ?",
                  (finding["case_id"],))
    assert (case["kind"], case["owner_role"]) == ("booking_finding", "erp_owner")


def test_partial_deliveries_cause_no_finding(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)
    assert all(f["gr_number"] not in ("WE-1002", "WE-1003") for f in _findings(rt))


def test_second_run_adds_nothing(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)
    booking_check.check_all(rt)
    stock_truth.recompute(rt)
    assert len(_findings(rt)) == 1
    corrections = db.rows(rt.conn, rt.ws,
                          "SELECT * FROM corrections WHERE workspace_id = ?")
    assert len(corrections) == 1
    assert corrections[0]["approver_role"] == "erp_owner"


def test_writer_needs_approval_and_writes_once(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)
    correction = db.one(rt.conn, rt.ws,
                        "SELECT * FROM corrections WHERE workspace_id = ?")
    correction["payload"] = json.loads(correction["payload"])
    writer = erp_writer.ProposalFileWriter(tmp_path / "out")

    with pytest.raises(erp_writer.ApprovalMissingError):
        writer.apply(correction)

    correction.update(approved_by="P3", approved_at="2027-03-01T07:00:00Z")
    first = writer.apply(correction)
    second = writer.apply(correction)

    assert (first["new"], second["new"]) == (True, False)
    written = json.loads((tmp_path / "out" / "corrections" / f"{correction['id']}.json").read_text())
    assert (written["booked_qty"], written["proposed_qty"]) == (1000, 100)
    assert len((tmp_path / "out" / "corrections.csv").read_text().splitlines()) == 2


def test_new_export_with_corrected_qty_verifies_the_correction(tmp_path, monkeypatch):
    rt = helpers.demo_runtime(tmp_path, monkeypatch)
    correction = db.one(rt.conn, rt.ws,
                        "SELECT * FROM corrections WHERE workspace_id = ?")
    db.update(rt.conn, "corrections", rt.ws, correction["id"], status="handed_over")
    rt.conn.execute(
        "UPDATE facts SET qty = 100 WHERE workspace_id = ? AND fact_type = 'gr_qty' "
        "AND ref = 'WE-1001'", (rt.ws,))

    stock_truth.recompute(rt)

    after = db.one(rt.conn, rt.ws, "SELECT * FROM corrections WHERE workspace_id = ?")
    assert after["status"] == "verified"
    assert _findings(rt)[0]["status"] == "corrected"


@pytest.mark.customer_data
def test_look_back_over_customer_snapshot(tmp_path, monkeypatch):
    rt = helpers.soony_runtime(tmp_path, monkeypatch)
    findings = [f for f in _findings(rt) if f["status"] in ("proposed", "needs_count")]
    causes = sorted(f["cause"] for f in findings)
    # Without documents, only the order quantity backs the decimal shift.
    shift = [f for f in findings if f["gr_number"] == "5000413065"]
    assert len(shift) == 1
    assert shift[0]["proposed_qty"] == 8000
    assert causes.count("unreferenced_receipt") == 3
    assert len(findings) == 4, causes
