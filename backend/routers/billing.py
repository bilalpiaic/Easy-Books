"""Billing + Stripe webhook (#119)."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import select

from models import Tenant
from services.saas import PLAN_LIMITS, apply_plan_defaults, usage_snapshot
from .common import AdminUserDep, CurrentUserDep, SessionDep

router = APIRouter(prefix="/api/billing", tags=["billing"])
stripe_router = APIRouter(prefix="/api/stripe", tags=["stripe"])


class CheckoutBody(BaseModel):
    plan: str


@router.get("/usage")
def get_usage(session: SessionDep, user: CurrentUserDep):
    tenant = session.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    return usage_snapshot(session, tenant)


@router.get("/plans")
def list_plans():
    return PLAN_LIMITS


@router.post("/checkout")
def create_checkout(body: CheckoutBody, session: SessionDep, user: AdminUserDep):
    if body.plan not in PLAN_LIMITS or body.plan == "free":
        raise HTTPException(400, "Choose a paid plan: starter, pro, or enterprise")
    tenant = session.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(404)
    secret = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not secret:
        # Test / offline mode — upgrade immediately without Stripe.
        apply_plan_defaults(tenant, body.plan)
        tenant.subscription_status = "active"
        session.add(tenant)
        session.commit()
        return {
            "ok": True,
            "mode": "offline",
            "checkout_url": None,
            "plan": tenant.plan,
            "message": "STRIPE_SECRET_KEY unset — plan applied locally",
        }
    import stripe
    stripe.api_key = secret
    price_env = {
        "starter": os.environ.get("STRIPE_PRICE_STARTER", ""),
        "pro": os.environ.get("STRIPE_PRICE_PRO", ""),
        "enterprise": os.environ.get("STRIPE_PRICE_ENTERPRISE", ""),
    }
    price = (price_env.get(body.plan) or "").strip() or None
    if not price:
        env_name = {
            "starter": "STRIPE_PRICE_STARTER",
            "pro": "STRIPE_PRICE_PRO",
            "enterprise": "STRIPE_PRICE_ENTERPRISE",
        }.get(body.plan, f"STRIPE_PRICE_{body.plan.upper()}")
        raise HTTPException(
            400,
            f"No Stripe price configured for plan '{body.plan}'. "
            f"Set {env_name} to your Stripe Price ID (see README Environment variables), "
            f"or unset STRIPE_SECRET_KEY to apply the plan offline.",
        )
    if not tenant.stripe_customer_id:
        cust = stripe.Customer.create(email=user.email, metadata={"tenant_id": tenant.id})
        tenant.stripe_customer_id = cust.id
        session.add(tenant)
        session.commit()
    base = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").rstrip("/")
    session_obj = stripe.checkout.Session.create(
        mode="subscription",
        customer=tenant.stripe_customer_id,
        line_items=[{"price": price, "quantity": 1}],
        success_url=f"{base}/settings/billing?success=1",
        cancel_url=f"{base}/settings/billing?canceled=1",
        metadata={"tenant_id": str(tenant.id), "plan": body.plan},
    )
    return {"ok": True, "mode": "stripe", "checkout_url": session_obj.url, "plan": body.plan}


@stripe_router.post("/webhook")
async def stripe_webhook(request: Request, session: SessionDep):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    event = None
    if secret:
        import stripe
        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
        try:
            event = stripe.Webhook.construct_event(payload, sig, secret)
        except Exception as exc:
            raise HTTPException(400, f"Webhook error: {exc}") from exc
    else:
        import json
        event = json.loads(payload.decode() or "{}")

    etype = event.get("type") if isinstance(event, dict) else getattr(event, "type", None)
    data = event.get("data", {}).get("object", {}) if isinstance(event, dict) else {}

    if etype == "customer.subscription.updated":
        cust_id = data.get("customer")
        status = data.get("status")
        meta = data.get("metadata") or {}
        tenant = _tenant_by_stripe(session, cust_id, meta.get("tenant_id"))
        if tenant:
            tenant.subscription_status = status
            plan = meta.get("plan")
            if plan:
                apply_plan_defaults(tenant, plan)
            session.add(tenant)
            session.commit()
    elif etype == "customer.subscription.deleted":
        cust_id = data.get("customer")
        meta = data.get("metadata") or {}
        tenant = _tenant_by_stripe(session, cust_id, meta.get("tenant_id"))
        if tenant:
            tenant.is_suspended = True
            tenant.subscription_status = "canceled"
            session.add(tenant)
            session.commit()
    elif etype == "invoice.payment_failed":
        cust_id = data.get("customer")
        tenant = _tenant_by_stripe(session, cust_id, None)
        if tenant:
            tenant.subscription_status = "past_due"
            session.add(tenant)
            session.commit()

    return {"received": True}


def _tenant_by_stripe(session, customer_id: Optional[str], tenant_id: Optional[str]):
    if tenant_id:
        try:
            t = session.get(Tenant, int(tenant_id))
            if t:
                return t
        except (TypeError, ValueError):
            pass
    if customer_id:
        return session.exec(
            select(Tenant).where(Tenant.stripe_customer_id == customer_id)
        ).first()
    return None
