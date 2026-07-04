# DB-managed LLM Providers & Routes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route all chat-completions LLM calls through one `chat(purpose=...)` client that resolves provider+model from admin-CRUD DB tables, with per-provider rate-limit queueing.

**Architecture:** Two Tortoise tables (`LlmProvider`, `LlmRoute`) drive a centralized `llm_client.chat()` that resolves a route (TTL-cached, invalidated on write), throttles per provider (rps+rpm windows + depth-bounded queue), POSTs, returns a normalized `LlmResult`, and records `LlmUsage`. Admin CRUD routers + frontend pages manage the tables. Callers pass only a `purpose`.

**Tech Stack:** Python, FastAPI, Tortoise ORM, aerich, httpx, pytest; React 18 + Vite + React Query + axios (frontend).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-04-llm-provider-route-management-design.md`.
- Branch: `feat/llm-provider-management` (already checked out).
- Backend cwd: `cd /mnt/c/Users/foo/thai-citizen-guide/backend`. Test runner: `.venv/bin/python -m pytest` (NOT `rtk pytest`). Frontend cwd: `cd /mnt/c/Users/foo/thai-citizen-guide/frontend`.
- TDD: failing test → confirm fail → minimal code → confirm pass → commit. Keep imports sorted. Timezone-aware time via `app.utils.now`.
- Every commit ends with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Admin gating via `Depends(require_admin)` (`app/auth/dependencies.py:209`); read via `require_admin_or_auditor` (`:218`). Audit via `record_audit(user, action, *, object_type, object_id, detail)` (`app/services/audit.py:10`). Secret mask constant `MASK = "*****"` (`app/routers/settings.py:28`).
- Rate limiter reused from `app/services/rate_limit.py`: `build_limiter()` returns an object with `async check(key, *, limit, window_s) -> RateLimitResult(allowed: bool, retry_after: int)`; `limit<=0` ⇒ always allowed.
- KNOWN_PURPOSES = `("classification", "brief", "judge", "parse_spec")`.
- Provider `rate_limit_rps`/`rate_limit_rpm` null/0 = unlimited; `max_queue_size` default 50 (0 = fail-fast). `api_key` stored plaintext (matches settings secret store), masked in API responses.
- After each backend task run the full suite (`.venv/bin/python -m pytest -q`) and confirm green before committing.

---

# PHASE A — Backend

### Task A1: Models + migration

**Files:**
- Create: `backend/app/models/llm_provider.py`, `backend/app/models/llm_route.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/migrations/models/20_20260704000000_llm_providers_routes.py`
- Test: `backend/tests/services/test_llm_models.py`

**Interfaces:**
- Produces: `LlmProvider`, `LlmRoute` models (fields per spec); `LlmRoute.provider` FK RESTRICT.

- [ ] **Step 1: Write the failing test**

`backend/tests/services/test_llm_models.py`:
```python
import pytest

from app.models import LlmProvider, LlmRoute


@pytest.mark.asyncio
async def test_provider_and_route_create_with_fk(db):
    p = await LlmProvider.create(name="openrouter", base_url="https://x/v1/chat/completions",
                                 api_key="k", auth_header="Authorization", auth_scheme="Bearer",
                                 timeout_seconds=60.0, request_usage=True)
    r = await LlmRoute.create(purpose="classification", provider=p, model="m1")
    assert r.purpose == "classification"
    assert (await r.provider).name == "openrouter"
    assert p.max_queue_size == 50 and p.enabled is True
    assert p.rate_limit_rps is None and p.rate_limit_rpm is None


@pytest.mark.asyncio
async def test_purpose_is_unique(db):
    p = await LlmProvider.create(name="p", base_url="u", api_key="k")
    await LlmRoute.create(purpose="brief", provider=p, model="m")
    with pytest.raises(Exception):
        await LlmRoute.create(purpose="brief", provider=p, model="m2")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_llm_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'LlmProvider'`.

- [ ] **Step 3: Create the models**

`backend/app/models/llm_provider.py`:
```python
import uuid

from tortoise import fields
from tortoise.models import Model


