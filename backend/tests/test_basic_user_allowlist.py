"""The basic-user allowlist maps 1:1 to the Chat + Architecture pages."""
from app.auth.dependencies import _is_allowed_for_basic_user


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
