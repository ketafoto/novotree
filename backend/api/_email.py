"""
Plain-text SMTP email helper. Used by:

- backend.api.auth             — owner / contributor email verification
- backend.api.privacy_requests — privacy-request notifications, reminders, escalations

Degrades gracefully: returns False (does not raise) when SMTP is not configured
or delivery fails, so caller code never has to guard SMTP availability around
its own logic. The caller decides whether unsent mail is an error.
"""

import logging
from email.message import EmailMessage

import aiosmtplib

from backend.config import settings

logger = logging.getLogger("novotree.backend")


async def send_email(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email. Returns True if delivered, False otherwise."""
    if not settings.smtp_enabled:
        return False

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=True,
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to send email to {to} (subject={subject!r}): {e}")
        return False
