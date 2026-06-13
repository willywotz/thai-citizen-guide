"""Rate limiters: in-process (single worker) and Redis-backed (multi worker)."""
import logging
import time
import uuid
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


logger = logging.getLogger(__name__)

_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window_us = tonumber(ARGV[2])
local member = ARGV[3]
local t = redis.call('TIME')
local now_us = (tonumber(t[1]) * 1000000) + tonumber(t[2])
redis.call('ZREMRANGEBYSCORE', key, 0, now_us - window_us)
local count = redis.call('ZCARD', key)
if count >= limit then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local retry = 1
  if oldest[2] then
    retry = math.ceil((tonumber(oldest[2]) + window_us - now_us) / 1000000)
    if retry < 1 then retry = 1 end
  end
  return {0, retry}
end
redis.call('ZADD', key, now_us, now_us .. '-' .. member)
redis.call('PEXPIRE', key, math.ceil(window_us / 1000))
return {1, 0}
"""


class RedisSlidingWindowLimiter:
    """Sliding-window rate limiter backed by a Redis sorted set.

    One atomic Lua script per check, so concurrent uvicorn workers share a
    single budget. Any Redis error fails open (allows the request).
    """

    def __init__(self, client):
        self._client = client
        self._script = client.register_script(_SLIDING_WINDOW_LUA)

    async def check(
        self, key: str, *, limit: int, window_s: float = 60.0
    ) -> RateLimitResult:
        if limit <= 0:
            return RateLimitResult(True, 0)
        window_us = int(window_s * 1_000_000)
        member = uuid.uuid4().hex
        try:
            allowed, retry = await self._script(
                keys=[f"rl:{key}"], args=[limit, window_us, member]
            )
        except Exception:  # RedisError, connection/timeout — fail open
            logger.warning("rate limiter: Redis unavailable, failing open", exc_info=True)
            return RateLimitResult(True, 0)
        return RateLimitResult(bool(allowed), int(retry))
