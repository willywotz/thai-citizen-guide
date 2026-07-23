from datetime import timedelta

import pytest

from app.models import Agency, ConnectionLog
from app.services.agency_health import embedded_health, error_window, health_history
from app.utils import now


async def _agency():
    return await Agency.create(name="A", short_name="A", connection_type="API", status="active")


async def _log(agency, status, ago_minutes, latency=300):
    log = await ConnectionLog.create(
        agency=agency, action="test", connection_type="API",
        status=status, latency_ms=latency, detail="",
    )
    log.created_at = now() - timedelta(minutes=ago_minutes)
    await log.save(update_fields=["created_at"])
    return log


@pytest.mark.asyncio
async def test_error_window_counts_all_without_reset(db):
    ag = await _agency()
    for _ in range(4):
        await _log(ag, "error", ago_minutes=180)
    await _log(ag, "success", ago_minutes=10)
    assert await error_window(ag.id) == (5, 4)


@pytest.mark.asyncio
async def test_error_window_ignores_pre_reset(db):
    ag = await _agency()
    for _ in range(4):
        await _log(ag, "error", ago_minutes=180)   # before reset
    await _log(ag, "success", ago_minutes=10)        # after reset
    reset_at = now() - timedelta(hours=1)
    assert await error_window(ag.id, reset_at) == (1, 0)


@pytest.mark.asyncio
async def test_embedded_health_ignores_pre_reset(db):
    ag = await _agency()
    await _log(ag, "error", ago_minutes=180)
    await _log(ag, "success", ago_minutes=5)
    reset_at = now() - timedelta(hours=1)
    h = await embedded_health(ag.id, reset_at)
    assert h["state"] == "up"
    assert h["uptime_24h"] == 100.0


@pytest.mark.asyncio
async def test_health_history_ignores_pre_reset_keeps_grid(db):
    ag = await _agency()
    await _log(ag, "error", ago_minutes=180)
    await _log(ag, "success", ago_minutes=5)
    reset_at = now() - timedelta(hours=1)
    buckets = await health_history(ag.id, "24h", reset_at)
    assert len(buckets) == 24
    assert sum(b["checks"] for b in buckets) == 1
    assert sum(b["failures"] for b in buckets) == 0
