"""Task status API (#115) — poll ARQ job results."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services.queue import job_status
from .common import CurrentUserDep

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/{job_id}")
async def get_task_status(job_id: str, _user: CurrentUserDep):
    """Return `{status, result, error}` for an ARQ (or sync-fallback) job."""
    info = await job_status(job_id)
    if info.get("status") == "not_found":
        raise HTTPException(404, "Task not found")
    return info
