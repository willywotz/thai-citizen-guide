"""Auditor has read access to management endpoints; writes stay admin-only."""
import pytest
from fastapi import HTTPException

from app.auth.dependencies import require_admin_or_auditor
from app.models.user import User


@pytest.mark.parametrize("role", ["admin", "auditor"])
async def test_require_admin_or_auditor_allows(db, role):
    u = await User.create(email=f"{role}-ra@x.com", hashed_password="h", role=role)
    assert await require_admin_or_auditor(u) is u


@pytest.mark.parametrize("role", ["user", "viewer", "agency_owner"])
async def test_require_admin_or_auditor_denies(db, role):
    u = await User.create(email=f"{role}-ra@x.com", hashed_password="h", role=role)
    with pytest.raises(HTTPException) as e:
        await require_admin_or_auditor(u)
    assert e.value.status_code == 403


async def test_connection_logs_auditor_sees_all(db):
    # Auditor should see all connection logs (like admin), not be 403'd.
    from app.routers.connection_logs import list_connection_logs
    auditor = await User.create(email="aud-cl@x.com", hashed_password="h", role="auditor")
    resp = await list_connection_logs(search=None, agency_id=None, page=1, limit=20, user=auditor)
    assert resp is not None  # no 403 raised; returns a response model


async def test_connection_logs_plain_user_denied(db):
    from app.routers.connection_logs import list_connection_logs
    plain = await User.create(email="usr-cl@x.com", hashed_password="h", role="user")
    with pytest.raises(HTTPException) as e:
        await list_connection_logs(search=None, agency_id=None, page=1, limit=20, user=plain)
    assert e.value.status_code == 403
