# Agency Management Redesign — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. TDD, checkbox steps.

**Goal:** Implement the backend half of the agency contract the frontend MSW layer defines — new fields, embedded health + history, status/discovery endpoints, all-protocol health checks, and router integration.

**Architecture:** FastAPI + Tortoise ORM + Aerich migrations. Health is aggregated from the existing `ConnectionLog` table (no new table). Reuse `app/services/agency.py::test_connection` for MCP/A2A health checks and `app/mcp/client.py` for discovery. Spec: `docs/superpowers/specs/2026-06-11-agency-management-redesign-backend-design.md`.

**Conventions:**
- Work dir `/mnt/c/Users/foo/thai-citizen-guide/backend`. Branch `feat/agency-backend-contract`.
- Run tests: `.venv/bin/python -m pytest tests/<file> -q`. Full: `.venv/bin/python -m pytest tests/ -q`.
- Format: `gofmt` N/A (Python). Lint not enforced in CI here, but keep imports sorted and code clean.
- Tests use the in-memory SQLite `db` fixture (`tests/conftest.py`). **Avoid Postgres-only SQL** (`TO_CHAR`, `SET TIME ZONE`, `RawSQL` date funcs) in new code that tests exercise — use Tortoise ORM aggregation (`Count`, `Avg`, `Sum`, `Case/When`) so it runs on SQLite.
- Wire format is snake_case and must match the frontend's `mapRowToAgency`/`mapBucketRow`.
- Prefix shell commands with `rtk`.
- The `AgencyStatus` enum already includes draft/active/maintenance/disabled/inactive (shipped in the prior fix).

---

### Task 1: Lifecycle transition service

**Files:** Create `app/services/agency_lifecycle.py`; Test `tests/services/test_agency_lifecycle.py`.

- [ ] **Step 1: failing test** — `tests/services/test_agency_lifecycle.py`:
```python
from app.services.agency_lifecycle import LEGAL_TRANSITIONS, is_legal_transition


def test_legal_transition_matrix():
    assert LEGAL_TRANSITIONS["draft"] == ["active", "disabled"]
    assert LEGAL_TRANSITIONS["active"] == ["maintenance", "disabled"]
    assert LEGAL_TRANSITIONS["maintenance"] == ["active", "disabled"]
    assert LEGAL_TRANSITIONS["disabled"] == ["active"]


def test_is_legal_transition():
    assert is_legal_transition("draft", "active") is True
    assert is_legal_transition("disabled", "maintenance") is False
    assert is_legal_transition("active", "draft") is False
```
- [ ] **Step 2:** `.venv/bin/python -m pytest tests/services/test_agency_lifecycle.py -q` → FAIL.
- [ ] **Step 3: implement** `app/services/agency_lifecycle.py`:
```python
"""Agency lifecycle transition rules — mirrors the frontend lifecycle.ts table."""

LEGAL_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["active", "disabled"],
    "active": ["maintenance", "disabled"],
    "maintenance": ["active", "disabled"],
    "disabled": ["active"],
}


def is_legal_transition(current: str, target: str) -> bool:
    return target in LEGAL_TRANSITIONS.get(current, [])
```
- [ ] **Step 4:** rerun → PASS.
- [ ] **Step 5: commit** `feat(agencies): add backend lifecycle transition rules`.

---

### Task 2: Model fields + Aerich migration

**Files:** Modify `app/models/agency.py`; Create `migrations/models/4_<ts>_agency_routing_fields.py`.

