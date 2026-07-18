"""Email sender — three backends in priority order:

1. Resend HTTP API  — set RESEND_API_KEY  (free tier: 100 emails/day, no extra package)
2. SMTP/STARTTLS    — set SMTP_HOST + SMTP_USER + SMTP_PASSWORD  (Gmail, Outlook, etc.)
3. Console fallback — dev mode when no provider is configured (tokens logged, not sent)

HTML emails are sent so links are clickable on all email clients.
"""
import asyncio

import httpx

from config import (
    RESEND_API_KEY,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM,
    APP_BASE_URL,
)
from logger import get_logger

log = get_logger("mailer")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_header(value: str) -> str:
    """Strip CR/LF to prevent email header injection."""
    return value.replace("\r", "").replace("\n", "")


def _html_wrap(subject: str, body_html: str) -> str:
    """Minimal responsive HTML email wrapper."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{subject}</title></head>
<body style="margin:0;padding:0;background:#f6f6f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f6f6f9;padding:32px 0;">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;padding:40px 36px;box-shadow:0 2px 12px rgba(0,0,0,0.07);">
        <tr><td>
          <p style="margin:0 0 4px;font-size:22px;font-weight:700;color:#1a1a2e;">Seelenruh</p>
          <p style="margin:0 0 28px;font-size:13px;color:#888;">peace of mind, powered by AI</p>
          {body_html}
          <p style="margin:28px 0 0;font-size:12px;color:#aaa;border-top:1px solid #eee;padding-top:16px;">
            If you didn't request this, you can safely ignore this email.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Backend 1: Resend HTTP API
# ---------------------------------------------------------------------------

async def _send_resend(*, to: str, subject: str, body_text: str, body_html: str) -> None:
    """Send via Resend API (https://resend.com). No extra package — uses httpx."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": SMTP_FROM,
                "to": [to],
                "subject": subject,
                "text": body_text,
                "html": body_html,
            },
        )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Resend API error {r.status_code}: {r.text[:200]}")


# ---------------------------------------------------------------------------
# Backend 2: SMTP/STARTTLS
# ---------------------------------------------------------------------------

async def _send_smtp(*, to: str, subject: str, body_text: str, body_html: str) -> None:
    """Send via SMTP with STARTTLS. Requires aiosmtplib (optional dep)."""
    try:
        import aiosmtplib
    except ImportError:
        log.warning("aiosmtplib not installed — add it to requirements.txt for SMTP support")
        raise RuntimeError("aiosmtplib not installed")

    safe_to = _sanitize_header(to)
    safe_subject = _sanitize_header(subject)
    from_addr = SMTP_FROM or SMTP_USER

    # Multipart MIME: plain text + HTML
    boundary = "==_seelenruh_boundary_=="
    message = (
        f"From: {from_addr}\r\n"
        f"To: {safe_to}\r\n"
        f"Subject: {safe_subject}\r\n"
        f"MIME-Version: 1.0\r\n"
        f"Content-Type: multipart/alternative; boundary=\"{boundary}\"\r\n"
        f"\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        f"{body_text}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: text/html; charset=utf-8\r\n\r\n"
        f"{body_html}\r\n"
        f"--{boundary}--\r\n"
    )
    await aiosmtplib.send(
        message,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER,
        password=SMTP_PASSWORD,
        start_tls=True,
    )


# ---------------------------------------------------------------------------
# Backend 3: Dev console fallback
# ---------------------------------------------------------------------------

def _log_fallback(*, to: str, subject: str, body_text: str) -> None:
    """No email provider configured — print token to server console (dev mode only)."""
    log.info(
        "DEV MODE — email not sent (configure RESEND_API_KEY or SMTP_HOST to enable)",
        to=to,
        subject=subject,
        body=body_text,
    )


# ---------------------------------------------------------------------------
# Shared dispatcher
# ---------------------------------------------------------------------------

async def _dispatch(*, to: str, subject: str, body_text: str, body_html: str) -> None:
    """Try Resend → SMTP → console fallback."""
    if RESEND_API_KEY:
        try:
            await _send_resend(to=to, subject=subject, body_text=body_text, body_html=body_html)
            log.info("email sent via Resend", to=to, subject=subject)
            return
        except Exception as err:
            log.warning("Resend failed, trying SMTP", error=str(err))

    if SMTP_HOST:
        try:
            await _send_smtp(to=to, subject=subject, body_text=body_text, body_html=body_html)
            log.info("email sent via SMTP", to=to, subject=subject)
            return
        except Exception as err:
            log.warning("SMTP failed, falling back to console log", error=str(err))

    _log_fallback(to=to, subject=subject, body_text=body_text)


# ---------------------------------------------------------------------------
# Public email functions
# ---------------------------------------------------------------------------

async def send_password_reset(*, to: str, token: str) -> None:
    link = f"{APP_BASE_URL}/reset-password?token={token}"
    subject = "Reset your Seelenruh password"
    body_text = (
        f"Hi,\n\n"
        f"Someone (hopefully you) requested a password reset for your Seelenruh account.\n\n"
        f"Click the link below to set a new password. It expires in 1 hour.\n\n"
        f"  {link}\n\n"
        f"If you didn't request this, you can safely ignore this email.\n\n"
        f"— Seelenruh"
    )
    body_html = _html_wrap(subject, f"""
        <p style="font-size:16px;color:#333;margin:0 0 16px;">Password Reset Request</p>
        <p style="font-size:14px;color:#555;margin:0 0 24px;line-height:1.6;">
          Someone (hopefully you) requested a password reset for your Seelenruh account.
          Click the button below to set a new password. The link expires in <strong>1 hour</strong>.
        </p>
        <a href="{link}" style="display:inline-block;background:#6366f1;color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:600;">
          Reset Password
        </a>
        <p style="margin:20px 0 0;font-size:12px;color:#999;">
          Or copy this link: <span style="color:#6366f1;">{link}</span>
        </p>
    """)
    await _dispatch(to=to, subject=subject, body_text=body_text, body_html=body_html)


async def send_email_verification(*, to: str, token: str) -> None:
    link = f"{APP_BASE_URL}/verify-email?token={token}"
    subject = "Verify your Seelenruh email address"
    body_text = (
        f"Hi,\n\n"
        f"Welcome to Seelenruh! Please verify your email address by clicking the link below.\n\n"
        f"  {link}\n\n"
        f"This link expires in 24 hours.\n\n"
        f"— Seelenruh"
    )
    body_html = _html_wrap(subject, f"""
        <p style="font-size:16px;color:#333;margin:0 0 16px;">Welcome to Seelenruh!</p>
        <p style="font-size:14px;color:#555;margin:0 0 24px;line-height:1.6;">
          Please verify your email address to complete your account setup.
          The link expires in <strong>24 hours</strong>.
        </p>
        <a href="{link}" style="display:inline-block;background:#6366f1;color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-size:14px;font-weight:600;">
          Verify Email Address
        </a>
        <p style="margin:20px 0 0;font-size:12px;color:#999;">
          Or copy this link: <span style="color:#6366f1;">{link}</span>
        </p>
    """)
    await _dispatch(to=to, subject=subject, body_text=body_text, body_html=body_html)
