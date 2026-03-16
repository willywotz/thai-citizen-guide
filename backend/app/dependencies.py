"""
FastAPI dependency injection: auth, DB session, permission checks.
"""
import uuid
from typing import Optional, Annotated
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.jwt import decode_supabase_jwt, JWTClaims
from app.auth.api_key import validate_api_key
from app.models import UserRole, RolePermission


bearer_scheme = HTTPBearer(auto_error=False)


class AuthContext:
    """Unified auth context regardless of auth method (JWT or API key)."""

    def __init__(
        self,
        user_id: str,
        roles: list[str],
        auth_method: str,
        email: Optional[str] = None,
        is_email_verified: bool = False,
    ):
        self.user_id = user_id
        self.roles = roles
        self.auth_method = auth_method
        self.email = email
        self.is_email_verified = is_email_verified

    def has_role(self, role: str) -> bool:
        return role in self.roles

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles or "super_admin" in self.roles

    @property
    def is_super_admin(self) -> bool:
        return "super_admin" in self.roles


async def _get_roles_from_db(user_id: str, db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(UserRole.role).where(UserRole.user_id == uuid.UUID(user_id))
    )
    return [row[0] for row in result.fetchall()]


async def _check_permission(user_id: str, permission: str, roles: list[str], db: AsyncSession) -> bool:
    if not roles:
        return False
    result = await db.execute(
        select(RolePermission.permission)
        .where(
            RolePermission.role.in_(roles),
            RolePermission.permission == permission,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def get_optional_auth(
    request: Request,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
) -> Optional[AuthContext]:
    """Auth is optional — returns None if not authenticated."""
    api_key_header = request.headers.get("x-api-key")

    # --- API key auth ---
    if api_key_header:
        client_ip = request.headers.get("x-forwarded-for") or request.client.host if request.client else None
        key_result = await validate_api_key(api_key_header, db, client_ip)
        if key_result:
            roles = await _get_roles_from_db(key_result.user_id, db)
            if "api_user" not in roles:
                roles.append("api_user")
            return AuthContext(user_id=key_result.user_id, roles=roles, auth_method="api_key")
        return None

    # --- JWT auth ---
    if credentials:
        claims = decode_supabase_jwt(credentials.credentials)
        if claims:
            roles = claims.user_roles if claims.user_roles else await _get_roles_from_db(claims.sub, db)
            return AuthContext(
                user_id=claims.sub,
                roles=roles,
                auth_method="jwt",
                email=claims.email,
                is_email_verified=claims.email_verified,
            )

    return None


async def require_auth(
    auth: Annotated[Optional[AuthContext], Depends(get_optional_auth)],
) -> AuthContext:
    """Require authentication. Raises 401 if not authenticated."""
    if not auth:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return auth


def require_permission(permission: str):
    """Dependency factory: require a specific permission."""

    async def _check(
        auth: Annotated[AuthContext, Depends(require_auth)],
        db: AsyncSession = Depends(get_db),
    ) -> AuthContext:
        has = await _check_permission(auth.user_id, permission, auth.roles, db)
        if not has:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return auth

    return _check


def require_role(role: str):
    """Dependency factory: require a specific role."""

    async def _check(auth: Annotated[AuthContext, Depends(require_auth)]) -> AuthContext:
        if not auth.has_role(role):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Role '{role}' required")
        return auth

    return _check
