"""Tests for the in-memory sliding-window rate limiter."""

from __future__ import annotations

import pytest

from app.llm.rate_limit import RateLimiter


class FakeClock:
    """Manually-advanced monotonic clock for deterministic tests."""

    def __init__(self, start: float = 0.0):
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def test_under_limit_acquires():
    clock = FakeClock()
    limiter = RateLimiter(max_requests=3, window_seconds=60.0, now=clock)
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is True


def test_eleventh_call_blocked_within_window():
    clock = FakeClock()
    limiter = RateLimiter(max_requests=10, window_seconds=60.0, now=clock)
    for _ in range(10):
        assert limiter.try_acquire() is True
    # 11th attempt within the same window is denied.
    assert limiter.try_acquire() is False


def test_window_rolls_off_after_period():
    clock = FakeClock()
    limiter = RateLimiter(max_requests=2, window_seconds=60.0, now=clock)
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False

    # Advance past the window; oldest entries should fall off.
    clock.advance(61.0)
    assert limiter.try_acquire() is True


def test_denied_calls_do_not_extend_window():
    clock = FakeClock()
    limiter = RateLimiter(max_requests=2, window_seconds=60.0, now=clock)
    limiter.try_acquire()
    limiter.try_acquire()
    assert limiter.try_acquire() is False  # denied — not recorded
    clock.advance(61.0)
    # If denied calls extended the window we'd still be blocked here.
    assert limiter.try_acquire() is True


def test_reset_clears_state():
    clock = FakeClock()
    limiter = RateLimiter(max_requests=1, window_seconds=60.0, now=clock)
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False
    limiter.reset()
    assert limiter.try_acquire() is True


def test_in_flight_property():
    clock = FakeClock()
    limiter = RateLimiter(max_requests=5, window_seconds=60.0, now=clock)
    assert limiter.in_flight == 0
    limiter.try_acquire()
    limiter.try_acquire()
    assert limiter.in_flight == 2
    clock.advance(61.0)
    assert limiter.in_flight == 0


def test_invalid_construction():
    with pytest.raises(ValueError):
        RateLimiter(max_requests=0)
    with pytest.raises(ValueError):
        RateLimiter(window_seconds=0)
