"""Promotional price rules — CRUD + check endpoint (Issue #72)."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import Product, ProductCategory, PromoRule
from routers.common import CurrentUserDep, SessionDep
from services.permissions import perm_dep

router = APIRouter(
    prefix="/api/promo-rules",
    tags=["promo_rules"],
    dependencies=[perm_dep("invoices")],
)


# ── Schemas ──────────────────────────────────────────────────────────────────

class PromoRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    product_id: Optional[int] = None
    category_id: Optional[int] = None
    min_qty: Optional[Decimal] = None
    min_invoice_value: Optional[Decimal] = None
    discount_type: str = "percent"   # "percent" | "fixed" | "giveaway"
    discount_value: Optional[Decimal] = None
    giveaway_product_id: Optional[int] = None
    giveaway_qty: Optional[Decimal] = None


class PromoRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    product_id: Optional[int] = None
    category_id: Optional[int] = None
    min_qty: Optional[Decimal] = None
    min_invoice_value: Optional[Decimal] = None
    discount_type: Optional[str] = None
    discount_value: Optional[Decimal] = None
    giveaway_product_id: Optional[int] = None
    giveaway_qty: Optional[Decimal] = None
    is_active: Optional[bool] = None


class CheckLine(BaseModel):
    product_id: int
    qty: Decimal
    rate: Decimal


class CheckRequest(BaseModel):
    date: str                       # YYYY-MM-DD — invoice date
    lines: list[CheckLine]
    invoice_total: Optional[Decimal] = None  # subtotal before discount


# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.get("")
def list_promo_rules(user: CurrentUserDep, session: SessionDep, active_only: bool = False):
    q = select(PromoRule).where(PromoRule.tenant_id == user.tenant_id)
    if active_only:
        q = q.where(PromoRule.is_active == True)  # noqa: E712
    rules = session.exec(q.order_by(PromoRule.name)).all()
    return [_fmt(r) for r in rules]


@router.post("", status_code=201, dependencies=[perm_dep("invoices", "edit")])
def create_promo_rule(body: PromoRuleCreate, user: CurrentUserDep, session: SessionDep):
    rule = PromoRule(tenant_id=user.tenant_id, **body.model_dump())
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return {"id": rule.id}


@router.put("/{rule_id}", dependencies=[perm_dep("invoices", "edit")])
def update_promo_rule(rule_id: int, body: PromoRuleUpdate, user: CurrentUserDep, session: SessionDep):
    rule = session.get(PromoRule, rule_id)
    if not rule or rule.tenant_id != user.tenant_id:
        raise HTTPException(404, "Rule not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(rule, k, v)
    session.add(rule)
    session.commit()
    return {"ok": True}


@router.delete("/{rule_id}", dependencies=[perm_dep("invoices", "edit")])
def deactivate_promo_rule(rule_id: int, user: CurrentUserDep, session: SessionDep):
    rule = session.get(PromoRule, rule_id)
    if not rule or rule.tenant_id != user.tenant_id:
        raise HTTPException(404, "Rule not found")
    rule.is_active = False
    session.add(rule)
    session.commit()
    return {"ok": True}


# ── Check endpoint ────────────────────────────────────────────────────────────

@router.post("/check")
def check_promos(body: CheckRequest, user: CurrentUserDep, session: SessionDep):
    """Return applicable promo suggestions for the given invoice lines + date.

    Response: list of {rule_id, rule_name, applies_to_line_idx?, discount_type,
    discount_value?, giveaway_product_id?, giveaway_qty?}
    """
    active_rules = session.exec(
        select(PromoRule).where(
            PromoRule.tenant_id == user.tenant_id,
            PromoRule.is_active == True,  # noqa: E712
        )
    ).all()

    # Pre-fetch product→category map for the lines
    product_ids = [line.product_id for line in body.lines]
    products = {
        p.id: p for p in session.exec(
            select(Product).where(Product.id.in_(product_ids))  # type: ignore[attr-defined]
        ).all()
    }

    suggestions: list[dict] = []
    invoice_total = body.invoice_total or sum(l.qty * l.rate for l in body.lines)

    for rule in active_rules:
        # Date range check
        if rule.start_date and body.date < rule.start_date:
            continue
        if rule.end_date and body.date > rule.end_date:
            continue

        # Invoice-value threshold check
        if rule.min_invoice_value and invoice_total < rule.min_invoice_value:
            continue

        # Match scope: find which line indices this rule applies to
        if rule.product_id is None and rule.category_id is None:
            # Applies to entire invoice (value-threshold promo)
            if rule.discount_type == "giveaway":
                suggestions.append(_suggestion(rule, line_idx=None))
            else:
                suggestions.append(_suggestion(rule, line_idx=None))
            continue

        for idx, line in enumerate(body.lines):
            prod = products.get(line.product_id)
            if not prod:
                continue

            # Product match
            if rule.product_id and prod.id != rule.product_id:
                continue
            # Category match
            if rule.category_id and prod.category_id != rule.category_id:
                continue
            # Qty threshold
            if rule.min_qty and line.qty < rule.min_qty:
                continue

            suggestions.append(_suggestion(rule, line_idx=idx))

    return suggestions


# ── Helpers ──────────────────────────────────────────────────────────────────

def _fmt(r: PromoRule) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "description": r.description,
        "is_active": r.is_active,
        "start_date": r.start_date,
        "end_date": r.end_date,
        "product_id": r.product_id,
        "category_id": r.category_id,
        "min_qty": float(r.min_qty) if r.min_qty is not None else None,
        "min_invoice_value": float(r.min_invoice_value) if r.min_invoice_value is not None else None,
        "discount_type": r.discount_type,
        "discount_value": float(r.discount_value) if r.discount_value is not None else None,
        "giveaway_product_id": r.giveaway_product_id,
        "giveaway_qty": float(r.giveaway_qty) if r.giveaway_qty is not None else None,
    }


def _suggestion(rule: PromoRule, *, line_idx: Optional[int]) -> dict:
    return {
        "rule_id": rule.id,
        "rule_name": rule.name,
        "line_idx": line_idx,
        "discount_type": rule.discount_type,
        "discount_value": float(rule.discount_value) if rule.discount_value is not None else None,
        "giveaway_product_id": rule.giveaway_product_id,
        "giveaway_qty": float(rule.giveaway_qty) if rule.giveaway_qty is not None else None,
    }
