"""
Tests for G1: EXPOSE_PASSWORD_RESET_TOKEN kill-switch.

The forgot_password handler requires a live DB to invoke directly, so we test
the setting-gating logic by patching at the router module level and verifying
the conditional branch with a mock user. The DB calls (User.filter, user.save)
are mocked so no real DB is required.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_reset_token_included_when_flag_true():
    """Response dict contains reset_token when EXPOSE_PASSWORD_RESET_TOKEN is True."""
    from app.routers import auth as auth_module
    from app.config import settings

    mock_user = MagicMock()
    mock_user.save = AsyncMock()

    with patch.object(settings, "EXPOSE_PASSWORD_RESET_TOKEN", True), \
         patch.object(auth_module, "generate_reset_token", return_value="tok-abc"), \
         patch.object(auth_module, "reset_token_expiry", return_value=None), \
         patch("app.models.user.User.filter") as mock_filter:

        mock_filter.return_value.first = AsyncMock(return_value=mock_user)

        request = MagicMock()
        request.email = "test@example.com"

        result = await auth_module.forgot_password(request)

    assert "reset_token" in result
    assert result["reset_token"] == "tok-abc"


@pytest.mark.asyncio
async def test_reset_token_omitted_when_flag_false():
    """Response dict omits reset_token when EXPOSE_PASSWORD_RESET_TOKEN is False."""
    from app.routers import auth as auth_module
    from app.config import settings

    mock_user = MagicMock()
    mock_user.save = AsyncMock()

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
