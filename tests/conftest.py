"""Shared fixtures. Tests with customer data skip when the snapshot is absent."""

import pathlib

import pytest

from lineguard import db

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOONY_SNAPSHOT = ROOT / "tests" / "fixtures" / "soony"
SOONY_PACK = ROOT / "packs" / "soony_gh6"
DEMO_PACK = ROOT / "tests" / "fixtures" / "packs" / "demo_bikes"
DEMO_NOW = "2027-03-01T08:00:00+01:00"


def pytest_collection_modifyitems(items):
    if SOONY_SNAPSHOT.is_dir() and SOONY_PACK.is_dir():
        return
    skip = pytest.mark.skip(reason="customer snapshot is not in the repository")
    for item in items:
        if "customer_data" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def conn(tmp_path, monkeypatch):
    """An empty migrated database in a temporary folder."""
    monkeypatch.setenv("LINEGUARD_DATA", str(tmp_path / "data"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    connection = db.connect("test_ws", tmp_path / "test.sqlite")
    yield connection
    connection.close()
