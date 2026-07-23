from app.services.rate_limit import (
    InProcessLimiter,
    RedisSlidingWindowLimiter,
    build_limiter,
)


def test_factory_returns_inprocess_when_no_url():
    assert isinstance(build_limiter(""), InProcessLimiter)


def test_factory_returns_redis_when_url_set():
    lim = build_limiter("redis://localhost:6379/0")
    assert isinstance(lim, RedisSlidingWindowLimiter)
