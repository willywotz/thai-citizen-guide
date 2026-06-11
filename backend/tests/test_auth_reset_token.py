"""
Tests for G1: EXPOSE_PASSWORD_RESET_TOKEN kill-switch and email delivery.

The forgot_password handler requires a live DB to invoke directly, so we test
the setting-gating logic by patching at the router module level and verifying
the conditional branch with a mock user. The DB calls (User.filter, user.save)
are mocked so no real DB is required.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_mock_user():
    mock_user = MagicMock()
    mock_user.email = "test@example.com"
    mock_user.save = AsyncMock()
    return mock_user


# ---------------------------------------------------------------------------
# Email delivered — reset_token NOT in response regardless of EXPOSE flag
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_email_sent_response_has_email_sent_true_no_token():
    """When email is delivered, response has email_sent=True and no reset_token."""
    from app.routers import auth as auth_module
    from app.config import settings

    mock_user = _make_mock_user()

    with patch.object(settings, "EXPOSE_PASSWORD_RESET_TOKEN", True), \
         patch.object(auth_module, "generate_reset_token", return_value="tok-abc"), \
         patch.object(auth_module, "reset_token_expiry", return_value=None), \
         patch("app.models.user.User.filter") as mock_filter, \
         patch.object(auth_module, "send_password_reset_email", AsyncMock(return_value=True)):

        mock_filter.return_value.first = AsyncMock(return_value=mock_user)

        request = MagicMock()
        request.email = "test@example.com"

        result = await auth_module.forgot_password(request)

    assert result["email_sent"] is True
    assert "reset_token" not in result


# ---------------------------------------------------------------------------
# Email NOT delivered + EXPOSE True — reset_token returned as fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_email_not_sent_expose_true_includes_reset_token():
    """When email fails and EXPOSE flag is True, reset_token is included as fallback."""
    from app.routers import auth as auth_module
    from app.config import settings

    mock_user = _make_mock_user()

    with patch.object(settings, "EXPOSE_PASSWORD_RESET_TOKEN", True), \
         patch.object(auth_module, "generate_reset_token", return_value="tok-xyz"), \
         patch.object(auth_module, "reset_token_expiry", return_value=None), \
         patch("app.models.user.User.filter") as mock_filter, \
         patch.object(auth_module, "send_password_reset_email", AsyncMock(return_value=False)):

        mock_filter.return_value.first = AsyncMock(return_value=mock_user)

        request = MagicMock()
        request.email = "test@example.com"

        result = await auth_module.forgot_password(request)

    assert result["email_sent"] is False
    assert result["reset_token"] == "tok-xyz"


# ---------------------------------------------------------------------------
# Legacy behaviour — email disabled (returns False) + EXPOSE True → token returned
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reset_token_included_when_flag_true():
    """Response dict contains reset_token when EXPOSE_PASSWORD_RESET_TOKEN is True and email not sent."""
    from app.routers import auth as auth_module
    from app.config import settings

    mock_user = _make_mock_user()

    with patch.object(settings, "EXPOSE_PASSWORD_RESET_TOKEN", True), \
         patch.object(auth_module, "generate_reset_token", return_value="tok-abc"), \
         patch.object(auth_module, "reset_token_expiry", return_value=None), \
         patch("app.models.user.User.filter") as mock_filter, \
         patch.object(auth_module, "send_password_reset_email", AsyncMock(return_value=False)):

        mock_filter.return_value.first = AsyncMock(return_value=mock_user)

        request = MagicMock()
        request.email = "test@example.com"

        result = await auth_module.forgot_password(request)

    assert "reset_token" in result
    assert result["reset_token"] == "tok-abc"


# ---------------------------------------------------------------------------
# EXPOSE False + no email → token NOT returned
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reset_token_omitted_when_flag_false():
    """Response dict omits reset_token when EXPOSE_PASSWORD_RESET_TOKEN is False."""
    from app.routers import auth as auth_module
    from app.config import settings

    mock_user = _make_mock_user()

    with patch.object(settings, "EXPOSE_PASSWORD_RESET_TOKEN", False), \
         patch.object(auth_module, "generate_reset_token", return_value="tok-xyz"), \
         patch.object(auth_module, "reset_token_expiry", return_value=None), \
         patch("app.models.user.User.filter") as mock_filter, \
         patch.object(auth_module, "send_password_reset_email", AsyncMock(return_value=False)):

        mock_filter.return_value.first = AsyncMock(return_value=mock_user)

        request = MagicMock()
        request.email = "test@example.com"

        result = await auth_module.forgot_password(request)

    assert "reset_token" not in result
    assert "message" in result
