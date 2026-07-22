"""/responses is reachable by every authenticated role and by anonymous callers.

It mirrors /chat: a programmatic surface that read-restricted roles may still
use. The chokepoint (enforce_role_allowlist) must therefore allow the POST.
"""

from app.auth.dependencies import (
    _is_allowed_for_auditor,
    _is_allowed_for_basic_user,
    _is_allowed_for_viewer,
)

PATH = "/api/v1/responses"


def test_basic_user_may_post_responses():
    assert _is_allowed_for_basic_user("POST", PATH) is True


def test_viewer_may_post_responses():
    assert _is_allowed_for_viewer("POST", PATH) is True


def test_auditor_may_post_responses():
    assert _is_allowed_for_auditor("POST", PATH) is True


def test_basic_user_still_cannot_post_elsewhere():
    assert _is_allowed_for_basic_user("POST", "/api/v1/agencies") is False
