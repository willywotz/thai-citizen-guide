# Rate-Limiter Fail-Open Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the rate limiter's Redis fail-open state visible (span events + a clear down/recovered log signal + an in-process counter) and stop the per-request log flood, without adding any new infrastructure.

**Architecture:** Add a module-level `RedisHealth` tracker to `rate_limit.py`, shared by all three limiters. In `RedisSlidingWindowLimiter.check()`, the fail-open path records a failure (logging only on the healthy→failing transition) and adds a `rate_limit.fail_open` event to the active request span; the success path detects recovery and logs once. Pure addition — fail-open semantics are unchanged.

**Tech Stack:** Python 3.12, `redis.asyncio`, OpenTelemetry traces (already wired to Jaeger), pytest + pytest-asyncio (`asyncio_mode = auto`).

**Spec:** `docs/superpowers/specs/2026-06-13-rate-limit-fail-open-observability-design.md`

**Run commands from `backend/`.** Test runner: `uv run pytest`.

---

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `backend/app/services/rate_limit.py` | Add `RedisHealth` + `_redis_health` singleton; wire failure/recovery/span-event into `RedisSlidingWindowLimiter.check()`; add `from opentelemetry import trace` import | Modify |
| `backend/tests/test_redis_health.py` | Unit tests for `RedisHealth` state machine | Create |
| `backend/tests/test_fail_open_observability.py` | Integration tests: transition logging, recovery logging, span event — using a fake script client (no real Redis) | Create |

The existing `backend/tests/test_redis_rate_limit.py::test_fail_open_when_redis_unreachable` stays unchanged and must keep passing.

---

### Task 1: `RedisHealth` state tracker

A tiny state machine that counts fail-open events and reports transitions. No Redis, no async — pure unit-testable logic.

**Files:**
- Modify: `backend/app/services/rate_limit.py`
- Test: `backend/tests/test_redis_health.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_redis_health.py`:

```python
from app.services.rate_limit import RedisHealth


def test_first_failure_is_a_transition_then_not():
    h = RedisHealth()
    assert h.record_failure() is True   # healthy -> failing
    assert h.record_failure() is False  # already failing
    assert h.record_failure() is False


def test_success_while_healthy_returns_none():
    h = RedisHealth()
    assert h.record_success() is None


def test_recovery_returns_failed_open_count():
    h = RedisHealth()
    h.record_failure()
    h.record_failure()
    h.record_failure()
    assert h.record_success() == 3      # 3 requests failed open during outage
    assert h.record_success() is None   # already healthy again


def test_counter_accumulates_across_outages():
    h = RedisHealth()
    h.record_failure()
    h.record_success()
    h.record_failure()
    h.record_success()
    assert h.fail_open_total == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_redis_health.py -v`
Expected: FAIL — `ImportError: cannot import name 'RedisHealth'`

- [ ] **Step 3: Implement `RedisHealth`**

In `backend/app/services/rate_limit.py`, add this class immediately **before** the `class RedisSlidingWindowLimiter:` line:

```python
class RedisHealth:
    """Tracks the rate limiter's Redis fail-open state for one worker.

    Single-threaded per worker (asyncio event loop, no await between the
    read-modify-writes here), so no locking is needed.
    """

    def __init__(self):
        self.failing = False
        self.fail_open_total = 0
        self._since = 0

    def record_failure(self) -> bool:
        """Count a fail-open. Return True only on a healthy -> failing change."""
        self.fail_open_total += 1
        if not self.failing:
            self.failing = True
            self._since = self.fail_open_total - 1
            return True
        return False

    def record_success(self) -> int | None:
        """Note a healthy call. On failing -> healthy, return how many requests
        failed open during the outage; otherwise None."""
        if self.failing:
            self.failing = False
            return self.fail_open_total - self._since
        return None


_redis_health = RedisHealth()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_redis_health.py -v`
Expected: PASS — all 4 tests green.

- [ ] **Step 5: Commit**

```bash
rtk git add app/services/rate_limit.py tests/test_redis_health.py
rtk git commit -m "feat(rate-limit): add RedisHealth fail-open state tracker"
```

---

### Task 2: Wire health tracking + recovery logging into `check()`

Convert the fail-open path to use `_redis_health` (log only on transition) and add recovery logging on the success path. Span event is added in Task 3 — this task is the logging/state half so it can be tested independently.

**Files:**
- Modify: `backend/app/services/rate_limit.py` (the `check()` method, currently lines 99-115)
- Test: `backend/tests/test_fail_open_observability.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_fail_open_observability.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_fail_open_observability.py -v`
Expected: FAIL — `test_fail_open_returns_allowed_and_logs_once` sees 3 warnings (current code logs every failure), and `test_recovery_logs_with_count` finds 0 recovery logs (no recovery logging yet).

- [ ] **Step 3: Rewrite the `check()` body**

In `backend/app/services/rate_limit.py`, replace the current `check()` method of `RedisSlidingWindowLimiter` (lines 99-115) with:

