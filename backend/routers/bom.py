"""Bills of Material — recipe library for manufacturing tenants.

A BoM = "to produce N units of output_product, consume the following
components". Each component line tags its source: own_stock (from a raw-
material store) or customer_supplied (from the customer godown).

Versioning: when you tweak a recipe, you POST a new version. The old
version stays in the catalogue (read-only) so historical production orders
that pinned it remain reconstructable.

Multi-output (#223): optional `outputs[]` (primary / co_product / by_product)
with a cost_alloc_method. Header output_product_id / output_qty stay the
denormalized primary for versioning and PO batch scale.
"""
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import BomHeader, BomLine, BomOutput, Product, StockLocation
from services.money import D, money

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit
from services.permissions import perm_dep, apply_own_filter

router = APIRouter(prefix="/api/bom", tags=["bom"], dependencies=[perm_dep("bom")])

_VALID_SOURCES = {"own_stock", "customer_supplied"}
_VALID_ROLES = {"primary", "co_product", "by_product"}
_VALID_ALLOC = {"primary_only", "fixed_pct", "relative_sales_value"}


class BomLineIn(BaseModel):
    component_product_id: int
    qty_per_output: Decimal
    source: str = "own_stock"
    default_location_id: Optional[int] = None
    is_optional: bool = False
    notes: Optional[str] = None


class BomOutputIn(BaseModel):
    product_id: int
    qty_per_batch: Decimal
    role: str = "primary"
    alloc_pct: Optional[Decimal] = None
    sales_price_hint: Optional[Decimal] = None


class BomCreate(BaseModel):
    output_product_id: int
    output_qty: Decimal = Decimal("1")
    cost_alloc_method: str = "primary_only"
    explode_on_invoice: bool = False
    description: Optional[str] = None
    notes: Optional[str] = None
    lines: List[BomLineIn]
    outputs: Optional[List[BomOutputIn]] = None


def _resolve_outputs(body: BomCreate) -> list[BomOutputIn]:
    """Use explicit outputs, or synthesize a single primary from header fields."""
    if body.outputs:
        return list(body.outputs)
    return [
        BomOutputIn(
            product_id=body.output_product_id,
            qty_per_batch=body.output_qty,
            role="primary",
            alloc_pct=Decimal("100") if body.cost_alloc_method == "fixed_pct" else None,
        )
    ]


def _validate_bom(session, tenant_id: int, body: BomCreate) -> list[BomOutputIn]:
    if not body.lines:
        raise HTTPException(400, "A BoM must have at least one component line")
    if D(body.output_qty) <= 0:
        raise HTTPException(400, "output_qty must be > 0")
    if body.cost_alloc_method not in _VALID_ALLOC:
        raise HTTPException(400, f"cost_alloc_method must be one of {sorted(_VALID_ALLOC)}")

    out_prod = session.get(Product, body.output_product_id)
    if not out_prod or out_prod.tenant_id != tenant_id:
        raise HTTPException(400, "output_product_id not found for tenant")

    component_ids = {ln.component_product_id for ln in body.lines}
    rows = session.exec(
        select(Product.id).where(
            Product.id.in_(component_ids), Product.tenant_id == tenant_id
        )
    ).all()
    if len(set(rows)) != len(component_ids):
        raise HTTPException(400, "One or more component products not found for tenant")
    for ln in body.lines:
        if ln.source not in _VALID_SOURCES:
            raise HTTPException(
                400, f"source must be one of {sorted(_VALID_SOURCES)}"
            )
        if D(ln.qty_per_output) <= 0:
            raise HTTPException(400, "qty_per_output must be > 0 on every line")
        if ln.default_location_id is not None:
            loc = session.get(StockLocation, ln.default_location_id)
            if not loc or loc.tenant_id != tenant_id:
                raise HTTPException(
                    400, f"default_location_id {ln.default_location_id} not found"
                )

    outputs = _resolve_outputs(body)
    if not outputs:
        raise HTTPException(400, "A BoM must have at least one output")

    primaries = [o for o in outputs if o.role == "primary"]
    if len(primaries) != 1:
        raise HTTPException(400, "Exactly one output must have role 'primary'")
    primary = primaries[0]
    if primary.product_id != body.output_product_id:
        raise HTTPException(
            400, "Primary output product_id must match output_product_id"
        )
    if abs(D(primary.qty_per_batch) - D(body.output_qty)) > Decimal("0.0001"):
        raise HTTPException(
            400, "Primary output qty_per_batch must match output_qty"
        )

    seen_products: set[int] = set()
    for o in outputs:
        if o.role not in _VALID_ROLES:
            raise HTTPException(400, f"role must be one of {sorted(_VALID_ROLES)}")
        if D(o.qty_per_batch) <= 0:
            raise HTTPException(400, "qty_per_batch must be > 0 on every output")
        if o.product_id in seen_products:
            raise HTTPException(400, "Duplicate product_id in outputs")
        seen_products.add(o.product_id)
        prod = session.get(Product, o.product_id)
        if not prod or prod.tenant_id != tenant_id:
            raise HTTPException(400, f"output product_id {o.product_id} not found")
        if o.alloc_pct is not None and D(o.alloc_pct) < 0:
            raise HTTPException(400, "alloc_pct must be >= 0")
        if o.sales_price_hint is not None and D(o.sales_price_hint) < 0:
            raise HTTPException(400, "sales_price_hint must be >= 0")

    if body.cost_alloc_method == "fixed_pct":
        total_pct = sum((D(o.alloc_pct or 0) for o in outputs), start=Decimal("0"))
        if abs(total_pct - Decimal("100")) > Decimal("0.01"):
            raise HTTPException(
                400, f"fixed_pct requires alloc_pct to sum to 100 (got {total_pct})"
            )

    return outputs


