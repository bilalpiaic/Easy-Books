"""
SQLModel tables for the Weighbridge mill workspace (#391).

Operational / memo tickets only in v1 — no GL posting.
Weights are stored in Kg; Lbs and 100-lb Bags are derived via
services.weaving_calc (same mill conversion as Weaving).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel

from services.money import ZERO


def _qty(default: Decimal = ZERO, **kw):
    return Field(default=default, sa_column=Column(Numeric(18, 4), nullable=False, **kw))


class WbTicket(SQLModel, table=True):
    """One weighbridge ticket: vehicle in/out with first + second weigh."""

    __tablename__ = "wb_ticket"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_wb_ticket_number"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    number: str = Field(index=True)
    ticket_date: str = Field(index=True)
    direction: str = Field(default="inbound", index=True)  # inbound | outbound
    vehicle_no: str
    driver_name: Optional[str] = None
    party_type: str = Field(default="other")  # vendor | customer | other
    party_id: Optional[int] = Field(default=None, index=True)
    party_name: Optional[str] = None
    commodity: Optional[str] = None
    lot_ref: Optional[str] = None
    gross_kg: Decimal = _qty()
    tare_kg: Decimal = _qty()
    net_kg: Decimal = _qty()
    first_weigh_kind: Optional[str] = None  # gross | tare
    first_weigh_at: Optional[datetime] = None
    second_weigh_at: Optional[datetime] = None
    status: str = Field(default="draft", index=True)  # draft | weighed_in | completed | cancelled
    operator_id: Optional[int] = None
    notes: Optional[str] = None
    po_id: Optional[int] = None
    gate_inward_id: Optional[int] = None
    invoice_id: Optional[int] = None
    sp_bale_receipt_id: Optional[int] = None
    cancel_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = None
