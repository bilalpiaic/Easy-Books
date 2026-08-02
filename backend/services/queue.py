"""ARQ task-queue helpers (#115) + dead-letter recording (#271).

When REDIS_URL is set, jobs go to Redis via ARQ. When unset (Electron /
script install / local pytest), `enqueue` awaits the task in-process so
callers keep a uniform API and offline installs never depend on Redis.

Failed runs (inline or reported) land in `TaskDeadLetter` for admin retry.
"""
from __future__ import annotations

import inspect
import json
import os
from datetime import datetime
from typing import Any, Optional

_REDIS_URL = os.environ.get("REDIS_URL", "").strip()
_pool = None


def redis_configured() -> bool:
    return bool(_REDIS_URL)


def redis_settings():
    from arq.connections import RedisSettings
    return RedisSettings.from_dsn(_REDIS_URL)


async def get_pool():
    """Lazy ARQ pool; None when Redis is not configured."""
    global _pool
    if not _REDIS_URL:
        return None
    if _pool is None:
        from arq import create_pool
        _pool = await create_pool(redis_settings())
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value, default=str)
        return value
    except Exception:
        return str(value)


def record_dead_letter(
    *,
    task_name: str,
    error: str,
    args: tuple = (),
    kwargs: Optional[dict] = None,
    tenant_id: Optional[int] = None,
) -> Optional[int]:
    """Persist a failed job for the DLQ UI. Best-effort — never raises."""
    try:
        from db import engine
        from models import TaskDeadLetter
        from sqlmodel import Session

        kwargs = kwargs or {}
        # Prefer explicit tenant_id kwarg; fall back to first int arg named patterns
        tid = tenant_id
        if tid is None and "tenant_id" in kwargs:
            try:
                tid = int(kwargs["tenant_id"])
            except (TypeError, ValueError):
                tid = None
        row = TaskDeadLetter(
            tenant_id=tid,
            task_name=task_name,
            args_json=json.dumps([_json_safe(a) for a in args], default=str),
            kwargs_json=json.dumps({k: _json_safe(v) for k, v in kwargs.items()}, default=str),
            error=(error or "unknown error")[:2000],
            status="open",
            created_at=datetime.utcnow(),
        )
        with Session(engine) as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.id
    except Exception as exc:
        print(f"[queue] DLQ record failed: {type(exc).__name__}: {exc}")
        return None


async def enqueue(
    function_name: str,
    *args: Any,
    _defer_by: Optional[float] = None,
    **kwargs: Any,
) -> dict:
    """Enqueue an ARQ job, or run the matching task in-process without Redis.

    Returns `{job_id, status}` — sync path may already be `complete`/`failed`
    with optional `result`/`error`.
    """
    pool = await get_pool()
    if pool is None:
        return await _run_inline(function_name, *args, **kwargs)
    job = await pool.enqueue_job(
        function_name, *args, _defer_by=_defer_by, **kwargs
    )
    return {"job_id": job.job_id if job else None, "status": "queued"}


async def _run_inline(function_name: str, *args: Any, **kwargs: Any) -> dict:
    from tasks import REGISTRY
    fn = REGISTRY.get(function_name)
    if fn is None:
        err = f"unknown task {function_name}"
        record_dead_letter(task_name=function_name, error=err, args=args, kwargs=kwargs)
        return {
            "job_id": None,
            "status": "failed",
            "error": err,
        }
    try:
        ctx: dict = {"redis": None}
        result = fn(ctx, *args, **kwargs)
        if inspect.isawaitable(result):
            result = await result
        return {
            "job_id": f"sync-{function_name}",
            "status": "complete",
            "result": result,
        }
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
        dlq_id = record_dead_letter(
            task_name=function_name, error=err, args=args, kwargs=kwargs,
        )
        return {
            "job_id": None,
            "status": "failed",
            "error": err,
            "dead_letter_id": dlq_id,
        }


async def job_status(job_id: str) -> dict:
    """Look up an ARQ job. Sync ids return a synthetic complete payload."""
    if job_id.startswith("sync-"):
        return {"status": "complete", "result": None, "error": None}
    pool = await get_pool()
    if pool is None:
        return {"status": "unknown", "result": None, "error": "Redis not configured"}
    from arq.jobs import Job
    job = Job(job_id, pool)
    try:
        info = await job.info()
    except Exception as exc:
        return {"status": "unknown", "result": None, "error": str(exc)}
    if info is None:
        return {"status": "not_found", "result": None, "error": None}
    status = info.status.value if hasattr(info.status, "value") else str(info.status)
    # Normalize ARQ status names toward the issue's `{status: complete}` shape.
    if status in ("complete", "completed"):
        status = "complete"
    return {
        "status": status,
        "result": info.result if status == "complete" else None,
        "error": str(info.result) if status == "failed" else None,
    }


async def queue_depth() -> dict:
    """Best-effort ARQ queue depth; zeros when Redis is unset."""
    pool = await get_pool()
    if pool is None:
        return {"redis": False, "queued": 0}
    try:
        # ARQ default queue key
        n = await pool.queued_jobs()
        return {"redis": True, "queued": len(n) if n is not None else 0}
    except Exception:
        try:
            raw = await pool.redis.llen("arq:queue")
            return {"redis": True, "queued": int(raw or 0)}
        except Exception as exc:
            return {"redis": True, "queued": 0, "error": str(exc)[:200]}