class LlmProvider(Model):
    id = fields.UUIDField(primary_key=True, default=uuid.uuid4)
    name = fields.CharField(max_length=50, unique=True)
    base_url = fields.CharField(max_length=500)
    api_key = fields.TextField(default="")
    auth_header = fields.CharField(max_length=100, default="Authorization")
    auth_scheme = fields.CharField(max_length=50, default="Bearer")
    timeout_seconds = fields.FloatField(default=60.0)
    request_usage = fields.BooleanField(default=False)
    rate_limit_rps = fields.IntField(null=True)
    rate_limit_rpm = fields.IntField(null=True)
    max_queue_size = fields.IntField(default=50)
    enabled = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "llm_providers"
```

`backend/app/models/llm_route.py`:
```python
import uuid

from tortoise import fields
from tortoise.models import Model


class LlmRoute(Model):
    id = fields.UUIDField(primary_key=True, default=uuid.uuid4)
    purpose = fields.CharField(max_length=50, unique=True)
    provider = fields.ForeignKeyField(
        "models.LlmProvider", related_name="routes", on_delete=fields.RESTRICT
    )
    model = fields.CharField(max_length=200)
    timeout_override = fields.FloatField(null=True)
    enabled = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "llm_routes"
```

Add to `backend/app/models/__init__.py` (alphabetical-ish, next to other `llm_*`):
```python
from .llm_provider import *
from .llm_route import *
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_llm_models.py -v`
Expected: PASS (SQLite schema built from models).

- [ ] **Step 5: Create the migration**

Try `cd backend && .venv/bin/aerich migrate --name llm_providers_routes`. If it misbehaves (it has in this repo), hand-write `backend/migrations/models/20_20260704000000_llm_providers_routes.py` modeled on `18_20260623154428_agency_add_stats_reset_at.py` (copy its imports, `RUN_IN_TRANSACTION`, and `MODELS_STATE` block verbatim — carry MODELS_STATE forward and note in the commit that it must be regenerated before the next model-changing migration). Bodies:
```python
async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "llm_providers" (
            "id" UUID NOT NULL PRIMARY KEY,
            "name" VARCHAR(50) NOT NULL UNIQUE,
            "base_url" VARCHAR(500) NOT NULL,
            "api_key" TEXT NOT NULL DEFAULT '',
            "auth_header" VARCHAR(100) NOT NULL DEFAULT 'Authorization',
            "auth_scheme" VARCHAR(50) NOT NULL DEFAULT 'Bearer',
            "timeout_seconds" DOUBLE PRECISION NOT NULL DEFAULT 60,
            "request_usage" BOOL NOT NULL DEFAULT False,
            "rate_limit_rps" INT,
            "rate_limit_rpm" INT,
            "max_queue_size" INT NOT NULL DEFAULT 50,
            "enabled" BOOL NOT NULL DEFAULT True,
            "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS "llm_routes" (
            "id" UUID NOT NULL PRIMARY KEY,
            "purpose" VARCHAR(50) NOT NULL UNIQUE,
            "model" VARCHAR(200) NOT NULL,
            "timeout_override" DOUBLE PRECISION,
            "enabled" BOOL NOT NULL DEFAULT True,
            "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "provider_id" UUID NOT NULL REFERENCES "llm_providers" ("id") ON DELETE RESTRICT
        );
        """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "llm_routes";
        DROP TABLE IF EXISTS "llm_providers";
        """
```

- [ ] **Step 6: Full suite + commit**

Run: `cd backend && .venv/bin/python -m pytest -q` → green.
```bash
git add backend/app/models/ backend/migrations/models/20_20260704000000_llm_providers_routes.py backend/tests/services/test_llm_models.py
git commit -m "feat(llm): LlmProvider + LlmRoute models and migration"
```

---

### Task A2: Idempotent seed from env settings

**Files:**
- Create: `backend/app/services/llm/__init__.py` (empty), `backend/app/services/llm/seed.py`
- Modify: `backend/app/database.py` (call seed after schema init)
- Test: `backend/tests/services/test_llm_seed.py`

**Interfaces:**
- Produces: `async def seed_llm_defaults() -> None` — get_or_create providers `openrouter`/`thaillm` + routes `classification`/`brief`/`judge`/`parse_spec`.

- [ ] **Step 1: Write the failing test**

`backend/tests/services/test_llm_seed.py`:
```python
import pytest

from app.models import LlmProvider, LlmRoute
from app.services.llm.seed import seed_llm_defaults


