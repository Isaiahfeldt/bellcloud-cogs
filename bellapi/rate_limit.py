import time
from collections import defaultdict


class RateLimiter:
    """
    Simple in-memory token-bucket rate limiter.
    Tracks calls per key within a sliding window.
    Safe for single-process use only (no distributed support needed).
    """

    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self._calls: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.period
        calls = self._calls[key]
        # Prune expired entries
        self._calls[key] = [t for t in calls if t > window_start]
        if len(self._calls[key]) >= self.max_calls:
            return False
        self._calls[key].append(now)
        return True
