import app.services.rate_limit as rl
from app.services.rate_limit import RedisSlidingWindowLimiter
from tests.test_fail_open_observability import FakeClient, FakeScript

import pytest


@pytest.fixture(autouse=True)
def _reset_health():
    rl._redis_health.failing = False
    rl._redis_health.fail_open_total = 0
    rl._redis_health._since = 0
    rl._fallback_limiter._impl._events.clear()
    yield


async def test_degrades_to_inprocess_and_enforces_limit():
    # Redis always fails -> limiter must fall back to a shared in-process limiter
    # and still enforce the per-worker budget (NOT fail open).
    lim = RedisSlidingWindowLimiter(FakeClient(FakeScript(fail_n=10_000)))
    allowed = []
    for _ in range(5):
        allowed.append((await lim.check("user:1", limit=2)).allowed)
    assert allowed[:2] == [True, True]
    assert allowed[2] is False  # third request blocked by in-process fallback
