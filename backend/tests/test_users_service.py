"""Tests for app.services.user — create flow and guardrails."""

import uuid
from unittest.mock import AsyncMock, patch

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
    created, extra = await user_service.create_user(
        UserCreate(email="new@example.com", role="user", password="secret123")
    )
    assert created.id is not None
    assert created.hashed_password != "secret123"
    assert extra == {}


@pytest.mark.asyncio
async def test_create_with_invite_issues_token_and_emails(db):
    with patch.object(user_service, "send_password_reset_email", AsyncMock(return_value=True)):
        created, extra = await user_service.create_user(
            UserCreate(email="inv@example.com", role="user", send_invite=True)
        )
    assert created.reset_token is not None
    assert extra["email_sent"] is True
    assert "reset_token" not in extra


@pytest.mark.asyncio
async def test_create_invite_email_fails_exposes_token_when_flag_on(db):
    from app.config import settings

    with patch.object(settings, "EXPOSE_PASSWORD_RESET_TOKEN", True), \
         patch.object(user_service, "send_password_reset_email", AsyncMock(return_value=False)):
        _created, extra = await user_service.create_user(
            UserCreate(email="inv2@example.com", send_invite=True)
        )
    assert extra["email_sent"] is False
    assert extra["reset_token"]


@pytest.mark.asyncio
async def test_create_rejects_both_password_and_invite(db):
    with pytest.raises(HTTPException) as exc:
        await user_service.create_user(
            UserCreate(email="x@example.com", password="secret123", send_invite=True)
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_create_rejects_neither_password_nor_invite(db):
    with pytest.raises(HTTPException) as exc:
        await user_service.create_user(UserCreate(email="x@example.com"))
    assert exc.value.status_code == 400


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
