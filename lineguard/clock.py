"""The one place that reads the clock.

Set LINEGUARD_NOW to an ISO timestamp to fix the clock for a demo replay or
a test. No other module reads the system time.
"""

import datetime
import os

NOW_ENV = "LINEGUARD_NOW"
UTC = datetime.UTC


def now() -> datetime.datetime:
    """Returns the current time as an aware UTC datetime."""
    fixed = os.environ.get(NOW_ENV)
    if fixed:
        return parse(fixed)
    return datetime.datetime.now(UTC)


def parse(value: str) -> datetime.datetime:
    """Parses an ISO timestamp. A value without offset counts as UTC."""
    moment = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def iso(moment: datetime.datetime | None = None) -> str:
    """Formats a moment as UTC text that sorts in time order."""
    moment = moment or now()
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
