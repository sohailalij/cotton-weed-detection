import pytest

from weedlab.api.ratelimit import RateLimiter


def test_rate_limiter_blocks_then_recovers() -> None:
    now = [0.0]
    limiter = RateLimiter(2, 60.0, clock=lambda: now[0])
    assert limiter.check("a") is None
    assert limiter.check("a") is None
    assert limiter.check("a") == pytest.approx(60.0)
    now[0] = 30.0
    assert limiter.check("a") == pytest.approx(30.0)
    assert limiter.check("b") is None  # another client is unaffected
    now[0] = 61.0
    assert limiter.check("a") is None


def test_rate_limiter_forgets_idle_clients() -> None:
    now = [0.0]
    limiter = RateLimiter(5, 60.0, clock=lambda: now[0])
    for i in range(999):
        limiter.check(f"c{i}")
    assert limiter.tracked_clients == 999
    now[0] = 100.0
    limiter.check("late")  # the 1000th call triggers cleanup
    assert limiter.tracked_clients == 1
