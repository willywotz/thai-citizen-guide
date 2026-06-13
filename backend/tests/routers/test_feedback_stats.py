"""Access-control policy for the feedback-stats endpoint.

The handler no longer gates on admin: access is governed by the global role
allowlist (`enforce_role_allowlist`). Viewers and auditors are entitled to read
it (it backs the Dashboard and Feedback pages); a plain `user` is not. The
aggregation query is Postgres-specific and cannot run against the SQLite test
DB, so the policy is asserted at the allowlist layer that runs before any SQL.
"""

from app.auth.dependencies import _is_allowed_for_basic_user, _is_allowed_for_viewer

_PATH = "/api/v1/feedback/stats"


def test_feedback_stats_readable_by_viewer():
    assert _is_allowed_for_viewer("GET", _PATH)


def test_feedback_stats_blocked_for_basic_user():
    assert not _is_allowed_for_basic_user("GET", _PATH)
