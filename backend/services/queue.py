"""ARQ task-queue helpers (#115).

When REDIS_URL is set, jobs go to Redis via ARQ. When unset (Electron /
script install / local pytest), `enqueue` awaits the task in-process so
callers keep a uniform API and offline installs never depend on Redis.
"""
from __future__ import annotations

import inspect
import os
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
        return {
            "job_id": None,
            "status": "failed",
            "error": f"unknown task {function_name}",
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
        return {
            "job_id": None,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
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
