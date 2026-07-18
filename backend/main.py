"""
FastAPI app bootstrap.

Everything that used to live in one 2,100-line file now lives in `routers/`
and `services/`. This file's only job is:
  - Create the FastAPI app + CORS
  - Run schema setup on startup (P1 / Alembic will replace this)
  - Wire up each domain router

Per-domain logic, DTOs, and helpers belong in their respective router module.
"""
import asyncio
import contextlib
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from db import create_db_and_tables
from routers import (
    accounts, admin, advances, aging, analytic_accounts, api_keys, assets, attachments,
    audit, auth, backup, bank_accounts, bank_imports, bills, bom, budgets,
    comparatives, credit_notes, dashboard_layout, customers, debit_notes, deferred_revenue, exchange_rates, gate_inward, gate_outward, grn,
    imports, invoices, manufacturing_reports, modules, payment_terms, payments, periods,
    product_categories, production_orders, products, purchase_demands, purchase_orders, purchase_reports, quotations, rate_plans,
    reconciliations, recurring, report_builder, reports, settings, stock_locations, store_issues, store_reports,
    subledger, tax_codes, telecom, telecom_reports, transactions, users, vendors,
    permissions, commissions, promo_rules, payroll, attendance, system_update,
    search, ai_chat,
)
from routers.pra import pra_router
from routers import healthcare, healthcare_reports
from services.csrf import CsrfMiddleware
from services.idempotency import IdempotencyMiddleware
from services.rate_limit import RateLimitMiddleware


def _run_overdue_sweep_once() -> None:
    """Sync, blocking — called via asyncio.to_thread so it never stalls the
    event loop. Imports db lazily so it always sees the current db.engine
    (tests monkeypatch it, though the scheduler never runs under TestClient
    since lifespan only fires for `with TestClient(app) as c:` usage, which
    no test in this repo uses)."""
    import db as _db
    from sqlmodel import Session as _Session
    from services.overdue import send_overdue_reminders, sweep_overdue
    with _Session(_db.engine) as session:
        changed = sweep_overdue(session)
        sent = send_overdue_reminders(session)
        if changed or sent:
            print(f"[overdue] swept {changed} invoice(s), sent {sent} reminder(s)", flush=True)


async def _overdue_scheduler_loop() -> None:
    """Runs once at startup, then every OVERDUE_SWEEP_INTERVAL_HOURS (default
    24). Both steps are cross-tenant and idempotent per tick — see
    services/overdue.py for the per-tenant reminder throttle."""
    interval_seconds = float(os.environ.get("OVERDUE_SWEEP_INTERVAL_HOURS", "24")) * 3600
    while True:
        try:
            await asyncio.to_thread(_run_overdue_sweep_once)
        except Exception:
            import traceback
            traceback.print_exc()
        await asyncio.sleep(interval_seconds)


def _run_revoked_token_prune_once() -> None:
    """Deletes RevokedToken rows past their expires_at (#113) — the token
    they denylist would have expired on its own by then, so the row is dead
    weight. Sync/blocking; called via asyncio.to_thread. Lazy db import for
    the same reason as _run_overdue_sweep_once."""
    from datetime import datetime as _dt

    import db as _db
    from sqlalchemy import delete as _delete
    from sqlmodel import Session as _Session
    from models import RevokedToken as _RevokedToken
    with _Session(_db.engine) as session:
        result = session.execute(
            _delete(_RevokedToken).where(_RevokedToken.expires_at < _dt.utcnow())
        )
        session.commit()
        if result.rowcount:
            print(f"[revoked-tokens] pruned {result.rowcount} expired row(s)", flush=True)


async def _revoked_token_prune_loop() -> None:
    """Once at startup, then every 6 hours — tokens live 24h, so pruning
    lags expiry by at most a quarter of a token's lifetime, keeping the
    denylist bounded at roughly one day's worth of logouts."""
    while True:
        try:
            await asyncio.to_thread(_run_revoked_token_prune_once)
        except Exception:
            import traceback
            traceback.print_exc()
        await asyncio.sleep(6 * 3600)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # `lifespan` replaces the deprecated @app.on_event("startup") hook.
    # For local dev / SQLite we let SQLModel create tables on demand so a
    # fresh checkout boots without an Alembic step. In production set
    # SCHEMA_BOOTSTRAP=alembic and run `alembic upgrade head` from CI so
    # schema changes are explicit and version-controlled.
    if os.environ.get("SCHEMA_BOOTSTRAP", "create_all") == "create_all":
        create_db_and_tables()

    tasks = []
    if os.environ.get("OVERDUE_SWEEP_ENABLED", "true").lower() != "false":
        tasks.append(asyncio.create_task(_overdue_scheduler_loop()))
    if os.environ.get("REVOKED_TOKEN_PRUNE_ENABLED", "true").lower() != "false":
        tasks.append(asyncio.create_task(_revoked_token_prune_loop()))

    yield

    for task in tasks:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Easy-Books API", lifespan=lifespan)

# Middleware ordering: rate limiting runs first (outermost), then CSRF, then
# idempotency, then CORS. Starlette wraps in reverse-add order, so
# add_middleware last → runs first on the request path. Rate limiting goes
# first so an over-limit request is rejected before any CSRF/idempotency
# work happens; CSRF still rejects before the idempotency cache is
# consulted.
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(CsrfMiddleware)
app.add_middleware(RateLimitMiddleware)

