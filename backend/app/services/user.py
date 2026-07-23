"""
Business logic for admin user management.

Kept separate from the router so guardrails (no self-mutation, protect the last
active admin) and password validation can be unit-tested directly.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status

from app.auth.security import hash_password
from app.config import settings
from app.models.user import User
from app.schemas.user import UserCreate


def hash_new_password(password: str) -> str:
    """Validate a plaintext password and return its bcrypt hash."""
    if len(password) < settings.MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร",
        )
    return hash_password(password)


def ensure_not_self(acting_user_id: uuid.UUID, target_id: uuid.UUID) -> None:
    """An admin may not change their own role, deactivate, or delete themselves."""
    if acting_user_id == target_id:
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


async def create_user(data: UserCreate) -> User:
    """
    Create a user with an admin-set initial password; the user can log in
    immediately.
    """
    hashed = hash_new_password(data.password)

    if await User.filter(email=data.email).exists():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="อีเมลนี้ถูกใช้งานแล้ว")

    return await User.create(
        email=data.email,
        display_name=data.display_name,
        hashed_password=hashed,
        role=data.role,
    )
