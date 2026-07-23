import pytest

from app.models import Agency
from app.utils import now


@pytest.mark.asyncio
async def test_stats_reset_at_defaults_to_none(db):
    ag = await Agency.create(name="A", short_name="A", connection_type="API", status="active")
    assert ag.stats_reset_at is None


@pytest.mark.asyncio
async def test_stats_reset_at_persists(db):
    ts = now()
    ag = await Agency.create(
        name="A", short_name="A", connection_type="API", status="active",
        stats_reset_at=ts,
    )
    refreshed = await Agency.get(id=ag.id)
    assert refreshed.stats_reset_at is not None
