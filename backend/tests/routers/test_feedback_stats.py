"""Access-control policy for the feedback-stats endpoint.

The handler no longer gates on admin: access is governed by the global role
allowlist (`enforce_role_allowlist`), which allows the plain `user` role
read-only access to this ops page. The aggregation query is Postgres-specific
and cannot run against the SQLite test DB, so the policy is asserted at the
allowlist layer that runs before any SQL.
"""

from app.auth.dependencies import _is_allowed_for_basic_user

_PATH = "/api/v1/feedback/stats"


def test_feedback_stats_allowed_for_basic_user():
    assert _is_allowed_for_basic_user("GET", _PATH)
