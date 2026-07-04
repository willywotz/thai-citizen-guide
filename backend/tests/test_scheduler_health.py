import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.mark.asyncio
async def test_health_check_job_reconciles_statuses(db):
    scheduler.sem = asyncio.Semaphore(5)
    with patch("app.scheduler.reconcile_statuses", AsyncMock()) as rec:
        await scheduler.agency_chat_test()
    rec.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_scheduler_uses_spawn_logged(db):
    """start_scheduler must use spawn_logged (not create_task) for fire-and-forget jobs."""
    captured = []

    def fake_spawn(coro, *, name):
        coro.close()  # discard without running
        captured.append(name)
        task = asyncio.ensure_future(asyncio.sleep(0))
        return task

    with (
        patch("app.scheduler.spawn_logged", side_effect=fake_spawn),
        patch("app.scheduler.scheduler") as mock_sched,
    ):
        mock_sched.add_job = MagicMock()
        mock_sched.start = MagicMock()
        await scheduler.start_scheduler()

    assert any("agency_chat_test" in n for n in captured), f"spawn_logged not called for agency_chat_test; got {captured}"
    assert any("regenerate_brief_job" in n for n in captured), f"spawn_logged not called for regenerate_brief_job; got {captured}"


@pytest.mark.asyncio
async def test_agency_chat_item_times_out(db, caplog):
    """A hanging _run_agency_item must be cancelled and an error logged."""
    scheduler.sem = asyncio.Semaphore(5)
    ag = await Agency.create(
        name="Slow", short_name="SL", connection_type="MCP",
        status="active", endpoint_url="https://slow.example",
    )

    async def hang(_agency):
        await asyncio.sleep(9999)

    with (
        patch("app.scheduler._run_agency_item", side_effect=hang),
        patch("app.scheduler.settings") as mock_settings,
        caplog.at_level(logging.ERROR, logger="app.scheduler"),
    ):
        mock_settings.AGENCY_CHAT_TIMEOUT = 0.01  # 10 ms
        await scheduler.agency_chat_item(ag)

    assert any("timed out" in r.getMessage().lower() for r in caplog.records if r.levelno >= logging.ERROR)
