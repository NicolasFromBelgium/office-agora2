"""Europe/Brussels helpers for due dates and calendar events."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

BRUSSELS = ZoneInfo("Europe/Brussels")
MONTHS_LONG = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)
WEEKDAYS_SHORT = ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")


def as_brussels(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=BRUSSELS)
    return value.astimezone(BRUSSELS)


def local_now() -> datetime:
    return datetime.now(BRUSSELS)


def parse_date(raw: str) -> date | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def parse_clock(raw: str) -> tuple[int, int] | None:
    text = (raw or "").strip()
    if not text:
        return None
    parts = text.split(":")
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour, minute


def at_local(day: date, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=BRUSSELS)


def parse_due(due_date: str, due_time: str = "") -> datetime | None:
    day = parse_date(due_date)
    if day is None:
        return None
    clock = parse_clock(due_time)
    if clock is None:
        return at_local(day, 0, 0)
    return at_local(day, clock[0], clock[1])


def parse_event_span(
    *,
    start_date: str,
    start_time: str,
    end_date: str,
    end_time: str,
    all_day: bool,
) -> tuple[datetime, datetime] | None:
    start_day = parse_date(start_date)
    if start_day is None:
        return None
    end_day = parse_date(end_date) or start_day
    if all_day:
        start = at_local(start_day, 0, 0)
        end = at_local(end_day, 23, 59)
        if end < start:
            end = at_local(start_day, 23, 59)
        return start, end
    start_clock = parse_clock(start_time) or (9, 0)
    end_clock = parse_clock(end_time)
    start = at_local(start_day, start_clock[0], start_clock[1])
    if end_clock is None:
        end = start + timedelta(hours=1)
    else:
        end = at_local(end_day, end_clock[0], end_clock[1])
        if end <= start:
            end = start + timedelta(hours=1)
    return start, end


def date_input(value: datetime | None) -> str:
    if value is None:
        return ""
    return as_brussels(value).date().isoformat()


def time_input(value: datetime | None, hide_midnight: bool = False) -> str:
    if value is None:
        return ""
    local = as_brussels(value)
    if hide_midnight and local.hour == 0 and local.minute == 0:
        return ""
    return f"{local.hour:02d}:{local.minute:02d}"


def month_grid_start(year: int, month: int) -> date:
    first = date(year, month, 1)
    return first - timedelta(days=first.weekday())


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    month += delta
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return year, month


def month_label(year: int, month: int) -> str:
    return f"{MONTHS_LONG[month - 1].capitalize()} {year}"


def is_date_only(value: datetime) -> bool:
    local = as_brussels(value)
    return local.hour == 0 and local.minute == 0 and local.second == 0


def time_label(value: datetime, *, all_day: bool = False) -> str:
    if all_day or is_date_only(value):
        return ""
    local = as_brussels(value)
    return f"{local.hour}h{local.minute:02d}"


def start_of_day(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=BRUSSELS)


def end_of_day(day: date) -> datetime:
    return datetime.combine(day, time(23, 59, 59), tzinfo=BRUSSELS)
