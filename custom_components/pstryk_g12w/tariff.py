"""Tariff classification and Polish public holiday dates."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")


def easter_sunday(year: int) -> date:
    """Return Gregorian Easter Sunday using the Meeus/Jones/Butcher algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def polish_holidays(year: int) -> set[date]:
    """Polish nationwide public holidays, including movable Easter holidays."""
    easter = easter_sunday(year)
    fixed = {(1, 1), (1, 6), (5, 1), (5, 3), (8, 15), (11, 1), (11, 11), (12, 25), (12, 26)}
    if year >= 2025:
        fixed.add((12, 24))
    days = {date(year, month, day) for month, day in fixed}
    days.update({
        easter,
        easter + timedelta(days=1),
        easter + timedelta(days=49),  # Pentecost Sunday
        easter + timedelta(days=60),  # Corpus Christi
    })
    return days


def parse_ranges(value: str) -> list[tuple[time, time]]:
    """Parse comma-separated local time ranges; 22:00-06:00 crosses midnight."""
    ranges: list[tuple[time, time]] = []
    if not value.strip():
        return ranges
    for item in value.split(","):
        start, end = (part.strip() for part in item.split("-", maxsplit=1))
        ranges.append((time.fromisoformat(start), time.fromisoformat(end)))
    return ranges


def _in_ranges(local: datetime, ranges: list[tuple[time, time]]) -> bool:
    now = local.timetz().replace(tzinfo=None)
    for start, end in ranges:
        if start < end and start <= now < end:
            return True
        if start > end and now >= start:
            return True
    return False


def is_peak(
    value: datetime,
    weekday_ranges: str,
    weekend_ranges: str = "",
    holidays_offpeak: bool = True,
) -> bool:
    """Classify an instant in Europe/Warsaw using local calendar and wall time."""
    local = value.astimezone(WARSAW) if value.tzinfo else value.replace(tzinfo=WARSAW)
    if holidays_offpeak and local.date() in polish_holidays(local.year):
        return False
    today_ranges = parse_ranges(weekend_ranges if local.weekday() >= 5 else weekday_ranges)
    if _in_ranges(local, today_ranges):
        return True
    # The after-midnight tail of a cross-midnight range uses the day on which
    # that range began (e.g. a Friday 22:00-06:00 window).
    previous = local.date() - timedelta(days=1)
    if holidays_offpeak and previous in polish_holidays(previous.year):
        return False
    previous_ranges = parse_ranges(weekend_ranges if previous.weekday() >= 5 else weekday_ranges)
    now = local.timetz().replace(tzinfo=None)
    return any(start > end and now < end for start, end in previous_ranges)
