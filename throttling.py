"""Minimal in-memory debouncing for repeated button clicks.

No external dependency (no Redis, no DB) — good enough for a single-process
long-polling bot. If the bot is later scaled to multiple processes, this
should be swapped for a shared store (Redis, DB row with a timestamp, etc).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class SimpleThrottler:
    """Rejects repeated calls for the same key within ``ttl_seconds``.

    ``clock`` is injectable for tests; defaults to ``time.monotonic``.
    """

    ttl_seconds: float = 2.0
    clock: Callable[[], float] = field(default=time.monotonic)
    _last_seen: dict[int | str, float] = field(default_factory=dict)

    def allow(self, key: int | str) -> bool:
        """Return True if this call should proceed, False if it should be
        dropped because an identical call happened too recently."""
        now = self.clock()
        last = self._last_seen.get(key)
        if last is not None and (now - last) < self.ttl_seconds:
            return False
        self._last_seen[key] = now
        return True