@pytest.mark.asyncio
async def test_seed_creates_defaults_and_is_idempotent(db):
    await seed_llm_defaults()
    assert await LlmProvider.filter(name="openrouter").exists()
    assert await LlmProvider.filter(name="thaillm").exists()
    assert {r.purpose for r in await LlmRoute.all()} == {"classification", "brief", "judge", "parse_spec"}

    # editing then re-seeding must NOT overwrite
    p = await LlmProvider.get(name="openrouter")
    p.base_url = "https://edited"
    await p.save()
    await seed_llm_defaults()
    assert (await LlmProvider.get(name="openrouter")).base_url == "https://edited"
    assert await LlmRoute.all().count() == 4
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_llm_seed.py -v`
Expected: FAIL — module `app.services.llm.seed` missing.

- [ ] **Step 3: Implement seed**

`backend/app/services/llm/seed.py`:
```python
from app.config import settings
from app.models import LlmProvider, LlmRoute


async def seed_llm_defaults() -> None:
    """Insert default providers/routes from env settings. Never overwrites edits."""
    openrouter, _ = await LlmProvider.get_or_create(
        name="openrouter",
        defaults={
            "base_url": settings.OPENROUTER_API_URL,
            "api_key": settings.OPENROUTER_API_KEY,
            "auth_header": "Authorization",
            "auth_scheme": "Bearer",
            "timeout_seconds": float(settings.LLM_CALL_TIMEOUT),
            "request_usage": True,
        },
    )
    thaillm, _ = await LlmProvider.get_or_create(
        name="thaillm",
        defaults={
            "base_url": settings.PARSE_SPEC_URL,
            "api_key": settings.PARSE_SPEC_API_KEY,
            "auth_header": "apikey",
            "auth_scheme": "",
            "timeout_seconds": float(settings.PARSE_SPEC_TIMEOUT),
            "request_usage": False,
        },
    )
    routes = [
        ("classification", openrouter, settings.CLASSIFICATION_MODEL, None),
        ("brief", openrouter, settings.CLASSIFICATION_MODEL, float(settings.WEEKLY_BRIEF_TIMEOUT)),
        ("judge", openrouter, settings.CLASSIFICATION_MODEL, None),
        ("parse_spec", thaillm, settings.PARSE_SPEC_LLM_MODEL, None),
    ]
    for purpose, provider, model, timeout_override in routes:
        await LlmRoute.get_or_create(
            purpose=purpose,
            defaults={"provider": provider, "model": model, "timeout_override": timeout_override},
        )
```

`backend/app/services/llm/__init__.py`: empty file.

In `backend/app/database.py`, call the seed after `generate_schemas`:
```python
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas(safe=True)
    from app.services.llm.seed import seed_llm_defaults
    await seed_llm_defaults()
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_llm_seed.py -v` → PASS.

- [ ] **Step 5: Full suite + commit**

```bash
git add backend/app/services/llm/ backend/app/database.py backend/tests/services/test_llm_seed.py
git commit -m "feat(llm): idempotent seed of default providers and routes"
```

---

### Task A3: Client core — types, resolution, cache

**Files:**
- Create: `backend/app/services/llm/client.py`
- Test: `backend/tests/services/test_llm_client_resolve.py`

**Interfaces:**
- Produces: `LlmUsageInfo`, `LlmResult`, `LlmError(message, *, status=None, provider=None, kind=None)`, `KNOWN_PURPOSES`, `invalidate() -> None`, and `async _resolve(purpose) -> _Resolved` (dataclass with provider fields + model + timeout).

- [ ] **Step 1: Write the failing test**

`backend/tests/services/test_llm_client_resolve.py`:
```python
import pytest

from app.models import LlmProvider, LlmRoute
from app.services.llm import client as c


@pytest.mark.asyncio
async def test_resolve_returns_provider_and_model(db):
    c.invalidate()
    p = await LlmProvider.create(name="openrouter", base_url="u", api_key="k",
                                 auth_header="Authorization", auth_scheme="Bearer",
                                 timeout_seconds=12.0, request_usage=True)
    await LlmRoute.create(purpose="classification", provider=p, model="m1")
    r = await c._resolve("classification")
    assert r.model == "m1" and r.base_url == "u" and r.timeout == 12.0
    assert r.auth_header == "Authorization" and r.request_usage is True


@pytest.mark.asyncio
async def test_resolve_missing_route_raises_config(db):
    c.invalidate()
    with pytest.raises(c.LlmError) as e:
        await c._resolve("nope")
    assert e.value.kind == "config"


