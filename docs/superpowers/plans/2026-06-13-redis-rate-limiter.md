# Redis-backed Multi-Worker Rate Limiting — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the three API rate limiters (`api_key_limiter`, `user_limiter`, `agency_limiter`) enforce one shared budget per key across all uvicorn workers by backing them with Redis.

**Architecture:** Introduce an async `RateLimiter` interface with a single atomic `check()` method. Two implementations: `InProcessLimiter` (wraps the existing `SlidingWindowLimiter`, used when `REDIS_URL` is unset) and `RedisSlidingWindowLimiter` (sorted-set sliding log via one atomic Lua script). A factory picks one at import time. Redis errors fail open (allow the request). All three call sites become `await`-based.

**Tech Stack:** Python 3.12, FastAPI, Tortoise ORM, `redis>=5` (`redis.asyncio`), pytest + pytest-asyncio (`asyncio_mode = auto`).

**Spec:** `docs/superpowers/specs/2026-06-13-redis-rate-limiter-design.md`

---

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `backend/pyproject.toml` | add `redis>=5` dependency | Modify |
| `backend/app/config.py` | `REDIS_URL`, `REDIS_SOCKET_TIMEOUT_MS` settings | Modify |
| `backend/app/services/rate_limit.py` | `RateLimitResult`, `RateLimiter`, `InProcessLimiter`, `RedisSlidingWindowLimiter`, factory, module-level limiters | Modify |
| `backend/app/main.py` | close the shared Redis client on shutdown | Modify |
| `backend/app/routers/chat.py` | `enforce_user_rate_limit` → async `check()` | Modify |
| `backend/app/auth/dependencies.py` | api-key limiter → async `check()` | Modify |
| `backend/app/services/chat/dispatch.py` | agency limiter → async `check()` | Modify |
| `backend/tests/test_rate_limit.py` | existing in-process unit tests (unchanged) | Keep |
| `backend/tests/test_inprocess_limiter.py` | `InProcessLimiter.check()` unit tests | Create |
| `backend/tests/test_redis_rate_limit.py` | `RedisSlidingWindowLimiter` tests (real Redis, skip if absent) + fail-open | Create |
| `backend/tests/test_user_rate_limit.py` | update for async `check()` | Modify |
| `backend/tests/test_api_key_enforcement.py` | update per-key test for async limiter | Modify |
| `backend/tests/services/test_dispatch.py` | update rate-limited test for async limiter | Modify |
| `docker-compose.yaml` | add `redis` service + wire `REDIS_URL` | Modify |
| `backend/Dockerfile` | production CMD → `--workers 4` | Modify |

**Run commands from `backend/` unless stated otherwise.** Tests: `uv run pytest`. After Go-free Python changes there is no gofmt/golangci step — this is a Python service.

---

### Task 1: Add Redis dependency and settings

**Files:**
- Modify: `backend/pyproject.toml:6-38`
- Modify: `backend/app/config.py:17-18` (add a Redis group near Database)

- [ ] **Step 1: Add the dependency**

In `backend/pyproject.toml`, add `redis` to the `dependencies` list (after the asyncpg ORM block):

```toml
    # ORM + PostgreSQL async driver
    "tortoise-orm[asyncpg]>=0.21.0",
    "pgvector>=0.3.0",
    # Distributed rate limiting
    "redis>=5.0.0",
```

- [ ] **Step 2: Lock the dependency**

Run: `uv lock`
Expected: `uv.lock` updates to include `redis` (and its `async-timeout`/`hiredis`-free core). No error.

- [ ] **Step 3: Add settings**

In `backend/app/config.py`, add a Redis block immediately after the Database block (after line 18, the `DATABASE_URL` line):

```python
    # ── Redis (distributed rate limiting) ────────────────────────────────────
    REDIS_URL: str = ""           # empty = in-process limiter (single worker)
    REDIS_SOCKET_TIMEOUT_MS: int = 100
```

- [ ] **Step 4: Verify import still works**