def _serialise(session, h: BomHeader) -> dict:
    lines = session.exec(
        select(BomLine).where(BomLine.bom_id == h.id).order_by(BomLine.id)
    ).all()
    outputs = session.exec(
        select(BomOutput).where(BomOutput.bom_id == h.id).order_by(BomOutput.id)
    ).all()
    return {
        **h.model_dump(),
        "lines": [ln.model_dump() for ln in lines],
        "outputs": [o.model_dump() for o in outputs],
    }


@router.get("")
def list_boms(
    session: SessionDep, user: CurrentUserDep,
    output_product_id: Optional[int] = None,
    active_only: bool = False,
    skip: int = 0, limit: int = 100,
):
    q = select(BomHeader).where(BomHeader.tenant_id == user.tenant_id)
    if output_product_id:
        q = q.where(BomHeader.output_product_id == output_product_id)
    if active_only:
        q = q.where(BomHeader.is_active == True)  # noqa: E712
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    heads = session.exec(
        q.order_by(BomHeader.output_product_id, BomHeader.version.desc())
         .offset(skip).limit(limit)
    ).all()
    return {"total": total, "items": [_serialise(session, h) for h in heads]}


@router.get("/{bom_id}")
def get_bom(session: SessionDep, user: CurrentUserDep, bom_id: int):
    h = session.exec(
        select(BomHeader).where(
            BomHeader.id == bom_id, BomHeader.tenant_id == user.tenant_id
        )
    ).first()
    if not h:
        raise HTTPException(404, "BoM not found")
    return _serialise(session, h)


@router.post("", status_code=201)
def create_bom(session: SessionDep, user: WriteUserDep, body: BomCreate):
    outputs = _validate_bom(session, user.tenant_id, body)

    existing_max = session.exec(
        select(func.max(BomHeader.version)).where(
            BomHeader.tenant_id == user.tenant_id,
            BomHeader.output_product_id == body.output_product_id,
        )
    ).one()
    new_version = (existing_max or 0) + 1

    prior = session.exec(
        select(BomHeader).where(
            BomHeader.tenant_id == user.tenant_id,
            BomHeader.output_product_id == body.output_product_id,
            BomHeader.is_active == True,  # noqa: E712
        )
    ).all()
    for p in prior:
        p.is_active = False
        session.add(p)

    h = BomHeader(
        tenant_id=user.tenant_id,
        output_product_id=body.output_product_id,
        output_qty=D(body.output_qty),
        cost_alloc_method=body.cost_alloc_method,
        version=new_version,
        is_active=True,
        explode_on_invoice=body.explode_on_invoice,
        description=body.description,
        notes=body.notes,
    )
    session.add(h)
    session.flush()
    for ln in body.lines:
        session.add(BomLine(
            bom_id=h.id,
            component_product_id=ln.component_product_id,
            qty_per_output=D(ln.qty_per_output),
            source=ln.source,
            default_location_id=ln.default_location_id,
            is_optional=ln.is_optional,
            notes=ln.notes,
        ))
    for o in outputs:
        session.add(BomOutput(
            bom_id=h.id,
            product_id=o.product_id,
            qty_per_batch=D(o.qty_per_batch),
            role=o.role,
            alloc_pct=money(D(o.alloc_pct)) if o.alloc_pct is not None else None,
            sales_price_hint=(
                money(D(o.sales_price_hint)) if o.sales_price_hint is not None else None
            ),
        ))
    log_audit(
        session, user, "CREATE", "bom", h.id,
        {
            "output_product_id": body.output_product_id,
            "version": new_version,
            "outputs": len(outputs),
            "cost_alloc_method": body.cost_alloc_method,
        },
    )
    session.commit()
    session.refresh(h)
    return _serialise(session, h)


@router.patch("/{bom_id}/deactivate")
def deactivate_bom(session: SessionDep, user: WriteUserDep, bom_id: int):
    """Soft-mark a BoM as inactive. Historical references stay intact."""
    h = session.exec(
        select(BomHeader).where(
            BomHeader.id == bom_id, BomHeader.tenant_id == user.tenant_id
        )
    ).first()
    if not h:
        raise HTTPException(404, "BoM not found")
    h.is_active = False
    session.add(h)
    log_audit(session, user, "DEACTIVATE", "bom", h.id, {})
    session.commit()
    session.refresh(h)
    return h
