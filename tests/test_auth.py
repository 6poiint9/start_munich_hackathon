import json

from fastapi import testclient
import httpx

from lineguard import db
from lineguard import main
from tests import helpers


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("LINEGUARD_DATA", str(tmp_path / "data"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    rt = helpers.demo_runtime(tmp_path, monkeypatch, conn=db.connect("demo_bikes"))
    correction = db.one(rt.conn, rt.ws, "SELECT * FROM corrections WHERE workspace_id = ?")
    return testclient.TestClient(main.create_app(rt.pack)), rt, correction["id"]


def test_approval_without_header_is_401(tmp_path, monkeypatch):
    client, _, correction_id = _client(tmp_path, monkeypatch)
    assert client.post(f"/corrections/{correction_id}/approve").status_code == 401


def test_known_person_without_role_can_approve_but_unknown_person_cannot(tmp_path, monkeypatch):
    client, _, correction_id = _client(tmp_path, monkeypatch)
    unknown = client.post(f"/corrections/{correction_id}/approve",
                          headers={"X-Lineguard-User": "nobody"})
    assert unknown.status_code == 403
    rejected = client.post(f"/corrections/{correction_id}/reject",
                           headers={"X-Lineguard-User": "P1"}, json={"reason": "test"})
    assert rejected.status_code == 403
    response = client.post(f"/corrections/{correction_id}/approve",
                           headers={"X-Lineguard-User": "P1"})
    assert response.status_code == 200
    assert response.json()["approved_by"] == "P1"


def test_erp_owner_approves_once_and_files_are_written(tmp_path, monkeypatch):
    client, rt, correction_id = _client(tmp_path, monkeypatch)
    headers = {"X-Lineguard-User": "P3"}

    first = client.post(f"/corrections/{correction_id}/approve", headers=headers)
    second = client.post(f"/corrections/{correction_id}/approve", headers=headers)

    assert first.status_code == 200
    assert first.json()["status"] == "handed_over"
    assert first.json()["approved_by"] == "P3"
    assert second.json()["status"] == "handed_over"
    out = tmp_path / "data" / "demo_bikes" / "out"
    assert (out / "corrections" / f"{correction_id}.json").is_file()
    assert len((out / "corrections.csv").read_text().splitlines()) == 2
    mails = db.rows(rt.conn, rt.ws,
                    "SELECT * FROM emails WHERE workspace_id = ? AND routine = 1")
    assert len(mails) == 1


def test_erp_preview_matches_local_proposal_without_updating_erp(tmp_path, monkeypatch):
    client, rt, correction_id = _client(tmp_path, monkeypatch)
    correction = db.one(rt.conn, rt.ws,
                        "SELECT * FROM corrections WHERE workspace_id = ? AND id = ?",
                        (correction_id,))
    finding = db.one(rt.conn, rt.ws,
                     "SELECT * FROM booking_findings WHERE workspace_id = ? AND id = ?",
                     (correction["finding_id"],))
    preview = next(a for a in client.get("/state").json()["approvals"]
                   if a["id"] == f"correction:{correction_id}")
    detail = client.get(f"/cases/{finding['case_id']}").json()
    assert preview["erp_writer"] == "proposal_file"
    assert preview["correction_payload"] == detail["corrections"][0]["payload"]
    before = db.rows(rt.conn, rt.ws,
                     "SELECT id, qty FROM facts WHERE workspace_id = ? AND fact_type = 'gr_qty'")
    response = client.post(f"/corrections/{correction_id}/approve",
                           headers={"X-Lineguard-User": "P3"})
    assert response.status_code == 200
    assert response.json()["status"] == "handed_over"
    assert response.json()["writer"] == "proposal_file"
    path = tmp_path / "data" / "demo_bikes" / "out" / "corrections" / f"{correction_id}.json"
    saved = json.loads(path.read_text())
    assert all(saved[key] == value for key, value in preview["correction_payload"].items())
    assert saved["approved_by"] == "P3"
    assert before == db.rows(rt.conn, rt.ws,
                             "SELECT id, qty FROM facts WHERE workspace_id = ? AND fact_type = 'gr_qty'")
    assert client.get(f"/cases/{finding['case_id']}").json()["corrections"][0]["status"] == "handed_over"


def test_failed_middleware_shows_local_fallback(tmp_path, monkeypatch):
    client, rt, correction_id = _client(tmp_path, monkeypatch)
    rt.pack.erp_writer.mode = "middleware"
    monkeypatch.setenv("ERP_MW_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("ERP_MW_TOKEN", "test-token")

    def unavailable(*_args, **_kwargs):
        raise httpx.ConnectError("unavailable")

    monkeypatch.setattr(httpx, "post", unavailable)
    assert next(a for a in client.get("/state").json()["approvals"]
                if a["id"] == f"correction:{correction_id}")["erp_writer"] == "middleware"
    response = client.post(f"/corrections/{correction_id}/approve",
                           headers={"X-Lineguard-User": "P3"})
    assert response.status_code == 200
    assert response.json()["status"] == "handed_over"
    assert response.json()["writer"] == "proposal_file"
    assert (tmp_path / "data" / "demo_bikes" / "out" / "corrections"
            / f"{correction_id}.json").is_file()


def test_reject_needs_reason_and_restores_erp_quantity(tmp_path, monkeypatch):
    from lineguard import pipeline
    from lineguard.coverage import core
    client, rt, correction_id = _client(tmp_path, monkeypatch)
    headers = {"X-Lineguard-User": "P3"}

    assert client.post(f"/corrections/{correction_id}/reject",
                       headers=headers, json={}).status_code == 422
    response = client.post(f"/corrections/{correction_id}/reject",
                           headers=headers, json={"reason": "Lager hat gezählt: 1000"})
    pipeline.drain(rt, ["stock_truth"])

    assert response.json()["status"] == "rejected"
    assert core.compute(rt).components["RAHMEN-01"].usable == 1450
    people = client.get("/state").json()["people"]
    assert {"P1", "P2", "P3", "P4"} == {p["person_id"] for p in people}
