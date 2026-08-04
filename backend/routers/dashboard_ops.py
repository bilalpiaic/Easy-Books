"""Aggregate operations / purpose dashboard KPIs for the dual-home dashboard.

Reuses existing module dashboard helpers — no new GL logic. Each key is gated
by the tenant's installed modules; permission failures are skipped (empty key)
so a user who can see some modules still gets a partial payload.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, func, select

from models import (
    GateInward,
    Product,
    PurchaseDemand,
    PurchaseOrder,
    Tenant,
)
from routers.common import CurrentUserDep, SessionDep
from routers.modules import _get_enabled

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Modules that contribute purpose/ops KPIs. Purpose-tab visibility excludes hrm-only.
OPS_MODULES = (
    "production",
    "spinning",
    "weaving",
    "textile_processing",
    "healthcare",
    "telecom",
    "purchase_store",
    "hrm",
)
PURPOSE_MODULES = tuple(m for m in OPS_MODULES if m != "hrm")


def _safe_call(fn, *args, **kwargs) -> Any | None:
    try:
        return fn(*args, **kwargs)
    except HTTPException:
        return None
    except Exception as exc:  # noqa: BLE001 — aggregate must never 500 the home
        print(f"[dashboard_ops] {fn.__name__}: {type(exc).__name__}: {exc}")
        return None


def _purchase_store_summary(session: Session, tid: int) -> dict:
    demand_open = session.exec(
        select(func.count(PurchaseDemand.id)).where(
            PurchaseDemand.tenant_id == tid,
            PurchaseDemand.status.in_(["draft", "approved"]),  # type: ignore[attr-defined]
        )
    ).one() or 0
    po_open = session.exec(
        select(func.count(PurchaseOrder.id)).where(
            PurchaseOrder.tenant_id == tid,
            PurchaseOrder.status.in_(["draft", "approved", "received"]),  # type: ignore[attr-defined]
        )
    ).one() or 0
    gi_open = session.exec(
        select(func.count(GateInward.id)).where(
            GateInward.tenant_id == tid,
            GateInward.status == "open",
        )
    ).one() or 0
    low_stock = session.exec(
        select(func.count(Product.id)).where(
            Product.tenant_id == tid,
            Product.product_type == "stock",
            Product.stock_qty <= Product.reorder_level,
        )
    ).one() or 0
    return {
        "open_demands": int(demand_open),
        "open_pos": int(po_open),
        "open_gate_inwards": int(gi_open),
        "low_stock_items": int(low_stock),
    }


@router.get("/operations-summary")
def operations_summary(session: SessionDep, user: CurrentUserDep):
    """Keyed bag of module ops KPIs for the Operations home dashboard."""
    tenant = session.get(Tenant, user.tenant_id)
    enabled = set(_get_enabled(tenant)) if tenant else {"base"}
    out: dict[str, Any] = {
        "modules": sorted(m for m in OPS_MODULES if m in enabled),
        "business_model": getattr(tenant, "business_model", None) if tenant else None,
    }

    if "production" in enabled:
        from routers.manufacturing_reports import dashboard as mfg_dashboard
        data = _safe_call(mfg_dashboard, session, user)
        if data is not None:
            out["production"] = data

    if "spinning" in enabled:
        from routers.spinning_reports import spinning_dashboard
        data = _safe_call(spinning_dashboard, user, session)
        if data is not None:
            out["spinning"] = data

    if "weaving" in enabled:
        from routers.weaving_reports import weaving_dashboard
        data = _safe_call(weaving_dashboard, user, session)
        if data is not None:
            out["weaving"] = data

    if "textile_processing" in enabled:
        from routers.textile_processing import dashboard as tp_dashboard
        data = _safe_call(tp_dashboard, user, session)
        if data is not None:
            out["textile_processing"] = data

    if "healthcare" in enabled:
        from routers.healthcare_reports import dashboard as hc_dashboard
        data = _safe_call(hc_dashboard, user, session)
        if data is not None:
            out["healthcare"] = data

    if "telecom" in enabled:
        from routers.telecom_reports import dashboard as tel_dashboard
        data = _safe_call(tel_dashboard, session, user)
        if data is not None:
            out["telecom"] = data

    if "purchase_store" in enabled:
        out["purchase_store"] = _purchase_store_summary(session, user.tenant_id)

    if "hrm" in enabled:
        from routers.payroll import hrm_summary
        data = _safe_call(hrm_summary, user, session)
        if data is not None:
            # Drop heavy recent_runs list for the home tile
            out["hrm"] = {
                "active_employees": data.get("active_employees"),
                "last_payroll_net": data.get("last_payroll_net"),
                "pending_runs": data.get("pending_runs"),
                "avg_attendance_pct": data.get("avg_attendance_pct"),
            }

    return out


@router.get("/operations-available")
def operations_available(session: SessionDep, user: CurrentUserDep):
    """Whether the tenant has any ops-capable module (drives the home toggle)."""
    tenant = session.get(Tenant, user.tenant_id)
    enabled = set(_get_enabled(tenant)) if tenant else {"base"}
    purpose = sorted(m for m in PURPOSE_MODULES if m in enabled)
    return {
        "available": bool(purpose),
        "modules": purpose,
        "business_model": getattr(tenant, "business_model", None) if tenant else None,
    }
