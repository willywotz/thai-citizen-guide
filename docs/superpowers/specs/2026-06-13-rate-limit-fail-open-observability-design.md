# Observability for rate-limiter fail-open

**Date:** 2026-06-13
**Status:** Approved, pending implementation

## Problem

`RedisSlidingWindowLimiter.check()` fails open when Redis is unreachable: on
`RedisError`/`OSError` it allows the request and logs a full-traceback WARNING.
Two problems:

1. **Silent enforcement gap.** When Redis is down, the limiter silently stops
   enforcing limits. There is no durable signal that the system is in a
   degraded, non-enforcing state.
2. **Log flood.** The warning fires on *every* request during an outage — under
   load that is thousands of identical tracebacks per minute, which buries the
   signal it is trying to provide.

## Goal

Make the fail-open state visible without standing up new infrastructure, and
stop the log flood. Use the observability that already exists (OpenTelemetry
traces → Jaeger) plus smarter logging.

## Non-goals (YAGNI)

- No `MeterProvider`, OTel metrics, Prometheus, `/metrics` endpoint, or new
  docker-compose services. The backend has **no metrics pipeline** today (traces
  only), so a real counter has nowhere to go. Deferred until a metrics backend
  exists.
- No change to fail-open *semantics* — Redis errors still allow the request.
- No exposing the counter via an HTTP endpoint. It lives in log messages and
  span events for now.

## Existing infrastructure (context)

- OTel **traces only**, exported to Jaeger at `jaeger:4317`
  (`app/main.py:165-182`). `FastAPIInstrumentor` creates a server span per
  request.
- No metrics pipeline, no Prometheus, no `/metrics`.
- Logging is plain `logging.getLogger(__name__)`.
- Current fail-open site: `app/services/rate_limit.py`, the
  `except (RedisError, OSError)` block in `RedisSlidingWindowLimiter.check()`.

## Design

### Component: `RedisHealth` tracker

A module-level object in `rate_limit.py`, shared by all three limiter instances
(`api_key_limiter`, `user_limiter`, `agency_limiter`). They share one Redis
client, so "is Redis reachable?" is a single fact per worker.

```python
class RedisHealth:
    def __init__(self):
        self.failing = False         # currently in fail-open state?
        self.fail_open_total = 0     # cumulative requests that failed open
        self._since = 0              # fail_open_total at the moment we went failing

    def record_failure(self) -> bool:
        """Count a fail-open. Return True only on healthy -> failing transition."""
        self.fail_open_total += 1
        if not self.failing:
            self.failing = True
            self._since = self.fail_open_total - 1
            return True
        return False

    def record_success(self) -> int | None:
        """Note a healthy call. Return #failed-open during the outage on
        failing -> healthy transition, else None."""
        if self.failing:
            self.failing = False
            return self.fail_open_total - self._since
        return None
```

- **What it does:** tracks fail-open state and a cumulative counter; reports
  transitions.
- **Concurrency:** no locking. Within a worker the event loop is
  single-threaded and these are non-`await` read-modify-writes.
- **Depends on:** nothing.

A single module-level instance: `_redis_health = RedisHealth()`.

### Wiring into `RedisSlidingWindowLimiter.check()`

On **fail-open** (existing `except (RedisError, OSError) as exc` block):

```python
except (RedisError, OSError) as exc:
    _redis_health_failure(key, exc)
    return RateLimitResult(True, 0)
```

where the helper:

1. Adds a span event to the active request span (every fail-open request):
   ```python
   trace.get_current_span().add_event(
       "rate_limit.fail_open", {"key": key, "error": type(exc).__name__}
   )
   ```
2. Records the failure and logs **only on transition**:
   ```python
   if _redis_health.record_failure():
       logger.warning(
           "rate limiter: Redis unavailable, failing open — "
           "requests are NOT being rate-limited",
           exc_info=exc,
       )
   ```

On **success** (after the script returns, before returning the result):

```python
recovered = _redis_health.record_success()
if recovered is not None:
    logger.info(
        "rate limiter: Redis recovered after %d request(s) failed open",
        recovered,
    )
return RateLimitResult(bool(allowed), int(retry))
```

`limit <= 0` continues to return early before the `try`, so unlimited keys never
touch health (correct — they do not hit Redis).

### Tracing detail

The span event attaches to the request's existing server span via
`opentelemetry.trace.get_current_span()`. No dedicated limiter span is created.
When there is no active span (e.g. a unit test without a tracer), `add_event` is
a no-op on the non-recording default span — safe.

## Behavior under multiple workers

Each uvicorn worker has its own `_redis_health`. An outage therefore yields ~1
WARNING per worker (on first failure) and ~1 INFO per worker (on recovery),
regardless of request volume or which of the three limiters tripped first — vs.
thousands of warnings today. Per-request fail-open detail across all workers is
still captured as span events in Jaeger.

## Testing (TDD)

- **`RedisHealth` unit tests:** `record_failure()` returns `True` then `False`
  on subsequent calls; `record_success()` returns the failed-open count then
  `None`; `fail_open_total` accumulates across failures.
- **Limiter integration (no real Redis):** construct `RedisSlidingWindowLimiter`
  with a fake client whose `register_script` returns a controllable callable.
  Make the callable raise `RedisError` on the first N calls, then return
  `[1, 0]`. Assert:
  - fail-open returns `RateLimitResult(True, 0)`;
  - exactly **one** WARNING is emitted across repeated failures (via `caplog`);
  - an INFO "recovered" log appears on the first success after failures, with
    the correct count.
- **Span event:** register an OTel SDK `TracerProvider` with
  `InMemorySpanExporter`; start a span; trigger a fail-open; assert a
  `rate_limit.fail_open` event with an `error` attribute was recorded on the
  span.
- **Regression:** the existing `test_fail_open_when_redis_unreachable` (real
  dead port) stays and still passes.

## Rollout

Pure addition; no config or infra change. Behavior with Redis healthy is
unchanged. During an outage: same fail-open behavior, far less log noise, plus
span events and a clear down/recovered signal.
