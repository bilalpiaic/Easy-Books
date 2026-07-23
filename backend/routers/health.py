"""Health check (#116) — db / redis / storage probes for compose + Caddy."""
from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])

VERSION = os.environ.get("APP_VERSION", "3.0.0")


@router.get("/api/health")
async def health():
    status = {"db": "ok", "redis": "ok", "storage": "ok", "version": VERSION}
    http = 200

    # DB
    try:
        import db as _db
        from sqlmodel import Session, text
        with Session(_db.engine) as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:
        status["db"] = f"error: {type(exc).__name__}"
        http = 503

    # Redis — optional; report "skipped" when REDIS_URL unset (offline install)
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

    # Storage
    try:
        from services.storage import storage_ok
        if not storage_ok():
            status["storage"] = "error"
            http = 503
    except Exception as exc:
        status["storage"] = f"error: {type(exc).__name__}"
        http = 503

    return JSONResponse(status, status_code=http)
