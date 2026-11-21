import datetime

from lineguard import clock
from lineguard import db

WS = "test_ws"


def test_partition_blocks_second_event(conn):
    for name, partition in [("a", "p1"), ("b", "p1"), ("c", "p2"), ("d", "p2")]:
        db.emit(conn, WS, "facts.updated", {"n": name}, partition_key=partition)

    first = db.claim_next(conn, WS, "w1", ["facts.updated"])
    second = db.claim_next(conn, WS, "w2", ["facts.updated"])
    third = db.claim_next(conn, WS, "w3", ["facts.updated"])

    assert first["payload"]["n"] == "a"
    assert second["payload"]["n"] == "c"
    assert third is None


def test_expired_lease_is_claimed_again(conn, monkeypatch):
    db.emit(conn, WS, "tick")
    monkeypatch.setenv(clock.NOW_ENV, "2027-01-01T10:00:00+00:00")
    first = db.claim_next(conn, WS, "w1", ["tick"], lease_seconds=60)
    assert db.claim_next(conn, WS, "w2", ["tick"]) is None

    later = clock.now() + datetime.timedelta(seconds=61)
    monkeypatch.setenv(clock.NOW_ENV, later.isoformat())
    again = db.claim_next(conn, WS, "w2", ["tick"])

    assert again["id"] == first["id"]
    assert again["locked_by"] == "w2"


def test_priority_order_and_type_filter(conn):
    db.emit(conn, WS, "file.added", {"n": "low"}, priority=3)
    db.emit(conn, WS, "file.changed", {"n": "high"}, priority=1)
    db.emit(conn, WS, "tick", {"n": "other"}, priority=1)

    event = db.claim_next(conn, WS, "w1", ["file.added", "file.changed"])

    assert event["payload"]["n"] == "high"


def test_coalesce_key_keeps_one_pending_event(conn):
    for _ in range(10):
        db.emit(conn, WS, "facts.updated", coalesce_key="facts.updated:part-1")
    pending = db.rows(
        conn, WS,
        "SELECT id FROM events WHERE workspace_id = ? AND status = 'pending'",
    )
    assert len(pending) == 1

    event = db.claim_next(conn, WS, "w1", ["facts.updated"])
    db.finish(conn, WS, event, "stock_truth")
    assert db.emit(conn, WS, "facts.updated",
                   coalesce_key="facts.updated:part-1") is not None


def test_dedupe_key_is_unique_forever(conn):
    assert db.emit(conn, WS, "file.added", dedupe_key="file:a:sha") is not None
    event = db.claim_next(conn, WS, "w1", ["file.added"])
    db.finish(conn, WS, event, "reader")
    assert db.emit(conn, WS, "file.added", dedupe_key="file:a:sha") is None


def test_failed_event_retries_then_fails(conn, monkeypatch):
    monkeypatch.setenv(clock.NOW_ENV, "2027-01-01T10:00:00+00:00")
    db.emit(conn, WS, "tick")
    for attempt in range(3):
        event = db.claim_next(conn, WS, "w1", ["tick"])
        assert event is not None, f"attempt {attempt}"
        db.finish(conn, WS, event, "worker", error="boom")
        later = clock.now() + datetime.timedelta(minutes=30)
        monkeypatch.setenv(clock.NOW_ENV, later.isoformat())
    row = db.one(conn, WS, "SELECT status FROM events WHERE workspace_id = ?")
    assert row["status"] == "failed"
