"""Cluster housekeeping (#425) — prune bounded tables and report the DLQ.

Desktop runs this from the API lifespan when Redis is unset. SaaS/compose
run it from the ARQ worker cron so API replicas do not each delete rows.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlmodel import Session

from models import (
    IdempotencyKey,
    LoginAttempt,
    PasswordResetAttempt,
    RevokedToken,
    TaskDeadLetter,
)

LOGIN_ATTEMPT_TTL = timedelta(hours=1)
RESET_ATTEMPT_TTL = timedelta(hours=1)
IDEMPOTENCY_TTL = timedelta(hours=24)
DEAD_LETTER_TTL = timedelta(days=30)


def run_housekeeping(session: Session, *, now: datetime | None = None) -> dict:
    """Prune expired rows. Returns counts for logs / ARQ result payloads."""
    now = now or datetime.utcnow()
    revoked = session.execute(
        delete(RevokedToken).where(RevokedToken.expires_at < now)
    ).rowcount or 0
    logins = session.execute(
        delete(LoginAttempt).where(LoginAttempt.attempted_at < now - LOGIN_ATTEMPT_TTL)
    ).rowcount or 0
    resets = session.execute(
        delete(PasswordResetAttempt).where(
            PasswordResetAttempt.attempted_at < now - RESET_ATTEMPT_TTL
        )
    ).rowcount or 0
    idem = session.execute(
        delete(IdempotencyKey).where(IdempotencyKey.created_at < now - IDEMPOTENCY_TTL)
    ).rowcount or 0
    dlq_closed = session.execute(
        delete(TaskDeadLetter).where(
            TaskDeadLetter.status.in_(("retried", "discarded")),
            TaskDeadLetter.created_at < now - DEAD_LETTER_TTL,
        )
    ).rowcount or 0
    open_dlq = session.execute(
        select(func.count()).select_from(TaskDeadLetter).where(
            TaskDeadLetter.status == "open",
        )
    ).scalar_one()
    session.commit()
    return {
        "revoked_tokens": int(revoked),
        "login_attempts": int(logins),
        "reset_attempts": int(resets),
        "idempotency_keys": int(idem),
        "dead_letters_pruned": int(dlq_closed),
        "dead_letters_open": int(open_dlq or 0),
    }
