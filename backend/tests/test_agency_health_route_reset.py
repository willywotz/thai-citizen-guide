from datetime import timedelta

import pytest

from app.models import Agency, ConnectionLog
from app.routers.agencies import lifecycle
from app.utils import now


async def _backdated_log(ag, status, ago_minutes):
    log = await ConnectionLog.create(
        agency=ag, action="test", connection_type="API",
        status=status, latency_ms=100, detail="",
    )
    log.created_at = now() - timedelta(minutes=ago_minutes)
    await log.save(update_fields=["created_at"])


@pytest.mark.asyncio
async def test_health_history_route_honors_reset(db):
    ag = await Agency.create(
        name="A", short_name="A", connection_type="API",
        status="active", stats_reset_at=now() - timedelta(hours=1),
    )
    await _backdated_log(ag, "error", ago_minutes=180)   # before reset
    await _backdated_log(ag, "success", ago_minutes=5)    # after reset
    resp = await lifecycle.agency_health_history(ag.id, "24h")
    assert sum(b.checks for b in resp.data) == 1
    assert sum(b.failures for b in resp.data) == 0
