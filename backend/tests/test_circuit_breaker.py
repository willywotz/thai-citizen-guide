from app.config import settings
from app.models import Agency
from app.services.circuit_breaker import record_dispatch_result


async def test_consecutive_failures_trip_maintenance(db, monkeypatch):
    monkeypatch.setattr(settings, "BREAKER_FAILURE_THRESHOLD", 3)
    ag = await Agency.create(name="A", status="active")

    for _ in range(3):
        await record_dispatch_result(str(ag.id), success=False)

    await ag.refresh_from_db()
    assert ag.status == "maintenance" and ag.auto_maintenance is True


async def test_success_resets_counter(db, monkeypatch):
    monkeypatch.setattr(settings, "BREAKER_FAILURE_THRESHOLD", 3)
    ag = await Agency.create(name="B", status="active")

    await record_dispatch_result(str(ag.id), success=False)
    await record_dispatch_result(str(ag.id), success=True)
    await record_dispatch_result(str(ag.id), success=False)
    await record_dispatch_result(str(ag.id), success=False)

    await ag.refresh_from_db()
    assert ag.status == "active"
