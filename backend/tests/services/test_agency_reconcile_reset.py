from datetime import timedelta

import pytest

from app.models import Agency, ConnectionLog
from app.services.agency_reconcile import reconcile_statuses
from app.utils import now


async def _backdated_logs(ag, statuses, ago_minutes):
    for s in statuses:
        log = await ConnectionLog.create(agency=ag, connection_type="API", status=s)
        log.created_at = now() - timedelta(minutes=ago_minutes)
        await log.save(update_fields=["created_at"])


@pytest.mark.asyncio
async def test_reconcile_ignores_pre_reset_failures(db):
    ag = await Agency.create(
        name="A", short_name="A", connection_type="API",
        status="active", stats_reset_at=now() - timedelta(minutes=30),
    )
    # 5 failures all BEFORE the reset baseline -> must be ignored
    await _backdated_logs(ag, ["error"] * 5, ago_minutes=120)
    await reconcile_statuses()
    assert (await Agency.get(id=ag.id)).status == "active"


@pytest.mark.asyncio
async def test_reconcile_still_flips_on_post_reset_failures(db):
    ag = await Agency.create(
        name="A", short_name="A", connection_type="API",
        status="active", stats_reset_at=now() - timedelta(hours=2),
    )
    # 5 failures AFTER the reset baseline -> still trips
    await _backdated_logs(ag, ["error"] * 5, ago_minutes=30)
    await reconcile_statuses()
    refreshed = await Agency.get(id=ag.id)
    assert refreshed.status == "maintenance"
    assert refreshed.auto_maintenance is True
