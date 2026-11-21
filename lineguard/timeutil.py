"""Parses the date and time texts that customer files contain."""

import datetime
import re
import zoneinfo

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SLASH = re.compile(r"^(\d{1,2})([/.])(\d{1,2})[/.](\d{2,4})(?:[ T](\d{1,2}):(\d{2}))?$")
_TITLE_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})(?:[ T](\d{1,2}):(\d{2}))?")
_TITLE_TIME = re.compile(r"(\d{1,2}):(\d{2})")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday",
            "saturday", "sunday", "montag", "dienstag", "mittwoch",
            "donnerstag", "freitag", "samstag", "sonntag")


def is_day_first(values: list[str]) -> bool:
    """Decides the order of day and month for one column of dates.

    A first number above 12 means day first. If the column stays ambiguous,
    a dot means day first and a slash means month first.
    """
    dotted = False
    for value in values:
        match = _SLASH.match(value.strip())
        if not match:
            continue
        if int(match[1]) > 12:
            return True
        if int(match[3]) > 12:
            return False
        dotted = dotted or match[2] == "."
    return dotted


def normalize(value: object, day_first: bool = False) -> str | None:
    """Turns a date cell into ISO text: a date, or a datetime with offset."""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return None
    match = _SLASH.match(text)
    if match:
        first, second, year = int(match[1]), int(match[3]), int(match[4])
        day, month = (first, second) if day_first else (second, first)
        year += 2000 if year < 100 else 0
        try:
            date = datetime.date(year, month, day)
        except ValueError:
            return None
        if match[5]:
            return f"{date.isoformat()}T{int(match[5]):02d}:{match[6]}:00"
        return date.isoformat()
    try:
        datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return text


def to_datetime(text: str | None, timezone: str, end_of_day: bool = True) -> datetime.datetime | None:
    """Parses ISO text into an aware datetime.

    A date without time counts as the end of that day in the given time
    zone. That is the careful reading for an arrival date.
    """
    if not text:
        return None
    zone = zoneinfo.ZoneInfo(timezone)
    if _ISO_DATE.match(text):
        day = datetime.date.fromisoformat(text)
        time = datetime.time(23, 59) if end_of_day else datetime.time(0, 0)
        return datetime.datetime.combine(day, time, zone)
    try:
        moment = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=zone)


def weekday_before(name: str, anchor: datetime.datetime) -> datetime.date | None:
    """The last day with this weekday name on or before the anchor."""
    lowered = name.lower()
    for index, weekday in enumerate(WEEKDAYS):
        if weekday in lowered:
            offset = (anchor.weekday() - index % 7) % 7
            return anchor.date() - datetime.timedelta(days=offset)
    return None


def from_title(title: str, anchor: datetime.datetime) -> str | None:
    """Reads the as-of moment from a report title.

    Supports a date with or without time, and a weekday with time relative
    to the anchor (the next demand date).
    """
    match = _TITLE_DATE.search(title)
    if match:
        if match[2]:
            return _local_iso(datetime.date.fromisoformat(match[1]),
                              int(match[2]), int(match[3]), anchor)
        return match[1]
    day = weekday_before(title, anchor)
    time = _TITLE_TIME.search(title)
    if day and time:
        return _local_iso(day, int(time[1]), int(time[2]), anchor)
    return None


def _local_iso(day: datetime.date, hour: int, minute: int, anchor: datetime.datetime) -> str:
    moment = datetime.datetime.combine(day, datetime.time(hour, minute), anchor.tzinfo)
    return moment.isoformat()
