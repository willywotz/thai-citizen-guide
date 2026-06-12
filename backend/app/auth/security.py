"""
Auth utilities — password hashing and JWT creation/verification.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
import bcrypt

from app.config import settings

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def create_access_token(payload: dict) -> str:
    """Return a signed JWT that expires in JWT_EXPIRE_MINUTES."""
    data = payload.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    data["exp"] = expire
    return jwt.encode(data, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT.
    Raises jose.JWTError on invalid / expired tokens.
    """
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


# ---------------------------------------------------------------------------
# Password-reset token (random URL-safe string)
# ---------------------------------------------------------------------------

def generate_reset_token() -> str:
    return secrets.token_urlsafe(settings.RESET_TOKEN_BYTES)


# ---------------------------------------------------------------------------
# API key generation and hashing
# ---------------------------------------------------------------------------

API_KEY_PREFIX = "tcg_"


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def reset_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=settings.RESET_TOKEN_EXPIRE_HOURS)
