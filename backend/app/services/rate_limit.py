"""Rate limiters: in-process (single worker) and Redis-backed (multi worker)."""
import time
from collections import defaultdict, deque
from typing import NamedTuple, Protocol


class RateLimitResult(NamedTuple):
    allowed: bool
    retry_after: int


class RateLimiter(Protocol):
    async def check(
        self, key: str, *, limit: int, window_s: float = 60.0
    ) -> RateLimitResult: ...


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


class InProcessLimiter:
    """Async adapter over SlidingWindowLimiter for the RateLimiter interface."""

    def __init__(self, now_fn=time.monotonic):
        self._impl = SlidingWindowLimiter(now_fn=now_fn)

    async def check(
        self, key: str, *, limit: int, window_s: float = 60.0
    ) -> RateLimitResult:
        allowed = self._impl.allow(key, limit=limit, window_s=window_s)
        retry = 0 if allowed else self._impl.retry_after(key, window_s=window_s)
        return RateLimitResult(allowed, retry)
