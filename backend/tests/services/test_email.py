"""Tests for app.services.email — stdlib SMTP email delivery."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# email_configured
# ---------------------------------------------------------------------------

def test_email_configured_false_when_host_empty():
    from app.services.email import email_configured
    from app.config import settings

    with patch.object(settings, "EMAIL_SMTP_HOST", ""):
        assert email_configured() is False


def test_email_configured_true_when_host_set():
    from app.services.email import email_configured
    from app.config import settings

    with patch.object(settings, "EMAIL_SMTP_HOST", "smtp.example.com"):
        assert email_configured() is True


# ---------------------------------------------------------------------------
# send_email — not configured
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_email_returns_false_when_not_configured():
    from app.services import email as email_module
    from app.config import settings

    with patch.object(settings, "EMAIL_SMTP_HOST", ""), \
         patch.object(email_module, "smtplib") as mock_smtplib:

        result = await email_module.send_email(
            to="user@example.com",
            subject="Test",
            text_body="Hello",
        )

    assert result is False
    mock_smtplib.SMTP.assert_not_called()
    mock_smtplib.SMTP_SSL.assert_not_called()


# ---------------------------------------------------------------------------
# send_email — STARTTLS path (EMAIL_USE_TLS=True, EMAIL_USE_SSL=False)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_email_starttls_calls_smtp_correctly():
    from app.services import email as email_module
    from app.config import settings

    mock_server = MagicMock()
    mock_smtplib = MagicMock()
    mock_smtplib.SMTP.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtplib.SMTP.return_value.__exit__ = MagicMock(return_value=False)

    with patch.object(settings, "EMAIL_SMTP_HOST", "smtp.example.com"), \
         patch.object(settings, "EMAIL_SMTP_PORT", 587), \
         patch.object(settings, "EMAIL_SMTP_TIMEOUT", 10), \
         patch.object(settings, "EMAIL_SMTP_USER", "sender@example.com"), \
         patch.object(settings, "EMAIL_SMTP_PASSWORD", "secret"), \
         patch.object(settings, "EMAIL_FROM", "sender@example.com"), \
         patch.object(settings, "EMAIL_USE_TLS", True), \
         patch.object(settings, "EMAIL_USE_SSL", False), \
         patch.object(email_module, "smtplib", mock_smtplib):

        result = await email_module.send_email(
            to="user@example.com",
            subject="Test subject",
            text_body="Hello world",
        )

    assert result is True
    mock_smtplib.SMTP.assert_called_once_with("smtp.example.com", 587, timeout=10)
    mock_smtplib.SMTP_SSL.assert_not_called()
    ctx = mock_smtplib.SMTP.return_value.__enter__.return_value
    ctx.starttls.assert_called_once()
    ctx.login.assert_called_once_with("sender@example.com", "secret")
    ctx.send_message.assert_called_once()


# ---------------------------------------------------------------------------
# send_email — implicit SSL path (EMAIL_USE_SSL=True)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_email_ssl_uses_smtp_ssl_no_starttls():
    from app.services import email as email_module
    from app.config import settings

    mock_server = MagicMock()
    mock_smtplib = MagicMock()
    mock_smtplib.SMTP_SSL.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtplib.SMTP_SSL.return_value.__exit__ = MagicMock(return_value=False)

    with patch.object(settings, "EMAIL_SMTP_HOST", "smtp.example.com"), \
         patch.object(settings, "EMAIL_SMTP_PORT", 465), \
         patch.object(settings, "EMAIL_SMTP_TIMEOUT", 10), \
         patch.object(settings, "EMAIL_SMTP_USER", "sender@example.com"), \
         patch.object(settings, "EMAIL_SMTP_PASSWORD", "secret"), \
         patch.object(settings, "EMAIL_FROM", "sender@example.com"), \
         patch.object(settings, "EMAIL_USE_TLS", False), \
         patch.object(settings, "EMAIL_USE_SSL", True), \
         patch.object(email_module, "smtplib", mock_smtplib):

        result = await email_module.send_email(
            to="user@example.com",
            subject="SSL Test",
            text_body="Hello SSL",
        )

    assert result is True
    mock_smtplib.SMTP_SSL.assert_called_once_with("smtp.example.com", 465, timeout=10)
    mock_smtplib.SMTP.assert_not_called()
    ctx = mock_smtplib.SMTP_SSL.return_value.__enter__.return_value
    ctx.starttls.assert_not_called()
    ctx.send_message.assert_called_once()


# ---------------------------------------------------------------------------
# send_email — plain SMTP (both EMAIL_USE_TLS and EMAIL_USE_SSL False)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_email_plain_smtp_no_starttls_no_ssl():
    from app.services import email as email_module
    from app.config import settings

    mock_server = MagicMock()
    mock_smtplib = MagicMock()
    mock_smtplib.SMTP.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtplib.SMTP.return_value.__exit__ = MagicMock(return_value=False)

    with patch.object(settings, "EMAIL_SMTP_HOST", "smtp.example.com"), \
         patch.object(settings, "EMAIL_SMTP_PORT", 25), \
         patch.object(settings, "EMAIL_SMTP_TIMEOUT", 10), \
         patch.object(settings, "EMAIL_SMTP_USER", ""), \
         patch.object(settings, "EMAIL_FROM", "noreply@example.com"), \
         patch.object(settings, "EMAIL_USE_TLS", False), \
         patch.object(settings, "EMAIL_USE_SSL", False), \
         patch.object(email_module, "smtplib", mock_smtplib):

        result = await email_module.send_email(
            to="user@example.com",
            subject="Plain Test",
            text_body="Hello plain",
        )

    assert result is True
    mock_smtplib.SMTP.assert_called_once_with("smtp.example.com", 25, timeout=10)
    mock_smtplib.SMTP_SSL.assert_not_called()
    ctx = mock_smtplib.SMTP.return_value.__enter__.return_value
    ctx.starttls.assert_not_called()
    ctx.login.assert_not_called()
    ctx.send_message.assert_called_once()


# ---------------------------------------------------------------------------
# send_email — SMTP raises → returns False, does not propagate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_email_returns_false_on_smtp_error():
    from app.services import email as email_module
    from app.config import settings

    mock_smtplib = MagicMock()
    mock_smtplib.SMTP.return_value.__enter__ = MagicMock(side_effect=OSError("connection refused"))
    mock_smtplib.SMTP.return_value.__exit__ = MagicMock(return_value=False)

    with patch.object(settings, "EMAIL_SMTP_HOST", "smtp.example.com"), \
         patch.object(settings, "EMAIL_SMTP_PORT", 587), \
         patch.object(settings, "EMAIL_SMTP_TIMEOUT", 10), \
         patch.object(settings, "EMAIL_SMTP_USER", ""), \
         patch.object(settings, "EMAIL_FROM", "noreply@example.com"), \
         patch.object(settings, "EMAIL_USE_TLS", True), \
         patch.object(settings, "EMAIL_USE_SSL", False), \
         patch.object(email_module, "smtplib", mock_smtplib):

        result = await email_module.send_email(
            to="user@example.com",
            subject="Test",
            text_body="Hello",
        )

    assert result is False


# ---------------------------------------------------------------------------
# send_password_reset_email
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_password_reset_email_calls_send_email_with_link():
    from app.services import email as email_module
    from app.config import settings

    mock_send = AsyncMock(return_value=True)

    with patch.object(settings, "FRONTEND_BASE_URL", "https://example.com"), \
         patch.object(email_module, "send_email", mock_send):

        result = await email_module.send_password_reset_email(
            to="user@example.com",
            token="mytoken123",
        )

    assert result is True
    mock_send.assert_called_once()
    args, kwargs = mock_send.call_args
    assert args[0] == "user@example.com"
    assert "/reset-password?token=mytoken123" in args[2]  # text_body contains the link
    # html_body may be positional (args[3]) or keyword
    html_body = args[3] if len(args) > 3 else kwargs.get("html_body", "")
    assert "/reset-password?token=mytoken123" in html_body


@pytest.mark.asyncio
async def test_send_password_reset_email_no_raw_token_in_body():
    """Raw token must NOT appear separately in the body — only via the reset link."""
    from app.services import email as email_module
    from app.config import settings

    mock_send = AsyncMock(return_value=True)
    token = "secrettoken456"

    with patch.object(settings, "FRONTEND_BASE_URL", "https://example.com"), \
         patch.object(email_module, "send_email", mock_send):

        await email_module.send_password_reset_email(to="user@example.com", token=token)

    args, kwargs = mock_send.call_args
    text_body = args[2]
    html_body = args[3] if len(args) > 3 else kwargs.get("html_body", "")
    link = f"/reset-password?token={token}"
    # Token appears only as part of the link, not standalone
    assert link in text_body
    assert link in html_body
    # Raw token should not appear outside the link context
    assert f"token นี้: {token}" not in text_body
    assert f"<code>{token}</code>" not in html_body


@pytest.mark.asyncio
async def test_send_password_reset_email_returns_send_email_result():
    from app.services import email as email_module
    from app.config import settings

    mock_send = AsyncMock(return_value=False)

    with patch.object(settings, "FRONTEND_BASE_URL", "https://example.com"), \
         patch.object(email_module, "send_email", mock_send):

        result = await email_module.send_password_reset_email("u@e.com", "tok")

    assert result is False
