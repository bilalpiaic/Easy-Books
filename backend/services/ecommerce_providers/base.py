"""Provider-agnostic eCommerce order / product types (#305)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional, Protocol, runtime_checkable

from sqlmodel import Session

from models_ecommerce import EcommerceConnection


@dataclass(frozen=True)
class NormalizedLine:
    external_product_id: str
    sku: str
    title: str
    qty: Decimal
    unit_price: Decimal


@dataclass(frozen=True)
class NormalizedOrder:
    external_order_id: str
    order_number: str
    order_date: date
    customer_name: str
    customer_email: str = ""
    currency: str = ""
    lines: tuple[NormalizedLine, ...] = field(default_factory=tuple)
    notes: str = ""


@dataclass(frozen=True)
class NormalizedProduct:
    external_product_id: str
    sku: str
    title: str
    price: Decimal
    stock_qty: Optional[Decimal] = None


@runtime_checkable
class EcommerceProvider(Protocol):
    name: str

    def list_orders(
        self,
        session: Session,
        connection: EcommerceConnection,
        *,
        since: Optional[date] = None,
    ) -> list[NormalizedOrder]:
        ...

    def list_products(
        self,
        session: Session,
        connection: EcommerceConnection,
    ) -> list[NormalizedProduct]:
        ...

    def push_stock(
        self,
        session: Session,
        connection: EcommerceConnection,
        *,
        external_product_id: str,
        qty: Decimal,
    ) -> None:
        """Push on-hand qty to the store (eb_to_store). No-op for mock."""
        ...
