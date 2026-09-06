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
    accounts, admin, advances, aging, alerts, analytic_accounts, analytic_dimensions, api_keys, assets, attachments,
    audit, auth, backup, bank_accounts, bank_imports, bills, bom, budgets, pos, ecommerce,
    comparatives, credit_notes, dashboard_layout, dashboard_ops, customers, debit_notes, deferred_revenue, exchange_rates, gate_inward, gate_outward, grn,
    imports, invoices, manufacturing_reports, modules, payment_terms, payments, periods,
    product_categories, production_orders, products, purchase_demands, purchase_orders, purchase_reports, quotations, rate_plans,
    reconciliations, recurring, report_builder, reports, settings, scrap_reasons, stock_locations, stock_transfers, pick_lists, store_issues, store_reports,
    subledger, tax_codes, telecom, telecom_reports, transactions, users, vendors,
    permissions, commissions, promo_rules, payroll, attendance, leave, expense_claims, system_update,
    search, ai_chat, webhooks, tasks, health,
    billing, portal, approvals, bank_feeds, agent_ext, inventory_depth,
    consolidation, leases, contract_assets, intercompany, india_gst,
    practice, custom_fields, form_schema, print_templates, ops_tenants,
)
from routers.pra import pra_router
from routers.uae_einvoice import uae_router
from routers.zatca import zatca_router
from routers.peppol import peppol_router
from routers import marketplace
from routers import healthcare, healthcare_reports, healthcare_dialysis
from routers import weaving, weaving_reports, weaving_calculators
from routers import spinning, spinning_reports, spinning_calculators
from routers import textile_processing, textile_processing_reports
# Side-effect import: registers TOTP/OAuth routes on auth.router (#118)
import routers.auth_security  # noqa: F401
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


def _run_webhook_drain_once() -> int:
    """Sync, blocking — via asyncio.to_thread. Lazy db import for the same
    reason as _run_overdue_sweep_once."""
    import db as _db
    from sqlmodel import Session as _Session
    from services.events import drain_once
    with _Session(_db.engine) as session:
        return drain_once(session)


async def _webhook_delivery_loop() -> None:
    """Drains the WebhookDelivery outbox (#114): woken instantly by emit()
    via a threadsafe Event, with a POLL_SECONDS fallback tick that picks up
    retry-due rows and anything queued outside this process. Loops while
    a batch came back full, so bursts drain without waiting for the next
    wake."""
    from services import events as _events
    wake = asyncio.Event()
    _events.register_wake(asyncio.get_running_loop(), wake)
    while True:
        try:
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(wake.wait(), timeout=_events.POLL_SECONDS)
            wake.clear()
            await asyncio.sleep(1)     # let the emitting request commit first
            while await asyncio.to_thread(_run_webhook_drain_once) >= _events.BATCH_SIZE:
                pass
        except asyncio.CancelledError:
            raise
        except Exception:
            import traceback
            traceback.print_exc()
            await asyncio.sleep(5)


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


def _run_bank_sync_once() -> None:
    """Pull-only bank feed sync (#301). EU/UK Open Banking has no bank-side
    webhooks — schedule + on-demand sync are the real path. Lazy db import
    matches the overdue sweep pattern."""
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


async def _bank_sync_scheduler_loop() -> None:
    """Once at startup, then every BANK_SYNC_INTERVAL_HOURS (default 24)."""
    interval_seconds = float(os.environ.get("BANK_SYNC_INTERVAL_HOURS", "24")) * 3600
    while True:
        try:
            await asyncio.to_thread(_run_bank_sync_once)
        except Exception:
            import traceback
            traceback.print_exc()
        await asyncio.sleep(interval_seconds)


def _env_flag(name: str, default: str = "true") -> bool:
    return os.environ.get(name, default).lower() not in ("0", "false", "no", "off")


def _is_serverless() -> bool:
    """Vercel (and similar) set VERCEL=1 — background loops can't survive
    across invocations, so default them off unless explicitly re-enabled."""
    return os.environ.get("VERCEL", "").lower() in ("1", "true")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # `lifespan` replaces the deprecated @app.on_event("startup") hook.
    # For local dev / SQLite we let SQLModel create tables on demand so a
    # fresh checkout boots without an Alembic step. In production set
    # SCHEMA_BOOTSTRAP=alembic and run `alembic upgrade head` from CI so
    # schema changes are explicit and version-controlled.
    if os.environ.get("SCHEMA_BOOTSTRAP", "create_all") == "create_all":
        create_db_and_tables()

    # On Vercel, long-lived asyncio loops do nothing useful (the function
    # freezes between requests). Opt in explicitly if you wire an external
    # cron to hit a sweep endpoint instead.
    _bg_default = "false" if _is_serverless() else "true"
    tasks = []
    if _env_flag("OVERDUE_SWEEP_ENABLED", _bg_default):
        tasks.append(asyncio.create_task(_overdue_scheduler_loop()))
    if _env_flag("REVOKED_TOKEN_PRUNE_ENABLED", _bg_default):
        tasks.append(asyncio.create_task(_revoked_token_prune_loop()))
    if _env_flag("WEBHOOKS_ENABLED", _bg_default):
        tasks.append(asyncio.create_task(_webhook_delivery_loop()))
    # Bank feeds: pull-only schedule (#301). Off on Vercel unless explicitly enabled.
    if _env_flag("BANK_SYNC_ENABLED", _bg_default):
        tasks.append(asyncio.create_task(_bank_sync_scheduler_loop()))

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


