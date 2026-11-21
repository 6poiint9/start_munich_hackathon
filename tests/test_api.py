from fastapi import testclient

from lineguard import db
from lineguard import main
from lineguard.agents import stock_truth
from tests import helpers


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("LINEGUARD_DATA", str(tmp_path / "data"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    pack_conn = db.connect("demo_bikes")
    rt = helpers.demo_runtime(tmp_path, monkeypatch, conn=pack_conn)
    stock_truth.recompute(rt)
    return testclient.TestClient(main.create_app(rt.pack)), rt


def test_state_header_and_case_list(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)

    body = client.get("/state").json()

    product = body["products"][0]
    assert product["coverage_system"] == 1.0
    assert product["coverage_secured"] < 1.0
    assert sum(product["units"].values()) == product["still_to_pack"]
    kinds = [(c["kind"], c["component_id"]) for c in body["cases_now"]]
    assert kinds == [("gap", "RAHMEN-01"), ("booking_finding", "RAHMEN-01")]
    assert body["cases_now"][0]["gap_qty"] == -50
    assert body["counters"]["open_corrections"] == 1
    assert body["booking_review"] == {"receipts_checked": 4, "findings": 1}


def test_case_leads_to_fact_file_and_place(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    case_id = client.get("/state").json()["cases_now"][0]["id"]

    body = client.get(f"/cases/{case_id}").json()

    stock = [e for e in body["evidence"] if e["fact_type"] == "stock_qty"]
    assert stock[0]["file"]["path"] == "bestand.csv"
    assert stock[0]["locator"] == "row 3"
    content = client.get(f"/files/{stock[0]['file']['id']}/content")
    assert content.status_code == 200
    assert b"RAHMEN-01" in content.content
    assert client.get("/cases/99999").status_code == 404


def test_state_at_another_moment_stores_nothing(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    body = client.get("/state", params={"at": "2027-04-01T08:00:00+02:00"}).json()
    assert body["next_due"] is None
    assert client.get("/healthz").json()["status"] == "ok"
