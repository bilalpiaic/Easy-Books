"""Sync cluster jobs shared by the API lifespan and the ARQ worker (#425).

Lazy-import db.engine so tests that monkeypatch ``db.engine`` are visible.
"""
from __future__ import annotations


def run_overdue_sweep_once() -> dict:
    """Sweep overdue invoices, send throttled reminders, refresh ops alerts."""
    import db as _db
    from sqlmodel import Session as _Session
    from services.overdue import send_overdue_reminders, sweep_overdue
    from services.alerts import refresh_ops_alerts

    with _Session(_db.engine) as session:
        changed = sweep_overdue(session)
        sent = send_overdue_reminders(session)
        alerts_n = refresh_ops_alerts(session, force=True)
        if changed or sent or alerts_n:
            print(
                f"[overdue] swept {changed} invoice(s), sent {sent} reminder(s), "
                f"alerts +{alerts_n}",
                flush=True,
            )
        return {"changed": changed, "sent": sent, "alerts": alerts_n}


def run_housekeeping_once() -> dict:
    import db as _db
    from sqlmodel import Session as _Session
    from services.housekeeping import run_housekeeping

    with _Session(_db.engine) as session:
        stats = run_housekeeping(session)
    pruned = (
        stats["revoked_tokens"]
        + stats["login_attempts"]
        + stats["reset_attempts"]
        + stats["idempotency_keys"]
        + stats["dead_letters_pruned"]
    )
    if pruned or stats["dead_letters_open"]:
        print(
            f"[housekeeping] pruned={pruned} open_dlq={stats['dead_letters_open']}",
            flush=True,
        )
    return stats


def run_webhook_drain_once() -> int:
    import db as _db
    from sqlmodel import Session as _Session
    from services.events import drain_once

    with _Session(_db.engine) as session:
        return drain_once(session)


def run_bank_sync_once() -> dict:
    import db as _db
    from sqlmodel import Session as _Session
    from services.bank_sync import sync_all_active_connections

    with _Session(_db.engine) as session:
        counts = sync_all_active_connections(session)
        if counts.get("ok") or counts.get("error"):
            print(
                f"[bank-sync] ok={counts.get('ok', 0)} error={counts.get('error', 0)} "
                f"skipped={counts.get('skipped', 0)}",
                flush=True,
            )
        return counts
