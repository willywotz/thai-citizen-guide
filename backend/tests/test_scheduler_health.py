import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app import scheduler
from app.models import Agency, ConnectionLog


@pytest.mark.asyncio
async def test_scheduler_checks_mcp_agency(db):
    scheduler.sem = asyncio.Semaphore(5)
    ag = await Agency.create(name="M", short_name="M", connection_type="MCP", status="active", endpoint_url="https://mcp.example")
    fake = {"success": True, "latency": "120ms", "protocol": "MCP", "version": "1", "steps": []}
    with patch("app.scheduler.test_connection", AsyncMock(return_value=fake)):
        await scheduler.agency_chat_item(ag)
    logs = await ConnectionLog.filter(agency_id=ag.id).count()
    assert logs == 1
    log = await ConnectionLog.filter(agency_id=ag.id).first()
    assert log.connection_type == "MCP"
    assert log.status == "success"
    assert log.latency_ms == 120


@pytest.mark.asyncio
async def test_scheduler_checks_a2a_agency(db):
    scheduler.sem = asyncio.Semaphore(5)
    ag = await Agency.create(name="X", short_name="X", connection_type="A2A", status="active", endpoint_url="https://a2a.example")
    fake = {"success": False, "latency": "0ms", "error": "boom", "steps": []}
    with patch("app.scheduler.test_connection", AsyncMock(return_value=fake)):
        await scheduler.agency_chat_item(ag)
    log = await ConnectionLog.filter(agency_id=ag.id).first()
    assert log.status == "error"


@pytest.mark.asyncio
async def test_scheduler_skips_draft(db):
    scheduler.sem = asyncio.Semaphore(5)
    ag = await Agency.create(name="D", short_name="D", connection_type="MCP", status="draft", endpoint_url="https://x")
    with patch("app.scheduler.test_connection", AsyncMock()) as tc:
        await scheduler.agency_chat_item(ag)
    tc.assert_not_called()
    assert await ConnectionLog.filter(agency_id=ag.id).count() == 0


@pytest.mark.asyncio
async def test_scheduler_skips_disabled(db):
    scheduler.sem = asyncio.Semaphore(5)
    ag = await Agency.create(name="Z", short_name="Z", connection_type="API", status="disabled", endpoint_url="https://x")
    with patch("app.scheduler.test_connection", AsyncMock()) as tc:
        await scheduler.agency_chat_item(ag)
    assert await ConnectionLog.filter(agency_id=ag.id).count() == 0
