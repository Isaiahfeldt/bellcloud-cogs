import time
import pytest
from bellapi.rate_limit import RateLimiter


def test_allows_requests_under_limit():
    limiter = RateLimiter(max_calls=3, period=60)
    assert limiter.is_allowed("user1") is True
    assert limiter.is_allowed("user1") is True
    assert limiter.is_allowed("user1") is True


def test_blocks_after_limit():
    limiter = RateLimiter(max_calls=3, period=60)
    limiter.is_allowed("user1")
    limiter.is_allowed("user1")
    limiter.is_allowed("user1")
    assert limiter.is_allowed("user1") is False


def test_different_users_independent():
    limiter = RateLimiter(max_calls=1, period=60)
    limiter.is_allowed("user1")
    assert limiter.is_allowed("user1") is False
    assert limiter.is_allowed("user2") is True


def test_resets_after_period(monkeypatch):
    limiter = RateLimiter(max_calls=1, period=1)
    limiter.is_allowed("user1")
    assert limiter.is_allowed("user1") is False
    original = time.time()
    monkeypatch.setattr(time, "time", lambda: original + 2)
    assert limiter.is_allowed("user1") is True
