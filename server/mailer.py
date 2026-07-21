"""Email sender — three backends in priority order:

1. Resend HTTP API  — set RESEND_API_KEY  (free tier: 100 emails/day, no extra package)
2. SMTP             — set SMTP_HOST + SMTP_USER + SMTP_PASSWORD
                      • port 465 → SSL  (Gmail: smtp.gmail.com:465)
                      • port 587 → STARTTLS (Gmail: smtp.gmail.com:587, SendGrid, etc.)
                      Uses Python built-in smtplib — no extra package required.
3. Console fallback — tokens logged to stdout when no provider is configured (dev mode)

Gmail setup (recommended for most deployments):
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=your-gmail@gmail.com
  SMTP_PASSWORD=<16-char App Password from https://myaccount.google.com/apppasswords>
  SMTP_FROM=your-gmail@gmail.com
  APP_BASE_URL=https://your-app-domain.com
"""
import asyncio
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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


def _build_mime(*, from_addr: str, to: str, subject: str, body_text: str, body_html: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["From"]    = _sanitize_header(from_addr)
    msg["To"]      = _sanitize_header(to)
    msg["Subject"] = _sanitize_header(subject)
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html",  "utf-8"))
    return msg


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
                "from": SMTP_FROM or "onboarding@resend.dev",
                "to": [to],
                "subject": subject,
                "text": body_text,
                "html": body_html,
            },
        )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Resend API error {r.status_code}: {r.text[:300]}")


# ---------------------------------------------------------------------------
# Backend 2: SMTP via built-in smtplib (no extra package needed)
# ---------------------------------------------------------------------------

def _send_smtp_sync(*, to: str, subject: str, body_text: str, body_html: str) -> None:
    """Synchronous SMTP send. Auto-selects SSL (port 465) or STARTTLS (other ports)."""
    from_addr = SMTP_FROM or SMTP_USER
    if not from_addr:
        raise RuntimeError("SMTP_FROM or SMTP_USER must be set.")

    msg = _build_mime(from_addr=from_addr, to=to, subject=subject, body_text=body_text, body_html=body_html)

    ctx = ssl.create_default_context()

    if SMTP_PORT == 465:
        # Implicit SSL
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=15) as server:
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(from_addr, [to], msg.as_string())
    else:
        # STARTTLS (port 587 or custom)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(from_addr, [to], msg.as_string())


async def _send_smtp(*, to: str, subject: str, body_text: str, body_html: str) -> None:
    """Async wrapper — runs smtplib in a thread pool so it doesn't block the event loop."""
    await asyncio.to_thread(_send_smtp_sync, to=to, subject=subject, body_text=body_text, body_html=body_html)


# ---------------------------------------------------------------------------
# Backend 3: Dev console fallback
# ---------------------------------------------------------------------------

def _log_fallback(*, to: str, subject: str, body_text: str) -> None:
    log.warning(
        "EMAIL NOT SENT — no provider configured. "
        "Set RESEND_API_KEY or SMTP_HOST+SMTP_USER+SMTP_PASSWORD in server/.env "
        "to enable real email delivery.",
        to=to,
        subject=subject,
        body=body_text,
    )


# ---------------------------------------------------------------------------
# Shared dispatcher
# ---------------------------------------------------------------------------

async def _dispatch(*, to: str, subject: str, body_text: str, body_html: str) -> bool:
    """Try Resend → SMTP → console fallback. Returns True if email was actually sent."""
    if RESEND_API_KEY:
        try:
            await _send_resend(to=to, subject=subject, body_text=body_text, body_html=body_html)
            log.info("email sent via Resend", to=to, subject=subject)
            return True
        except Exception as err:
            log.warning("Resend failed, trying SMTP", error=str(err))

    if SMTP_HOST and SMTP_USER and SMTP_PASSWORD:
        try:
            await _send_smtp(to=to, subject=subject, body_text=body_text, body_html=body_html)
            log.info("email sent via SMTP", to=to, subject=subject, host=SMTP_HOST, port=SMTP_PORT)
            return True
        except Exception as err:
            log.error(
                "SMTP delivery failed — falling back to console log. "
                "Check SMTP_HOST / SMTP_USER / SMTP_PASSWORD in your .env.",
                error=str(err), host=SMTP_HOST, port=SMTP_PORT, user=SMTP_USER,
            )

    _log_fallback(to=to, subject=subject, body_text=body_text)
    return False


async def send_test_email(*, to: str) -> dict:
    """Send a test email and return a result dict (used by admin test endpoint)."""
    subject = "Seelenruh — email test"
    body_text = "This is a test email from Seelenruh. If you received it, email delivery is working."
    body_html = _html_wrap(subject, """
        <p style="font-size:16px;color:#333;margin:0 0 16px;">Email delivery test</p>
        <p style="font-size:14px;color:#555;margin:0 0 8px;line-height:1.6;">
          This test email was sent from your Seelenruh instance.<br>
          If you received it, email delivery is configured correctly.
        </p>
    """)

    provider = None
    error = None

    if RESEND_API_KEY:
        try:
            await _send_resend(to=to, subject=subject, body_text=body_text, body_html=body_html)
            provider = "resend"
        except Exception as err:
            error = f"Resend: {err}"

    if not provider and SMTP_HOST and SMTP_USER and SMTP_PASSWORD:
        try:
            await _send_smtp(to=to, subject=subject, body_text=body_text, body_html=body_html)
            provider = f"smtp ({SMTP_HOST}:{SMTP_PORT})"
        except Exception as err:
            error = f"SMTP: {err}"

    if not provider:
        return {
            "ok": False,
            "provider": None,
            "error": error or "No email provider configured (set RESEND_API_KEY or SMTP_HOST+SMTP_USER+SMTP_PASSWORD)",
        }

    return {"ok": True, "provider": provider, "to": to}


