"""In-memory sliding-window rate limiter for the chat endpoint.

PLAN §8/§9 calls for 10 requests per minute per process on `POST /api/chat`,
returning 429 RATE_LIMITED when exceeded. State lives in process memory and
is reset on restart — that's acceptable for a single-user demo and matches
the spec.

The limiter is implemented as a simple sliding window: we keep a deque of
recent request timestamps and drop entries older than `window_seconds`
before counting. Clock injection via the `now` callable keeps tests fast.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable


class RateLimiter:
    """Sliding-window per-process counter."""

    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: float = 60.0,
        now: Callable[[], float] | None = None,
    ) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._now = now or time.monotonic
        self._events: deque[float] = deque()
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        """Record an attempt; return True if it fits within the window.

        On a False return the attempt is *not* added to the bucket, so a
        flood of denied calls does not stretch the cooldown window.
        """
        now = self._now()
        cutoff = now - self.window_seconds
        with self._lock:
            while self._events and self._events[0] <= cutoff:
                self._events.popleft()
            if len(self._events) >= self.max_requests:
                return False
            self._events.append(now)
            return True

    def reset(self) -> None:
        """Drop all recorded events (test helper)."""
        with self._lock:
            self._events.clear()

    @property
    def in_flight(self) -> int:
        """Number of recorded events in the current window (test helper)."""
        now = self._now()
        cutoff = now - self.window_seconds
        with self._lock:
            while self._events and self._events[0] <= cutoff:
                self._events.popleft()
            return len(self._events)


# Module-level singleton used by the chat route. Tests reach in via
# `chat_rate_limiter.reset()` between cases.
chat_rate_limiter = RateLimiter(max_requests=10, window_seconds=60.0)


__all__ = ["RateLimiter", "chat_rate_limiter"]
