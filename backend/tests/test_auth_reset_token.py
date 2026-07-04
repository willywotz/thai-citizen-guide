"""Tests for EXPOSE_PASSWORD_RESET_TOKEN.

Email delivery was removed from the project, so the forgot_password handler
returns the reset token in the API response when the flag is on, and omits it
when off. DB calls are mocked so no real DB is required.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_mock_user():
    mock_user = MagicMock()
    mock_user.email = "test@example.com"
    mock_user.save = AsyncMock()
    return mock_user


@pytest.mark.asyncio
async def test_expose_true_includes_reset_token():
    """EXPOSE flag True -> reset_token returned in the response (email_sent False)."""
    from app.routers import auth as auth_module
    from app.config import settings

    mock_user = _make_mock_user()

    with patch.object(settings, "EXPOSE_PASSWORD_RESET_TOKEN", True), \
         patch.object(auth_module, "generate_reset_token", return_value="tok-xyz"), \
         patch.object(auth_module, "reset_token_expiry", return_value=None), \
         patch("app.models.user.User.filter") as mock_filter:

        mock_filter.return_value.first = AsyncMock(return_value=mock_user)

        request = MagicMock()
        request.email = "test@example.com"

        result = await auth_module.forgot_password(request)

    assert result["email_sent"] is False
    assert result["reset_token"] == "tok-xyz"


@pytest.mark.asyncio
async def test_reset_token_omitted_when_flag_false():
    """Response omits reset_token when EXPOSE_PASSWORD_RESET_TOKEN is False."""
    from app.routers import auth as auth_module
    from app.config import settings

    mock_user = _make_mock_user()

    with patch.object(settings, "EXPOSE_PASSWORD_RESET_TOKEN", False), \
         patch.object(auth_module, "generate_reset_token", return_value="tok-xyz"), \
         patch.object(auth_module, "reset_token_expiry", return_value=None), \
         patch("app.models.user.User.filter") as mock_filter:

        mock_filter.return_value.first = AsyncMock(return_value=mock_user)

        request = MagicMock()
        request.email = "test@example.com"

        result = await auth_module.forgot_password(request)

    assert "reset_token" not in result
    assert "message" in result
