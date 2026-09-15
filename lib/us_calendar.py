"""NYSE trading calendar · weekends + observed full-day holidays.

Half-day sessions still count as trading days (we still want 盘前 / 盘后).
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# Observed NYSE full-day closures (not half-days).
NYSE_HOLIDAYS: frozenset[date] = frozenset(
    {
        date(2026, 1, 1),
        date(2026, 1, 19),
        date(2026, 2, 16),
        date(2026, 4, 3),
        date(2026, 5, 25),
        date(2026, 6, 19),
        date(2026, 7, 3),
        date(2026, 9, 7),
        date(2026, 11, 26),
        date(2026, 12, 25),
        date(2027, 1, 1),
        date(2027, 1, 18),
        date(2027, 2, 15),
        date(2027, 3, 26),
        date(2027, 5, 31),
        date(2027, 6, 18),
        date(2027, 7, 5),
        date(2027, 9, 6),
        date(2027, 11, 25),
        date(2027, 12, 24),
    }
)


def nyse_date(dt: datetime | None = None) -> date:
    d = dt or datetime.now(ET)
    if d.tzinfo is None:
        d = d.replace(tzinfo=ET)
    else:
        d = d.astimezone(ET)
    return d.date()


def utc_date(dt: datetime | None = None) -> date:
    d = dt or datetime.now(UTC)
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    else:
        d = d.astimezone(UTC)
    return d.date()


def is_nyse_trading_day(d: date | datetime | None = None) -> bool:
    if d is None:
        d = nyse_date()
    elif isinstance(d, datetime):
        d = nyse_date(d)
    if d.weekday() >= 5:
        return False
    return d not in NYSE_HOLIDAYS


def in_us_pre_window(dt_et: datetime | None = None) -> bool:
    from lib.us_premarket.fetch import resolve_us_session

    return resolve_us_session(dt_et)["session"] == "premarket"


def in_us_after_window(dt_et: datetime | None = None) -> bool:
    from lib.us_premarket.fetch import resolve_us_session

    return resolve_us_session(dt_et)["session"] == "afterhours"


def in_wave_utc_window(dt_utc: datetime | None = None) -> bool:
    d = dt_utc or datetime.now(UTC)
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    else:
        d = d.astimezone(UTC)
    return d.hour in (0, 1)
