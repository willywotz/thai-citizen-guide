# Password-Reset Email Delivery — Design + Plan

**Date:** 2026-06-11
**Status:** Approved (autonomous; completes the G1 security item from PR #16)
**Branch:** `feat/password-reset-email`

## Goal

Deliver the password-reset token by email so production can set
`EXPOSE_PASSWORD_RESET_TOKEN=False` and stop returning the token in the HTTP response —
closing the account-takeover gap flagged in the bug hunt. **Strictly non-breaking:** when
SMTP is not configured, behavior is exactly as today (token gated by the existing flag).

## Why this is safe / self-contained
- The frontend `ResetPasswordPage` already reads the token from the URL query
  (`searchParams.get("token")`), so an emailed link `…/reset-password?token=<token>` works
  with **zero frontend changes**.
- Uses the Python stdlib `smtplib` (no new dependency; `aiosmtplib` isn't installed), run via
  `asyncio.to_thread` so it never blocks the event loop.
- When `EMAIL_SMTP_HOST` is empty (the default), email is disabled and the forgot-password
  flow falls back to the current behavior unchanged.

## New: `app/services/email.py`
- `email_configured() -> bool` — true iff `settings.EMAIL_SMTP_HOST` is non-empty.
- `async send_email(to, subject, text_body, html_body=None) -> bool` — builds a MIME message
  (`EmailMessage`), sends via `smtplib.SMTP`/`SMTP_SSL` (TLS per `EMAIL_USE_TLS`, auth if
  user/password set), executed in `asyncio.to_thread`. Returns `False` (logged) if not
  configured or on any SMTP error — never raises into the caller.
- `async send_password_reset_email(to, token) -> bool` — builds the reset link
  `f"{settings.FRONTEND_BASE_URL}/reset-password?token={token}"`, a Thai subject + plain-text
  and minimal HTML body containing the link (and the raw token as a fallback to paste), and
  calls `send_email`.

## Config additions (`app/config.py`, with a new "Email" settings group)
- `EMAIL_SMTP_HOST: str = ""`  (empty = disabled)
- `EMAIL_SMTP_PORT: int = 587`
- `EMAIL_SMTP_USER: str = ""`
- `EMAIL_SMTP_PASSWORD: str = ""`
- `EMAIL_FROM: str = ""`  (falls back to `EMAIL_SMTP_USER` if empty)
- `EMAIL_USE_TLS: bool = True`  (STARTTLS; if false and port 465, use SMTP_SSL)
- `FRONTEND_BASE_URL: str = "http://localhost:8080"`

## Wire-up: `app/routers/auth.py` forgot-password
After persisting `user.reset_token` (unchanged), attempt delivery:
```python
emailed = await send_password_reset_email(user.email, token)
resp = {"message": "..."}
if not emailed and settings.EXPOSE_PASSWORD_RESET_TOKEN:
    resp["reset_token"] = token
return resp
```
So: email succeeds → token NOT in response (secure). Email disabled/failed → fall back to the
existing flag behavior. Optionally include `"email_sent": emailed` for the frontend (the
frontend already only shows the token block `if (res.reset_token)`, so this is compatible).

## Tests (`backend/tests/services/test_email.py` + extend `test_auth_reset_token.py`)
- `email_configured`: false when host empty, true when set.
- `send_email`: not configured → returns False without touching SMTP; configured → constructs
  the message and calls a mocked `smtplib.SMTP` (patch `app.services.email.smtplib`), STARTTLS
  + login when creds present; SMTP exception → returns False (logged), no raise.
- `send_password_reset_email`: builds the correct `/reset-password?token=` link and passes it
  to `send_email` (mock send_email); returns its result.
- forgot-password handler: when `send_password_reset_email` returns True → response has NO
  `reset_token`; when it returns False and flag True → response includes `reset_token` (extend
  the existing reset-token tests by also patching the email send).

## Verification
- `cd backend && .venv/bin/python -m pytest tests/ -q` (all green incl. new) + `from app.main import app`.
- No live SMTP server here — send path verified only via mocked `smtplib`.

## Out of scope
- HTML email templating beyond a minimal body; provider-API backends (SendGrid/SES) — SMTP is
  the universal default and the `send_email` impl is the only thing to swap if a provider is
  preferred. Rate-limiting forgot-password. Email verification on signup.
