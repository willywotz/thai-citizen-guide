"""Non-admin callers must be denied by both connection-logs handlers.

Deleting either `if not user.is_admin: raise HTTPException(403)` guard leaves
the rest of the suite green, so this pins the deny path directly.
"""
import pytest
from fastapi import HTTPException

from app.models.user import User
from app.routers.connection_logs import get_connection_log_info, list_connection_logs


async def _list_connection_logs(user: User):
    # Query(...) defaults only resolve through FastAPI's dependency injection,
    # so a direct call must supply plain values in their place.
    return await list_connection_logs(
        search=None, agency_id=None, status_filter=None, connection_type=None,
        page=1, limit=20, page_size=None, user=user,
    )


async def test_non_admin_denied_list_connection_logs(db):
    user = await User.create(email="cl-user@x.com", hashed_password="h", role="user")
    with pytest.raises(HTTPException) as exc:
        await _list_connection_logs(user)
    assert exc.value.status_code == 403


async def test_admin_allowed_list_connection_logs(db):
    admin = await User.create(email="cl-admin@x.com", hashed_password="h", role="admin")
    result = await _list_connection_logs(admin)
    assert result.total_items == 0


async def test_non_admin_denied_connection_log_info(db):
    user = await User.create(email="cl-user2@x.com", hashed_password="h", role="user")
    with pytest.raises(HTTPException) as exc:
        await get_connection_log_info(user=user)
    assert exc.value.status_code == 403


async def test_admin_allowed_connection_log_info(db):
    admin = await User.create(email="cl-admin2@x.com", hashed_password="h", role="admin")
    result = await get_connection_log_info(user=admin)
    assert result.total_connections == 0
