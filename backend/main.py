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

from db import create_db_and_tables
from routers import (
    accounts, aging, audit, auth, bank_accounts, bills, customers, imports,
    invoices, payments, periods, products, reconciliations, reports, settings,
    transactions, vendors,
)


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

_allowed_origins = [o.strip() for o in os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Routers are listed roughly in the order the UI exercises them so the
# /docs page renders predictably.
app.include_router(auth.router)
app.include_router(settings.router)
app.include_router(accounts.router)
app.include_router(customers.router)
app.include_router(vendors.router)
app.include_router(products.router)
app.include_router(invoices.router)
app.include_router(bills.router)
app.include_router(payments.router)
app.include_router(aging.router)
app.include_router(bank_accounts.router)
app.include_router(reconciliations.router)
app.include_router(periods.router)
app.include_router(audit.router)
app.include_router(transactions.router)
app.include_router(reports.router)
app.include_router(imports.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="localhost", port=8000, reload=True)
