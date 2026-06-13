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

import re

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.auth.security import API_KEY_PREFIX, decode_access_token, hash_api_key
from app.models.user import User, UserAPIKey
from app.services.rate_limit import api_key_limiter
from app.services.usage_context import current_api_key_id, current_user_id
from app.utils import now

_bearer = HTTPBearer(auto_error=True)
_bearer_optional = HTTPBearer(auto_error=False)

_invalid_credentials = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

_MESSAGE_RATING_PATH = re.compile(r"^/api/v1/messages/[^/]+/rating$")
_CONVERSATION_PATH = re.compile(r"^/api/v1/conversations(?:/[^/]+)?$")


def _is_allowed_for_basic_user(method: str, path: str) -> bool:
    """Allowlist of (method, path) a plain ``user`` role may reach.

    Maps 1:1 to the Chat and Architecture pages, plus the auth/self endpoints
    every authenticated session needs. Everything else is forbidden.
    """
    if path.startswith("/api/v1/auth/"):  # all auth endpoints — each guards itself internally
        return True
    if method == "POST" and path in ("/api/v1/chat", "/api/v1/chat/stream"):
        return True
    if method == "PATCH" and _MESSAGE_RATING_PATH.match(path):
        return True
    if method == "GET" and path == "/api/v1/agencies":  # Architecture page (list only)
        return True
    if _CONVERSATION_PATH.match(path):  # all verbs: a user may manage their own conversation history
        return True
    return False


async def _resolve_role(token: str) -> str | None:
    """Return the caller's role without the side effects of ``_resolve_token``.

    Used only by the basic-user chokepoint. Deliberately skips API-key rate
    limiting and ``last_used_at`` stamping so wiring it globally never double-
    charges those — it only needs the role.
    """
    if token.startswith(API_KEY_PREFIX):
        api_key = await UserAPIKey.filter(key_hash=hash_api_key(token)).first()
        if api_key is None or not api_key.is_usable():
            return None
        user = await User.filter(id=api_key.user_id, is_active=True).first()
        return user.role if user else None

    try:
        payload = decode_access_token(token)
    except JWTError:
        return None
    user_id: str = payload.get("sub", "")
    if not user_id:
        return None
    user = await User.filter(id=user_id, is_active=True).first()
    return user.role if user else None


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
            result = await api_key_limiter.check(key, limit=rpm)
            if not result.allowed:
                raise HTTPException(
                    status_code=429,
                    detail="API key rate limit exceeded",
                    headers={"Retry-After": str(result.retry_after)},
                )
        api_key.last_used_at = now()
        await api_key.save(update_fields=["last_used_at"])
        current_user_id.set(user.id)
        current_api_key_id.set(api_key.id)
        return user

    try:
        payload = decode_access_token(token)
    except JWTError:
        return None
    user_id: str = payload.get("sub", "")
    if not user_id:
        return None
    user = await User.filter(id=user_id, is_active=True).first()
    if user is not None:
        current_user_id.set(user.id)
    return user


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
