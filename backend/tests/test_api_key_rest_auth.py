"""REST endpoints accept tcg_ API keys as bearer tokens, not just JWTs."""
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import get_current_user, get_current_user_optional
from app.auth.security import create_access_token, generate_api_key, hash_api_key
from app.models.user import User, UserAPIKey


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


async def _user_with_key(email: str, *, is_active: bool = True):
    user = await User.create(email=email, hashed_password="h", is_active=is_active)
    raw = generate_api_key()
    key = await UserAPIKey.create(
        user_id=user.id, name="n", key_hash=hash_api_key(raw), key_prefix=raw[:12]
    )
    return user, raw, key


async def test_api_key_authenticates_rest(db):
    user, raw, _ = await _user_with_key("k@x.com")
    result = await get_current_user(_creds(raw))
    assert result.id == user.id


async def test_api_key_stamps_last_used(db):
    _, raw, key = await _user_with_key("k2@x.com")
    assert key.last_used_at is None
    await get_current_user(_creds(raw))
    refreshed = await UserAPIKey.get(id=key.id)
    assert refreshed.last_used_at is not None


async def test_jwt_still_works(db):
    user = await User.create(email="j@x.com", hashed_password="h")
    token = create_access_token({"sub": str(user.id)})
    result = await get_current_user(_creds(token))
    assert result.id == user.id


async def test_invalid_token_required_raises_401(db):
    with pytest.raises(HTTPException) as e:
        await get_current_user(_creds("tcg_bogus-key-value"))
    assert e.value.status_code == 401


async def test_inactive_user_key_rejected(db):
    _, raw, _ = await _user_with_key("i@x.com", is_active=False)
    with pytest.raises(HTTPException) as e:
        await get_current_user(_creds(raw))
    assert e.value.status_code == 401


async def test_optional_no_credentials_is_anonymous(db):
    assert await get_current_user_optional(None) is None


async def test_optional_valid_key_resolves(db):
    user, raw, _ = await _user_with_key("o@x.com")
    result = await get_current_user_optional(_creds(raw))
    assert result is not None and result.id == user.id


async def test_optional_invalid_api_key_raises_401(db):
    # Footgun fix: a deliberate (tcg_) API-key auth that fails is rejected, not
    # silently treated as anonymous (which would bypass rate limits / quotas).
    with pytest.raises(HTTPException) as e:
        await get_current_user_optional(_creds("tcg_nope"))
    assert e.value.status_code == 401


async def test_optional_expired_jwt_degrades_to_anonymous(db):
    # A browser's stale/invalid JWT on an optional-auth endpoint degrades to
    # anonymous so anonymous-allowed endpoints (e.g. chat) keep working.
    assert await get_current_user_optional(_creds("not-a-valid-jwt")) is None