@pytest.mark.asyncio
async def test_route_timeout_override_wins(db):
    c.invalidate()
    p = await LlmProvider.create(name="p", base_url="u", api_key="k", timeout_seconds=60.0)
    await LlmRoute.create(purpose="brief", provider=p, model="m", timeout_override=99.0)
    assert (await c._resolve("brief")).timeout == 99.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_llm_client_resolve.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement core + resolution**

`backend/app/services/llm/client.py`:
```python
import time
from dataclasses import dataclass

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
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_llm_client_resolve.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm/client.py backend/tests/services/test_llm_client_resolve.py
git commit -m "feat(llm): client types + DB route resolution with TTL cache"
```

---

### Task A4: Per-provider rate-limit queue

**Files:**
- Modify: `backend/app/services/llm/client.py`
- Test: `backend/tests/services/test_llm_client_queue.py`

**Interfaces:**
- Consumes: `LlmError` (A3).
- Produces: `async _acquire(name, rps, rpm, max_queue_size) -> None` — raises `LlmError(kind="queue_full")` when waiters ≥ max_queue_size; otherwise waits (rps then rpm windows) until a slot is free.

- [ ] **Step 1: Write the failing test**

`backend/tests/services/test_llm_client_queue.py`:
```python
import asyncio
from unittest.mock import AsyncMock

import pytest

from app.services.llm import client as c
from app.services.rate_limit import RateLimitResult


@pytest.mark.asyncio
async def test_acquire_unlimited_returns_immediately():
    await c._acquire("p", None, None, 50)  # no error, no wait


@pytest.mark.asyncio
async def test_acquire_queue_full_raises():
    # pre-fill the waiter counter beyond the bound
    c._queue_waiters["pfull"] = 3
    with pytest.raises(c.LlmError) as e:
        await c._acquire("pfull", 5, 200, 3)
    assert e.value.kind == "queue_full"
    c._queue_waiters["pfull"] = 0


@pytest.mark.asyncio
async def test_acquire_waits_then_proceeds(monkeypatch):
    calls = {"n": 0}

    async def fake_check(key, *, limit, window_s):
        calls["n"] += 1
        # deny the very first rps check, then allow everything
        allowed = not (calls["n"] == 1)
        return RateLimitResult(allowed, 0 if allowed else 1)

    monkeypatch.setattr(c._provider_limiter, "check", fake_check)
    monkeypatch.setattr(c.asyncio, "sleep", AsyncMock())
    await c._acquire("pw", 5, 200, 50)
    assert calls["n"] >= 3  # denied rps, retry rps, then rpm
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_llm_client_queue.py -v`
Expected: FAIL — `_acquire`/`_provider_limiter`/`_queue_waiters` undefined.

- [ ] **Step 3: Implement the queue**

Add to the top of `backend/app/services/llm/client.py` imports:
```python
import asyncio
from collections import defaultdict

from app.services.rate_limit import build_limiter
```
And below the cache definitions:
```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_llm_client_queue.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm/client.py backend/tests/services/test_llm_client_queue.py
git commit -m "feat(llm): per-provider rate-limit queue (rps+rpm, depth-bounded)"
```

---

### Task A5: `chat(purpose=...)` end-to-end + usage recording

**Files:**
- Modify: `backend/app/services/llm/client.py`
- Test: `backend/tests/services/test_llm_client_chat.py`

**Interfaces:**
- Consumes: `_resolve` (A3), `_acquire` (A4), `LlmResult`/`LlmError` (A3), `LlmUsage` model, `usage_context` (`current_user_id`, `current_api_key_id`).
- Produces: `async def chat(*, purpose, messages, tools=None, tool_choice=None, user_id=None, agency_id=None, conversation_id=None) -> LlmResult`.

- [ ] **Step 1: Write the failing test**