Run: `uv run python -c "from app.config import settings; print(repr(settings.REDIS_URL), settings.REDIS_SOCKET_TIMEOUT_MS)"`
Expected: `'' 100`

- [ ] **Step 5: Commit**

```bash
rtk git add pyproject.toml uv.lock app/config.py
rtk git commit -m "feat(rate-limit): add redis dependency and settings"
```

---

### Task 2: `RateLimitResult`, `RateLimiter` protocol, and `InProcessLimiter`

Add the async interface and an in-process implementation that wraps the existing `SlidingWindowLimiter`. The existing `SlidingWindowLimiter` class stays untouched (its unit tests in `test_rate_limit.py` keep passing).

**Files:**
- Modify: `backend/app/services/rate_limit.py`
- Test: `backend/tests/test_inprocess_limiter.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_inprocess_limiter.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_inprocess_limiter.py -v`
Expected: FAIL — `ImportError: cannot import name 'InProcessLimiter'`

- [ ] **Step 3: Implement the interface and in-process limiter**

Edit `backend/app/services/rate_limit.py`. Replace the module docstring + imports + the three module-level limiter assignments at the bottom (lines 30-32). Keep the `SlidingWindowLimiter` class exactly as-is. The file becomes:

```python
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
```

(The module-level `agency_limiter` / `user_limiter` / `api_key_limiter` assignments are intentionally removed here — they are re-added by the factory in Task 4. Do not run the call-site tests until Task 5.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_inprocess_limiter.py tests/test_rate_limit.py -v`
Expected: PASS — new `InProcessLimiter` tests and the original `SlidingWindowLimiter` tests all green.

- [ ] **Step 5: Commit**

```bash
rtk git add app/services/rate_limit.py tests/test_inprocess_limiter.py
rtk git commit -m "feat(rate-limit): add RateLimiter interface and InProcessLimiter"
```

---

### Task 3: `RedisSlidingWindowLimiter` with atomic Lua script

Sorted-set sliding log. One Lua script does trim → count → (block with retry_after | add + expire). Time comes from `redis.call('TIME')` so every worker shares one clock. The client supplies a unique member token per call so identical-microsecond events don't collide. Redis errors fail open.

**Files:**
- Modify: `backend/app/services/rate_limit.py`
- Test: `backend/tests/test_redis_rate_limit.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_redis_rate_limit.py`:

```python
import asyncio
import os

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
    assert (await lim.check("k", limit=1, window_s=1.0)).allowed is True
    assert (await lim.check("k", limit=1, window_s=1.0)).allowed is False
    await asyncio.sleep(1.1)
    assert (await lim.check("k", limit=1, window_s=1.0)).allowed is True


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_redis_rate_limit.py -v`
Expected: FAIL — `ImportError: cannot import name 'RedisSlidingWindowLimiter'`

- [ ] **Step 3: Implement the Redis limiter**

Append to `backend/app/services/rate_limit.py` (after `InProcessLimiter`). Add `import logging` and `import uuid` to the top of the file alongside `import time`:

```python
import logging
import uuid

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
```

- [ ] **Step 4: Run test to verify it passes**

Run (with a local Redis available, e.g. `docker run -p 6379:6379 redis`): `uv run pytest tests/test_redis_rate_limit.py -v`
Expected: PASS for all tests. Without a local Redis: the four `redis_client` tests SKIP and `test_fail_open_when_redis_unreachable` PASSES.

- [ ] **Step 5: Commit**

```bash
rtk git add app/services/rate_limit.py tests/test_redis_rate_limit.py
rtk git commit -m "feat(rate-limit): add RedisSlidingWindowLimiter with atomic Lua script"
```

---

### Task 4: Factory, module-level limiters, and client shutdown

Re-add the three module-level limiters via a factory that reads `settings.REDIS_URL`. One shared Redis client is created when `REDIS_URL` is set; closed on app shutdown.

**Files:**
- Modify: `backend/app/services/rate_limit.py`
- Modify: `backend/app/main.py:69-82` (lifespan shutdown)
- Test: `backend/tests/test_limiter_factory.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_limiter_factory.py`:

```python
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


def test_module_level_limiters_exist():
    import app.services.rate_limit as rl
    for name in ("agency_limiter", "user_limiter", "api_key_limiter"):
        assert hasattr(rl, name)
        assert hasattr(getattr(rl, name), "check")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_limiter_factory.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_limiter'`

- [ ] **Step 3: Implement the factory and module-level limiters**

Append to `backend/app/services/rate_limit.py`. Add `from app.config import settings` to the imports at the top:

```python
_redis_client = None


def _get_redis_client(url: str):
    """Create (once) the shared async Redis client, or None when url is empty."""
    global _redis_client
    if not url:
        return None
    if _redis_client is None:
        import redis.asyncio as aioredis

        timeout_s = settings.REDIS_SOCKET_TIMEOUT_MS / 1000
        _redis_client = aioredis.from_url(
            url,
            socket_timeout=timeout_s,
            socket_connect_timeout=timeout_s,
        )
    return _redis_client


def build_limiter(url: str | None = None):
    """Return a Redis-backed limiter when REDIS_URL is set, else in-process."""
    url = settings.REDIS_URL if url is None else url
    client = _get_redis_client(url)
    return RedisSlidingWindowLimiter(client) if client is not None else InProcessLimiter()


async def close_limiter_client() -> None:
    """Close the shared Redis client on application shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


agency_limiter = build_limiter()
user_limiter = build_limiter()
api_key_limiter = build_limiter()
```

Note: when `REDIS_URL` is set, all three share the one `_redis_client`; keys are already namespaced (`agency:` / `user:` / `apikey:`), so a single client is correct.

- [ ] **Step 4: Wire shutdown into the lifespan**

In `backend/app/main.py`, add the import near the other app imports (after line 40):

```python
from app.services.rate_limit import close_limiter_client
```

Then in the `lifespan` function, add the close call in the shutdown section (after `await stop_scheduler()`, line 81):

```python
    await stop_scheduler()
    await close_limiter_client()
    await close_db()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_limiter_factory.py -v`
Expected: PASS — all three tests green. (`build_limiter("redis://...")` constructs the client lazily; `from_url` does not connect until first use, so no Redis is needed for this test.)

- [ ] **Step 6: Commit**

```bash
rtk git add app/services/rate_limit.py app/main.py tests/test_limiter_factory.py
rtk git commit -m "feat(rate-limit): factory selects redis vs in-process; close client on shutdown"
```

---

### Task 5: Convert call sites to async `check()` and update their tests

Three call sites move from `limiter.allow(...)` + `limiter.retry_after(...)` to `await limiter.check(...)`. Update the three affected tests in the same task (red → green per file).

**Files:**
- Modify: `backend/app/routers/chat.py:49-56` and callers at `:64`, `:176`, `:322`
- Modify: `backend/app/auth/dependencies.py:55-63`
- Modify: `backend/app/services/chat/dispatch.py:190-192`
- Modify: `backend/tests/test_user_rate_limit.py`
- Modify: `backend/tests/test_api_key_enforcement.py:47-58`
- Modify: `backend/tests/services/test_dispatch.py:585-610`

- [ ] **Step 1: Update the user-limit test (failing)**

Replace the body of `backend/tests/test_user_rate_limit.py` with:

```python
import pytest
from fastapi import HTTPException

from app.routers.chat import enforce_user_rate_limit
from app.services.rate_limit import InProcessLimiter


async def test_blocks_after_limit(monkeypatch):
    import app.routers.chat as chat_mod
    t = [0.0]
    monkeypatch.setattr(chat_mod, "user_limiter", InProcessLimiter(now_fn=lambda: t[0]))
    monkeypatch.setattr(chat_mod.settings, "USER_RATE_LIMIT_RPM", 2)

    class U:
        id = "u1"

    await enforce_user_rate_limit(U())
    await enforce_user_rate_limit(U())
    with pytest.raises(HTTPException) as e:
        await enforce_user_rate_limit(U())
    assert e.value.status_code == 429
    assert "Retry-After" in e.value.headers
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_user_rate_limit.py -v`
Expected: FAIL — `TypeError` (awaiting a non-coroutine / `enforce_user_rate_limit` still sync) or assertion error.

- [ ] **Step 3: Make `enforce_user_rate_limit` async in `chat.py`**

In `backend/app/routers/chat.py`, replace lines 49-56:

```python
async def enforce_user_rate_limit(user) -> None:
    key = f"user:{user.id}"
    result = await user_limiter.check(key, limit=settings.USER_RATE_LIMIT_RPM)
    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(result.retry_after)},
        )
```

Then update all three callers (lines 64, 176, 322) from:

```python
        enforce_user_rate_limit(user)
```

to:

```python
        await enforce_user_rate_limit(user)
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/test_user_rate_limit.py -v`
Expected: PASS

- [ ] **Step 5: Update the api-key enforcement test (failing)**

In `backend/tests/test_api_key_enforcement.py`, replace `test_per_key_rate_limit` (lines 47-58) with:

```python
async def test_per_key_rate_limit(db, monkeypatch):
    import app.auth.dependencies as dep
    from app.services.rate_limit import InProcessLimiter
    monkeypatch.setattr(dep, "api_key_limiter", InProcessLimiter())
    u = await User.create(email="rl@x.com", hashed_password="h")
    raw = await _key(u, rate_limit_rpm=1)
    await get_current_user(_creds(raw))  # 1st ok
    with pytest.raises(HTTPException) as e:
        await get_current_user(_creds(raw))  # 2nd over limit
    assert e.value.status_code == 429
    assert "Retry-After" in e.value.headers
```

- [ ] **Step 6: Run it to verify it fails**

Run: `uv run pytest tests/test_api_key_enforcement.py::test_per_key_rate_limit -v`
Expected: FAIL — `api_key_limiter.allow(...)` is still called in `dependencies.py` (the monkeypatched `InProcessLimiter` has no `allow`), raising `AttributeError`.

- [ ] **Step 7: Update `dependencies.py` to async `check()`**

In `backend/app/auth/dependencies.py`, replace lines 55-63:

```python
        rpm = api_key.rate_limit_rpm or 0
        if rpm:
            key = f"apikey:{api_key.id}"
            result = await api_key_limiter.check(key, limit=rpm)
            if not result.allowed:
                raise HTTPException(
                    status_code=429,
                    detail="API key rate limit exceeded",
                    headers={"Retry-After": str(result.retry_after)},
                )
```

- [ ] **Step 8: Run it to verify it passes**

Run: `uv run pytest tests/test_api_key_enforcement.py -v`
Expected: PASS — all tests in the file (the unset-limit tests already short-circuit on `rpm == 0`).

- [ ] **Step 9: Update the dispatch rate-limit test (failing)**

In `backend/tests/services/test_dispatch.py`, in `test_dispatch_one_rate_limited` (lines 585-610), change the import and monkeypatch:

```python
    import app.services.chat.dispatch as d
    from app.services.rate_limit import InProcessLimiter

    monkeypatch.setattr(d, "agency_limiter", InProcessLimiter())
```

(Leave the rest of the test unchanged.)

- [ ] **Step 10: Run it to verify it fails**

Run: `uv run pytest tests/services/test_dispatch.py::test_dispatch_one_rate_limited -v`
Expected: FAIL — `dispatch_one` still calls `agency_limiter.allow(...)`, raising `AttributeError` on the `InProcessLimiter`.

- [ ] **Step 11: Update `dispatch.py` to async `check()`**

In `backend/app/services/chat/dispatch.py`, replace lines 190-192:

```python
    rpm = route.get("rate_limit_rpm") or 0
    if rpm:
        result = await agency_limiter.check(f"agency:{route.get('agency_id')}", limit=rpm)
        if not result.allowed:
            return {"agency": name, "response": "rate limit exceeded", "status": "rate_limited"}
```

- [ ] **Step 12: Run it to verify it passes**

Run: `uv run pytest tests/services/test_dispatch.py::test_dispatch_one_rate_limited -v`
Expected: PASS

- [ ] **Step 13: Run the full suite**

Run: `uv run pytest`
Expected: PASS (Redis-only tests SKIP without a local Redis). No failures.

- [ ] **Step 14: Commit**

```bash
rtk git add app/routers/chat.py app/auth/dependencies.py app/services/chat/dispatch.py \
  tests/test_user_rate_limit.py tests/test_api_key_enforcement.py tests/services/test_dispatch.py
rtk git commit -m "refactor(rate-limit): call sites use async RateLimiter.check()"
```

---

### Task 6: Infrastructure — Redis service and multi-worker uvicorn

Add a Redis service to compose, point the backend at it, and bump the production server to 4 workers so the distributed limiter is actually exercised.

**Files:**
- Modify: `docker-compose.yaml`
- Modify: `backend/Dockerfile:29`

- [ ] **Step 1: Add the `redis` service**

In `docker-compose.yaml`, add a new service after the `postgres-init` block (before `backend:`, around line 40):

```yaml
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    networks:
      - chatbot-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 5s
```

- [ ] **Step 2: Wire `REDIS_URL` and the dependency into the backend service**

In the `backend` service `environment` block (after the `OPENROUTER_API_KEY` line, ~line 48), add:

```yaml
      REDIS_URL: ${REDIS_URL:-redis://redis:6379/0}
```

In the `backend` service `depends_on` block (after the `postgres-init` condition, ~line 55), add:

```yaml
      redis:
        condition: service_healthy
        restart: true
```

- [ ] **Step 3: Bump uvicorn to 4 workers**

In `backend/Dockerfile`, replace the production CMD on line 29:

```dockerfile
cmd ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]
```

- [ ] **Step 4: Validate the compose file**

Run from repo root: `docker compose config -q`
Expected: no output, exit 0 (compose file is valid).

- [ ] **Step 5: Commit**

```bash
rtk git add docker-compose.yaml backend/Dockerfile
rtk git commit -m "feat(rate-limit): add redis service and run backend with 4 workers"
```

---

### Task 7: End-to-end verification

- [ ] **Step 1: Run the full backend test suite**

Run from `backend/`: `uv run pytest`
Expected: all PASS; Redis-backed tests SKIP if no local Redis (or PASS if `docker run -p 6379:6379 redis:7-alpine` is running and `TEST_REDIS_URL` points at it).

- [ ] **Step 2: Run the Redis tests against a real Redis**

Run: `docker run -d -p 6379:6379 --name rl-redis redis:7-alpine` then `uv run pytest tests/test_redis_rate_limit.py -v`
Expected: all 5 tests PASS (including `test_shared_budget_across_instances`, proving two limiter instances share one budget — the multi-worker guarantee). Tear down: `docker rm -f rl-redis`.

- [ ] **Step 3: Confirm no stray `allow(`/`retry_after(` call sites remain**

Run from `backend/`: `rtk grep -rn "_limiter.allow\|_limiter.retry_after" app/`
Expected: no matches (all production call sites now use `.check()`).

- [ ] **Step 4: Final commit (if anything was adjusted)**

```bash
rtk git add -A
rtk git commit -m "test(rate-limit): verify distributed limiter end-to-end"
```

---

## Self-Review Notes

- **Spec coverage:** interface (Task 2), Redis algorithm + Lua + fail-open (Task 3), not-configured vs unreachable distinction (Tasks 3–4), async call-site ripple (Task 5), config + dependency (Task 1), infra compose + workers (Task 6), all five test scenarios incl. shared-budget and fail-open (Tasks 3, 7). The `redis.call('TIME')` clock decision from the spec is implemented in the Lua script (Task 3).
- **Fail-open** is exercised by `test_fail_open_when_redis_unreachable` (dead port, runs without Redis).
- **In-process fallback** preserved for tests and single-worker/no-`REDIS_URL` deployments.
- **Naming consistency:** `RateLimitResult(allowed, retry_after)`, method `check(key, *, limit, window_s)`, factory `build_limiter`, `close_limiter_client` — used identically across all tasks.
