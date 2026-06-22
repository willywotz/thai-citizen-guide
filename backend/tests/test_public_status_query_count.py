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
    calls = {"n": 0}
    real_get_connection = Tortoise.get_connection

    def patched_get_connection(name: str):
        conn = real_get_connection(name)
        orig = conn.__class__.execute_query_dict

        async def counting(self, *a, **k):
            calls["n"] += 1
            return await orig(self, *a, **k)

        monkeypatch.setattr(conn.__class__, "execute_query_dict", counting)
        monkeypatch.setattr(Tortoise, "get_connection", real_get_connection)
        return conn

    monkeypatch.setattr(Tortoise, "get_connection", patched_get_connection)
    await public_status()
    assert calls["n"] <= 2   # NOT 2*N
