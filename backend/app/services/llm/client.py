import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass

from app.services.rate_limit import build_limiter

KNOWN_PURPOSES = ("classification", "brief", "judge", "parse_spec")
_CACHE_TTL_S = 30.0


@dataclass
class LlmUsageInfo:
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float | None


@dataclass
class LlmResult:
    content: str
    tool_calls: list | None
    usage: LlmUsageInfo
    raw: dict


class LlmError(Exception):
    def __init__(self, message: str, *, status: int | None = None,
                 provider: str | None = None, kind: str | None = None):
        super().__init__(message)
        self.status = status
        self.provider = provider
        self.kind = kind


@dataclass
class _Resolved:
    provider_name: str
    base_url: str
    api_key: str
    auth_header: str
    auth_scheme: str
    timeout: float
    request_usage: bool
    rate_limit_rps: int | None
    rate_limit_rpm: int | None
    max_queue_size: int
    model: str


_cache: dict[str, tuple[_Resolved, float]] = {}


def invalidate() -> None:
    _cache.clear()


async def _resolve(purpose: str) -> _Resolved:
    entry = _cache.get(purpose)
    if entry is not None and time.monotonic() - entry[1] < _CACHE_TTL_S:
        return entry[0]
    from app.models import LlmRoute
    route = await LlmRoute.filter(purpose=purpose, enabled=True).first()
    if route is None:
        raise LlmError(f"no enabled route for purpose {purpose!r}", kind="config")
    provider = await route.provider  # lazy FK load
    if not provider.enabled:
        raise LlmError(f"provider {provider.name!r} is disabled", provider=provider.name, kind="config")
    resolved = _Resolved(
        provider_name=provider.name, base_url=provider.base_url, api_key=provider.api_key,
        auth_header=provider.auth_header, auth_scheme=provider.auth_scheme,
        timeout=route.timeout_override if route.timeout_override is not None else provider.timeout_seconds,
        request_usage=provider.request_usage, rate_limit_rps=provider.rate_limit_rps,
        rate_limit_rpm=provider.rate_limit_rpm, max_queue_size=provider.max_queue_size,
        model=route.model,
    )
    _cache[purpose] = (resolved, time.monotonic())
    return resolved


_provider_limiter = build_limiter()
_queue_waiters: dict[str, int] = defaultdict(int)


async def _acquire(name: str, rps: int | None, rpm: int | None, max_queue_size: int) -> None:
    """Wait for a rate slot (rps then rpm windows). Fail fast when the queue is full.

    rps is acquired before rpm so a denied rpm wastes at most one rps slot (recovers
    within 1s); this never over-admits either window.
    """
    if not rps and not rpm:
        return
    if _queue_waiters[name] >= max_queue_size:
        raise LlmError(f"provider {name!r} rate-limit queue is full", provider=name, kind="queue_full")
    _queue_waiters[name] += 1
    try:
        while True:
            if rps:
                r = await _provider_limiter.check(f"llm:{name}:s", limit=rps, window_s=1.0)
                if not r.allowed:
                    await asyncio.sleep(max(r.retry_after, 0.02))
                    continue
            if rpm:
                r = await _provider_limiter.check(f"llm:{name}:m", limit=rpm, window_s=60.0)
                if not r.allowed:
                    await asyncio.sleep(max(r.retry_after, 0.02))
                    continue
            return
    finally:
        _queue_waiters[name] -= 1
