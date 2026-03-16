"""
Supabase JWT verification using the project's JWT secret.
Validates token signature and extracts claims without calling Supabase API.
"""
import uuid
from typing import Optional
from jose import jwt, JWTError
from app.config import settings


class JWTClaims:
    def __init__(self, payload: dict):
        self.sub: str = payload.get("sub", "")
        self.email: Optional[str] = payload.get("email")
        self.user_roles: list[str] = payload.get("user_roles", [])
        self.is_admin: bool = payload.get("is_admin", False)
        self.email_verified: bool = payload.get("email_verified", False)
        self.role: str = payload.get("role", "authenticated")  # Supabase anon/authenticated
        self._raw = payload

    @property
    def user_id(self) -> uuid.UUID:
        return uuid.UUID(self.sub)


def decode_supabase_jwt(token: str) -> Optional[JWTClaims]:
    """
    Decode and verify a Supabase-issued JWT using SUPABASE_JWT_SECRET.
    Returns None if invalid / expired.
    """
    if not settings.SUPABASE_JWT_SECRET:
        return None
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return JWTClaims(payload)
    except JWTError:
        return None
