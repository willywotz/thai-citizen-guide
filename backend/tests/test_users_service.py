"""Tests for app.services.user — create flow and guardrails."""

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User
from app.schemas.user import UserCreate
from app.services import user as user_service


async def _make_admin(email="admin@example.com", active=True):
    return await User.create(
        email=email, hashed_password="x", role="admin", is_active=active
    )


@pytest.mark.asyncio
async def test_create_with_password_hashes_and_persists(db):
    created = await user_service.create_user(
        UserCreate(email="new@example.com", role="user", password="secret123")
    )
    assert created.id is not None
    assert created.hashed_password != "secret123"


@pytest.mark.asyncio
async def test_create_rejects_short_password(db):
    with pytest.raises(HTTPException) as exc:
        await user_service.create_user(
            UserCreate(email="x@example.com", password="123")
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_create_rejects_duplicate_email(db):
    await _make_admin(email="dup@example.com")
    with pytest.raises(HTTPException) as exc:
        await user_service.create_user(
            UserCreate(email="dup@example.com", password="secret123")
        )
    assert exc.value.status_code == 409


def test_ensure_not_self_blocks_same_id():
    uid = uuid.uuid4()
    with pytest.raises(HTTPException) as exc:
        user_service.ensure_not_self(uid, uid)
    assert exc.value.status_code == 400


def test_ensure_not_self_allows_different_id():
    user_service.ensure_not_self(uuid.uuid4(), uuid.uuid4())  # no raise


@pytest.mark.asyncio
async def test_ensure_not_last_admin_blocks_demoting_only_admin(db):
    admin = await _make_admin()
    with pytest.raises(HTTPException) as exc:
        await user_service.ensure_not_last_admin(admin)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_ensure_not_last_admin_allows_when_another_admin_exists(db):
    admin = await _make_admin()
    await _make_admin(email="admin2@example.com")
    await user_service.ensure_not_last_admin(admin)  # no raise


@pytest.mark.asyncio
async def test_ensure_not_last_admin_ignores_non_admin_target(db):
    await _make_admin()
    plain = await User.create(email="u@example.com", hashed_password="x", role="user")
    await user_service.ensure_not_last_admin(plain)  # no raise
