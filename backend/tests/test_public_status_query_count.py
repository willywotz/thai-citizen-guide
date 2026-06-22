"""Query-count characterization for public_status N+1 fix."""
import pytest

from app.models import Agency, ConnectionLog
from app.routers.public_status import public_status


@pytest.mark.usefixtures("db")
async def test_uptime_values_preserved():
    ag = await Agency.create(name="A", status="active")
    for ok in (True, True, True, False):
        await ConnectionLog.create(agency=ag, connection_type="API",
                                   status="success" if ok else "error", action="test")
    rows = await public_status()
    assert rows == [{"name": "A", "status": "active", "uptime_24h_pct": 75.0}]


@pytest.mark.usefixtures("db")
async def test_query_count_is_constant_not_per_agency(monkeypatch):
    for i in range(5):
        ag = await Agency.create(name=f"A{i}", status="active")
        await ConnectionLog.create(agency=ag, connection_type="API", status="success", action="test")

    from tortoise import Tortoise
    conn = Tortoise.get_connection("default")
    calls = {"n": 0}
    orig = conn.execute_query_dict

    async def counting(*a, **k):
        calls["n"] += 1
        return await orig(*a, **k)

    monkeypatch.setattr(conn, "execute_query_dict", counting)
    await public_status()
    assert calls["n"] <= 2   # NOT 2*N
