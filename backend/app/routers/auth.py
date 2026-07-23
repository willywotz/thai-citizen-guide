"""
Auth router — JWT-based authentication.

Accounts are created by an admin via ``POST /api/v1/users``; there is no
public self-registration.

Endpoints
---------
  POST  /auth/login             Sign in → returns access_token
  GET   /auth/me                Return the currently authenticated user
  PATCH /auth/me                Update display_name / avatar_url
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from app.auth.dependencies import get_current_user
from app.models.user import User
from pydantic import BaseModel, EmailStr

from app.auth.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["Auth"])


# ---------------------------------------------------------------------------
# Pydantic schemas (defined inline — small enough not to need a separate file)
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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