- [ ] **Step 1:** Add to the `Agency` model (after `api_headers`, before `# Metrics`):
```python
    # Routing controls
    priority = fields.IntField(null=True)
    router_hint = fields.TextField(default="")
    dispatch_timeout_s = fields.IntField(null=True)
    mcp_tool_name = fields.CharField(max_length=255, null=True)
```
- [ ] **Step 2:** Write the migration manually (don't rely on `aerich migrate` in this env). Create `migrations/models/4_20260611000000_agency_routing_fields.py` mirroring the existing migration format (see `migrations/models/2_*.py`):
```python
from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "agencies" ADD "priority" INT;
        ALTER TABLE "agencies" ADD "router_hint" TEXT NOT NULL DEFAULT '';
        ALTER TABLE "agencies" ADD "dispatch_timeout_s" INT;
        ALTER TABLE "agencies" ADD "mcp_tool_name" VARCHAR(255);
        UPDATE "agencies" SET "status" = 'disabled' WHERE "status" = 'inactive';
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        UPDATE "agencies" SET "status" = 'inactive' WHERE "status" = 'disabled';
        ALTER TABLE "agencies" DROP COLUMN "mcp_tool_name";
        ALTER TABLE "agencies" DROP COLUMN "dispatch_timeout_s";
        ALTER TABLE "agencies" DROP COLUMN "router_hint";
        ALTER TABLE "agencies" DROP COLUMN "priority";
    """
```
Match the exact header/structure of an existing migration file (copy `RUN_IN_TRANSACTION`/`MODELS_STATE` boilerplate if present in siblings; read `migrations/models/2_*.py` and `3_*.py` first and replicate their top-of-file format). If the sibling migrations carry a `MODELS_STATE` blob, you cannot hand-author it reliably — in that case omit it and keep just the `upgrade`/`downgrade` SQL functions, which Aerich executes; note this in the report.
- [ ] **Step 3:** Verify the model imports cleanly and tests (SQLite `generate_schemas` builds from the model, not the migration): `.venv/bin/python -c "from app.models import Agency; print('ok')"`.
- [ ] **Step 4: commit** `feat(agencies): add routing columns + migration; normalize inactive→disabled`.

Note: the SQLite test DB uses `generate_schemas()` from the model, so tests see the new columns immediately. The migration is for the real Postgres DB.

---

### Task 3: Schemas

**Files:** Modify `app/schemas/agency.py`; Test `tests/test_agency_schemas.py`.

- [ ] **Step 1: failing test** — `tests/test_agency_schemas.py`:
```python
from app.schemas.agency import (
    AgencyCreate,
    AgencyHealthEmbed,
    HealthHistoryBucket,
    McpDiscoverRequest,
    StatusUpdateRequest,
)


def test_agency_create_accepts_routing_fields():
    body = AgencyCreate(
        name="x", priority=2, router_hint="ภาษี",
        dispatch_timeout_s=30, mcp_tool_name="chat",
    )
    assert body.priority == 2
    assert body.router_hint == "ภาษี"
    assert body.dispatch_timeout_s == 30
    assert body.mcp_tool_name == "chat"


def test_health_embed_shape():
    h = AgencyHealthEmbed(state="up", uptime_24h=99.2, avg_latency_ms_24h=320, last_check_at=None)
    assert h.state == "up"


def test_status_update_and_discover_request():
    assert StatusUpdateRequest(status="active").status == "active"
    assert McpDiscoverRequest(endpoint_url="https://x").endpoint_url == "https://x"


def test_history_bucket_fields():
    b = HealthHistoryBucket(bucket_start="2026-06-11T00:00:00Z", uptime_pct=99.0, avg_latency_ms=300, checks=12, failures=0)
    assert b.checks == 12
```
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: implement.** In `app/schemas/agency.py`:
  - Add to `AgencyBase` (so create/replace accept them): `priority: int | None = None`, `router_hint: str = ""`, `dispatch_timeout_s: int | None = None`, `mcp_tool_name: str | None = None`.
  - Add the same four (all `| None = None`) to `AgencyUpdate`.
  - Add new schemas:
```python
class AgencyHealthEmbed(BaseModel):
    state: str  # up | degraded | down | unknown
    uptime_24h: float | None = None
    avg_latency_ms_24h: int | None = None
    last_check_at: datetime | None = None


class HealthHistoryBucket(BaseModel):
    bucket_start: datetime
    uptime_pct: float
    avg_latency_ms: int
    checks: int
    failures: int


class HealthHistoryResponse(BaseModel):
    data: list[HealthHistoryBucket]


class StatusUpdateRequest(BaseModel):
    status: str


class McpDiscoverRequest(BaseModel):
    endpoint_url: str


class McpToolInfo(BaseModel):
    name: str
    description: str = ""
    input_schema: dict[str, Any] = {}


class McpDiscoverResponse(BaseModel):
    tools: list[McpToolInfo]
```
  - Add to `AgencyResponse`: `rating_up: int = 0`, `rating_down: int = 0`, `priority: int | None = None`, `router_hint: str = ""`, `dispatch_timeout_s: int | None = None`, `mcp_tool_name: str | None = None`, `health: AgencyHealthEmbed | None = None`.
    (`model_config = ConfigDict(from_attributes=True)` is already there; `health` is injected manually since it isn't a model attribute.)
- [ ] **Step 4:** run → PASS.
- [ ] **Step 5: commit** `feat(agencies): extend schemas with routing fields, health, status/discover`.

---

### Task 4: Agency health aggregation service (SQLite-portable)

**Files:** Create `app/services/agency_health.py`; Test `tests/services/test_agency_health.py`.

- [ ] **Step 1: failing test** — seed ConnectionLog rows and assert. `tests/services/test_agency_health.py`:
```python
from datetime import timedelta

import pytest

from app.models import Agency, ConnectionLog
from app.services.agency_health import embedded_health, health_history
from app.utils import now


async def _agency(status="active"):
    return await Agency.create(name="A", short_name="A", connection_type="API", status=status)


async def _log(agency, status="success", latency=300, ago_minutes=10):
    log = await ConnectionLog.create(
        agency=agency, action="test", connection_type="API",
        status=status, latency_ms=latency, detail="",
    )
    # created_at is auto_now_add; override for windowing
    log.created_at = now() - timedelta(minutes=ago_minutes)
    await log.save(update_fields=["created_at"])
    return log


@pytest.mark.asyncio
async def test_embedded_health_unknown_when_no_logs(db):
    ag = await _agency()
    h = await embedded_health(ag.id)
    assert h["state"] == "unknown"
    assert h["uptime_24h"] is None
    assert h["last_check_at"] is None


@pytest.mark.asyncio
async def test_embedded_health_up(db):
    ag = await _agency()
    for _ in range(10):
        await _log(ag, status="success", latency=300)
    h = await embedded_health(ag.id)
    assert h["state"] == "up"
    assert h["uptime_24h"] == 100.0
    assert h["avg_latency_ms_24h"] == 300


@pytest.mark.asyncio
async def test_embedded_health_down_when_last_failed(db):
    ag = await _agency()
    await _log(ag, status="success", ago_minutes=60)
    await _log(ag, status="error", ago_minutes=1)  # most recent
    h = await embedded_health(ag.id)
    assert h["state"] == "down"


@pytest.mark.asyncio
async def test_embedded_health_degraded(db):
    ag = await _agency()
    # 8 ok + 2 fail over 24h = 80% uptime, last is ok
    await _log(ag, status="error", ago_minutes=120)
    await _log(ag, status="error", ago_minutes=110)
    for i in range(8):
        await _log(ag, status="success", ago_minutes=10 + i)
    h = await embedded_health(ag.id)
    assert h["state"] == "degraded"
    assert h["uptime_24h"] == 80.0


@pytest.mark.asyncio
async def test_health_history_bucket_counts(db):
    ag = await _agency()
    await _log(ag, status="success", ago_minutes=30)
    buckets = await health_history(ag.id, "24h")
    assert len(buckets) == 24
    assert {"bucket_start", "uptime_pct", "avg_latency_ms", "checks", "failures"} <= set(buckets[0].keys())
    buckets7 = await health_history(ag.id, "7d")
    assert len(buckets7) == 7 * 24
    buckets30 = await health_history(ag.id, "30d")
    assert len(buckets30) == 30
```
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: implement** `app/services/agency_health.py`. Use the Tortoise ORM (portable to SQLite) — fetch the agency's logs in the window with `.values("status","latency_ms","created_at")` and aggregate in Python (simplest + portable). Build buckets in Python by flooring timestamps to the bucket size.
```python
"""Per-agency health aggregated from ConnectionLog, in the frontend contract shape."""
from datetime import datetime, timedelta
from uuid import UUID

from app.config import settings
from app.models import ConnectionLog
from app.utils import now

_WINDOW = {
    "24h": (24, timedelta(hours=1)),
    "7d": (7 * 24, timedelta(hours=1)),
    "30d": (30, timedelta(days=1)),
}


async def _rows(agency_id: UUID, since: datetime):
    return await ConnectionLog.filter(
        agency_id=agency_id, created_at__gte=since
    ).order_by("created_at").values("status", "latency_ms", "created_at")


async def embedded_health(agency_id: UUID) -> dict:
    since = now() - timedelta(hours=24)
    rows = await _rows(agency_id, since)
    if not rows:
        return {"state": "unknown", "uptime_24h": None, "avg_latency_ms_24h": None, "last_check_at": None}
    total = len(rows)
    failures = sum(1 for r in rows if r["status"] != "success")
    uptime = round((total - failures) / total * 100, 1)
    avg_latency = round(sum(r["latency_ms"] for r in rows) / total)
    last = rows[-1]  # ordered ascending by created_at
    if last["status"] != "success":
        state = "down"
    elif uptime < settings.HEALTH_DEGRADED_UPTIME_PCT:
        state = "degraded"
    else:
        state = "up"
    return {
        "state": state,
        "uptime_24h": uptime,
        "avg_latency_ms_24h": avg_latency,
        "last_check_at": last["created_at"],
    }


async def health_history(agency_id: UUID, window: str) -> list[dict]:
    count, step = _WINDOW.get(window, _WINDOW["24h"])
    end = now()
    start = end - count * step
    rows = await _rows(agency_id, start)
    # Pre-create empty buckets oldest→newest.
    buckets = []
    for i in range(count):
        b_start = start + i * step
        buckets.append({
            "bucket_start": b_start, "_end": b_start + step,
            "uptime_pct": 100.0, "avg_latency_ms": 0, "checks": 0, "failures": 0,
            "_latency_sum": 0,
        })
    for r in rows:
        ts = r["created_at"]
        idx = int((ts - start) / step)
        if 0 <= idx < count:
            b = buckets[idx]
            b["checks"] += 1
            b["_latency_sum"] += r["latency_ms"]
            if r["status"] != "success":
                b["failures"] += 1
    for b in buckets:
        if b["checks"]:
            b["uptime_pct"] = round((b["checks"] - b["failures"]) / b["checks"] * 100, 1)
            b["avg_latency_ms"] = round(b["_latency_sum"] / b["checks"])
        del b["_end"]
        del b["_latency_sum"]
    return buckets
```
Add `HEALTH_DEGRADED_UPTIME_PCT: float = 95.0` to `app/config.py` (in the agency-health section).
- [ ] **Step 4:** run → PASS (5 tests).
- [ ] **Step 5: commit** `feat(agencies): add ConnectionLog-based health aggregation service`.

---

### Task 5: Wire health + new fields into list/get/create/update

**Files:** Modify `app/routers/agencies.py`; Test `tests/test_agencies_health_wiring.py`.

- [ ] **Step 1: failing test** — `tests/test_agencies_health_wiring.py`:
```python
import pytest

from app.models import Agency, ConnectionLog
from app.routers import agencies as r
from app.schemas.agency import AgencyCreate
from app.models.user import User


async def _admin():
    return await User.create(email="a@e.com", hashed_password="x", role="admin", is_active=True)


@pytest.mark.asyncio
async def test_create_persists_routing_fields_and_get_returns_health(db):
    admin = await _admin()
    created = await r.create_agency(
        body=AgencyCreate(name="RD", short_name="RD", connection_type="API",
                          status="active", priority=1, router_hint="ภาษี",
                          dispatch_timeout_s=30, mcp_tool_name=None),
        _=admin,
    )
    assert created.priority == 1
    assert created.router_hint == "ภาษี"
    got = await r.get_agency(created.id)
    assert got.health is not None
    assert got.health.state == "unknown"  # no logs yet
```
- [ ] **Step 2:** run → FAIL (get_agency returns no health / create drops fields).
- [ ] **Step 3: implement.** READ `app/routers/agencies.py`.
  - `create_agency`/`replace_agency`: `body.model_dump()` now includes the 4 new fields (they're on `AgencyBase`), so `Agency.create(**data)` persists them automatically — verify no manual field list excludes them.
  - In `get_agency`, `list_agencies`, `create_agency`, `replace_agency`, `update_agency` responses: after building the `AgencyResponse`, attach health. Add a helper:
```python
from app.services.agency_health import embedded_health
from app.schemas.agency import AgencyHealthEmbed

async def _with_health(agency) -> AgencyResponse:
    resp = AgencyResponse.model_validate(agency)
    resp.health = AgencyHealthEmbed(**(await embedded_health(agency.id)))
    return resp
```
  Use `_with_health` for single-agency responses. For `list_agencies`, map each agency through it (await in a loop or `asyncio.gather`). Keep pagination/filtering intact.
  - Confirm `AgencyResponse` now carries `rating_up`/`rating_down` from the model via `from_attributes`.
- [ ] **Step 4:** run → PASS. Also run the existing agencies tests + `test_agencies_router.py` to confirm no regression.
- [ ] **Step 5: commit** `feat(agencies): embed health and persist routing fields in CRUD responses`.

---

### Task 6: Health history endpoint

**Files:** Modify `app/routers/agencies.py`; Test add to `tests/test_agencies_health_wiring.py` (or new file).

- [ ] **Step 1: failing test:**
```python
@pytest.mark.asyncio
async def test_health_history_endpoint(db):
    ag = await Agency.create(name="A", short_name="A", connection_type="API", status="active")
    await ConnectionLog.create(agency=ag, action="test", connection_type="API", status="success", latency_ms=200, detail="")
    res = await r.agency_health_history(ag.id, window="24h")
    assert len(res.data) == 24
    assert res.data[0].checks >= 0
```
(Add the import for `agency_health_history` once implemented.)
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: implement** in `app/routers/agencies.py`:
```python
@router.get("/{agency_id}/health/history", response_model=HealthHistoryResponse, summary="Agency health history")
async def agency_health_history(agency_id: uuid.UUID, window: str = "24h"):
    try:
        await Agency.get(id=agency_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    buckets = await health_history(agency_id, window)
    return HealthHistoryResponse(data=[HealthHistoryBucket(**b) for b in buckets])
```
Import `health_history`, `HealthHistoryResponse`, `HealthHistoryBucket`. **Place this route BEFORE `/{agency_id}`** is not required (path is more specific), but ensure it's registered. No auth (matches GET list/get which are public).
- [ ] **Step 4:** run → PASS.
- [ ] **Step 5: commit** `feat(agencies): add health history endpoint`.

---

### Task 7: Status transition endpoint

**Files:** Modify `app/routers/agencies.py`; Test `tests/test_agency_status_endpoint.py`.

- [ ] **Step 1: failing test:**
```python
import pytest
from fastapi import HTTPException
from app.models import Agency
from app.models.user import User
from app.routers import agencies as r
from app.schemas.agency import StatusUpdateRequest


async def _admin():
    return await User.create(email="a@e.com", hashed_password="x", role="admin", is_active=True)


@pytest.mark.asyncio
async def test_status_legal_transition(db):
    admin = await _admin()
    ag = await Agency.create(name="A", short_name="A", connection_type="API", status="active")
    res = await r.update_agency_status(ag.id, StatusUpdateRequest(status="maintenance"), _=admin)
    assert res.status == "maintenance"


@pytest.mark.asyncio
async def test_status_illegal_transition_422(db):
    admin = await _admin()
    ag = await Agency.create(name="A", short_name="A", connection_type="API", status="active")
    with pytest.raises(HTTPException) as exc:
        await r.update_agency_status(ag.id, StatusUpdateRequest(status="draft"), _=admin)
    assert exc.value.status_code == 422
    assert "transition" in exc.value.detail.lower()
```
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: implement:**
```python
@router.patch("/{agency_id}/status", response_model=AgencyResponse, summary="Transition agency lifecycle status")
async def update_agency_status(agency_id: uuid.UUID, body: StatusUpdateRequest, _: User = Depends(require_admin)):
    try:
        agency = await Agency.get(id=agency_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    if not is_legal_transition(str(agency.status), body.status):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Illegal status transition: {agency.status} → {body.status}",
        )
    agency.status = body.status
    await agency.save(update_fields=["status", "updated_at"])
    return await _with_health(agency)
```
Import `is_legal_transition`, `StatusUpdateRequest`.
- [ ] **Step 4:** run → PASS.
- [ ] **Step 5: commit** `feat(agencies): add lifecycle status transition endpoint`.

---

### Task 8: MCP discovery service + endpoint

**Files:** Create `app/services/mcp_discovery.py`; Modify `app/routers/agencies.py`; Test `tests/services/test_mcp_discovery.py` + endpoint test.

- [ ] **Step 1: failing test** (mock the fastmcp client) — `tests/services/test_mcp_discovery.py`:
```python
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.mcp_discovery import discover_tools


@pytest.mark.asyncio
async def test_discover_tools_maps_fastmcp_tools():
    tool = SimpleNamespace(name="chat_with_fda", description="ask", inputSchema={"type": "object"})
    fake_client = AsyncMock()
    fake_client.__aenter__.return_value = fake_client
    fake_client.list_tools.return_value = [tool]
    with patch("app.services.mcp_discovery.Client", return_value=fake_client):
        tools = await discover_tools("https://mcp.example/sse")
    assert tools[0]["name"] == "chat_with_fda"
    assert tools[0]["input_schema"] == {"type": "object"}
```
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: implement** `app/services/mcp_discovery.py`:
```python
"""Discover tools exposed by an MCP endpoint via fastmcp."""
from typing import Any

from fastmcp import Client


def _schema(tool: Any) -> dict:
    return getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {}


async def discover_tools(endpoint_url: str) -> list[dict]:
    async with Client(endpoint_url) as client:
        tools = await client.list_tools()
    return [
        {
            "name": getattr(t, "name", "") if not isinstance(t, dict) else t.get("name", ""),
            "description": (getattr(t, "description", "") if not isinstance(t, dict) else t.get("description", "")) or "",
            "input_schema": _schema(t) if not isinstance(t, dict) else (t.get("inputSchema") or t.get("input_schema") or {}),
        }
        for t in tools
    ]
```
(Confirm the import path matches `app/mcp/client.py`'s `from fastmcp import Client`.)
- [ ] **Step 4:** Add endpoint test to a router test file:
```python
@pytest.mark.asyncio
async def test_mcp_discover_requires_endpoint_url(db):
    admin = await _admin()
    with pytest.raises(HTTPException) as exc:
        await r.mcp_discover(McpDiscoverRequest(endpoint_url=""), _=admin)
    assert exc.value.status_code == 422
```
- [ ] **Step 5: implement endpoint** in `app/routers/agencies.py`:
```python
@router.post("/mcp/discover", response_model=McpDiscoverResponse, summary="Discover MCP tools at an endpoint")
async def mcp_discover(body: McpDiscoverRequest, _: User = Depends(require_admin)):
    if not body.endpoint_url.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="endpoint_url is required")
    try:
        tools = await discover_tools(body.endpoint_url)
    except Exception as exc:  # noqa: BLE001 — surface any MCP/connection failure to the client
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"MCP discovery failed: {exc}")
    return McpDiscoverResponse(tools=[McpToolInfo(**t) for t in tools])
```
**Route ordering:** register `/mcp/discover` BEFORE `/{agency_id}` so "mcp" isn't captured as an agency_id. Verify in the file.
Import `discover_tools`, `McpDiscoverRequest`, `McpDiscoverResponse`, `McpToolInfo`.
- [ ] **Step 6:** run both test files → PASS.
- [ ] **Step 7: commit** `feat(agencies): add MCP tool discovery service + endpoint`.

---

### Task 9: Scheduler health-checks MCP + A2A

**Files:** Modify `app/scheduler.py`; Test `tests/test_scheduler_health.py`.

- [ ] **Step 1: failing test** (mock `test_connection`) — `tests/test_scheduler_health.py`:
```python
from unittest.mock import AsyncMock, patch

import pytest

from app import scheduler
from app.models import Agency, ConnectionLog


@pytest.mark.asyncio
async def test_scheduler_checks_mcp_agency(db):
    scheduler.sem = __import__("asyncio").Semaphore(5)
    ag = await Agency.create(name="M", short_name="M", connection_type="MCP", status="active", endpoint_url="https://mcp.example")
    fake = {"success": True, "latency": "120ms", "protocol": "MCP", "version": "1", "steps": []}
    with patch("app.scheduler.test_connection", AsyncMock(return_value=fake)):
        await scheduler.agency_chat_item(ag)
    logs = await ConnectionLog.filter(agency_id=ag.id).count()
    assert logs == 1


@pytest.mark.asyncio
async def test_scheduler_skips_draft(db):
    scheduler.sem = __import__("asyncio").Semaphore(5)
    ag = await Agency.create(name="D", short_name="D", connection_type="MCP", status="draft", endpoint_url="https://x")
    with patch("app.scheduler.test_connection", AsyncMock()) as tc:
        await scheduler.agency_chat_item(ag)
    tc.assert_not_called()
```
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: implement.** READ `app/scheduler.py`. Modify `agency_chat_item`:
  - At the top of the `async with sem:` block, skip non-checkable agencies: `if agency.status in ("draft", "disabled"): return`.
  - Keep the existing API real-query branch.
  - Add an `elif agency.connection_type in ("MCP", "A2A"):` branch that calls `test_connection(agency.connection_type, agency)`, parses its `latency` ("120ms" → int), and writes a `ConnectionLog` (action="test", connection_type=agency.connection_type, status="success" if result["success"] else "error", latency_ms, detail).
  - Import `from app.services.agency import test_connection`. Parse latency with `int(result["latency"].rstrip("ms"))` guarded by try/except → 0.
  Example branch:
```python
            elif agency.connection_type in ("MCP", "A2A"):
                result = await test_connection(agency.connection_type, agency)
                try:
                    latency = int(str(result.get("latency", "0")).rstrip("ms"))
                except ValueError:
                    latency = 0
                await ConnectionLog.create(
                    id=str(generate_uuid()), agency=agency, action="test",
                    connection_type=agency.connection_type,
                    status="success" if result.get("success") else "error",
                    latency_ms=latency, detail=result.get("error", "") or "ok",
                )
```
  - Keep the outer `try/except` that logs errors.
- [ ] **Step 4:** run → PASS. Confirm existing scheduler behavior (API) still intact by reading the diff.
- [ ] **Step 5: commit** `feat(agencies): health-check MCP and A2A agencies in scheduler`.

---

### Task 10: Router integration (router_hint, priority, per-agency timeout)

**Files:** Modify `app/services/chat/llm.py`, `app/services/chat/graph.py`, `app/services/chat/dispatch.py`; Test `tests/services/test_router_integration.py`.

- [ ] **Step 1: failing test:**
```python
from app.services.chat.llm import build_router_prompt


def test_router_prompt_includes_router_hint():
    agencies = [{
        "id": "1", "name": "RD", "connection_type": "API",
        "endpoint_url": "https://x", "description": "tax",
        "data_scope": ["ภาษี"], "router_hint": "คำถามภาษีนำเข้า",
    }]
    prompt = build_router_prompt(agencies)
    assert "คำถามภาษีนำเข้า" in prompt
```
Plus a graph sort test (if `route_query` is unit-testable) OR assert dispatch timeout selection. For dispatch, add `tests/services/test_dispatch_timeout.py`:
```python
from app.services.chat.dispatch import _dispatch_timeout  # add this small helper


def test_dispatch_timeout_prefers_per_agency():
    assert _dispatch_timeout({"dispatch_timeout_s": 45}) == 45


def test_dispatch_timeout_falls_back_to_global():
    from app.config import settings
    assert _dispatch_timeout({"dispatch_timeout_s": None}) == settings.AGENCY_CHAT_TIMEOUT
```
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: implement:**
  - `llm.py::build_router_prompt`: when `ag.get("router_hint")` is non-empty, append ` — คำแนะนำ routing: {router_hint}` to that agency's source line.
  - `graph.py::route_query`: in the `Agency.filter(status="active").values()` call, ensure `router_hint`, `priority`, `dispatch_timeout_s` are in the selected values (`.values()` with no args returns all columns — confirm; if it lists explicit columns, add them). In the route-enrichment loop, also copy `priority` and `dispatch_timeout_s` onto each route. After building `routes`, sort by priority (None last): `routes.sort(key=lambda r: (r.get("priority") is None, r.get("priority") or 0))`.
  - `dispatch.py`: add a module-level helper `_dispatch_timeout(route) -> int` returning `route.get("dispatch_timeout_s") or settings.AGENCY_CHAT_TIMEOUT`. Use it in `dispatch_api` (and `dispatch_a2a` if appropriate) for the `httpx.AsyncClient(timeout=...)`.
- [ ] **Step 4:** run → PASS. Run the full chat-graph test file to confirm no regression.
- [ ] **Step 5: commit** `feat(agencies): feed router_hint, priority, and per-agency timeout into routing`.

---

### Task 11: Final verification

- [ ] `cd backend && .venv/bin/python -m pytest tests/ -q` — all green.
- [ ] `.venv/bin/python -c "from app.main import app; print('ok')"` — imports.
- [ ] Spot-check the contract field names against `frontend/src/mocks/handlers.ts` (snake_case: health.uptime_24h, bucket_start, input_schema, etc.).
- [ ] Commit any final fixes.

## Out of scope
- Frontend (sub-project 1, separate branch). The existing camelCase `get_agency_health`/insights page is left unchanged.
