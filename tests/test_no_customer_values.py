"""The core holds no customer value (docs/kern-und-kundenpaket.md §6)."""

import csv
import pathlib
import re

import pytest

from tests import helpers

CORE = helpers.ROOT / "lineguard"
FORBIDDEN_WORDS = ("per_std", "per_ce", "edition", "launch")
_ID_COLUMNS = ("component_id", "material_id", "product_id", "supplier_id",
               "po_number", "teil", "modell", "lieferant", "bestellung",
               "artikel", "kuerzel", "name", "contact_name", "buyer")


def _core_text() -> str:
    parts = []
    for path in sorted(CORE.rglob("*")):
        if path.suffix in (".py", ".md"):
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts).lower()


def _identifiers(folder: pathlib.Path) -> set[str]:
    """Ids and names from the tables of a customer folder."""
    found = set()
    for path in folder.rglob("*.csv"):
        text = path.read_text(encoding="utf-8", errors="replace")
        delimiter = ";" if text.splitlines()[0].count(";") > text.splitlines()[0].count(",") else ","
        for row in csv.DictReader(text.splitlines(), delimiter=delimiter):
            for column in _ID_COLUMNS:
                value = (row.get(column) or "").strip()
                # Short codes and plain numbers are too generic to search for.
                if len(value) >= 6 and not value.isdigit() and not re.fullmatch(r"[\d.,-]+", value):
                    found.add(value.lower())
    return found


def test_no_forbidden_word_in_the_core():
    text = _core_text()
    for word in FORBIDDEN_WORDS:
        assert word not in text, f"'{word}' belongs to a pack, not to the core"


def test_no_identifier_of_the_invented_customer_in_the_core():
    text = _core_text()
    identifiers = _identifiers(helpers.DEMO_PACK)
    assert len(identifiers) > 10
    assert [i for i in identifiers if i in text] == []


@pytest.mark.customer_data
def test_no_identifier_of_the_customer_snapshot_in_the_core():
    text = _core_text()
    identifiers = _identifiers(helpers.SOONY_SNAPSHOT) | _identifiers(helpers.SOONY_PACK)
    assert len(identifiers) > 40
    assert [i for i in identifiers if i in text] == []
