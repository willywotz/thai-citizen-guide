import asyncio
import os
import uuid

import pytest
import pytest_asyncio
import redis.asyncio as aioredis

from app.services.rate_limit import RedisSlidingWindowLimiter

REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")


@pytest_asyncio.fixture
async def redis_client():
    client = aioredis.from_url(REDIS_URL)
    try:
        await client.ping()
    except Exception:
        pytest.skip("Redis not available at %s" % REDIS_URL)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


async def test_enforces_limit_within_window(redis_client):
    lim = RedisSlidingWindowLimiter(redis_client)
    for _ in range(3):
        assert (await lim.check("k", limit=3)).allowed is True
    blocked = await lim.check("k", limit=3)
    assert blocked.allowed is False
    assert blocked.retry_after > 0


async def test_unlimited_when_limit_zero(redis_client):
    lim = RedisSlidingWindowLimiter(redis_client)
    for _ in range(50):
        assert (await lim.check("k", limit=0)).allowed is True


async def test_window_slides(redis_client):
    lim = RedisSlidingWindowLimiter(redis_client)
    key = uuid.uuid4().hex  # unique key so no other test's events can leak in
    # Back-to-back calls are sub-millisecond apart, well within the 1s window.
    assert (await lim.check(key, limit=1, window_s=1.0)).allowed is True
    assert (await lim.check(key, limit=1, window_s=1.0)).allowed is False
    # Sleep generously past the window; extra delay only frees the slot sooner.
    await asyncio.sleep(2.0)
    assert (await lim.check(key, limit=1, window_s=1.0)).allowed is True


async def test_shared_budget_across_instances(redis_client):
    a = RedisSlidingWindowLimiter(redis_client)
    b = RedisSlidingWindowLimiter(redis_client)
    assert (await a.check("shared", limit=2)).allowed is True
    assert (await b.check("shared", limit=2)).allowed is True
    # Third request on either instance is over the *combined* budget.
    assert (await a.check("shared", limit=2)).allowed is False


async def test_fail_open_when_redis_unreachable():
    dead = aioredis.from_url(
        "redis://localhost:6390/0",
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
    )
    lim = RedisSlidingWindowLimiter(dead)
    result = await lim.check("k", limit=1)
    assert result.allowed is True
    assert result.retry_after == 0
    await dead.aclose()
