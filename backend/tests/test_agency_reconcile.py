import pytest

from app.models import Agency, ConnectionLog
from app.services.agency_reconcile import reconcile_statuses


async def _logs(ag, statuses):
    for s in statuses:
        await ConnectionLog.create(agency=ag, connection_type="API", status=s)


@pytest.mark.asyncio
async def test_active_to_maintenance_when_error_over_50(db):
    ag = await Agency.create(name="A", short_name="A", connection_type="API", status="active")
    await _logs(ag, ["error", "error", "error", "error", "success"])  # 80% error, 5 checks
    await reconcile_statuses()
    refreshed = await Agency.get(id=ag.id)
    assert refreshed.status == "maintenance"
    assert refreshed.auto_maintenance is True


@pytest.mark.asyncio
async def test_no_flip_when_fewer_than_5_checks(db):
    ag = await Agency.create(name="A", short_name="A", connection_type="API", status="active")
    await _logs(ag, ["error", "error", "error", "error"])  # 100% error but only 4 checks
    await reconcile_statuses()
    assert (await Agency.get(id=ag.id)).status == "active"


@pytest.mark.asyncio
async def test_no_flip_at_exactly_50(db):
    ag = await Agency.create(name="A", short_name="A", connection_type="API", status="active")
    await _logs(ag, ["error", "error", "error", "success", "success", "success"])  # 50%, 6 checks
    await reconcile_statuses()
    assert (await Agency.get(id=ag.id)).status == "active"


@pytest.mark.asyncio
async def test_auto_maintenance_back_to_active_when_error_under_50(db):
    ag = await Agency.create(
        name="A", short_name="A", connection_type="API",
        status="maintenance", auto_maintenance=True,
    )
    await _logs(ag, ["success", "success", "success", "success", "error"])  # 20% error, 5 checks
    await reconcile_statuses()
    refreshed = await Agency.get(id=ag.id)
    assert refreshed.status == "active"
    assert refreshed.auto_maintenance is False


@pytest.mark.asyncio
async def test_human_set_maintenance_not_reactivated(db):
    ag = await Agency.create(
        name="A", short_name="A", connection_type="API",
        status="maintenance", auto_maintenance=False,
    )
    await _logs(ag, ["success", "success", "success", "success", "success"])  # 0% error
    await reconcile_statuses()
    assert (await Agency.get(id=ag.id)).status == "maintenance"


@pytest.mark.asyncio
async def test_draft_and_disabled_untouched(db):
    draft = await Agency.create(name="D", short_name="D", connection_type="API", status="draft")
    disabled = await Agency.create(name="Z", short_name="Z", connection_type="API", status="disabled")
    await _logs(draft, ["error"] * 5)
    await _logs(disabled, ["error"] * 5)
    await reconcile_statuses()
    assert (await Agency.get(id=draft.id)).status == "draft"
    assert (await Agency.get(id=disabled.id)).status == "disabled"
