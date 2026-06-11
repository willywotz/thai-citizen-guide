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
    await _log(ag, status="error", ago_minutes=1)
    h = await embedded_health(ag.id)
    assert h["state"] == "down"


@pytest.mark.asyncio
async def test_embedded_health_degraded(db):
    ag = await _agency()
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
