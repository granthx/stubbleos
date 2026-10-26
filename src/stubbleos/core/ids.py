"""ID factories. Production uses uuid4; simulation uses a seeded factory so runs are reproducible."""

from __future__ import annotations

import random
import uuid
from collections.abc import Callable

IdFactory = Callable[[], uuid.UUID]


class SeededUUIDFactory:
    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)

    def __call__(self) -> uuid.UUID:
        return uuid.UUID(int=self._rng.getrandbits(128), version=4)
