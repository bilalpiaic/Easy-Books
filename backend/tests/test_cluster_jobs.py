"""#425 — housekeeping prune + ARQ leftover cron registration."""
from datetime import datetime, timedelta

from sqlmodel import Session, select

from models import (
    IdempotencyKey,
    LoginAttempt,
    PasswordResetAttempt,
    RevokedToken,
    TaskDeadLetter,
)
from services.housekeeping import run_housekeeping


def test_housekeeping_prunes_expired_rows_and_reports_open_dlq(client, admin_headers):
    engine = client.app.state.engine
    now = datetime.utcnow()
    old = now - timedelta(days=40)
    with Session(engine) as s:
        s.add(LoginAttempt(ip="1.1.1.1", attempted_at=now - timedelta(hours=3)))
        s.add(LoginAttempt(ip="2.2.2.2", attempted_at=now))
        s.add(PasswordResetAttempt(ip="1.1.1.1", email_key="a", attempted_at=now - timedelta(hours=3)))
        s.add(IdempotencyKey(
            tenant_id=1, key="old", method="POST", path="/x",
            status_code=200, response_body="{}", created_at=now - timedelta(hours=25),
        ))
        s.add(IdempotencyKey(
            tenant_id=1, key="fresh", method="POST", path="/x",
            status_code=200, response_body="{}", created_at=now,
        ))
        s.add(RevokedToken(jti="dead", tenant_id=1, expires_at=now - timedelta(minutes=1)))
        s.add(RevokedToken(jti="live", tenant_id=1, expires_at=now + timedelta(hours=1)))
        s.add(TaskDeadLetter(
            task_name="send_email_task", error="boom", status="open", created_at=old,
        ))
        s.add(TaskDeadLetter(
            task_name="send_email_task", error="old", status="discarded", created_at=old,
        ))
        s.commit()

    with Session(engine) as s:
        stats = run_housekeeping(s, now=now)

    assert stats["login_attempts"] == 1
    assert stats["reset_attempts"] == 1
    assert stats["idempotency_keys"] == 1
    assert stats["revoked_tokens"] == 1
    assert stats["dead_letters_pruned"] == 1
    assert stats["dead_letters_open"] == 1

    with Session(engine) as s:
        ips = {row.ip for row in s.exec(select(LoginAttempt)).all()}
        assert "1.1.1.1" not in ips
        assert "2.2.2.2" in ips
        assert len(s.exec(select(IdempotencyKey)).all()) == 1
        assert s.exec(select(RevokedToken)).one().jti == "live"
        assert s.exec(select(TaskDeadLetter)).one().status == "open"


def test_worker_crons_include_leftover_loops():
    from worker import WorkerSettings
    names = {fn.__name__ for fn in WorkerSettings.functions}
    assert "run_overdue_sweep_task" in names
    assert "run_housekeeping_task" in names
    assert "run_bank_sync_task" in names
    cron_names = {job.coroutine.__name__ for job in WorkerSettings.cron_jobs}
    assert "run_overdue_sweep_task" in cron_names
    assert "drain_webhook_outbox_task" in cron_names
