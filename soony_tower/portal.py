"""Sync with the Soony portal: detect new, replaced and removed files.

Every file version is kept under data/versions so that a replaced file can be
compared with its previous version. Each detected change is appended to
data/changes.jsonl. The agents read this log to know what is new.
"""

import dataclasses
import datetime
import hashlib
import json
import os
import pathlib

import dotenv
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CURRENT_DIR = DATA_DIR / "current" / "soony-data"
VERSIONS_DIR = DATA_DIR / "versions"
MANIFEST_PATH = DATA_DIR / "manifest.json"
CHANGES_PATH = DATA_DIR / "changes.jsonl"
_TIMEOUT_SECONDS = 60


class PortalError(Exception):
    """The portal did not answer as expected."""


@dataclasses.dataclass(frozen=True)
class FileChange:
    """One change in the portal file list."""

    path: str
    kind: str  # "added", "replaced" or "removed"
    sha256: str | None
    previous_sha256: str | None
    detected_at: str


def _session() -> tuple[requests.Session, str]:
    dotenv.load_dotenv(ROOT / ".env")
    base_url = os.environ.get("LIO_BASE_URL")
    token = os.environ.get("LIO_TOKEN")
    if not base_url or not token:
        raise PortalError("LIO_BASE_URL and LIO_TOKEN must be set in .env")
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {token}"
    return session, base_url.rstrip("/")


def _load_manifest() -> dict[str, str]:
    if not MANIFEST_PATH.exists():
        return {}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _seed_manifest_from_disk(remote: dict[str, str]) -> dict[str, str]:
    """Treats files already on disk with the same content as known.

    This prevents a full re-download after the first manual archive import.
    """
    known = {}
    for path, sha in remote.items():
        local = CURRENT_DIR / path
        if local.exists():
            if hashlib.sha256(local.read_bytes()).hexdigest() == sha:
                known[path] = sha
    return known


def _version_path(path: str, sha: str) -> pathlib.Path:
    local = pathlib.PurePosixPath(path)
    return VERSIONS_DIR / local.parent / f"{local.stem}@{sha[:10]}{local.suffix}"


def sync() -> list[FileChange]:
    """Downloads changed files and returns the list of changes."""
    session, base_url = _session()
    response = session.get(f"{base_url}/api/v1/files", timeout=_TIMEOUT_SECONDS)
    if response.status_code != 200:
        raise PortalError(f"File list failed with HTTP {response.status_code}")
    remote = {f["path"]: f["sha256"] for f in response.json()["files"]}
    urls = {f["path"]: f["url"] for f in response.json()["files"]}

    known = _load_manifest() if MANIFEST_PATH.exists() else (
            _seed_manifest_from_disk(remote))
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    changes: list[FileChange] = []

    for path, sha in remote.items():
        old_sha = known.get(path)
        if old_sha == sha:
            continue
        file_response = session.get(urls[path], timeout=_TIMEOUT_SECONDS)
        if file_response.status_code != 200:
            raise PortalError(
                    f"Download of {path} failed with HTTP {file_response.status_code}")
        target = CURRENT_DIR / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file_response.content)
        version = _version_path(path, sha)
        version.parent.mkdir(parents=True, exist_ok=True)
        version.write_bytes(file_response.content)
        kind = "added" if old_sha is None else "replaced"
        changes.append(FileChange(path, kind, sha, old_sha, now))

    for path in set(known) - set(remote):
        changes.append(FileChange(path, "removed", None, known[path], now))

    MANIFEST_PATH.write_text(json.dumps(remote, indent=1), encoding="utf-8")
    if changes:
        with CHANGES_PATH.open("a", encoding="utf-8") as log:
            for change in changes:
                log.write(json.dumps(dataclasses.asdict(change)) + "\n")
    return changes


def read_changes() -> list[FileChange]:
    """Returns every change detected so far, oldest first."""
    if not CHANGES_PATH.exists():
        return []
    with CHANGES_PATH.open(encoding="utf-8") as log:
        return [FileChange(**json.loads(line)) for line in log if line.strip()]
