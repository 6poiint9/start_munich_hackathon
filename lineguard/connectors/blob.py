"""Port for file storage. Agents never touch the disk directly.

`LocalBlobStore` is the only implementation today. An object store can
replace it without a change in any agent (docs/skalierung.md N5).
"""

import pathlib
from typing import Protocol


class BlobStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...


class LocalBlobStore:
    """Stores blobs as files below one root folder."""

    def __init__(self, root: pathlib.Path):
        self._root = root

    def _path(self, key: str) -> pathlib.Path:
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root.resolve()):
            raise ValueError(f"Blob key '{key}' leaves the store")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def local_path(self, key: str) -> pathlib.Path:
        """The file on disk, for tools that need a path (pdftotext)."""
        return self._path(key)
