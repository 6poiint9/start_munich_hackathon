"""Port for a customer file source, with two implementations.

A source lists files with checksum and returns the content of one file.
The watcher needs nothing else, so a push source can replace polling later
(docs/skalierung.md, stage 3).
"""

import dataclasses
import hashlib
import pathlib
from typing import Protocol

import httpx

from lineguard import config
from lineguard import pack as pack_module

_TIMEOUT_SECONDS = 60.0


class SourceError(Exception):
    """The source did not answer as expected."""


@dataclasses.dataclass(frozen=True)
class SourceFile:
    path: str
    sha256: str
    size: int
    url: str | None = None


class SourceConnector(Protocol):
    def list(self) -> list[SourceFile]: ...
    def download(self, file: SourceFile) -> bytes: ...


class LocalFolderSource:
    """Reads files from a folder. Used for tests, replay and local mirrors."""

    def __init__(self, root: pathlib.Path):
        self._root = root

    def list(self) -> list[SourceFile]:
        """All files below the root with checksum. Hidden files are skipped."""
        found = []
        for path in sorted(self._root.rglob("*")):
            if not path.is_file() or path.name.startswith("."):
                continue
            if path.name == "AS_OF":
                continue
            data = path.read_bytes()
            found.append(SourceFile(
                path.relative_to(self._root).as_posix(),
                hashlib.sha256(data).hexdigest(), len(data),
            ))
        return found

    def download(self, file: SourceFile) -> bytes:
        return (self._root / file.path).read_bytes()


class PortalApiSource:
    """Reads files from a portal with `GET /api/v1/files`."""

    def __init__(self, base_url: str, token: str):
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}

    def list(self) -> list[SourceFile]:
        response = self._get(f"{self._base_url}/api/v1/files")
        return [
            SourceFile(f["path"], f["sha256"], f.get("bytes", 0), f.get("url"))
            for f in response.json()["files"]
        ]

    def download(self, file: SourceFile) -> bytes:
        url = file.url or f"{self._base_url}/api/v1/files/{file.path}"
        if url.startswith("/"):
            url = f"{self._base_url}{url}"
        data = self._get(url).content
        if hashlib.sha256(data).hexdigest() != file.sha256:
            raise SourceError(f"Checksum of '{file.path}' does not match")
        return data

    def _get(self, url: str) -> httpx.Response:
        try:
            response = httpx.get(url, headers=self._headers,
                                 timeout=_TIMEOUT_SECONDS, follow_redirects=True)
        except httpx.HTTPError as error:
            raise SourceError(f"Request to '{url}' failed: {error}") from error
        if response.status_code != 200:
            raise SourceError(f"'{url}' answered HTTP {response.status_code}")
        return response


def from_pack(pack: pack_module.PackConfig) -> SourceConnector:
    """Builds the first source of the pack.

    LINEGUARD_SOURCE_PATH overrides it with a local folder, for a replay
    without network.
    """
    override = config.get("LINEGUARD_SOURCE_PATH")
    if override:
        return LocalFolderSource(pathlib.Path(override))
    source = pack.sources[0]
    if source.connector == "local_folder":
        root = pathlib.Path(source.path or ".")
        if not root.is_absolute() and pack.path:
            root = pack.path / root
        return LocalFolderSource(root)
    if source.connector == "portal_api":
        base_url = config.get(source.base_url_env or "")
        token = config.get(source.token_env or "")
        if not base_url or not token:
            raise SourceError(
                f"Set {source.base_url_env} and {source.token_env} in .env"
            )
        return PortalApiSource(base_url, token)
    raise SourceError(f"Unknown connector '{source.connector}'")
