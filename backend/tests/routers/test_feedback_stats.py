"""Access-control scenario for the feedback-stats endpoint.

The aggregation query in `feedback_stats` is Postgres-specific (SET TIME ZONE,
TO_CHAR) and cannot run against the in-memory SQLite test DB, so this test
covers the admin gate — which runs before any SQL — confirming non-admins are
rejected.
"""

import pytest
from fastapi import HTTPException

from app.models.user import User
from app.routers import feedback as feedback_router


@pytest.mark.asyncio
async def test_feedback_stats_rejects_non_admin(db):
    user = await User.create(
        email="user@example.com", hashed_password="x", role="user"
    )

    with pytest.raises(HTTPException) as exc:
        await feedback_router.feedback_stats(user=user)

    assert exc.value.status_code == 403
