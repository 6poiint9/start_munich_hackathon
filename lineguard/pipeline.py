"""Event handlers and the synchronous way to run them.

Every agent is a set of plain functions that take the runtime and one
event. The orchestrator runs them with several workers. `drain` runs them
one after the other, for the first import, the command line and tests.
"""

from collections.abc import Callable, Iterable
import logging
from typing import Any

from lineguard import approvals
from lineguard import db
from lineguard import runtime
from lineguard.agents import action
from lineguard.agents import stock_truth
from lineguard.agents import watcher
from lineguard.agents.reader import documents
from lineguard.agents.reader import router
from lineguard.connectors import source as source_module
from lineguard.coverage import closing

logger = logging.getLogger(__name__)

Handler = Callable[[runtime.Runtime, dict[str, Any]], Any]

# group -> event type -> handler. The orchestrator starts a fixed number
# of workers for each group.
HANDLERS: dict[str, dict[str, Handler]] = {
    "reader": {
        "file.added": router.handle_file,
        "file.changed": router.handle_file,
        "notes.read": documents.read_notes,
    },
    "stock_truth": {
        "facts.updated": stock_truth.recompute,
        "file.removed": stock_truth.recompute,
        "correction.approved": stock_truth.recompute,
        "correction.rejected": stock_truth.recompute,
        "fact.corrected": stock_truth.recompute,
    },
}


HANDLERS["decision"] = {
    "gap.changed": closing.close_gaps,
    "gap.closed": approvals.on_gap_closed,
    "decision.rejected": closing.close_gaps,
    "tick": closing.close_gaps,
}
HANDLERS["action"] = {
    "action.requested": action.handle_requested,
    "tick.action": action.poll_and_follow_up,
}


def register(group: str, event_type: str, handler: Handler) -> None:
    """Adds a handler. Later modules extend the table at import time."""
    HANDLERS.setdefault(group, {})[event_type] = handler


def handle_one(rt: runtime.Runtime, group: str, event: dict[str, Any]) -> None:
    """Runs one handler. An error fails this event only (isolation boundary)."""
    handler = HANDLERS[group][event["type"]]
    try:
        handler(rt, event)
    except Exception as error:  # pylint: disable=broad-exception-caught
        logger.exception("Handler %s failed for event %s", group, event["id"])
        db.finish(rt.conn, rt.ws, event, group, error=f"{type(error).__name__}: {error}")
        return
    db.finish(rt.conn, rt.ws, event, group)


def drain(rt: runtime.Runtime, groups: Iterable[str] | None = None, max_priority: int | None = None, limit: int = 100000) -> int:
    """Handles pending events until none is left.

    Args:
        groups: Handler groups to run. Default: all.
        max_priority: Handle only events up to this priority. Wave 1 of the
            first import passes 1.
        limit: Safety stop.

    Returns:
        The number of handled events.
    """
    groups = list(groups or HANDLERS)
    handled = 0
    progress = True
    while progress and handled < limit:
        progress = False
        for group in groups:
            event = db.claim_next(rt.conn, rt.ws, f"drain-{group}",
                                  list(HANDLERS[group]), max_priority=max_priority)
            if event is None:
                continue
            handle_one(rt, group, event)
            handled += 1
            progress = True
    return handled


def import_wave_one(rt: runtime.Runtime, source: source_module.SourceConnector) -> list[dict[str, Any]]:
    """Syncs the source and reads all tables. No LLM call happens here."""
    changes = watcher.sync(rt, source)
    # All tables first, then one calculation on the complete master data.
    drain(rt, ["reader"], max_priority=1)
    drain(rt, ["stock_truth"], max_priority=1)
    drain(rt, ["decision", "action", "stock_truth"])
    return changes
