"""Injectable time. Nothing in StubbleOS should call ``datetime.now()`` directly:
the simulator needs deterministic time and the Policy Guard needs testable contact hours."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Protocol

# India observes no DST, so a fixed offset is exact and avoids a tz-database dependency.
IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def as_utc(dt: datetime) -> datetime:
    """Return ``dt`` as an aware UTC datetime. Naive values are assumed to already be UTC
    (SQLite drops tzinfo on read; Postgres does not)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def require_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetime not allowed here; attach a timezone")
    return dt


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class SimClock:
    """Deterministic clock controlled by the simulator or by tests."""

    def __init__(self, start: datetime) -> None:
        self._now = as_utc(require_aware(start))

    def now(self) -> datetime:
        return self._now

    def set(self, value: datetime) -> None:
        value = as_utc(require_aware(value))
        if value < self._now:
            raise ValueError("SimClock cannot move backwards")
        self._now = value

    def advance(self, delta: timedelta) -> datetime:
        if delta < timedelta(0):
            raise ValueError("SimClock cannot move backwards")
        self._now += delta
        return self._now

    def advance_days(self, days: float) -> datetime:
        return self.advance(timedelta(days=days))
