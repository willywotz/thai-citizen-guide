import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


def email_configured() -> bool:
    return bool(settings.EMAIL_SMTP_HOST)


def _send_sync(msg: EmailMessage) -> None:
    if settings.EMAIL_USE_TLS:
        with smtplib.SMTP(settings.EMAIL_SMTP_HOST, settings.EMAIL_SMTP_PORT, timeout=settings.EMAIL_SMTP_TIMEOUT) as server:
            server.starttls()
            if settings.EMAIL_SMTP_USER:
                server.login(settings.EMAIL_SMTP_USER, settings.EMAIL_SMTP_PASSWORD)
            server.send_message(msg)
    else:
        with smtplib.SMTP_SSL(settings.EMAIL_SMTP_HOST, settings.EMAIL_SMTP_PORT, timeout=settings.EMAIL_SMTP_TIMEOUT) as server:
            if settings.EMAIL_SMTP_USER:
                server.login(settings.EMAIL_SMTP_USER, settings.EMAIL_SMTP_PASSWORD)
            server.send_message(msg)


async def send_email(to: str, subject: str, text_body: str, html_body: str | None = None) -> bool:
    if not email_configured():
        logger.info("Email not configured; skipping send to %s", to)
        return False
    msg = EmailMessage()
    msg["From"] = settings.EMAIL_FROM or settings.EMAIL_SMTP_USER
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    try:
        await asyncio.to_thread(_send_sync, msg)
        return True
    except Exception as e:  # never propagate into the request
        logger.error("Failed to send email to %s: %s", to, e)
        return False


async def send_password_reset_email(to: str, token: str) -> bool:
    link = f"{settings.FRONTEND_BASE_URL}/reset-password?token={token}"
    subject = "รีเซ็ตรหัสผ่าน"
    text_body = (
        "คุณได้ขอรีเซ็ตรหัสผ่าน\n\n"
        f"คลิกลิงก์นี้เพื่อตั้งรหัสผ่านใหม่:\n{link}\n\n"
        f"หรือใช้รหัส token นี้: {token}\n\n"
        "หากคุณไม่ได้ร้องขอ โปรดเพิกเฉยต่ออีเมลนี้"
    )
    html_body = (
        f"<p>คุณได้ขอรีเซ็ตรหัสผ่าน</p>"
        f'<p><a href="{link}">คลิกที่นี่เพื่อตั้งรหัสผ่านใหม่</a></p>'
        f"<p>หรือใช้รหัส token นี้: <code>{token}</code></p>"
        f"<p>หากคุณไม่ได้ร้องขอ โปรดเพิกเฉยต่ออีเมลนี้</p>"
    )
    return await send_email(to, subject, text_body, html_body)
