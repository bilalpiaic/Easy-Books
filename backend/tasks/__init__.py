"""Background task callables for ARQ (#115).

Each function is also registered in REGISTRY so `services.queue.enqueue`
can run them inline when REDIS_URL is unset.
"""
from __future__ import annotations

from tasks.email import send_email_task
from tasks.pdf import generate_pdf_task
from tasks.webhooks import deliver_webhook_task, drain_webhook_outbox_task
from tasks.imports import process_bulk_import_task
from tasks.recurring import post_recurring_entries_task
from tasks.insights import scan_insights_task
from tasks.dunning import run_dunning_rules_task

REGISTRY = {
    "send_email_task": send_email_task,
    "generate_pdf_task": generate_pdf_task,
    "deliver_webhook_task": deliver_webhook_task,
    "drain_webhook_outbox_task": drain_webhook_outbox_task,
    "process_bulk_import_task": process_bulk_import_task,
    "post_recurring_entries_task": post_recurring_entries_task,
    "scan_insights_task": scan_insights_task,
    "run_dunning_rules_task": run_dunning_rules_task,
}

__all__ = list(REGISTRY.keys()) + ["REGISTRY"]
