"""ARQ worker entrypoint (#115).

Run with:  arq worker.WorkerSettings
Requires REDIS_URL. Cron posts due recurring journals daily at 01:00 UTC
and drains the webhook outbox every minute as a belt-and-suspenders path
alongside the FastAPI lifespan loop.
"""
from __future__ import annotations

import os

from arq import cron

from services.queue import redis_settings
from tasks import (
    deliver_webhook_task,
    drain_webhook_outbox_task,
    generate_pdf_task,
    post_recurring_entries_task,
    process_bulk_import_task,
    send_email_task,
)


async def startup(ctx):
    import db as _db
    from sqlmodel import Session
    ctx["db_factory"] = lambda: Session(_db.engine)


async def shutdown(ctx):
    pass


class WorkerSettings:
    functions = [
        send_email_task,
        generate_pdf_task,
        deliver_webhook_task,
        drain_webhook_outbox_task,
        process_bulk_import_task,
        post_recurring_entries_task,
    ]
    cron_jobs = [
        cron(post_recurring_entries_task, hour=1, minute=0),
        cron(drain_webhook_outbox_task, second={0, 30}),  # every 30s
    ]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10


# Bound at import so `arq worker.WorkerSettings` works when REDIS_URL is set.
if os.environ.get("REDIS_URL"):
    WorkerSettings.redis_settings = redis_settings()
