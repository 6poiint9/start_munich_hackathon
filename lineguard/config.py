"""Reads operating settings from the environment and from `.env`.

These values describe how the process runs. Values that describe a customer
come from the pack, never from here.
"""

import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_dotenv(path: pathlib.Path | None = None) -> None:
    """Copies KEY=VALUE lines from `.env` into the environment once.

    A variable that is already set keeps its value.
    """
    path = path or ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"'))


def get(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def get_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


def data_dir(workspace: str) -> pathlib.Path:
    """The folder for one workspace: database, files, corrections, demo."""
    return pathlib.Path(get("LINEGUARD_DATA", str(ROOT / "data"))) / workspace
