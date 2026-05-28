"""SMTP email service for transactional notifications.

Configure via env vars:
  SMTP_HOST     — SMTP server hostname (required to enable sending)
  SMTP_PORT     — port, default 587
  SMTP_USER     — login username
  SMTP_PASSWORD — login password
  FROM_EMAIL    — sender address, defaults to SMTP_USER

All send calls silently no-op when SMTP_HOST is not configured, so the app
works in dev without any email setup.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(to: str, subject: str, html_body: str) -> None:
    """Send an HTML email. Silently no-ops when SMTP_HOST is not set."""
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    if not smtp_host:
        return  # email not configured; skip

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    from_addr = os.getenv("FROM_EMAIL", smtp_user) or smtp_user

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as srv:
            srv.ehlo()
            srv.starttls()
            if smtp_user:
                srv.login(smtp_user, smtp_pass)
            srv.sendmail(from_addr, [to], msg.as_string())
    except Exception:
        # Log but don't crash the request if email fails
        import traceback
        traceback.print_exc()
