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
from services.permissions import perm_dep

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Modules that contribute purpose/ops KPIs. Purpose-tab visibility excludes hrm-only.
OPS_MODULES = (
    "production",
    "spinning",
    "weaving",
    "weighbridge",
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


def _status_counts(session: Session, model, tid: int) -> dict[str, int]:
    rows = session.exec(
        select(model.status, func.count(model.id))  # type: ignore[attr-defined]
        .where(model.tenant_id == tid)
        .group_by(model.status)  # type: ignore[attr-defined]
    ).all()
    return {str(status): int(cnt) for status, cnt in rows}


def _purchase_store_summary(session: Session, tid: int) -> dict:
    demand_by_status = _status_counts(session, PurchaseDemand, tid)
    po_by_status = _status_counts(session, PurchaseOrder, tid)
    gi_by_status = _status_counts(session, GateInward, tid)

    demand_open = sum(demand_by_status.get(s, 0) for s in ("draft", "approved"))
    po_open = sum(po_by_status.get(s, 0) for s in ("draft", "approved", "received"))
    gi_open = gi_by_status.get("open", 0)
    low_stock = session.exec(
        select(func.count(Product.id)).where(
            Product.tenant_id == tid,
            Product.product_type == "stock",
            Product.stock_qty <= Product.reorder_level,
        )
    ).one() or 0

    # Funnel for process visibility: Demand → PO → Gate In → Billed PO
    funnel = {
        "demands": int(sum(demand_by_status.values())),
        "demands_open": int(demand_open),
        "pos": int(sum(po_by_status.values())),
        "pos_open": int(po_open),
        "gate_inwards": int(sum(gi_by_status.values())),
        "gate_open": int(gi_open),
        "pos_billed": int(po_by_status.get("billed", 0)),
    }
    return {
        "open_demands": int(demand_open),
        "open_pos": int(po_open),
        "open_gate_inwards": int(gi_open),
        "low_stock_items": int(low_stock),
        "demand_by_status": demand_by_status,
        "po_by_status": po_by_status,
        "gi_by_status": gi_by_status,
        "funnel": funnel,
    }


@router.get("/operations-summary", dependencies=[perm_dep("dashboard.operations", "view")])
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

    if "weighbridge" in enabled:
        from routers.weighbridge import hub_summary as wb_summary
        data = _safe_call(wb_summary, user, session)
        if data is not None:
            out["weighbridge"] = {
                "today_count": data.get("today_count"),
                "on_site": data.get("on_site"),
                "net_kg_today": data.get("net_kg_today"),
            }

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


@router.get("/operations-available", dependencies=[perm_dep("dashboard.operations", "view")])
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
