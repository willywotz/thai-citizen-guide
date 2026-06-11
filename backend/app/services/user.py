"""
Business logic for admin user management.

Kept separate from the router so guardrails (no self-mutation, protect the last
active admin) and the dual create/invite flow can be unit-tested directly.
"""

from __future__ import annotations

import secrets
import uuid

from fastapi import HTTPException, status

from app.auth.security import (
    generate_reset_token,
    hash_password,
    reset_token_expiry,
)
from app.config import settings
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.email import send_password_reset_email


def ensure_not_self(acting_user_id: uuid.UUID, target_id: uuid.UUID) -> None:
    """An admin may not change their own role, deactivate, or delete themselves."""
    if str(acting_user_id) == str(target_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ไม่สามารถดำเนินการกับบัญชีของตนเองได้",
        )


async def ensure_not_last_admin(target: User) -> None:
    """Reject an action that would leave the system with zero active admins."""
    if target.role != "admin" or not target.is_active:
        return
    others = await User.filter(role="admin", is_active=True).exclude(id=target.id).count()
    if others == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ต้องมีผู้ดูแลระบบที่ใช้งานได้อย่างน้อยหนึ่งคน",
        )


async def create_user(data: UserCreate) -> tuple[User, dict]:
    """
    Create a user via one of two mutually-exclusive modes:
      * password — admin sets an initial password; user can log in immediately.
      * send_invite — generate a reset token and email it; account starts with
        an unusable random password.
    Returns the created user plus any extra response fields (invite metadata).
    """
    has_password = bool(data.password)
    if has_password == data.send_invite:  # both set or neither set
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ต้องระบุรหัสผ่าน หรือเลือกส่งคำเชิญทางอีเมล อย่างใดอย่างหนึ่ง",
        )

    if has_password and len(data.password) < settings.MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร",
        )

    if await User.filter(email=data.email).exists():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="อีเมลนี้ถูกใช้งานแล้ว")

    hashed = hash_password(data.password if has_password else secrets.token_urlsafe(32))
    user = await User.create(
        email=data.email,
        display_name=data.display_name,
        hashed_password=hashed,
        role=data.role,
    )

    extra: dict = {}
    if data.send_invite:
        token = generate_reset_token()
        user.reset_token = token
        user.reset_token_expires = reset_token_expiry()
        await user.save(update_fields=["reset_token", "reset_token_expires"])
        emailed = await send_password_reset_email(user.email, token)
        extra["email_sent"] = emailed
        if not emailed and settings.EXPOSE_PASSWORD_RESET_TOKEN:
            extra["reset_token"] = token

    return user, extra
