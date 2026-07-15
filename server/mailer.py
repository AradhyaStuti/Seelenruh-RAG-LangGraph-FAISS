"""Email sender — aiosmtplib when SMTP_HOST is set, console output otherwise (dev)."""
from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, APP_BASE_URL
from logger import get_logger

log = get_logger("mailer")


def _sanitize_header(value: str) -> str:
    """Strip CR/LF to prevent email header injection."""
    return value.replace("\r", "").replace("\n", "")


async def _send_smtp(*, to: str, subject: str, body: str) -> None:
    """Send a plain-text email via SMTP/STARTTLS."""
    try:
        import aiosmtplib  # optional dep
    except ImportError:
        log.warning("aiosmtplib not installed — add it to requirements.txt for real email")
        _log_fallback(to=to, subject=subject, body=body)
        return

    safe_to = _sanitize_header(to)
    safe_subject = _sanitize_header(subject)
    message = (
        f"From: {SMTP_FROM or SMTP_USER}\r\n"
        f"To: {safe_to}\r\n"
        f"Subject: {safe_subject}\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n"
        f"\r\n"
        f"{body}"
    )
    await aiosmtplib.send(
        message,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER,
        password=SMTP_PASSWORD,
        start_tls=True,
    )


def _log_fallback(*, to: str, subject: str, body: str) -> None:
    """Dev-mode fallback: log the email content (no SMTP configured)."""
    log.info("no SMTP configured — email not sent", to=to, subject=subject, body=body)


async def send_password_reset(*, to: str, token: str) -> None:
    link = f"{APP_BASE_URL}/reset-password?token={token}"
    subject = "Reset your Seelenruh password"
    body = (
        f"Hi,\n\n"
        f"Someone (hopefully you) requested a password reset for your Seelenruh account.\n\n"
        f"Click the link below to set a new password. It expires in 1 hour.\n\n"
        f"  {link}\n\n"
        f"If you didn't request this, you can safely ignore this email.\n\n"
        f"— Seelenruh"
    )
    if SMTP_HOST:
        try:
            await _send_smtp(to=to, subject=subject, body=body)
            log.info("password-reset email sent", to=to)
            return
        except Exception as err:
            log.warning("SMTP failed, falling back to console log", error=str(err))
    _log_fallback(to=to, subject=subject, body=body)


async def send_email_verification(*, to: str, token: str) -> None:
    link = f"{APP_BASE_URL}/verify-email?token={token}"
    subject = "Verify your Seelenruh email address"
    body = (
        f"Hi,\n\n"
        f"Welcome to Seelenruh! Please verify your email address by clicking the link below.\n\n"
        f"  {link}\n\n"
        f"This link expires in 24 hours.\n\n"
        f"— Seelenruh"
    )
    if SMTP_HOST:
        try:
            await _send_smtp(to=to, subject=subject, body=body)
            log.info("verification email sent", to=to)
            return
        except Exception as err:
            log.warning("SMTP failed, falling back to console log", error=str(err))
    _log_fallback(to=to, subject=subject, body=body)