`backend/tests/services/test_llm_client_chat.py`:
```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import LlmProvider, LlmRoute, LlmUsage
from app.services.llm import client as c


def _mock_httpx(json_body, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_body
    resp.text = "body"
    client = MagicMock()
    client.post = AsyncMock(return_value=resp)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=cm), client


@pytest.mark.asyncio
async def test_chat_returns_result_and_records_usage(db):
    c.invalidate()
    p = await LlmProvider.create(name="openrouter", base_url="https://api/x", api_key="sk",
                                 auth_header="Authorization", auth_scheme="Bearer", request_usage=True)
    await LlmRoute.create(purpose="classification", provider=p, model="m1")
    body = {"model": "m1", "choices": [{"message": {"content": "hi", "tool_calls": None}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "cost": 0.001}}
    factory, client = _mock_httpx(body)
    with patch.object(c.httpx, "AsyncClient", factory):
        res = await c.chat(purpose="classification", messages=[{"role": "user", "content": "x"}])
    assert res.content == "hi"
    # auth header + usage-include injected
    _, kwargs = client.post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer sk"
    assert kwargs["json"]["usage"] == {"include": True}
    assert await LlmUsage.filter(purpose="classification").count() == 1


@pytest.mark.asyncio
async def test_chat_non_2xx_raises_llmerror(db):
    c.invalidate()
    p = await LlmProvider.create(name="p", base_url="u", api_key="k")
    await LlmRoute.create(purpose="judge", provider=p, model="m")
    factory, _ = _mock_httpx({"error": "x"}, status=500)
    with patch.object(c.httpx, "AsyncClient", factory):
        with pytest.raises(c.LlmError) as e:
            await c.chat(purpose="judge", messages=[])
    assert e.value.status == 500
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_llm_client_chat.py -v`
Expected: FAIL — `chat` not defined.

- [ ] **Step 3: Implement `chat` + usage recording**

Add `import logging`, `import httpx` and to `backend/app/services/llm/client.py`:
```python
logger = logging.getLogger(__name__)


async def chat(*, purpose: str, messages: list[dict], tools: list | None = None,
               tool_choice=None, user_id=None, agency_id=None, conversation_id=None) -> LlmResult:
    r = await _resolve(purpose)
    await _acquire(r.provider_name, r.rate_limit_rps, r.rate_limit_rpm, r.max_queue_size)

    body: dict = {"model": r.model, "messages": messages}
    if tools is not None:
        body["tools"] = tools
    if tool_choice is not None:
        body["tool_choice"] = tool_choice
    if r.request_usage:
        body["usage"] = {"include": True}

    auth_value = f"{r.auth_scheme} {r.api_key}".strip()
    headers = {"Content-Type": "application/json", r.auth_header: auth_value}
    try:
        async with httpx.AsyncClient(timeout=r.timeout) as client:
            resp = await client.post(r.base_url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise LlmError(f"{purpose}: network error: {exc}", provider=r.provider_name, kind="network")
    if resp.status_code != 200:
        raise LlmError(f"{purpose}: provider returned {resp.status_code}",
                       status=resp.status_code, provider=r.provider_name, kind="http")
    data = resp.json()
    msg = (data.get("choices") or [{}])[0].get("message", {})
    usage = data.get("usage") or {}
    info = LlmUsageInfo(
        model=data.get("model") or r.model,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        cost_usd=usage.get("cost"),
    )
    await _record_usage(purpose, info, user_id, agency_id, conversation_id)
    return LlmResult(content=(msg.get("content") or "").strip(),
                     tool_calls=msg.get("tool_calls"), usage=info, raw=data)


async def _record_usage(purpose, info: LlmUsageInfo, user_id, agency_id, conversation_id) -> None:
    from app.models import LlmUsage
    from app.services.usage_context import current_api_key_id, current_user_id
    try:
        await LlmUsage.create(
            model=info.model, purpose=purpose,
            prompt_tokens=info.prompt_tokens, completion_tokens=info.completion_tokens,
            cost_usd=info.cost_usd,
            user_id=user_id if user_id is not None else current_user_id.get(),
            agency_id=agency_id, conversation_id=conversation_id,
            api_key_id=current_api_key_id.get(),
        )
    except Exception:  # accounting must never break the call path
        logger.exception("failed to record llm usage")
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_llm_client_chat.py -v` → PASS.

- [ ] **Step 5: Re-export from the package + commit**

In `backend/app/services/llm/__init__.py`:
```python
from app.services.llm.client import (
    KNOWN_PURPOSES, LlmError, LlmResult, LlmUsageInfo, chat, invalidate,
)
```
```bash
git add backend/app/services/llm/ backend/tests/services/test_llm_client_chat.py
git commit -m "feat(llm): chat(purpose=...) end-to-end with usage recording"
```

---

### Task A6: Migrate callers to `chat(purpose=...)`; remove old client

**Files:**
- Modify: `backend/app/services/chat/llm.py`, `backend/app/services/analytics/brief.py`, `backend/app/services/evaluation.py`, `backend/app/services/agency.py`
- Delete: `backend/app/services/llm_client.py`
- Test: update `backend/tests/services/test_parse_spec_auth.py` + any brief/eval/classify tests to the new client

