"""Point of Sale tables (#304).

Thin ops layer: real GL still goes through Invoice + PaymentReceived via
``services.pos.complete_pos_sale``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel

from services.money import ZERO


class PosRegister(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    name: str
    code: str = Field(default="REG1", index=True)
    cash_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    bank_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    default_customer_id: Optional[int] = Field(default=None, foreign_key="customer.id")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PosShift(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    register_id: int = Field(foreign_key="posregister.id", index=True)
    opened_by_id: int = Field(foreign_key="user.id")
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    opening_float: float = Field(default=0, sa_column=Column(Numeric(18, 4), nullable=False, server_default="0"))
    closed_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    closed_at: Optional[datetime] = None
    closing_count: Optional[float] = Field(default=None, sa_column=Column(Numeric(18, 4), nullable=True))
    expected_cash: Optional[float] = Field(default=None, sa_column=Column(Numeric(18, 4), nullable=True))
    variance: Optional[float] = Field(default=None, sa_column=Column(Numeric(18, 4), nullable=True))
    status: str = Field(default="open", index=True)  # open | closed
    notes: Optional[str] = None


class PosSale(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    shift_id: int = Field(foreign_key="posshift.id", index=True)
    invoice_id: int = Field(foreign_key="invoice.id", index=True)
    payment_received_id: Optional[int] = Field(default=None, foreign_key="paymentreceived.id")
    tender: str = Field(default="cash")  # cash | card | bank
    cash_tendered: Optional[float] = Field(default=None, sa_column=Column(Numeric(18, 4), nullable=True))
    change_given: Optional[float] = Field(default=None, sa_column=Column(Numeric(18, 4), nullable=True))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: int = Field(foreign_key="user.id")
