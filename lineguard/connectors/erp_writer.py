"""Port for writing a correction to the ERP, with two implementations.

Every write carries the approval of a person with the role `erp_owner`.
`apply` checks that first (docs/buchungspruefung.md §7).
"""

import csv
import json
import pathlib
from typing import Any, Protocol

import httpx

from lineguard import clock
from lineguard import config

_CSV_COLUMNS = ("correction_id", "gr_number", "po_number", "po_line",
                "material_id", "site", "booked_qty", "proposed_qty",
                "delta_qty", "cause", "approved_by", "approved_at")


class ApprovalMissingError(Exception):
    """A correction reached the writer without an approval."""


class ErpWriter(Protocol):
    name: str

    def apply(self, correction: dict[str, Any]) -> dict[str, Any]: ...


def _require_approval(correction: dict[str, Any]) -> None:
    if not correction.get("approved_by") or not correction.get("approved_at"):
        raise ApprovalMissingError(
            f"Correction {correction.get('id')} has no approval by the erp_owner")


class ProposalFileWriter:
    """Writes the correction as JSON and CSV for the ERP owner.

    The default, because the ERP of the customer is protected. Idempotent:
    a second call for the same correction writes nothing new.
    """

    name = "proposal_file"

    def __init__(self, folder: pathlib.Path):
        self._folder = folder

    def apply(self, correction: dict[str, Any]) -> dict[str, Any]:
        """Writes the files once. Returns status and the file as reference."""
        _require_approval(correction)
        target = self._folder / "corrections" / f"{correction['id']}.json"
        if target.is_file():
            return {"status": "handed_over", "external_ref": str(target), "new": False}
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = correction["payload"]
        record = {**payload, "correction_id": correction["id"],
                  "approved_by": correction["approved_by"],
                  "approved_at": correction["approved_at"],
                  "written_at": clock.iso()}
        target.write_text(json.dumps(record, indent=1, ensure_ascii=False),
                          encoding="utf-8")
        table = self._folder / "corrections.csv"
        is_new = not table.is_file()
        with table.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, _CSV_COLUMNS, extrasaction="ignore")
            if is_new:
                writer.writeheader()
            writer.writerow(record)
        return {"status": "handed_over", "external_ref": str(target), "new": True}


class MiddlewareWriter:
    """Posts the correction to the middleware of the customer.

    Falls back to the file writer when the middleware does not accept it.
    """

    name = "middleware"

    def __init__(self, url: str, token: str, fallback: ProposalFileWriter):
        self._url = url.rstrip("/")
        self._token = token
        self._fallback = fallback

    def apply(self, correction: dict[str, Any]) -> dict[str, Any]:
        """Posts the correction with an idempotency key. Three attempts."""
        _require_approval(correction)
        for _ in range(3):
            try:
                response = httpx.post(
                    f"{self._url}/corrections", json=correction["payload"],
                    headers={"Authorization": f"Bearer {self._token}",
                             "Idempotency-Key": correction["idempotency_key"]},
                    timeout=30.0)
            except httpx.HTTPError:
                continue
            if response.status_code < 300:
                reference = response.json().get("id", correction["idempotency_key"])
                return {"status": "posted", "external_ref": str(reference), "new": True}
        result = self._fallback.apply(correction)
        return {**result, "fallback": True}


def from_pack(mode: str, workspace: str) -> ErpWriter:
    """Builds the writer that the pack names in `erp_writer.mode`."""
    files = ProposalFileWriter(config.data_dir(workspace) / "out")
    url, token = config.get("ERP_MW_URL"), config.get("ERP_MW_TOKEN")
    if mode == "middleware" and url and token:
        return MiddlewareWriter(url, token, files)
    return files
