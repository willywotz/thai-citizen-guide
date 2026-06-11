"""
Admin user-management routes. Every endpoint requires an authenticated admin.

Endpoints
---------
  GET    /users                 List/search users (filters: search, role, status)
  POST   /users                 Create a user (password OR email invite)
  GET    /users/{id}            Get a single user
  PATCH  /users/{id}            Update display_name and/or role
  POST   /users/{id}/deactivate Soft-delete: set is_active=False
  POST   /users/{id}/activate   Set is_active=True
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from tortoise.exceptions import DoesNotExist
from tortoise.expressions import Q

from app.auth.dependencies import require_admin
from app.models.user import User
from app.schemas.user import UserCreate, UserListResponse, UserResponse, UserUpdate
from app.services import user as user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=UserListResponse, summary="List users")
async def list_users(
    search: str | None = Query(None, description="Search email or display name"),
    role: str | None = Query(None, description="Filter by role: user | admin"),
    status_filter: Literal["active", "inactive", "all"] = Query(
        "all", alias="status", description="Filter by active status"
    ),
    admin: User = Depends(require_admin),
) -> UserListResponse:
    qs = User.all()
    if search:
        qs = qs.filter(Q(email__icontains=search) | Q(display_name__icontains=search))
    if role:
        qs = qs.filter(role=role)
    if status_filter == "active":
        qs = qs.filter(is_active=True)
    elif status_filter == "inactive":
        qs = qs.filter(is_active=False)

    rows = await qs.order_by("-created_at")
    return UserListResponse(
        data=[UserResponse.from_user(u) for u in rows],
        total=len(rows),
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a user")
async def create_user(body: UserCreate, admin: User = Depends(require_admin)) -> dict:
    user, extra = await user_service.create_user(body)
    return {"user": UserResponse.from_user(user).model_dump(), **extra}


@router.get("/{user_id}", response_model=UserResponse, summary="Get user by ID")
async def get_user(user_id: uuid.UUID, admin: User = Depends(require_admin)) -> UserResponse:
    try:
        user = await User.get(id=user_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.from_user(user)


@router.patch("/{user_id}", response_model=UserResponse, summary="Update a user")
async def update_user(
    user_id: uuid.UUID, body: UserUpdate, admin: User = Depends(require_admin)
) -> UserResponse:
    try:
        user = await User.get(id=user_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.role is not None and body.role != user.role:
        user_service.ensure_not_self(admin.id, user.id)
        if user.role == "admin" and body.role == "user":
            await user_service.ensure_not_last_admin(user)
        user.role = body.role

    if body.display_name is not None:
        user.display_name = body.display_name

    await user.save()
    return UserResponse.from_user(user)


@router.post("/{user_id}/deactivate", response_model=UserResponse, summary="Deactivate (soft-delete) a user")
async def deactivate_user(user_id: uuid.UUID, admin: User = Depends(require_admin)) -> UserResponse:
    try:
        user = await User.get(id=user_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user_service.ensure_not_self(admin.id, user.id)
    await user_service.ensure_not_last_admin(user)
    user.is_active = False
    await user.save(update_fields=["is_active"])
    return UserResponse.from_user(user)


@router.post("/{user_id}/activate", response_model=UserResponse, summary="Reactivate a user")
async def activate_user(user_id: uuid.UUID, admin: User = Depends(require_admin)) -> UserResponse:
    try:
        user = await User.get(id=user_id)
    except DoesNotExist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = True
    await user.save(update_fields=["is_active"])
    return UserResponse.from_user(user)
