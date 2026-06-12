"""Integration tests verifying that sensitive mutation handlers write AuditLog rows."""

import pytest

from app.models import Agency, AuditLog
from app.models.user import User, UserAPIKey
from app.routers import agencies as agencies_router
from app.routers.api_key import CreateAPIKeyRequest, create_api_key, revoke_api_key
from app.routers import users as users_router
from app.schemas.agency import StatusUpdateRequest
from app.schemas.user import UserCreate


async def _admin(email="admin@audit.com"):
    return await User.create(email=email, hashed_password="x", role="admin", is_active=True)


async def _user(email="target@audit.com"):
    return await User.create(email=email, hashed_password="x", role="user", is_active=True)


@pytest.mark.asyncio
async def test_update_agency_status_writes_audit(db):
    admin = await _admin()
    ag = await Agency.create(
        name="A", short_name="A", connection_type="API", status="draft",
        conformance_report={"passed": True, "checks": []},
    )
    await agencies_router.update_agency_status(ag.id, StatusUpdateRequest(status="active"), user=admin)
    row = await AuditLog.filter(action="agency.status_change").first()
    assert row is not None
    assert row.actor_id == admin.id
    assert row.object_type == "agency"
    assert row.object_id == str(ag.id)
    assert row.detail == {"from": "draft", "to": "active"}


@pytest.mark.asyncio
async def test_revoke_api_key_writes_audit(db):
    user = await User.create(email="keyowner@audit.com", hashed_password="x", role="user", is_active=True)
    created = await create_api_key(CreateAPIKeyRequest(name="mykey"), user=user)
    await revoke_api_key(created.id, user=user)
    row = await AuditLog.filter(action="api_key.revoke").first()
    assert row is not None
    assert row.actor_id == user.id
    assert row.object_type == "api_key"
    assert row.object_id == created.id


@pytest.mark.asyncio
async def test_deactivate_user_writes_audit(db):
    admin = await _admin()
    target = await _user()
    await users_router.deactivate_user(target.id, admin=admin)
    row = await AuditLog.filter(action="user.deactivate").first()
    assert row is not None
    assert row.actor_id == admin.id
    assert row.object_type == "user"
    assert row.object_id == str(target.id)