**Interfaces:**
- Consumes: `chat`, `LlmError` from `app.services.llm`.

- [ ] **Step 1: Update callers**

`chat/llm.py` `classify_message_category` — replace the `payload`+`openrouter_chat` block with:
```python
    from app.services.llm import LlmError, chat
    try:
        res = await chat(purpose="classification", messages=[{"role": "user", "content": content}])
        await Message.filter(id=message_id).update(category=res.content)
    except (LlmError, Exception) as e:
        logger.error("Error classifying message category: %s", e)
```
Remove `from app.services.llm_client import openrouter_chat` and the `settings.CLASSIFICATION_MODEL` payload usage.

`analytics/brief.py` `_generate_brief_content`:
```python
    from app.services.llm import chat
    try:
        res = await chat(purpose="brief", messages=[{"role": "user", "content": prompt}])
        return res.content, "ok"
    except Exception as e:
        logger.error("Error generating weekly brief: %s", e)
        return _BRIEF_FALLBACK, "error"
```
Remove the `openrouter_chat` import.

`evaluation.py` `_judge`:
```python
    from app.services.llm import chat
    res = await chat(purpose="judge", messages=[{"role": "user", "content": prompt}])
    data = json.loads(res.content)
    return float(data["score"]), str(data.get("reason", ""))
```
Remove the `openrouter_chat` import.

`agency.py` `parse_spec` — replace the httpx block (`async with httpx.AsyncClient... resp.raise_for_status()... data = resp.json()... tool_call...`) with:
```python
    from app.services.llm import chat
    res = await chat(purpose="parse_spec", messages=payload["messages"],
                     tools=payload["tools"], tool_choice=payload["tool_choice"])
    tool_call = (res.tool_calls or [{}])[0]
    args_raw = tool_call.get("function", {}).get("arguments")
    if not args_raw:
        raise ValueError("Failed to parse specification")
    return _json.loads(args_raw)
```
(Keep the existing `payload` dict construction above; drop `payload["model"]` — model now comes from the route. Remove the now-unused `settings.PARSE_SPEC_*` references and the `httpx` import if unused.)

- [ ] **Step 2: Delete the old client**

```bash
cd backend && git rm app/services/llm_client.py
```

- [ ] **Step 3: Update tests to the new client**

Update `tests/services/test_parse_spec_auth.py` and any classify/brief/eval tests that patched `openrouter_chat` or `app.services.llm_client` — patch `app.services.llm.chat` (returning an `LlmResult`) instead. Verify each with `-v`.

- [ ] **Step 4: Verify no stragglers**

Run: `cd backend && grep -rn "openrouter_chat\|services.llm_client" app/ tests/`
Expected: empty.

- [ ] **Step 5: Full suite + commit**

Run: `cd backend && .venv/bin/python -m pytest -q` → green.
```bash
git add -A
git commit -m "refactor(llm): route classify/brief/judge/parse_spec through chat(purpose)"
```

---

### Task A7: Config cleanup — drop superseded LLM settings from the UI

**Files:**
- Modify: `backend/app/config.py` (`SETTINGS_GROUPS` only)
- Test: `backend/tests/test_settings_groups.py`

**Interfaces:** none new. Keep the pydantic fields (seed uses them); remove them from `SETTINGS_GROUPS` so admins manage LLM via the new pages.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_settings_groups.py`:
```python
from app.config import SETTINGS_GROUPS


