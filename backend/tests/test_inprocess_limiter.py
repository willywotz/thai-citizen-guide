import pytest

from app.services.rate_limit import InProcessLimiter, RateLimitResult


async def test_check_allows_up_to_limit_then_blocks():
    t = [0.0]
    lim = InProcessLimiter(now_fn=lambda: t[0])
    for _ in range(3):
        r = await lim.check("a", limit=3)
        assert r.allowed is True
        assert r.retry_after == 0
    blocked = await lim.check("a", limit=3)
    assert blocked.allowed is False
    assert blocked.retry_after > 0


async def test_check_unlimited_when_limit_zero():
    lim = InProcessLimiter()
    for _ in range(100):
        r = await lim.check("a", limit=0)
        assert r == RateLimitResult(True, 0)


async def test_check_window_expiry_frees_slots():
    t = [0.0]
    lim = InProcessLimiter(now_fn=lambda: t[0])
    for _ in range(3):
        await lim.check("a", limit=3)
    t[0] = 61.0
    r = await lim.check("a", limit=3)
    assert r.allowed is True