@app.middleware("http")
async def check_tenant_suspension(request, call_next):
    """Suspended tenants get 402 on accounting routes (#119)."""
    path = request.url.path
    allow = (
        path.startswith("/api/auth")
        or path.startswith("/api/billing")
        or path.startswith("/api/stripe")
        or path.startswith("/api/health")
        or path.startswith("/api/version")
        or path.startswith("/api/portal")
        or path == "/docs"
        or path == "/openapi.json"
    )
    if allow or request.method == "OPTIONS":
        return await call_next(request)
    # Best-effort: decode JWT without full auth dependency
    auth = request.headers.get("authorization") or ""
    token = auth[7:] if auth.lower().startswith("bearer ") else request.cookies.get("eb_access")
    if token:
        try:
            from jose import jwt as _jwt
            from auth import SECRET_KEY, ALGORITHM
            from db import engine
            from sqlmodel import Session
            from models import Tenant
            payload = _jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            tid = payload.get("tenant_id")
            if tid is not None:
                with Session(engine) as s:
                    t = s.get(Tenant, tid)
                    if t and t.is_suspended:
                        from fastapi.responses import JSONResponse
                        return JSONResponse(
                            {"error": "Account suspended", "code": "tenant_suspended"},
                            status_code=402,
                        )
        except Exception:
            pass
    return await call_next(request)


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
    reconciliations.router, periods.router, audit.router, webhooks.router,
    transactions.router, reports.router, dashboard_layout.router, dashboard_ops.router, imports.router,
    tax_codes.router, recurring.router, exchange_rates.router,
    bank_imports.router, stock_locations.router, stock_transfers.router, pick_lists.router,
    bom.router, rate_plans.router,
    grn.router, production_orders.router,
    scrap_reasons.router,
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
    analytic_dimensions.router,
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
    leave.router,
    expense_claims.router,
    healthcare.router,
    healthcare_reports.router,
    healthcare_dialysis.router,
    weaving.router,
    weaving_reports.router,
    weaving_calculators.router,
    spinning.router,
    spinning_reports.router,
    spinning_calculators.router,
    textile_processing.router,
    textile_processing_reports.router,
    system_update.router,
    search.router,
    ai_chat.router,
    alerts.router,
    tasks.router,
    billing.router,
    billing.stripe_router,
    portal.router,
    approvals.router,
    bank_feeds.router,
    pos.router,
    ecommerce.router,
    agent_ext.router,
    inventory_depth.router,
    consolidation.router,
    practice.router,
    leases.router,
    contract_assets.router,
    intercompany.router,
    india_gst.router,
    custom_fields.router,
    form_schema.router,
    print_templates.router,
    ops_tenants.router,
]

# Health is mounted once (no /api/v1 duplicate) — load balancers + Caddy probe it.
app.include_router(health.router)

# PRA / UAE / ZATCA e-Invoice routers mounted separately (not in the shared prefix list above)
app.include_router(pra_router, prefix="/api")
app.include_router(uae_router, prefix="/api")
app.include_router(zatca_router, prefix="/api")
app.include_router(peppol_router, prefix="/api")
app.include_router(marketplace.router)

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
from models import Invoice as _Invoice  # noqa: F401 — kept for type clarity in webhook docs
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
        meta = data.get("metadata") or {}
        invoice_id = int(meta.get("invoice_id") or 0)
        tenant_id = int(meta.get("tenant_id") or 0)
        session_id = data.get("id") or ""
        amount_total = data.get("amount_total")  # cents
        if invoice_id and tenant_id and session_id:
            with next(_get_session()) as session:
                from decimal import Decimal as _Dec
                from services.portal_pay import apply_checkout_payment
                amount = None
                if amount_total is not None:
                    amount = _Dec(amount_total) / _Dec(100)
                try:
                    apply_checkout_payment(
                        session,
                        tenant_id=tenant_id,
                        invoice_id=invoice_id,
                        checkout_session_id=str(session_id),
                        amount=amount,
                        currency=(data.get("currency") or "").upper() or None,
                    )
                    session.commit()
                except Exception as exc:
                    print(f"[stripe_webhook] portal pay failed: {type(exc).__name__}: {exc}")
                    session.rollback()
    return {"received": True}


# Serve uploaded files (company logos, attachments) under /uploads/.
# Use local_config.uploads_dir() so Vercel (read-only /var/task) lands in /tmp.
from local_config import uploads_dir as _uploads_dir
_uploads = _uploads_dir()
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
