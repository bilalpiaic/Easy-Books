"""ARQ worker entrypoint (#115 / #425).

Run with:  arq worker.WorkerSettings
Requires REDIS_URL. Crons own overdue sweep, webhook drain, bank sync, and
housekeeping so API replicas (APP_ROLE=api) do not double-send. Desktop
without Redis keeps the FastAPI lifespan loops instead.
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
    run_bank_sync_task,
    run_dunning_rules_task,
    run_housekeeping_task,
    run_overdue_sweep_task,
    scan_insights_task,
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
        scan_insights_task,
        run_dunning_rules_task,
        run_overdue_sweep_task,
        run_housekeeping_task,
        run_bank_sync_task,
    ]
    cron_jobs = [
        cron(post_recurring_entries_task, hour=1, minute=0),
        cron(drain_webhook_outbox_task, second={0, 30}),
        cron(scan_insights_task, hour=2, minute=0),
        cron(run_dunning_rules_task, hour=3, minute=0),
        cron(run_overdue_sweep_task, minute=0),
        cron(run_housekeeping_task, hour={0, 6, 12, 18}, minute=20),
        cron(run_bank_sync_task, hour=5, minute=0),
    ]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10


# Bound at import so `arq worker.WorkerSettings` works when REDIS_URL is set.
if os.environ.get("REDIS_URL"):
    WorkerSettings.redis_settings = redis_settings()