```python
    async def check(
        self, key: str, *, limit: int, window_s: float = 60.0
    ) -> RateLimitResult:
        if limit <= 0:
            return RateLimitResult(True, 0)
        window_us = int(window_s * 1_000_000)
        member = uuid.uuid4().hex
        try:
            # The script returns {allowed, retry_after}; retry_after is always
            # >= 1 when blocked (the oldest in-window event expires in the future).
            allowed, retry = await self._script(
                keys=[f"rl:{key}"], args=[limit, window_us, member]
            )
        except (RedisError, OSError) as exc:  # connection/timeout — fail open
            if _redis_health.record_failure():
                logger.warning(
                    "rate limiter: Redis unavailable, failing open — "
                    "requests are NOT being rate-limited",
                    exc_info=exc,
                )
            return RateLimitResult(True, 0)
        recovered = _redis_health.record_success()
        if recovered is not None:
            logger.info(
                "rate limiter: Redis recovered after %d request(s) failed open",
                recovered,
            )
        return RateLimitResult(bool(allowed), int(retry))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_fail_open_observability.py -v`
Expected: PASS — both tests green (one warning on the outage; one recovery info with the count).

- [ ] **Step 5: Run the Redis regression test (real Redis or dead-port)**

Run: `uv run pytest tests/test_redis_rate_limit.py::test_fail_open_when_redis_unreachable -v`
Expected: PASS (still fails open and returns allowed). This test needs no live Redis.

- [ ] **Step 6: Commit**

```bash
rtk git add app/services/rate_limit.py tests/test_fail_open_observability.py
rtk git commit -m "feat(rate-limit): log fail-open on transition, log on recovery"
```

---

### Task 3: Add the `rate_limit.fail_open` span event

Attach a span event to the active request span on every fail-open, so per-request detail is visible in Jaeger across all workers.

**Files:**
- Modify: `backend/app/services/rate_limit.py` (import + the fail-open block in `check()`)
- Test: `backend/tests/test_fail_open_observability.py` (add a span-event test)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_fail_open_observability.py`:

```python
def test_fail_open_adds_span_event():
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")

    import asyncio

    lim = RedisSlidingWindowLimiter(FakeClient(FakeScript(fail_n=1)))
    with tracer.start_as_current_span("request"):
        # asyncio.run copies the current context (incl. the active span) into
        # the task, so get_current_span() inside check() sees this span.
        asyncio.run(lim.check("k", limit=5))

    spans = exporter.get_finished_spans()
    events = [e for s in spans for e in s.events]
    assert any(e.name == "rate_limit.fail_open" for e in events)
    fail_event = next(e for e in events if e.name == "rate_limit.fail_open")
    assert fail_event.attributes["error"] == "ConnectionError"
    assert fail_event.attributes["key"] == "k"
```

Note: this test is synchronous (no `async def`) on purpose — it drives the span context manager itself and runs the coroutine inside it, because the span must be current on the same context as the awaited `check()`. Reset of `_redis_health` is handled by the existing autouse fixture.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_fail_open_observability.py::test_fail_open_adds_span_event -v`
Expected: FAIL — no `rate_limit.fail_open` event is recorded (span event not implemented yet); `assert any(...)` fails.

- [ ] **Step 3: Add the import and the span event**

In `backend/app/services/rate_limit.py`, add to the imports (after `from redis.exceptions import RedisError`, keeping the third-party group together):

```python
from opentelemetry import trace
```

Then in `check()`, inside the `except (RedisError, OSError) as exc:` block, add the span event as the **first** line of the block (before `record_failure`):

```python
        except (RedisError, OSError) as exc:  # connection/timeout — fail open
            trace.get_current_span().add_event(
                "rate_limit.fail_open", {"key": key, "error": type(exc).__name__}
            )
            if _redis_health.record_failure():
                logger.warning(
                    "rate limiter: Redis unavailable, failing open — "
                    "requests are NOT being rate-limited",
                    exc_info=exc,
                )
            return RateLimitResult(True, 0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_fail_open_observability.py -v`
Expected: PASS — all tests in the file, including the span-event test.

- [ ] **Step 5: Commit**

```bash
rtk git add app/services/rate_limit.py tests/test_fail_open_observability.py
rtk git commit -m "feat(rate-limit): emit rate_limit.fail_open span event"
```

---

### Task 4: Full-suite verification

- [ ] **Step 1: Run the whole backend suite**

Run from `backend/`: `uv run pytest -q`
Expected: all PASS (Redis-backed tests in `test_redis_rate_limit.py` SKIP if no local Redis, or PASS with one running). No failures.

- [ ] **Step 2: Confirm no leftover per-request flood**

Run: `rtk grep -n "logger.warning" app/services/rate_limit.py`
Expected: exactly one match — the transition-guarded warning inside `if _redis_health.record_failure():`. There must be no unconditional warning on the fail-open path.

- [ ] **Step 3: Commit (only if anything was adjusted)**

```bash
rtk git add -A
rtk git commit -m "test(rate-limit): verify fail-open observability end-to-end"
```

---

## Self-Review Notes

- **Spec coverage:** `RedisHealth` tracker + shared singleton (Task 1); span event on every fail-open via `get_current_span()` (Task 3); transition-only WARNING + recovery INFO with count (Task 2); `limit <= 0` still short-circuits before the try (unchanged in the Task 2/3 rewrite); regression test preserved (Task 2 Step 5, Task 4). Multi-worker behavior is a property of the per-worker singleton — no code beyond Task 1.
- **No new infra:** no MeterProvider/Prometheus/endpoint — matches the spec's non-goals.
- **Naming consistency:** `RedisHealth`, `record_failure() -> bool`, `record_success() -> int | None`, `fail_open_total`, module singleton `_redis_health`, span event name `rate_limit.fail_open` with attributes `key`/`error` — used identically across tasks.
- **Test isolation:** `_redis_health` is a module singleton, so `test_fail_open_observability.py` resets it via an autouse fixture before each test.