def test_llm_provider_settings_not_editable_via_generic_ui():
    flat = {k for v in SETTINGS_GROUPS.values() for k in v}
    for key in ("OPENROUTER_API_KEY", "OPENROUTER_API_URL", "CLASSIFICATION_MODEL",
                "PARSE_SPEC_URL", "PARSE_SPEC_API_KEY", "PARSE_SPEC_LLM_MODEL"):
        assert key not in flat
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_settings_groups.py -v`
Expected: FAIL (keys still grouped).

- [ ] **Step 3: Edit SETTINGS_GROUPS**

Remove the `"LLM / OpenRouter"` and `"Parse spec"` entries entirely from `SETTINGS_GROUPS` in `backend/app/config.py`. Leave `LLM_CALL_TIMEOUT`/`WEEKLY_BRIEF_TIMEOUT` where they are if grouped elsewhere; do not remove any pydantic field definitions.

- [ ] **Step 4: Run to verify it passes** — `-v` → PASS.

- [ ] **Step 5: Full suite + commit**

```bash
git add backend/app/config.py backend/tests/test_settings_groups.py
git commit -m "chore(llm): remove superseded LLM settings from Settings UI groups"
```

---

### Task A8: Admin CRUD API (providers, routes, purposes)

**Files:**
- Create: `backend/app/schemas/llm_provider.py`, `backend/app/schemas/llm_route.py`
- Create: `backend/app/routers/llm.py`
- Modify: `backend/app/main.py` (register router)
- Test: `backend/tests/routers/test_llm_admin.py`

**Interfaces:**
- Consumes: `LlmProvider`/`LlmRoute` models, `require_admin`/`require_admin_or_auditor`, `record_audit`, `MASK`, `KNOWN_PURPOSES`, `invalidate`.
- Produces: routes under `/api/v1/llm/providers`, `/api/v1/llm/routes`, `GET /api/v1/llm/purposes`.

**Schemas** — `backend/app/schemas/llm_provider.py`: `LLMProviderCreate` (all provider fields; `api_key` optional default ""), `LLMProviderUpdate` (all optional), `LLMProviderResponse` (all fields **except** raw `api_key`; instead `api_key: str` always set to `MASK`). `backend/app/schemas/llm_route.py`: `LLMRouteCreate` (`purpose`, `provider_id: UUID`, `model`, `timeout_override`, `enabled`), `LLMRouteUpdate` (all optional), `LLMRouteResponse` (+ `provider_name`).

**Router behaviors** (mirror `app/routers/agencies/crud.py` + secret handling from `settings.py`):
- List/get/create/patch/delete for providers and routes; `Depends(require_admin)` on mutations, `require_admin_or_auditor` on reads.
- Provider response masks `api_key`; on update, `if body.api_key in (None, MASK): don't change it`.
- Route create/update: 404 if `provider_id` unknown; 409 on duplicate `purpose`.
- Provider delete: if any `LlmRoute` references it → 409 `{"detail": "provider in use by routes"}`.
- Every mutation: `await record_audit(user, "llm_provider.create"/... , object_type="llm_provider"/"llm_route", object_id=obj.id)` then `from app.services.llm import invalidate; invalidate()`.
- `GET /llm/purposes` → `{"data": list(KNOWN_PURPOSES)}`.
- Register in `app/main.py`: `from app.routers import llm as llm_router` then `app.include_router(llm_router.router, prefix="/api/v1")`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/routers/test_llm_admin.py` — cover: create provider returns masked key; list masks key; update with `api_key=MASK` keeps stored key; create route ok; duplicate purpose → 409; delete provider in use → 409; non-admin → 403; `GET /llm/purposes` returns the four purposes; a mutation calls `invalidate`. (Use the app/TestClient pattern from `tests/test_chat_schema.py` + an admin user fixture as in existing router tests; patch `app.routers.llm.invalidate` with a MagicMock to assert it's called.)

- [ ] **Step 2: Run to verify they fail** — module/endpoints missing.

- [ ] **Step 3: Implement schemas + router + registration** (per behaviors above; mirror `agencies/crud.py` structure and `settings.py` masking).

- [ ] **Step 4: Run the new tests** `-v` → PASS.

- [ ] **Step 5: Full suite + commit**

```bash
git add backend/app/schemas/llm_provider.py backend/app/schemas/llm_route.py backend/app/routers/llm.py backend/app/main.py backend/tests/routers/test_llm_admin.py
git commit -m "feat(llm): admin CRUD API for providers, routes, and purposes"
```

---

# PHASE B — Frontend

Mirror `frontend/src/features/api-keys/` (page + api module + Create/Edit/Delete dialogs), React Query + axios via `@/shared/lib/apiClient`. Endpoints from Phase A.

### Task B1: API modules + types

**Files:**
- Create: `frontend/src/features/llm-providers/llmProviderApi.ts`, `frontend/src/features/llm-routes/llmRouteApi.ts`

Complete code — providers module:
```ts
import { api } from "@/shared/lib/apiClient";

export interface LlmProvider {
  id: string; name: string; base_url: string; api_key: string;
  auth_header: string; auth_scheme: string; timeout_seconds: number;
  request_usage: boolean; rate_limit_rps: number | null; rate_limit_rpm: number | null;
  max_queue_size: number; enabled: boolean;
}
export type LlmProviderInput = Omit<LlmProvider, "id">;

