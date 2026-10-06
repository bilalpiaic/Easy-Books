"""Health check (#116 / #427) — live / ready / deep diagnostic."""
from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])

VERSION = os.environ.get("APP_VERSION", "3.0.0")


@router.get("/api/health/live")
async def live():
    """Process is up. No dependency checks — safe as a Docker/K8s liveness probe."""
    return {"status": "ok", "version": VERSION}


@router.get("/api/health/ready")
async def ready():
    """Postgres SELECT 1. Redis is optional and never fails readiness."""
    try:
        import db as _db
        from sqlmodel import Session, text
        with Session(_db.engine) as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:
        return JSONResponse(
            {"status": "not_ready", "db": f"error: {type(exc).__name__}", "version": VERSION},
            status_code=503,
        )
    redis_status = "skipped"
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if redis_url:
        try:
            from redis.asyncio import from_url
            client = from_url(redis_url, socket_connect_timeout=0.5, socket_timeout=0.5)
            await client.ping()
            await client.aclose()
            redis_status = "ok"
        except Exception:
            redis_status = "error"
    return {"status": "ok", "db": "ok", "redis": redis_status, "version": VERSION}


@router.get("/api/health")
async def health():
    """Deep diagnostic — DB + Redis + storage. Not a liveness probe."""
    status = {"db": "ok", "redis": "ok", "storage": "ok", "version": VERSION}
    http = 200

    try:
        import db as _db
        from sqlmodel import Session, text
        with Session(_db.engine) as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:
        status["db"] = f"error: {type(exc).__name__}"
        http = 503

    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        status["redis"] = "skipped"
    else:
        try:
            from redis.asyncio import from_url
            client = from_url(redis_url)
            await client.ping()
            await client.aclose()
        except Exception as exc:
            status["redis"] = f"error: {type(exc).__name__}"
            http = 503

    try:
        from services.storage import storage_ok
        if not storage_ok():
            status["storage"] = "error"
            http = 503
    except Exception as exc:
        status["storage"] = f"error: {type(exc).__name__}"
        http = 503

    return JSONResponse(status, status_code=http)
