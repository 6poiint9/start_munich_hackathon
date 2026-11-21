from fastapi import testclient

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


def test_person_without_role_is_403(tmp_path, monkeypatch):
    client, _, correction_id = _client(tmp_path, monkeypatch)
    response = client.post(f"/corrections/{correction_id}/approve",
                           headers={"X-Lineguard-User": "P1"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Diese Freigabe braucht die Rolle erp_owner"
    unknown = client.post(f"/corrections/{correction_id}/approve",
                          headers={"X-Lineguard-User": "nobody"})
    assert unknown.status_code == 403


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
