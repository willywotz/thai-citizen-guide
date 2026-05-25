"""
Auth router — JWT-based authentication.

Endpoints
---------
  POST  /auth/register          Create a new account
  POST  /auth/login             Sign in → returns access_token
  GET   /auth/me                Return the currently authenticated user
  POST  /auth/forgot-password   Request a password-reset token
  POST  /auth/reset-password    Set a new password using the reset token
  PATCH /auth/me                Update display_name / avatar_url
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Depends
from app.auth.dependencies import require_admin
from app.models.user import User
from pydantic import BaseModel, EmailStr

from app.config import settings
from app.auth.dependencies import get_current_user
from app.auth.security import (
    create_access_token,
    generate_reset_token,
    hash_password,
    reset_token_expiry,
    verify_password,
)
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Auth"])


# ---------------------------------------------------------------------------
# Pydantic schemas (defined inline — small enough not to need a separate file)
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None


def _user_dict(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "displayName": user.display_name or user.email.split("@")[0],
        "role": user.role,
        "avatarUrl": user.avatar_url,
    }


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@router.post("/register", status_code=status.HTTP_201_CREATED, summary="Create a new account")
async def register(body: RegisterRequest) -> dict:
    if len(body.password) < settings.MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail="รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร")

    exists = await User.filter(email=body.email).exists()
    if exists:
        raise HTTPException(status_code=409, detail="อีเมลนี้ถูกใช้งานแล้ว")

    user = await User.create(
        email=body.email,
        display_name=body.display_name,
        hashed_password=hash_password(body.password),
        role="user",
    )

    token = create_access_token({"sub": str(user.id)})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _user_dict(user),
    }


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login", summary="Sign in and get an access token")
async def login(body: LoginRequest) -> dict:
    user = await User.filter(email=body.email, is_active=True).first()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="อีเมลหรือรหัสผ่านไม่ถูกต้อง",
        )

    token = create_access_token({"sub": str(user.id)})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _user_dict(user),
    }


# ---------------------------------------------------------------------------
# Me — get current user
# ---------------------------------------------------------------------------

@router.get("/me", summary="Get current authenticated user")
async def me(user: User = Depends(get_current_user)) -> dict:
    return {"user": _user_dict(user)}


# ---------------------------------------------------------------------------
# Update profile
# ---------------------------------------------------------------------------

@router.patch("/me", summary="Update display name or avatar")
async def update_me(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_user),
) -> dict:
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url
    await user.save()
    return {"user": _user_dict(user)}


# ---------------------------------------------------------------------------
# Forgot password — generate reset token
# ---------------------------------------------------------------------------

@router.post("/forgot-password", summary="Request a password-reset token")
async def forgot_password(body: ForgotPasswordRequest) -> dict:
    user = await User.filter(email=body.email, is_active=True).first()

    # Always return 200 to avoid email enumeration
    if not user:
        return {"message": "หากอีเมลนี้มีอยู่ในระบบ คุณจะได้รับลิงก์รีเซ็ตรหัสผ่าน"}

    token = generate_reset_token()
    user.reset_token = token
    user.reset_token_expires = reset_token_expiry()
    await user.save(update_fields=["reset_token", "reset_token_expires"])

    # In production — send the token by email.
    # For now, return it directly so the frontend can use it.
    return {
        "message": "สร้าง token รีเซ็ตรหัสผ่านเรียบร้อยแล้ว",
        "reset_token": token,   # ← remove / email this in production
    }


# ---------------------------------------------------------------------------
# Reset password — consume the token
# ---------------------------------------------------------------------------

@router.post("/reset-password", summary="Set a new password using the reset token")
async def reset_password(body: ResetPasswordRequest) -> dict:
    if len(body.new_password) < settings.MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail="รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร")

    user = await User.filter(reset_token=body.token, is_active=True).first()

    if not user:
        raise HTTPException(status_code=400, detail="Token ไม่ถูกต้องหรือหมดอายุแล้ว")

    # Check expiry
    if user.reset_token_expires and datetime.now(timezone.utc) > user.reset_token_expires.replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=400, detail="Token หมดอายุแล้ว กรุณาขอ token ใหม่")

    user.hashed_password = hash_password(body.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    await user.save(update_fields=["hashed_password", "reset_token", "reset_token_expires"])

    return {"message": "เปลี่ยนรหัสผ่านสำเร็จ"}
