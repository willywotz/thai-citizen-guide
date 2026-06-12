"""
FastAPI dependencies for authenticated routes.

Usage
-----
    from app.auth.dependencies import get_current_user, require_admin

    @router.get("/protected")
    async def protected(user = Depends(get_current_user)):
        ...

    @router.get("/admin-only")
    async def admin_only(user = Depends(require_admin)):
        ...
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.auth.security import API_KEY_PREFIX, decode_access_token, hash_api_key
from app.models.user import User, UserAPIKey
from app.services.rate_limit import api_key_limiter
from app.utils import now

_bearer = HTTPBearer(auto_error=True)
_bearer_optional = HTTPBearer(auto_error=False)

_invalid_credentials = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def _resolve_token(token: str) -> User | None:
    """Resolve a bearer token to an active user.

    Accepts either a JWT or a ``tcg_`` API key (distinguished by prefix), so
    REST endpoints authenticate the same keys the MCP server already does.
    Returns None when the token is invalid or the user is missing/inactive.
    """
    if token.startswith(API_KEY_PREFIX):
        api_key = await UserAPIKey.filter(key_hash=hash_api_key(token)).first()
        if api_key is None:
            return None
        if not api_key.is_usable():
            return None
        user = await User.filter(id=api_key.user_id, is_active=True).first()
        if user is None:
            return None
        rpm = api_key.rate_limit_rpm or 0
        if rpm:
            key = f"apikey:{api_key.id}"
            if not api_key_limiter.allow(key, limit=rpm):
                raise HTTPException(
                    status_code=429,
                    detail="API key rate limit exceeded",
                    headers={"Retry-After": str(api_key_limiter.retry_after(key))},
                )
        api_key.last_used_at = now()
        await api_key.save(update_fields=["last_used_at"])
        return user

    try:
        payload = decode_access_token(token)
    except JWTError:
        return None
    user_id: str = payload.get("sub", "")
    if not user_id:
        return None
    return await User.filter(id=user_id, is_active=True).first()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> User:
    user = await _resolve_token(credentials.credentials)
    if user is None:
        raise _invalid_credentials
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_optional),
) -> User | None:
    # No credential → anonymous.
    if credentials is None:
        return None
    token = credentials.credentials
    user = await _resolve_token(token)
    # A deliberate API-key auth that fails must NOT silently degrade to anonymous
    # — that would let a typo'd key bypass rate limits / quotas. A JWT, by
    # contrast, is a session token a browser auto-attaches; an expired one
    # degrades to anonymous so optional-auth endpoints (e.g. chat) still work.
    if user is None and token.startswith(API_KEY_PREFIX):
        raise _invalid_credentials
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user
