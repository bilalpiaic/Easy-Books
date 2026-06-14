"""
FastAPI app bootstrap.

Everything that used to live in one 2,100-line file now lives in `routers/`
and `services/`. This file's only job is:
  - Create the FastAPI app + CORS
  - Run schema setup on startup (P1 / Alembic will replace this)
  - Wire up each domain router

Per-domain logic, DTOs, and helpers belong in their respective router module.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from db import create_db_and_tables
from routers import (
    accounts, admin, advances, aging, analytic_accounts, assets, attachments,
    audit, auth, backup, bank_accounts, bank_imports, bills, bom, budgets,
    credit_notes, dashboard_layout, customers, debit_notes, deferred_revenue, exchange_rates, grn,
    imports, invoices, manufacturing_reports, payment_terms, payments, periods,
    product_categories, production_orders, products, purchase_orders, rate_plans,
    reconciliations, recurring, report_builder, reports, settings, stock_locations,
    subledger, tax_codes, telecom, telecom_reports, transactions, users, vendors,
    permissions,
)
from services.csrf import CsrfMiddleware
from services.idempotency import IdempotencyMiddleware


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # `lifespan` replaces the deprecated @app.on_event("startup") hook.
    # For local dev / SQLite we let SQLModel create tables on demand so a
    # fresh checkout boots without an Alembic step. In production set
    # SCHEMA_BOOTSTRAP=alembic and run `alembic upgrade head` from CI so
    # schema changes are explicit and version-controlled.
    if os.environ.get("SCHEMA_BOOTSTRAP", "create_all") == "create_all":
        create_db_and_tables()
    yield


app = FastAPI(title="Easy-Books API", lifespan=lifespan)

# Middleware ordering: CSRF runs first (outermost), then idempotency, then
# CORS. Starlette wraps in reverse-add order, so add_middleware last → runs
# first on the request path. We want CSRF to reject before the idempotency
# cache is consulted.
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(CsrfMiddleware)

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
    auth.router, settings.router, accounts.router, customers.router,
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
    analytic_accounts.router,
    deferred_revenue.router,
    debit_notes.router,
    advances.router,
    backup.router,
    admin.router,
    permissions.router,
]

for r in _ROUTERS:
    app.include_router(r)

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
