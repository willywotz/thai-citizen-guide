# Redis-backed multi-worker rate limiting

**Date:** 2026-06-13
**Status:** Approved, pending implementation

## Problem

The API-key rate limiter (`SlidingWindowLimiter`) is in-process: each uvicorn
worker holds its own `dict[str, deque]` of request timestamps. Running N workers
multiplies a key's effective limit by N — a key configured for 60 rpm gets 240
rpm across 4 workers. The same flaw affects all three limiters built on this
class: `api_key_limiter`, `user_limiter`, and `agency_limiter`.

This spec migrates all three to a shared Redis backend so the budget is enforced
once across every worker.

## Goals

- One rate-limit budget per key, shared across all uvicorn workers.
- Preserve today's true sliding-window semantics (not a weaker fixed window).
- A Redis outage must not take down the API (fail open).
- Keep an in-process path for single-worker / no-Redis / unit-test runs.

## Non-goals

- Changing the configured limits or where `rate_limit_rpm` comes from.
- Distributed coordination beyond rate limiting.
- Per-key analytics (already shipped separately).

## Architecture

### Pluggable limiter behind one async interface

```python
class RateLimitResult(NamedTuple):
    allowed: bool
    retry_after: int

class RateLimiter(Protocol):
    async def check(
        self, key: str, *, limit: int, window_s: float = 60.0
    ) -> RateLimitResult: ...
```

Two implementations:

- **`InProcessLimiter`** — async wrapper over the existing `SlidingWindowLimiter`.
  Used when `REDIS_URL` is unset. Keeps current single-worker behavior and lets
  unit tests run without Redis.
- **`RedisSlidingWindowLimiter`** — sorted-set sliding log executed as a single
  atomic Lua script.

A factory selects the implementation at startup based on `settings.REDIS_URL`.
The three module-level limiters (`api_key_limiter`, `user_limiter`,
`agency_limiter`) are produced by this factory.

**"Not configured" vs "unreachable" are distinct:**

- `REDIS_URL` unset → in-process limiter (enforcement still works per-worker).
- `REDIS_URL` set but Redis errors/times out → **fail open** (allow the request),
  log once.

### Interface becomes async

Redis I/O is async, so `check()` must be awaited. The in-process implementation
is `async def` with no `await` inside. `check()` merges today's separate
`allow()` + `retry_after()` calls into one atomic operation, removing the
existing two-call race.

Call sites affected:

| File | Function | Change |
|------|----------|--------|
| `backend/app/routers/chat.py` | `enforce_user_rate_limit` | becomes `async def`; awaited at its 3 callers (all already async endpoints) |
| `backend/app/auth/dependencies.py` | `_resolve_token` | already async; add `await` |
| `backend/app/services/chat/dispatch.py` | `dispatch_one` | already async; add `await` |

### Redis algorithm — atomic Lua sorted-set log

One Lua script per check, keyed on the rate-limit key:

1. `ZREMRANGEBYSCORE key 0 (now - window)` — drop expired events.
2. `ZCARD key` — count events in window.
3. If count `>= limit` → return `{0, retry_after}` where
   `retry_after = ceil(oldest_score + window - now)`.
4. Else `ZADD key now <unique-member>` + `PEXPIRE key window_ms` →
   return `{1, 0}`.

Details:

- `limit <= 0` short-circuits to allowed (unlimited), matching current behavior.
- Unique member = `"<now_ns>:<incr-counter>"` (or score=now plus a uniqueness
  suffix) so two events at the same timestamp don't collide in the sorted set.
- Atomicity guarantees concurrent workers cannot collectively overshoot `limit`.
- Time source is `redis.call('TIME')` inside the script, so all workers share one
  clock and worker-host clock skew cannot affect the window.

### Connection lifecycle & failure handling

- A single `redis.asyncio.Redis` client + connection pool created in the FastAPI
  lifespan handler; the Lua script registered once via `register_script`.
- Short socket timeout (`REDIS_SOCKET_TIMEOUT_MS`, default ~100ms) so a slow/dead
  Redis can't stall requests.
- `RedisError` / `TimeoutError` / connection failure → log once at WARNING +
  return `RateLimitResult(allowed=True, retry_after=0)` (fail open).

## Configuration

New settings:

- `REDIS_URL` — default empty string → in-process limiter.
- `REDIS_SOCKET_TIMEOUT_MS` — default `100`.

Dependency: add `redis>=5` to `backend/pyproject.toml`.

## Infrastructure

- Add a `redis` service to `docker-compose.yaml`; wire backend `REDIS_URL` to it.
- Bump the uvicorn command in `backend/Dockerfile` to `--workers 4` so the
  multi-worker scenario is actually exercised in container runs.

## Testing (TDD)

- Keep existing in-process unit tests (`tests/test_rate_limit.py`) unchanged.
- New `RedisSlidingWindowLimiter` tests against a **real Redis** (docker-compose
  service / CI), covering:
  - limit enforcement within the window,
  - sliding expiry (events age out),
  - `retry_after` value correctness,
  - unlimited path (`limit <= 0`),
  - **fail open** when the client points at a dead port.
- A **shared-budget** test: two separate limiter instances against the same Redis
  enforce one combined limit (simulates two workers).
- Update the three call-site tests for the async/`await` signature.

## Rollout

1. Ship code + config with `REDIS_URL` unset → behavior identical to today
   (in-process), no functional change.
2. Add the Redis service + set `REDIS_URL` + bump workers → distributed
   enforcement active.
