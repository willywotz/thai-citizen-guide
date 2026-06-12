from datetime import timedelta

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import get_current_user, get_current_user_optional
from app.auth.security import generate_api_key, hash_api_key
from app.models.user import User, UserAPIKey
from app.utils import now


def _creds(token):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


async def _key(user, **extra):
    raw = generate_api_key()
    await UserAPIKey.create(user_id=user.id, name="n", key_hash=hash_api_key(raw),
                            key_prefix=raw[:12], **extra)
    return raw


async def test_revoked_key_rejected(db):
    u = await User.create(email="r@x.com", hashed_password="h")
    raw = await _key(u, revoked_at=now())
    with pytest.raises(HTTPException) as e:
        await get_current_user(_creds(raw))
    assert e.value.status_code == 401


async def test_expired_key_rejected(db):
    u = await User.create(email="e@x.com", hashed_password="h")
    raw = await _key(u, expires_at=now() - timedelta(seconds=1))
    with pytest.raises(HTTPException) as e:
        await get_current_user(_creds(raw))
    assert e.value.status_code == 401


async def test_future_expiry_key_works(db):
    u = await User.create(email="f@x.com", hashed_password="h")
    raw = await _key(u, expires_at=now() + timedelta(days=1))
    result = await get_current_user(_creds(raw))
    assert result.id == u.id


async def test_per_key_rate_limit(db, monkeypatch):
    import app.auth.dependencies as dep
    from app.services.rate_limit import SlidingWindowLimiter
    t = [0.0]
    monkeypatch.setattr(dep, "api_key_limiter", SlidingWindowLimiter(now_fn=lambda: t[0]))
    u = await User.create(email="rl@x.com", hashed_password="h")
    raw = await _key(u, rate_limit_rpm=1)
    await get_current_user(_creds(raw))  # 1st ok
    with pytest.raises(HTTPException) as e:
        await get_current_user(_creds(raw))  # 2nd over limit
    assert e.value.status_code == 429
    assert "Retry-After" in e.value.headers


async def test_no_per_key_limit_when_unset(db):
    u = await User.create(email="nl@x.com", hashed_password="h")
    raw = await _key(u)  # rate_limit_rpm is None
    for _ in range(5):
        assert (await get_current_user(_creds(raw))).id == u.id


async def test_optional_revoked_key_raises_401(db):
    u = await User.create(email="or@x.com", hashed_password="h")
    raw = await _key(u, revoked_at=now())
    with pytest.raises(HTTPException) as e:
        await get_current_user_optional(_creds(raw))
    assert e.value.status_code == 401


async def test_optional_expired_key_raises_401(db):
    u = await User.create(email="oe@x.com", hashed_password="h")
    raw = await _key(u, expires_at=now() - timedelta(seconds=1))
    with pytest.raises(HTTPException) as e:
        await get_current_user_optional(_creds(raw))
    assert e.value.status_code == 401
