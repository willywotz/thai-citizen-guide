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
# send_email — configured, TLS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_email_tls_calls_smtp_correctly():
    from app.services import email as email_module
    from app.config import settings

    mock_server = MagicMock()
    mock_smtp_cls = MagicMock(return_value=mock_server)
    mock_smtp_cls.__enter__ = MagicMock(return_value=mock_server)
    mock_smtp_cls.__exit__ = MagicMock(return_value=False)

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
         patch.object(email_module, "smtplib", mock_smtplib):

        result = await email_module.send_email(
            to="user@example.com",
            subject="Test subject",
            text_body="Hello world",
        )

    assert result is True
    mock_smtplib.SMTP.assert_called_once_with("smtp.example.com", 587, timeout=10)
    ctx = mock_smtplib.SMTP.return_value.__enter__.return_value
    ctx.starttls.assert_called_once()
    ctx.login.assert_called_once_with("sender@example.com", "secret")
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
    assert "/reset-password?token=mytoken123" in args[2]  # text_body
    # html_body may be positional (args[3]) or keyword
    html_body = args[3] if len(args) > 3 else kwargs.get("html_body", "")
    assert "/reset-password?token=mytoken123" in html_body


@pytest.mark.asyncio
async def test_send_password_reset_email_returns_send_email_result():
    from app.services import email as email_module
    from app.config import settings

    mock_send = AsyncMock(return_value=False)

    with patch.object(settings, "FRONTEND_BASE_URL", "https://example.com"), \
         patch.object(email_module, "send_email", mock_send):

        result = await email_module.send_password_reset_email("u@e.com", "tok")

    assert result is False
