"""Task status API (#115) + dead-letter queue (#271)."""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from models import TaskDeadLetter, WebhookDelivery
from services.queue import enqueue, job_status, queue_depth, redis_configured
from .common import AdminUserDep, CurrentUserDep, SessionDep, log_audit

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/dead-letter")
def list_dead_letter(
    session: SessionDep,
    user: AdminUserDep,
    status: str = "open",
    limit: int = 100,
):
    """Failed PDF/email/import jobs visible to tenant admins (#271)."""
    q = select(TaskDeadLetter).where(
        (TaskDeadLetter.tenant_id == user.tenant_id) | (TaskDeadLetter.tenant_id.is_(None))  # type: ignore
    )
    if status and status != "all":
        q = q.where(TaskDeadLetter.status == status)
    rows = session.exec(
        q.order_by(TaskDeadLetter.id.desc()).limit(min(limit, 200))  # type: ignore
    ).all()
    return [
        {
            "id": r.id,
            "tenant_id": r.tenant_id,
            "task_name": r.task_name,
            "args_json": r.args_json,
            "kwargs_json": r.kwargs_json,
            "error": r.error,
            "status": r.status,
            "created_at": r.created_at,
            "retried_at": r.retried_at,
        }
        for r in rows
    ]


@router.post("/dead-letter/{dlq_id}/retry")
async def retry_dead_letter(dlq_id: int, session: SessionDep, user: AdminUserDep):
    """Re-enqueue a dead-lettered job and mark the DLQ row retried."""
    row = session.get(TaskDeadLetter, dlq_id)
    if not row or (row.tenant_id is not None and row.tenant_id != user.tenant_id):
        raise HTTPException(404, "Dead-letter entry not found")
    try:
        args = json.loads(row.args_json or "[]")
        kwargs = json.loads(row.kwargs_json or "{}")
        if not isinstance(args, list):
            args = []
        if not isinstance(kwargs, dict):
            kwargs = {}
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"Corrupt DLQ payload: {exc}") from exc
    result = await enqueue(row.task_name, *args, **kwargs)
    row.status = "retried"
    row.retried_at = datetime.utcnow()
    session.add(row)
    log_audit(
        session, user, "RETRY", "task_dead_letter", row.id,
        {"task_name": row.task_name, "enqueue": result.get("status")},
    )
    session.commit()
    return {"dead_letter_id": row.id, "enqueue": result}


@router.get("/ops")
async def ops_metrics(session: SessionDep, user: AdminUserDep):
    """Basic admin metrics: queue depth + webhook failure rate (#271)."""
    from datetime import timedelta

    since = datetime.utcnow() - timedelta(hours=24)
    wh_total = session.exec(
        select(func.count()).select_from(WebhookDelivery).where(
            WebhookDelivery.tenant_id == user.tenant_id,
            WebhookDelivery.created_at >= since,
        )
    ).one()
    wh_failed = session.exec(
        select(func.count()).select_from(WebhookDelivery).where(
            WebhookDelivery.tenant_id == user.tenant_id,
            WebhookDelivery.status == "failed",
            WebhookDelivery.created_at >= since,
        )
    ).one()
    wh_pending = session.exec(
        select(func.count()).select_from(WebhookDelivery).where(
            WebhookDelivery.tenant_id == user.tenant_id,
            WebhookDelivery.status == "pending",
        )
    ).one()
    dlq_open = session.exec(
        select(func.count()).select_from(TaskDeadLetter).where(
            TaskDeadLetter.status == "open",
            (TaskDeadLetter.tenant_id == user.tenant_id) | (TaskDeadLetter.tenant_id.is_(None)),  # type: ignore
        )
    ).one()
    total_n = int(wh_total or 0)
    failed_n = int(wh_failed or 0)
    depth = await queue_depth()
    return {
        "redis_configured": redis_configured(),
        "queue": depth,
        "webhook": {
            "window_hours": 24,
            "total": total_n,
            "failed": failed_n,
            "pending": int(wh_pending or 0),
            "failure_rate": round(failed_n / total_n, 4) if total_n else 0.0,
        },
        "dead_letter_open": int(dlq_open or 0),
    }


@router.get("/{job_id}")
async def get_task_status(job_id: str, _user: CurrentUserDep):
    """Return `{status, result, error}` for an ARQ (or sync-fallback) job."""
    # Avoid colliding with static paths if a client hits /api/tasks/dead-letter
    # as a job id — those routes are registered above.
    info = await job_status(job_id)
    if info.get("status") == "not_found":
        raise HTTPException(404, "Task not found")
    return info
