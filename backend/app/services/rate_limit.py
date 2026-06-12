"""In-process sliding-window rate limiter (single-worker deployment)."""
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, now_fn=time.monotonic):
        self._now = now_fn
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, *, limit: int, window_s: float = 60.0) -> bool:
        if limit <= 0:
            return True  # 0/None-configured = unlimited
        now = self._now()
        q = self._events[key]
        while q and q[0] <= now - window_s:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True

    def retry_after(self, key: str, *, window_s: float = 60.0) -> int:
        q = self._events.get(key)
        if not q:
            return 0
        return max(0, int(q[0] + window_s - self._now()) + 1)


agency_limiter = SlidingWindowLimiter()
user_limiter = SlidingWindowLimiter()
