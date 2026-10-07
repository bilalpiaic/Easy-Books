"""ARQ wrappers for leftover API-lifespan loops (#425)."""
from __future__ import annotations


async def run_overdue_sweep_task(ctx) -> dict:
    from services.cluster_jobs import run_overdue_sweep_once
    return run_overdue_sweep_once()


async def run_housekeeping_task(ctx) -> dict:
    from services.cluster_jobs import run_housekeeping_once
    return run_housekeeping_once()


async def run_bank_sync_task(ctx) -> dict:
    from services.cluster_jobs import run_bank_sync_once
    return run_bank_sync_once()
