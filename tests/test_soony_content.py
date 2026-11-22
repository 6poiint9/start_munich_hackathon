"""Local extraction smoke test for the frozen customer snapshot."""

import pytest

from lineguard.tools import content
from tests import helpers

pytestmark = pytest.mark.customer_data


def test_all_snapshot_files_can_be_opened_without_a_network():
    files = [path for path in helpers.SOONY_SNAPSHOT.rglob("*")
             if path.is_file() and path.name != "AS_OF"]
    assert files
    for path in files:
        text, images = content.extract(str(path.relative_to(helpers.SOONY_SNAPSHOT)),
                                       path.read_bytes())
        assert text.strip() or images, f"No text or image extracted from {path.name}"
