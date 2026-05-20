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
    invoices, payments, periods, products, reconciliations, recurring, reports,
    settings, tax_codes, transactions, vendors,
)
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

# Middleware: idempotency BEFORE CORS so the cached response also gets CORS
# headers on replay.
app.add_middleware(IdempotencyMiddleware)

_allowed_origins = [o.strip() for o in os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Routers are listed roughly in the order the UI exercises them so the
# /docs page renders predictably. Each router is mounted twice: at its
# original /api/* path (legacy) and at /api/v1/* (versioned). Future
# breaking changes ship under /api/v2/ without disturbing the legacy
# surface.
_ROUTERS = [
    auth.router, settings.router, accounts.router, customers.router,
    vendors.router, products.router, invoices.router, bills.router,
    payments.router, aging.router, bank_accounts.router,
    reconciliations.router, periods.router, audit.router,
    transactions.router, reports.router, imports.router,
    tax_codes.router, recurring.router,
]

for r in _ROUTERS:
    app.include_router(r)

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
    uvicorn.run("main:app", host="localhost", port=8000, reload=True)
