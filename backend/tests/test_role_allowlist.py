"""Viewer and auditor allowlists: read-only with a chat write exception."""
from app.auth.dependencies import (
    _is_allowed_for_auditor,
    _is_allowed_for_viewer,
    _is_shared_write,
)


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
