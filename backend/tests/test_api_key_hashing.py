import hashlib

import pytest

from app.auth.security import generate_api_key, hash_api_key
from app.models.user import User, UserAPIKey


def test_hash_api_key_is_sha256_hex():
    assert hash_api_key("abc") == hashlib.sha256(b"abc").hexdigest()


def test_generate_api_key_has_prefix():
    raw = generate_api_key()
    assert raw.startswith("tcg_") and len(raw) > 30


@pytest.mark.asyncio
async def test_create_key_stores_hash_not_plaintext(db):
    user = await User.create(email="k@x.com", hashed_password="h")
    raw = generate_api_key()
    key = await UserAPIKey.create(
        user_id=user.id, name="n",
        key_hash=hash_api_key(raw), key_prefix=raw[:12],
    )
    assert key.key_hash != raw
    assert await UserAPIKey.filter(key_hash=hash_api_key(raw)).first() is not None
