"""Runs the agent handlers with a fixed number of workers per group.

Each worker is a thread with its own database connection. It takes events
with `claim_next`, so more workers or more processes can join without a
change (docs/skalierung.md N2). Blocking work (LLM, OCR tools, mail) runs
in the worker thread and never holds a database transaction.
"""

from collections.abc import Callable
import logging
import threading
import time

from lineguard import config
from lineguard import db
from lineguard import pipeline
from lineguard import runtime

logger = logging.getLogger(__name__)
_IDLE_SECONDS = 0.3

RuntimeFactory = Callable[[], runtime.Runtime]


def worker_counts() -> dict[str, int]:
    """Workers per handler group. These values describe the operation."""
    return {
        "reader": config.get_int("READER_CONCURRENCY", 8),
        "stock_truth": 1,
        "decision": config.get_int("DECISION_CONCURRENCY", 1),
        "action": 1,
    }


def _work(make_runtime: RuntimeFactory, group: str, name: str, stop: threading.Event, until_empty: bool, max_priority: int | None, handled: list[int]) -> None:
    rt = make_runtime()
    try:
        while not stop.is_set():
            types = list(pipeline.HANDLERS.get(group, {}))
            event = db.claim_next(rt.conn, rt.ws, name, types,
                                  max_priority=max_priority)
            if event is None:
                if until_empty and not _has_open(rt, types, max_priority):
                    return
                time.sleep(_IDLE_SECONDS)
                continue
            pipeline.handle_one(rt, group, event)
            handled.append(event["id"])
    finally:
        rt.conn.close()


def _has_open(rt: runtime.Runtime, types: list[str], max_priority: int | None) -> bool:
    """True while an event of these types waits or runs."""
    if not types:
        return False
    marks = ", ".join("?" for _ in types)
    row = db.one(
        rt.conn, rt.ws,
        "SELECT COUNT(*) AS n FROM events WHERE workspace_id = ? "
        f"AND status IN ('pending', 'processing') AND type IN ({marks}) "
        "AND priority <= ? AND available_at <= ?",
        (*types, max_priority or 9, db.clock.iso()))
    return bool(row and row["n"])


def run_until_empty(make_runtime: RuntimeFactory, groups: list[str] | None = None, max_priority: int | None = None) -> int:
    """Handles all open events of the groups with parallel workers.

    Used for the first import and in tests. Returns the number of handled
    events.
    """
    groups = groups or list(pipeline.HANDLERS)
    counts = worker_counts()
    handled: list[int] = []
    previous = -1
    # A handler can emit events for a group that is already done. Repeat
    # until a full round handles nothing.
    while len(handled) != previous:
        previous = len(handled)
        stop = threading.Event()
        threads = []
        for group in groups:
            for index in range(counts.get(group, 1)):
                thread = threading.Thread(
                    target=_work, daemon=True,
                    args=(make_runtime, group, f"{group}-{index}", stop, True,
                          max_priority, handled))
                thread.start()
                threads.append(thread)
        for thread in threads:
            thread.join()
    return len(handled)


class Orchestrator:
    """Long-running workers plus timers for polling and ticks."""

    def __init__(self, make_runtime: RuntimeFactory):
        self._make_runtime = make_runtime
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._timers: list[tuple[float, Callable[[runtime.Runtime], None]]] = []

    def every(self, seconds: float, job: Callable[[runtime.Runtime], None]) -> None:
        """Registers a job that runs again and again with this pause."""
        self._timers.append((seconds, job))

    def start(self) -> None:
        """Starts the workers of every group and the timers."""
        handled: list[int] = []
        for group, count in worker_counts().items():
            if group not in pipeline.HANDLERS:
                continue
            for index in range(count):
                self._spawn(_work, (self._make_runtime, group, f"{group}-{index}",
                                    self._stop, False, None, handled))
        for seconds, job in self._timers:
            self._spawn(self._timer, (seconds, job))

    def _spawn(self, target: Callable[..., None], args: tuple) -> None:
        thread = threading.Thread(target=target, args=args, daemon=True)
        thread.start()
        self._threads.append(thread)

    def _timer(self, seconds: float, job: Callable[[runtime.Runtime], None]) -> None:
        while not self._stop.is_set():
            rt = self._make_runtime()
            try:
                job(rt)
            except Exception:  # pylint: disable=broad-exception-caught
                # Isolation boundary: one failed poll must not stop the timer.
                logger.exception("Timer job %s failed", getattr(job, "__name__", job))
            finally:
                rt.conn.close()
            self._stop.wait(seconds)

    def stop(self) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=5)
