"""
API key validation: SHA-256 hash lookup in the api_keys table.
"""
import hashlib
import secrets
import base64
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ApiKey


def sha256_hex(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key(prefix: str = "tcg_live_") -> tuple[str, str, str]:
    """
    Returns (raw_key, key_hash, key_prefix).
    raw_key is shown once; key_hash is stored; key_prefix is for display.
    """
    random_bytes = secrets.token_bytes(32)
    b64 = base64.urlsafe_b64encode(random_bytes).decode().rstrip("=")
    raw_key = prefix + b64
    key_hash = sha256_hex(raw_key)
    key_prefix = raw_key[:20]
    return raw_key, key_hash, key_prefix


class ApiKeyResult:
    def __init__(self, user_id: str, scopes: list[str], key_id: str):
        self.user_id = user_id
        self.scopes = scopes
        self.key_id = key_id


async def validate_api_key(
    raw_key: str,
    db: AsyncSession,
    client_ip: Optional[str] = None,
) -> Optional[ApiKeyResult]:
    """
    Validates an API key. Returns ApiKeyResult or None if invalid.
    Updates last_used_at asynchronously.
    """
    key_hash = sha256_hex(raw_key)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.revoked_at.is_(None),
        )
    )
    key_row = result.scalar_one_or_none()

    if not key_row:
        return None

    if key_row.expires_at and key_row.expires_at < now:
        return None

    # Fire-and-forget update of last_used_at
    await db.execute(
        update(ApiKey)
        .where(ApiKey.id == key_row.id)
        .values(last_used_at=now, last_used_ip=client_ip, updated_at=now)
    )
    await db.commit()

    return ApiKeyResult(
        user_id=str(key_row.user_id),
        scopes=list(key_row.scopes or []),
        key_id=str(key_row.id),
    )