export const listProviders = () => api.get<{ data: LlmProvider[]; total: number }>("/api/v1/llm/providers");
export const createProvider = (b: LlmProviderInput) => api.post<LlmProvider>("/api/v1/llm/providers", b);
export const updateProvider = (id: string, b: Partial<LlmProviderInput>) => api.patch<LlmProvider>(`/api/v1/llm/providers/${id}`, b);
export const deleteProvider = (id: string) => api.delete(`/api/v1/llm/providers/${id}`);
```
routes module (`llmRouteApi.ts`): `LlmRoute { id, purpose, provider_id, provider_name, model, timeout_override, enabled }`; `listRoutes`, `createRoute`, `updateRoute`, `deleteRoute` against `/api/v1/llm/routes`; `listPurposes = () => api.get<{data:string[]}>("/api/v1/llm/purposes")`.

- [ ] Create both files. Run `cd frontend && npx tsc --noEmit` (expect no new errors). Commit:
```bash
git add frontend/src/features/llm-providers/llmProviderApi.ts frontend/src/features/llm-routes/llmRouteApi.ts
git commit -m "feat(llm-ui): provider/route api modules"
```

### Task B2: Providers admin page + dialogs

**Files:** Create `frontend/src/features/llm-providers/LlmProvidersPage.tsx` + `LlmProviderList.tsx`, `CreateLlmProviderDialog.tsx`, `EditLlmProviderDialog.tsx`, `DeleteLlmProviderDialog.tsx` — mirror the corresponding `features/api-keys/*` files. Form fields: name, base_url, api_key (password input; blank = unchanged on edit), auth_header, auth_scheme, timeout_seconds, request_usage (switch), rate_limit_rps, rate_limit_rpm, max_queue_size, enabled (switch). `useQuery(["llm-providers"], listProviders)`; mutations invalidate `["llm-providers"]` + toast. Hide create/edit for `useAuth().isReadOnly`.

- [ ] Build the page + dialogs mirroring api-keys. Verify `npx tsc --noEmit` and (if the project has a component test harness) a render test per existing conventions. Commit `feat(llm-ui): providers admin page`.

### Task B3: Routes admin page + dialogs

**Files:** Create `frontend/src/features/llm-routes/LlmRoutesPage.tsx` + List/Create/Edit/Delete dialogs, mirroring api-keys. Create form: `purpose` (select populated from `listPurposes`), `provider_id` (select from `listProviders`), `model`, `timeout_override`, `enabled`. Edit: same minus purpose (immutable) — or allow. Invalidate `["llm-routes"]`.

- [ ] Build mirroring api-keys. Verify `npx tsc --noEmit`. Commit `feat(llm-ui): routes admin page`.

### Task B4: Register routes, roles, and nav

**Files:**
- Modify: `frontend/src/App.tsx` (lazy import + admin `ProtectedRoute` routes `/llm-providers`, `/llm-routes`)
- Modify: `frontend/src/features/auth/roles.ts` (`ROUTE_ROLES`: `"/llm-providers": ["admin"]`, `"/llm-routes": ["admin"]`)
- Modify: `frontend/src/shared/components/layout/AppSidebar.tsx` (nav items with `lucide-react` icons)

- [ ] Add the three registrations mirroring the existing `/settings` admin route + sidebar entries. Verify `npx tsc --noEmit` and that the app builds (`npm run build` or the project's check). Commit:
```bash
git add frontend/src/App.tsx frontend/src/features/auth/roles.ts frontend/src/shared/components/layout/AppSidebar.tsx
git commit -m "feat(llm-ui): register providers/routes admin pages in nav + routes"
```

---

## Final verification

- [ ] `cd backend && grep -rn "openrouter_chat\|services.llm_client" app/ tests/` → empty.
- [ ] `cd backend && .venv/bin/python -m pytest -q` → green.
- [ ] `cd frontend && npx tsc --noEmit` → no new errors; app builds.
- [ ] Manual/e2e: `docker compose up` on a fresh DB seeds providers+routes, backend boots, and the four call sites work through `chat(purpose=...)`.
- [ ] Admin can add/edit a provider (incl. rps/rpm/max_queue_size) and remap a purpose in the UI; change takes effect after cache TTL / invalidation.
