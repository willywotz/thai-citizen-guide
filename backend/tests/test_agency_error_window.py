import pytest
from datetime import datetime, timedelta, timezone

from app.models import Agency, ConnectionLog
from app.services.agency_health import error_window


@pytest.mark.asyncio
async def test_error_window_counts_checks_and_failures(db):
    ag = await Agency.create(name="A", short_name="A", connection_type="API", status="active")
    for s in ["success", "success", "error", "error", "error"]:
        await ConnectionLog.create(agency=ag, connection_type="API", status=s)
    checks, failures = await error_window(ag.id)
    assert checks == 5
    assert failures == 3


@pytest.mark.asyncio
async def test_error_window_empty_returns_zeros(db):
    ag = await Agency.create(name="B", short_name="B", connection_type="API", status="active")
    assert await error_window(ag.id) == (0, 0)


@pytest.mark.asyncio
async def test_error_window_excludes_old_logs(db):
    ag = await Agency.create(name="C", short_name="C", connection_type="API", status="active")
    # Create a log with created_at set 25 hours ago — should be excluded
    old_time = datetime.now(timezone.utc) - timedelta(hours=25)
    log = await ConnectionLog.create(agency=ag, connection_type="API", status="error")
    await ConnectionLog.filter(id=log.id).update(created_at=old_time)
    checks, failures = await error_window(ag.id)
    assert checks == 0
    assert failures == 0
