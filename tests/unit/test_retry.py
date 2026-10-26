import asyncio

import pytest

from stubbleos.core.retry import RetryExhausted, retry_async


class Flaky:
    def __init__(self, failures: int, exc: type[Exception] = ConnectionError) -> None:
        self.failures, self.exc, self.calls = failures, exc, 0

    async def __call__(self) -> str:
        self.calls += 1
        if self.calls <= self.failures:
            raise self.exc("boom")
        return "ok"


async def test_succeeds_after_retries_with_exponential_delays() -> None:
    delays: list[float] = []

    async def fake_sleep(d: float) -> None:
        delays.append(d)

    fn = Flaky(2)
    assert await retry_async(fn, attempts=3, base_delay=1.0, jitter=0.0, sleep=fake_sleep) == "ok"
    assert delays == [1.0, 2.0]


async def test_exhaustion_wraps_last_error() -> None:
    async def no_sleep(_: float) -> None: ...

    with pytest.raises(RetryExhausted) as ei:
        await retry_async(Flaky(10), attempts=2, sleep=no_sleep)
    assert ei.value.attempts == 2
    assert isinstance(ei.value.last_error, ConnectionError)


async def test_non_retryable_propagates_immediately() -> None:
    fn = Flaky(5, ValueError)
    with pytest.raises(ValueError, match="boom"):
        await retry_async(fn, attempts=3, retry_on=(ConnectionError,))
    assert fn.calls == 1


async def test_timeout_is_retryable() -> None:
    async def no_sleep(_: float) -> None: ...

    async def slow() -> str:
        await asyncio.sleep(1)
        return "late"

    with pytest.raises(RetryExhausted) as ei:
        await retry_async(slow, attempts=2, timeout_s=0.01, retry_on=(TimeoutError,), sleep=no_sleep)
    assert isinstance(ei.value.last_error, TimeoutError)
