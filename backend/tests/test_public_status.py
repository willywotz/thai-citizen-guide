from app.models import Agency, ConnectionLog
from app.routers.public_status import public_status


async def test_uptime_from_recent_logs_no_internal_fields(db):
    ag = await Agency.create(name="A", status="active")
    for ok in (True, True, True, False):
        await ConnectionLog.create(agency=ag, connection_type="API",
                                   status="success" if ok else "error", action="test")

    rows = await public_status()

    assert rows == [{"name": "A", "status": "active", "uptime_24h_pct": 75.0}]
