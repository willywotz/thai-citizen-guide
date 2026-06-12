"""Pydantic schemas for admin user-management endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr

from app.models.user import User

Role = Literal["user", "admin", "agency_owner"]


class UserCreate(BaseModel):
    email: EmailStr
    role: Role = "user"
    display_name: str | None = None
    password: str | None = None
    send_invite: bool = False


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: Role | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    displayName: str
    role: Role
    avatarUrl: str | None = None
    isActive: bool
    createdAt: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(
            id=str(user.id),
            email=user.email,
            displayName=user.display_name or user.email.split("@")[0],
            role=user.role,
            avatarUrl=user.avatar_url,
            isActive=user.is_active,
            createdAt=user.created_at,
        )


class UserCreateResponse(BaseModel):
    user: UserResponse
    email_sent: bool | None = None
    reset_token: str | None = None


class UserListResponse(BaseModel):
    data: list[UserResponse]
    total: int
