"""Bills of Material — recipe library for manufacturing tenants.

A BoM = "to produce N units of output_product, consume the following
components". Each component line tags its source: own_stock (from a raw-
material store) or customer_supplied (from the customer godown).

Versioning: when you tweak a recipe, you POST a new version. The old
version stays in the catalogue (read-only) so historical production orders
that pinned it remain reconstructable.
"""
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, select

from models import BomHeader, BomLine, Product, StockLocation
from services.money import D

from .common import CurrentUserDep, SessionDep, WriteUserDep, log_audit

router = APIRouter(prefix="/api/bom", tags=["bom"])

_VALID_SOURCES = {"own_stock", "customer_supplied"}


class BomLineIn(BaseModel):
    component_product_id: int
    qty_per_output: Decimal
    source: str = "own_stock"
    default_location_id: Optional[int] = None
    is_optional: bool = False
    notes: Optional[str] = None


class BomCreate(BaseModel):
    output_product_id: int
    output_qty: Decimal = Decimal("1")
    description: Optional[str] = None
    notes: Optional[str] = None
    lines: List[BomLineIn]


def _validate_bom(session, tenant_id: int, body: BomCreate) -> None:
    if not body.lines:
        raise HTTPException(400, "A BoM must have at least one component line")
    if D(body.output_qty) <= 0:
        raise HTTPException(400, "output_qty must be > 0")
    # Output product belongs to tenant
    out_prod = session.get(Product, body.output_product_id)
    if not out_prod or out_prod.tenant_id != tenant_id:
        raise HTTPException(400, "output_product_id not found for tenant")
    # Every component product belongs to tenant; sources valid
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


def _serialise(session, h: BomHeader) -> dict:
    lines = session.exec(
        select(BomLine).where(BomLine.bom_id == h.id).order_by(BomLine.id)
    ).all()
    return {
        **h.model_dump(),
        "lines": [ln.model_dump() for ln in lines],
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
    _validate_bom(session, user.tenant_id, body)

    # Resolve version: max(existing) + 1 for the same output product
    existing_max = session.exec(
        select(func.max(BomHeader.version)).where(
            BomHeader.tenant_id == user.tenant_id,
            BomHeader.output_product_id == body.output_product_id,
        )
    ).one()
    new_version = (existing_max or 0) + 1

    # Deactivate prior versions so only one BoM per output product is "active"
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
        version=new_version,
        is_active=True,
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
    log_audit(
        session, user, "CREATE", "bom", h.id,
        {"output_product_id": body.output_product_id, "version": new_version},
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
