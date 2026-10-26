from datetime import UTC, datetime, timedelta

import pytest

from stubbleos.core.clock import IST, SimClock, as_utc


def test_sim_clock_advances_and_refuses_backwards() -> None:
    c = SimClock(datetime(2026, 10, 20, tzinfo=UTC))
    c.advance_days(1.5)
    assert c.now() == datetime(2026, 10, 21, 12, tzinfo=UTC)
    with pytest.raises(ValueError, match="SimClock cannot move backwards"):
        c.advance(timedelta(seconds=-1))
    with pytest.raises(ValueError, match="SimClock cannot move backwards"):
        c.set(datetime(2026, 1, 1, tzinfo=UTC))


def test_naive_start_rejected() -> None:
    with pytest.raises(ValueError, match="naive datetime not allowed"):
        SimClock(datetime(2026, 10, 20))


def test_ist_offset_and_as_utc() -> None:
    local = datetime(2026, 10, 20, 8, 0, tzinfo=IST)
    assert as_utc(local) == datetime(2026, 10, 20, 2, 30, tzinfo=UTC)
    assert as_utc(datetime(2026, 10, 20, 2, 30)).tzinfo is UTC
