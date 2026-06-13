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

from fastapi import Depends, HTTPException, Request, status
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
# Matches the collection and /{id} only — sub-resources like /{id}/messages are intentionally excluded; only HistoryPage uses them and it's gated at the frontend.
_CONVERSATION_PATH = re.compile(r"^/api/v1/conversations(?:/[^/]+)?$")

# GET endpoints backing the pages a `viewer` may open (Architecture, Dashboard,
# Executive, Health, Heatmap, analytics insights, Usage, Feedback). Detail/admin
# endpoints are deliberately excluded — viewer is narrower than auditor.
_VIEWER_GET_EXACT = frozenset({
    "/api/v1/agencies",            # Architecture list
    "/api/v1/dashboard/stats",     # Dashboard
    "/api/v1/executive-summary",   # Executive
    "/api/v1/agency-health",       # Agency Health
    "/api/v1/usage-heatmap",       # Usage Heatmap
    "/api/v1/analytics-insights",  # Dashboard insights
    "/api/v1/insight/usage",       # Usage analytics
    "/api/v1/feedback/stats",      # Feedback
})
_VIEWER_GET_PATTERN = [
    re.compile(r"^/api/v1/agencies/[^/]+/health/history$"),       # Health detail
    re.compile(r"^/api/v1/feedback/agencies/[^/]+/low-rated$"),   # Feedback detail
]
_SETTINGS_PREFIX = "/api/v1/settings"


def _is_shared_write(method: str, path: str) -> bool:
    """Writes every authenticated role (incl. read-only ones) may perform.

    Chat, message rating, own-conversation management, and the self/auth
    endpoints. Everything else is a privileged write.
    """
    if path.startswith("/api/v1/auth/"):  # all auth endpoints — each guards itself internally
        return True
    if method == "POST" and path in ("/api/v1/chat", "/api/v1/chat/stream"):
        return True
    if method == "PATCH" and _MESSAGE_RATING_PATH.match(path):
        return True
    if _CONVERSATION_PATH.match(path):  # all verbs: manage own conversation history
        return True
    return False


def _is_allowed_for_basic_user(method: str, path: str) -> bool:
    """A plain ``user`` role: chat + architecture list + the shared writes."""
    if _is_shared_write(method, path):
        return True
    if method == "GET" and path == "/api/v1/agencies":  # Architecture page (list only)
        return True
    return False


def _is_allowed_for_viewer(method: str, path: str) -> bool:
    """``viewer``: read-only on its operational/analytics pages, plus chat."""
    if _is_shared_write(method, path):
        return True
    if method == "GET" and (
        path in _VIEWER_GET_EXACT or any(p.match(path) for p in _VIEWER_GET_PATTERN)
    ):
        return True
    return False


def _is_allowed_for_auditor(method: str, path: str) -> bool:
    """``auditor``: read-only on everything except Settings, plus chat."""
    if _is_shared_write(method, path):
        return True
    if method == "GET" and not path.startswith(_SETTINGS_PREFIX):
        return True
    return False


# NOTE: token-branching mirrors _resolve_token; kept separate to stay side-effect-free.
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


async def enforce_basic_user_allowlist(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_optional),
) -> None:
    """Chokepoint: a ``user``-role caller may only reach chat + architecture.

    Anonymous, ``admin`` and ``agency_owner`` callers pass straight through;
    their access is governed by each endpoint's own auth. Wired as a global
    dependency in ``app.main`` so it runs once per request.
    """
    if credentials is None:
        return
    role = await _resolve_role(credentials.credentials)
    if role != "user":
        return
    if not _is_allowed_for_basic_user(request.method, request.url.path):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This role may only access chat and architecture",
        )
