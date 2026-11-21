import pytest

from lineguard.policy import engine
from tests import helpers


@pytest.fixture
def rt(tmp_path, monkeypatch):
    return helpers.demo_runtime(tmp_path, monkeypatch)


def test_value_tiers(rt):
    assert engine.route(rt, "purchase_order", 4500) == ["buyer"]
    assert engine.route(rt, "purchase_order", 10000) == ["category_lead"]


def test_flags_add_roles(rt):
    roles = engine.route(rt, "purchase_order", 4500, ["inbound_delivery"])
    assert roles == ["buyer", "site_lead"]


def test_erp_correction_goes_to_erp_owner_only(rt):
    assert engine.route(rt, "erp_correction") == ["erp_owner"]


def test_unknown_type_falls_back(rt):
    assert engine.route(rt, "something_new") == ["category_lead"]


def test_person_is_resolved_and_vacant_role_falls_back(rt):
    assert engine.resolve_person(rt, "buyer")["person_id"] == "P1"
    assert engine.resolve_person(rt, "cfo")["person_id"] == "P2"
    assert engine.next_role(rt, "buyer") == "category_lead"
    assert engine.next_role(rt, "category_lead") is None


def test_require_role(rt):
    assert engine.require_role(rt, "P3", ["erp_owner"])["person_id"] == "P3"
    with pytest.raises(engine.NotAllowedError, match="erp_owner"):
        engine.require_role(rt, "P1", ["erp_owner"])
    # Nobody holds 'cfo', so the fallback role may act for it.
    assert engine.require_role(rt, "P2", ["cfo"])["person_id"] == "P2"
