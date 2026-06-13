"""The basic-user allowlist maps 1:1 to the Chat + Architecture pages."""
from app.auth.dependencies import _is_allowed_for_basic_user, _resolve_role
from app.auth.security import create_access_token, generate_api_key, hash_api_key
from app.models.user import User, UserAPIKey


def test_chat_endpoints_allowed():
    assert _is_allowed_for_basic_user("POST", "/api/v1/chat")
    assert _is_allowed_for_basic_user("POST", "/api/v1/chat/stream")
    assert not _is_allowed_for_basic_user("GET", "/api/v1/chat")


def test_message_rating_allowed():
    assert _is_allowed_for_basic_user("PATCH", "/api/v1/messages/abc-123/rating")
    assert not _is_allowed_for_basic_user("PATCH", "/api/v1/messages/abc-123/rating/extra")


def test_agencies_list_allowed_but_not_mutations():
    assert _is_allowed_for_basic_user("GET", "/api/v1/agencies")
    assert not _is_allowed_for_basic_user("DELETE", "/api/v1/agencies/abc-123")
    assert not _is_allowed_for_basic_user("PATCH", "/api/v1/agencies/abc-123/status")


def test_own_conversations_allowed():
    assert _is_allowed_for_basic_user("GET", "/api/v1/conversations")
    assert _is_allowed_for_basic_user("DELETE", "/api/v1/conversations/abc-123")


def test_auth_self_endpoints_allowed():
    assert _is_allowed_for_basic_user("GET", "/api/v1/auth/me")
    assert _is_allowed_for_basic_user("POST", "/api/v1/auth/login")


def test_restricted_pages_blocked():
    assert not _is_allowed_for_basic_user("GET", "/api/v1/dashboard/stats")
    assert not _is_allowed_for_basic_user("GET", "/api/v1/connection-logs")
    assert not _is_allowed_for_basic_user("GET", "/api/v1/api-keys/")
    assert not _is_allowed_for_basic_user("GET", "/api/v1/executive-summary")
    assert not _is_allowed_for_basic_user("GET", "/api/v1/insight/usage")


async def test_resolve_role_from_jwt(db):
    user = await User.create(email="role-jwt@x.com", hashed_password="h", role="user")
    token = create_access_token({"sub": str(user.id)})
    assert await _resolve_role(token) == "user"


async def test_resolve_role_admin(db):
    user = await User.create(email="role-admin@x.com", hashed_password="h", role="admin")
    token = create_access_token({"sub": str(user.id)})
    assert await _resolve_role(token) == "admin"


async def test_resolve_role_from_api_key(db):
    user = await User.create(email="role-key@x.com", hashed_password="h", role="user")
    raw = generate_api_key()
    await UserAPIKey.create(
        user_id=user.id, name="n", key_hash=hash_api_key(raw), key_prefix=raw[:12]
    )
    assert await _resolve_role(raw) == "user"


async def test_resolve_role_invalid_returns_none(db):
    assert await _resolve_role("not-a-jwt") is None
    assert await _resolve_role("tcg_bogus") is None


async def test_resolve_role_inactive_user_returns_none(db):
    user = await User.create(
        email="role-inactive@x.com", hashed_password="h", role="user", is_active=False
    )
    token = create_access_token({"sub": str(user.id)})
    assert await _resolve_role(token) is None


async def test_resolve_role_unusable_api_key_returns_none(db):
    from app.utils import now

    user = await User.create(email="role-revoked@x.com", hashed_password="h", role="user")
    raw = generate_api_key()
    await UserAPIKey.create(
        user_id=user.id,
        name="n",
        key_hash=hash_api_key(raw),
        key_prefix=raw[:12],
        revoked_at=now(),
    )
    assert await _resolve_role(raw) is None
