"""Loads and validates a customer pack.

A pack holds every value that belongs to one customer: deadline, sources,
routes, thresholds and approval rules (docs/kern-und-kundenpaket.md). The
core loads exactly one pack at start, named by LINEGUARD_PACK.
"""

import csv
import datetime
import pathlib
import re
from typing import Any

import pydantic
import yaml

from lineguard import config

PACK_ENV = "LINEGUARD_PACK"


class PackError(Exception):
    """The pack is missing, incomplete or invalid."""


class _Model(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", populate_by_name=True)


class Source(_Model):
    connector: str
    base_url_env: str | None = None
    token_env: str | None = None
    path: str | None = None
    poll_seconds: int = 60


class DemandLine(_Model):
    product: str
    demand_class: str = pydantic.Field(alias="class")
    units: float
    due_at: datetime.datetime | None = None


class BookingCheck(_Model):
    over_tolerance: float = 0.10
    weight_ratio_range: tuple[float, float] = (0.5, 2.0)
    min_agreeing_sources: int = 2


class Coverage(_Model):
    confirm_threshold: float = 0.8
    thin_margin: float = 0.05
    stale_count_days: int = 14
    default_handling_hours: float = 2.0
    horizon_days: int = 30


class Watch(_Model):
    default_notice_days: int = 14
    confirm_days: int = 5
    silent_after_hours: dict[str, float] = {}
    feed_stale_hours: float = 12.0


class Mail(_Model):
    subject_tag: str = ""
    sender_env: str = "GMAIL_ADDRESS"
    sender_name: str = "Procurement"
    follow_up_hours: float = 2.0


class ErpWriter(_Model):
    mode: str = "proposal_file"


class AutoApprove(_Model):
    action_kinds: list[str] = []
    max_cost_eur: float = 0.0


class TableSpec(_Model):
    kind: str
    header: list[str] = []
    sheet: str | None = None
    columns: dict[str, str] = {}


class Route(_Model):
    """Maps a path pattern to a parser (docs/import-und-routen.md §2)."""

    match: str
    parser: str = "document"
    kind: str | None = None
    doc_class: str | None = None
    columns: dict[str, str] = {}
    normalize: dict[str, str] = {}
    split: dict[str, str] = {}
    values: dict[str, dict[str, str]] = {}
    path_fields: dict[str, str] = {}
    records: str | None = None
    as_of: str | None = None
    tables: list[TableSpec] = []
    expect: list[str] = []
    priority: int | None = None


class PackConfig(_Model):
    """All values of one customer, from `pack.yaml` and its sibling files."""

    workspace: str
    customer: str
    labels: dict[str, str] = {}
    timezone: str = "UTC"
    deadline: datetime.datetime
    site: str
    sources: list[Source]
    demand: list[DemandLine] = []
    priority_order: list[str]
    booking_check: BookingCheck = BookingCheck()
    coverage: Coverage = Coverage()
    watch: Watch = Watch()
    mail: Mail = Mail()
    erp_writer: ErpWriter = ErpWriter()
    auto_approve: AutoApprove = AutoApprove()
    roles: dict[str, str] = {}
    # Filled from the other files of the pack.
    path: pathlib.Path | None = None
    routes: list[Route] = []
    default_route: Route = Route(match="**", parser="document", priority=3)
    source_rank: dict[str, int] = {}
    approval_policy: dict[str, Any] = {}
    aliases: list[dict[str, str]] = []

    def route_for(self, file_path: str) -> Route:
        """The first route whose pattern matches the path, else the default."""
        for route in self.routes:
            if _glob_regex(route.match).fullmatch(file_path):
                return route
        return self.default_route

    def rank_of(self, doc_class: str | None) -> int:
        """Source rank 1 (physical proof) to 5 (manual list)."""
        return self.source_rank.get(doc_class or "", 5)


def _glob_regex(pattern: str) -> re.Pattern[str]:
    """Translates a glob with `**`, `*`, `?` and `{a,b}` into a regex."""
    parts = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if pattern.startswith("**/", index):
            parts.append("(?:.*/)?")
            index += 3
            continue
        if pattern.startswith("**", index):
            parts.append(".*")
            index += 2
            continue
        if char == "*":
            parts.append("[^/]*")
        elif char == "?":
            parts.append("[^/]")
        elif char == "{":
            end = pattern.index("}", index)
            choices = pattern[index + 1:end].split(",")
            parts.append("(?:" + "|".join(re.escape(c) for c in choices) + ")")
            index = end
        else:
            parts.append(re.escape(char))
        index += 1
    return re.compile("".join(parts))


def _read_yaml(path: pathlib.Path, required: bool) -> Any:
    if not path.is_file():
        if required:
            raise PackError(f"Pack file '{path}' is missing.")
        return {}
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load(path: str | pathlib.Path | None = None) -> PackConfig:
    """Loads the pack from a folder.

    Args:
        path: The pack folder. Without it, LINEGUARD_PACK names the folder.

    Raises:
        PackError: The folder or a required field is missing or invalid.
    """
    raw_path = path or config.get(PACK_ENV)
    if not raw_path:
        raise PackError(f"Set {PACK_ENV} to the folder of a pack.")
    folder = pathlib.Path(raw_path)
    if not folder.is_absolute():
        folder = config.ROOT / folder
    if not folder.is_dir():
        raise PackError(f"Pack folder '{folder}' does not exist.")
    data = _read_yaml(folder / "pack.yaml", required=True)
    routes = _read_yaml(folder / "routes.yaml", required=False)
    try:
        pack = PackConfig(
            **data,
            routes=routes.get("routes", []),
            source_rank=_read_yaml(folder / "source_rank.yaml", False),
            approval_policy=_read_yaml(folder / "approval_policy.yaml", False),
        )
        if "default" in routes:
            pack.default_route = Route(match="**", **routes["default"])
    except pydantic.ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
            for e in error.errors()
        )
        raise PackError(f"Pack '{folder.name}' is invalid: {problems}") from error
    pack.path = folder
    aliases = folder / "aliases.csv"
    if aliases.is_file():
        with aliases.open(encoding="utf-8", newline="") as handle:
            pack.aliases = list(csv.DictReader(handle))
    return pack
