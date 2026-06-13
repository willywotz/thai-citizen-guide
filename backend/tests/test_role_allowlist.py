"""Viewer and auditor allowlists: read-only with a chat write exception."""
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

from app.auth.dependencies import (
    _is_allowed_for_auditor,
    _is_allowed_for_viewer,
    _is_shared_write,
    enforce_role_allowlist,
)
from app.auth.security import create_access_token
from app.models.user import User


def test_shared_writes_allowed_for_both():
    for check in (_is_allowed_for_viewer, _is_allowed_for_auditor):
        assert check("POST", "/api/v1/chat")
        assert check("POST", "/api/v1/chat/stream")
        assert check("PATCH", "/api/v1/messages/abc-123/rating")
        assert check("GET", "/api/v1/conversations")
        assert check("DELETE", "/api/v1/conversations/abc-123")
        assert check("GET", "/api/v1/auth/me")


def test_shared_write_helper_excludes_other_writes():
    assert not _is_shared_write("POST", "/api/v1/agencies")
    assert not _is_shared_write("DELETE", "/api/v1/api-keys/abc-123")


def test_viewer_reads_its_pages():
    allowed_gets = [
        "/api/v1/agencies",
        "/api/v1/dashboard/stats",
        "/api/v1/executive-summary",
        "/api/v1/agency-health",
        "/api/v1/usage-heatmap",
        "/api/v1/analytics-insights",
        "/api/v1/insight/usage",
        "/api/v1/feedback/stats",
        "/api/v1/agencies/abc-123/health/history",
        "/api/v1/feedback/agencies/abc-123/low-rated",
    ]
    for path in allowed_gets:
        assert _is_allowed_for_viewer("GET", path), path


def test_viewer_cannot_read_auditor_only_or_write():
    assert not _is_allowed_for_viewer("GET", "/api/v1/users")
    assert not _is_allowed_for_viewer("GET", "/api/v1/audit-log/")
    assert not _is_allowed_for_viewer("GET", "/api/v1/api-keys/")
    assert not _is_allowed_for_viewer("GET", "/api/v1/connection-logs")
    assert not _is_allowed_for_viewer("GET", "/api/v1/agencies/abc-123")  # detail, not list
    assert not _is_allowed_for_viewer("POST", "/api/v1/agencies")
    assert not _is_allowed_for_viewer("POST", "/api/v1/executive-summary/regenerate")


def test_auditor_reads_everything_but_settings():
    for path in [
        "/api/v1/users",
        "/api/v1/audit-log/",
        "/api/v1/api-keys/",
        "/api/v1/connection-logs",
        "/api/v1/agencies/abc-123",
        "/api/v1/dashboard/stats",
    ]:
        assert _is_allowed_for_auditor("GET", path), path
    assert not _is_allowed_for_auditor("GET", "/api/v1/settings")


def test_auditor_blocks_all_non_chat_writes():
    assert not _is_allowed_for_auditor("POST", "/api/v1/agencies")
    assert not _is_allowed_for_auditor("DELETE", "/api/v1/api-keys/abc-123")
    assert not _is_allowed_for_auditor("PATCH", "/api/v1/users/abc-123")
    assert not _is_allowed_for_auditor("PUT", "/api/v1/settings")
    assert not _is_allowed_for_auditor("POST", "/api/v1/executive-summary/regenerate")


def test_auditor_settings_block_is_exact():
    # Real settings routes blocked:
    assert not _is_allowed_for_auditor("GET", "/api/v1/settings")
    assert not _is_allowed_for_auditor("GET", "/api/v1/settings/cache/flush")
    # A different route that merely shares the prefix is NOT blocked:
    assert _is_allowed_for_auditor("GET", "/api/v1/settings-extended")


# ---------------------------------------------------------------------------
# Chokepoint integration tests
# ---------------------------------------------------------------------------


def _request(method: str, path: str) -> Request:
    return Request(
        {"type": "http", "method": method, "path": path, "headers": [], "query_string": b""}
    )


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


async def _token_for(email: str, role: str) -> str:
    user = await User.create(email=email, hashed_password="h", role=role)
    return create_access_token({"sub": str(user.id)})


async def test_viewer_blocked_on_users(db):
    token = await _token_for("v1@x.com", "viewer")
    with pytest.raises(HTTPException) as e:
        await enforce_role_allowlist(_request("GET", "/api/v1/users"), _creds(token))
    assert e.value.status_code == 403


async def test_viewer_allowed_on_dashboard(db):
    token = await _token_for("v2@x.com", "viewer")
    assert await enforce_role_allowlist(
        _request("GET", "/api/v1/dashboard/stats"), _creds(token)
    ) is None


async def test_auditor_allowed_on_users_but_blocked_on_settings(db):
    token = await _token_for("a1@x.com", "auditor")
    assert await enforce_role_allowlist(
        _request("GET", "/api/v1/users"), _creds(token)
    ) is None
    with pytest.raises(HTTPException) as e:
        await enforce_role_allowlist(_request("GET", "/api/v1/settings"), _creds(token))
    assert e.value.status_code == 403


async def test_auditor_blocked_on_write(db):
    token = await _token_for("a2@x.com", "auditor")
    with pytest.raises(HTTPException) as e:
        await enforce_role_allowlist(_request("POST", "/api/v1/agencies"), _creds(token))
    assert e.value.status_code == 403


async def test_admin_and_owner_pass_through(db):
    for role in ("admin", "agency_owner"):
        token = await _token_for(f"{role}@x.com", role)
        assert await enforce_role_allowlist(
            _request("GET", "/api/v1/users"), _creds(token)
        ) is None
