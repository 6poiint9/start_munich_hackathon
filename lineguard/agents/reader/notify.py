"""Tells Stock Truth that facts changed."""

from lineguard import db
from lineguard import runtime

_MANY_COMPONENTS = 20


def facts_updated(rt: runtime.Runtime, touched: set[str]) -> None:
    """One recalculation event per touched part, merged while pending.

    The calculation covers the whole workspace today, so all these events
    share one partition and never run at the same time.
    """
    if not touched:
        return
    if "*" in touched or len(touched) > _MANY_COMPONENTS:
        touched = {"*"}
    for component in sorted(touched):
        db.emit(rt.conn, rt.ws, "facts.updated", {"component_id": component},
                priority=1, coalesce_key=f"facts.updated:{component}",
                partition_key="coverage")
