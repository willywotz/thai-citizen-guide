import logging

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

import app.services.rate_limit as rl
from app.services.rate_limit import RateLimitResult, RedisSlidingWindowLimiter


class FakeScript:
    """Stand-in for a redis-py registered Script: fails the first `fail_n`
    calls, then returns [1, 0] (allowed)."""

    def __init__(self, fail_n):
        self.fail_n = fail_n
        self.calls = 0

    async def __call__(self, *, keys, args):
        self.calls += 1
        if self.calls <= self.fail_n:
            raise RedisConnectionError("boom")
        return [1, 0]


class FakeClient:
    def __init__(self, script):
        self._script = script

    def register_script(self, _src):
        return self._script


@pytest.fixture(autouse=True)
def _reset_health():
    # _redis_health is a module-level singleton shared across tests.
    rl._redis_health.failing = False
    rl._redis_health.fail_open_total = 0
    rl._redis_health._since = 0
    yield


async def test_fail_open_returns_allowed_and_logs_once(caplog):
    lim = RedisSlidingWindowLimiter(FakeClient(FakeScript(fail_n=3)))
    with caplog.at_level(logging.WARNING, logger="app.services.rate_limit"):
        for _ in range(3):
            assert await lim.check("k", limit=5) == RateLimitResult(True, 0)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "failing open" in warnings[0].getMessage()


async def test_recovery_logs_with_count(caplog):
    lim = RedisSlidingWindowLimiter(FakeClient(FakeScript(fail_n=2)))
    with caplog.at_level(logging.INFO, logger="app.services.rate_limit"):
        await lim.check("k", limit=5)  # fail 1
        await lim.check("k", limit=5)  # fail 2
        result = await lim.check("k", limit=5)  # success -> recovery
    assert result == RateLimitResult(True, 0)
    infos = [r for r in caplog.records if r.levelno == logging.INFO
             and "recovered" in r.getMessage()]
    assert len(infos) == 1
    assert "2 request" in infos[0].getMessage()
