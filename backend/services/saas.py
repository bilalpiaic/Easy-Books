"""SaaS plan limits + usage metering (#119 / #271)."""
from __future__ import annotations

from calendar import monthrange
from datetime import date

from fastapi import HTTPException
from sqlmodel import Session, func, select

from models import Attachment, Bill, Invoice, Tenant, User

PLAN_LIMITS = {
    "free": {
        "max_users": 2,
        "max_documents": 50,
        "storage_quota_mb": 100,
        "max_ai_per_hour": 20,
        "price": 0,
    },
    "starter": {
        "max_users": 5,
        "max_documents": 500,
        "storage_quota_mb": 1024,
        "max_ai_per_hour": 60,
        "price": 15,
    },
    "pro": {
        "max_users": 15,
        "max_documents": 5000,
        "storage_quota_mb": 10240,
        "max_ai_per_hour": 200,
        "price": 49,
    },
    "enterprise": {
        "max_users": 10_000,
        "max_documents": 10_000_000,
        "storage_quota_mb": 102400,
        "max_ai_per_hour": 2000,
        "price": 199,
    },
}


def apply_plan_defaults(tenant: Tenant, plan: str) -> None:
    limits = PLAN_LIMITS.get(plan) or PLAN_LIMITS["free"]
    tenant.plan = plan if plan in PLAN_LIMITS else "free"
    tenant.max_users = limits["max_users"]
    tenant.max_documents = limits["max_documents"]
    tenant.storage_quota_mb = limits["storage_quota_mb"]


def plan_ai_limit(plan: str) -> int:
    limits = PLAN_LIMITS.get(plan) or PLAN_LIMITS["free"]
    return int(limits["max_ai_per_hour"])


def documents_this_month(session: Session, tenant_id: int) -> int:
    today = date.today()
    start = today.replace(day=1).isoformat()
    end_day = monthrange(today.year, today.month)[1]
    end = today.replace(day=end_day).isoformat()
    inv = session.exec(
        select(func.count(Invoice.id)).where(
            Invoice.tenant_id == tenant_id,
            Invoice.issue_date >= start,
            Invoice.issue_date <= end,
        )
    ).one()
    bill = session.exec(
        select(func.count(Bill.id)).where(
            Bill.tenant_id == tenant_id,
            Bill.bill_date >= start,
            Bill.bill_date <= end,
        )
    ).one()
    return int(inv or 0) + int(bill or 0)


def storage_used_bytes(session: Session, tenant_id: int) -> int:
    try:
        total = session.exec(
            select(func.coalesce(func.sum(Attachment.size_bytes), 0)).where(
                Attachment.tenant_id == tenant_id
            )
        ).one()
        return int(total or 0)
    except Exception:
        return 0


def _quota_http(error: str, *, used: int | float, limit: int | float, plan: str) -> HTTPException:
    return HTTPException(
        402,
        detail={
            "error": error,
            "message": f"Plan quota exceeded ({error.replace('_', ' ')})",
            "used": used,
            "limit": limit,
            "plan": plan,
        },
    )


def check_document_quota(session: Session, tenant_id: int) -> None:
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        return
    used = documents_this_month(session, tenant_id)
    if used >= (tenant.max_documents or 0):
        raise _quota_http(
            "document_quota_exceeded",
            used=used,
            limit=tenant.max_documents,
            plan=tenant.plan,
        )


def check_user_quota(session: Session, tenant_id: int) -> None:
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        return
    used = session.exec(
        select(func.count(User.id)).where(
            User.tenant_id == tenant_id,
            User.is_active == True,  # noqa: E712
        )
    ).one()
    used_n = int(used or 0)
    if used_n >= (tenant.max_users or 0):
        raise _quota_http(
            "user_quota_exceeded",
            used=used_n,
            limit=tenant.max_users,
            plan=tenant.plan,
        )


def check_storage_quota(session: Session, tenant_id: int, extra_bytes: int = 0) -> None:
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        return
    used = storage_used_bytes(session, tenant_id) + max(0, extra_bytes)
    limit_bytes = int(tenant.storage_quota_mb or 0) * 1024 * 1024
    if limit_bytes and used > limit_bytes:
        raise _quota_http(
            "storage_quota_exceeded",
            used=round(used / (1024 * 1024), 2),
            limit=tenant.storage_quota_mb,
            plan=tenant.plan,
        )


def usage_snapshot(session: Session, tenant: Tenant) -> dict:
    users = session.exec(
        select(func.count(User.id)).where(User.tenant_id == tenant.id)
    ).one()
    docs = documents_this_month(session, tenant.id)
    storage = storage_used_bytes(session, tenant.id)
    return {
        "users": int(users or 0),
        "documents_this_month": docs,
        "storage_mb": round(int(storage or 0) / (1024 * 1024), 2),
        "plan": tenant.plan,
        "plan_limits": {
            "max_users": tenant.max_users,
            "max_documents": tenant.max_documents,
            "storage_quota_mb": tenant.storage_quota_mb,
            "max_ai_per_hour": plan_ai_limit(tenant.plan),
        },
        "is_suspended": tenant.is_suspended,
        "subscription_status": tenant.subscription_status,
    }
