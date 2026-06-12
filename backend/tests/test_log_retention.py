from datetime import timedelta

from app.models import ConnectionLog
from app.scheduler import purge_old_connection_logs
from app.utils import now


async def test_purges_only_logs_older_than_retention(db):
    old = await ConnectionLog.create(connection_type="API", status="success")
    await ConnectionLog.filter(id=old.id).update(created_at=now() - timedelta(days=120))
    fresh = await ConnectionLog.create(connection_type="API", status="success")

    deleted = await purge_old_connection_logs()

    assert deleted == 1
    assert await ConnectionLog.filter(id=old.id).first() is None
    assert await ConnectionLog.filter(id=fresh.id).first() is not None
