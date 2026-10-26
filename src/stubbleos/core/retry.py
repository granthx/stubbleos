"""Retry with exponential backoff, jitter and per-attempt timeouts for all external calls."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")
_DEFAULT_RNG = random.Random()


class RetryExhausted(Exception):  # noqa: N818
    def __init__(self, attempts: int, last_error: BaseException) -> None:
        super().__init__(f"gave up after {attempts} attempts: {type(last_error).__name__}: {last_error}")
        self.attempts = attempts
        self.last_error = last_error


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    jitter: float = 0.1,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    timeout_s: float | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    rng: random.Random | None = None,
) -> T:
    """Call ``fn`` up to ``attempts`` times. ``timeout_s`` applies per attempt and a timeout counts
    as a retryable failure when ``TimeoutError`` is covered by ``retry_on``. Exceptions outside
    ``retry_on`` propagate immediately."""
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    rand = rng or _DEFAULT_RNG
    last: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            if timeout_s is None:
                return await fn()
            async with asyncio.timeout(timeout_s):
                return await fn()
        except retry_on as exc:
            last = exc
            if attempt == attempts:
                break
            delay = min(max_delay, base_delay * 2 ** (attempt - 1))
            delay *= 1 + rand.uniform(-jitter, jitter)
            await sleep(delay)
    assert last is not None  # noqa: S101  (loop always sets it before falling through)
    raise RetryExhausted(attempts, last) from last