_allowed_origins = [o.strip() for o in os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-CSRF-Token", "Idempotency-Key"],
)

# Routers are listed roughly in the order the UI exercises them so the
# /docs page renders predictably. Each router is mounted twice: at its
# original /api/* path (legacy) and at /api/v1/* (versioned). Future
# breaking changes ship under /api/v2/ without disturbing the legacy
# surface.
_ROUTERS = [
    auth.router, api_keys.router, settings.router, modules.router, accounts.router, customers.router,
    vendors.router, products.router, product_categories.router, aging.router, invoices.router, bills.router,
    report_builder.router,
    payments.router, payment_terms.router, bank_accounts.router,
    reconciliations.router, periods.router, audit.router,
    transactions.router, reports.router, dashboard_layout.router, imports.router,
    tax_codes.router, recurring.router, exchange_rates.router,
    bank_imports.router, stock_locations.router,
    bom.router, rate_plans.router,
    grn.router, production_orders.router,
    manufacturing_reports.router,
    subledger.router,
    attachments.router,
    users.router,
    telecom.router,
    telecom_reports.router,
    credit_notes.router,
    assets.router,
    budgets.router,
    purchase_orders.router,
    purchase_demands.router,
    quotations.router,
    comparatives.router,
    gate_inward.router,
    gate_outward.router,
    store_issues.router,
    store_reports.router,
    purchase_reports.router,
    analytic_accounts.router,
    deferred_revenue.router,
    debit_notes.router,
    advances.router,
    backup.router,
    admin.router,
    permissions.router,
    commissions.router,
    promo_rules.router,
    payroll.router,
    attendance.router,
    healthcare.router,
    healthcare_reports.router,
    system_update.router,
    search.router,
    ai_chat.router,
]

# PRA e-Invoice router mounted separately (not in the shared prefix list above)
app.include_router(pra_router, prefix="/api")

for r in _ROUTERS:
    app.include_router(r)

# ── Version endpoint ──────────────────────────────────────────────────────────

import tomllib as _tomllib
from sqlalchemy import text as _text
from db import engine as _engine

def _read_app_version() -> str:
    try:
        _pyproject = os.path.join(os.path.dirname(__file__), "pyproject.toml")
        with open(_pyproject, "rb") as _f:
            return _tomllib.load(_f)["project"]["version"]
    except Exception:
        return "unknown"

_APP_VERSION = _read_app_version()

@app.get("/api/version")
def get_version():
    """Return the app version and current Alembic revision. No auth required."""
    try:
        with _engine.connect() as _conn:
            row = _conn.execute(_text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
            alembic_head = row[0] if row else "none"
    except Exception:
        alembic_head = "unknown"
    return {"version": _APP_VERSION, "alembic_head": alembic_head}

# ── Stripe webhook ────────────────────────────────────────────────────────────

from fastapi import Request as _Request
from models import Invoice as _Invoice
from db import get_session as _get_session

@app.post("/api/stripe/webhook")
async def stripe_webhook(request: _Request):
    """Handle Stripe Checkout events. G-12."""
    import stripe as _stripe
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if not webhook_secret:
        return {"received": True}
    try:
        event = _stripe.Webhook.construct_event(payload, sig, webhook_secret)
    except Exception:
        from fastapi import HTTPException as _HTTP
        raise _HTTP(400, "Invalid webhook signature")

    if event["type"] == "checkout.session.completed":
        data = event["data"]["object"]
        invoice_id = int(data.get("metadata", {}).get("invoice_id", 0))
        tenant_id = int(data.get("metadata", {}).get("tenant_id", 0))
        if invoice_id and tenant_id:
            with next(_get_session()) as session:
                from sqlmodel import select as _select
                inv = session.exec(
                    _select(_Invoice).where(
                        _Invoice.id == invoice_id, _Invoice.tenant_id == tenant_id
                    )
                ).first()
                if inv:
                    inv.payment_link_status = "paid"
                    session.add(inv)
                    session.commit()
    return {"received": True}


# Serve uploaded files (company logos, attachments) under /uploads/
import pathlib as _pl
_uploads = _pl.Path(__file__).parent / "uploads"
_uploads.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads)), name="uploads")

# v1 alias: a thin pass-through that re-mounts every /api/* route at /api/v1/*
# pointing to the same endpoint function. Future v2 breaking changes ship
# under /api/v2/ without disturbing the legacy surface.
from fastapi.routing import APIRoute

_existing_v1_paths: set[str] = set()
for route in list(app.routes):
    if not isinstance(route, APIRoute):
        continue
    if not route.path.startswith("/api/") or route.path.startswith("/api/v1/"):
        continue
    v1_path = "/api/v1/" + route.path[len("/api/"):]
    if v1_path in _existing_v1_paths:
        continue
    _existing_v1_paths.add(v1_path)
    app.add_api_route(
        v1_path,
        route.endpoint,
        methods=list(route.methods),
        name=f"v1_{route.name}",
        response_model=route.response_model,
        status_code=route.status_code,
        tags=route.tags + ["v1"],
        dependencies=route.dependencies,
        summary=route.summary,
        description=route.description,
        deprecated=route.deprecated,
        operation_id=f"v1_{route.operation_id}" if route.operation_id else None,
        include_in_schema=False,  # keep /docs uncluttered while v1 is identical
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
