"""Email task — wraps services.email.send_email for the ARQ worker."""
from __future__ import annotations


async def send_email_task(ctx, to: str, subject: str, body_html: str) -> dict:
    from services.email import send_email
    send_email(to, subject, body_html)
    return {"ok": True, "to": to}
