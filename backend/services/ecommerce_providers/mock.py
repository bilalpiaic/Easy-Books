"""Deterministic mock store for tests + demo (#305)."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlmodel import Session

from models_ecommerce import EcommerceConnection
from services.ecommerce_providers.base import (
    NormalizedLine, NormalizedOrder, NormalizedProduct,
)


class MockEcommerceProvider:
    name = "mock"

    def list_orders(
        self,
        session: Session,
        connection: EcommerceConnection,
        *,
        since: Optional[date] = None,
    ) -> list[NormalizedOrder]:
        base = date.today()
        tid = connection.tenant_id
        cid = connection.id or 0
        return [
            NormalizedOrder(
                external_order_id=f"mock-{tid}-{cid}-1001",
                order_number="M-1001",
                order_date=base,
                customer_name="Walk-in Web",
                customer_email="web@example.com",
                currency="USD",
                lines=(
                    NormalizedLine(
                        external_product_id=f"mock-sku-A-{tid}",
                        sku="WEB-SKU-A",
                        title="Canvas Tote",
                        qty=Decimal("2"),
                        unit_price=Decimal("18.00"),
                    ),
                ),
                notes="Mock Shopify/Woo order",
            ),
            NormalizedOrder(
                external_order_id=f"mock-{tid}-{cid}-1002",
                order_number="M-1002",
                order_date=base,
                customer_name="Online Buyer",
                customer_email="buyer@example.com",
                currency="USD",
                lines=(
                    NormalizedLine(
                        external_product_id=f"mock-sku-B-{tid}",
                        sku="WEB-SKU-B",
                        title="Notebook Pack",
                        qty=Decimal("1"),
                        unit_price=Decimal("12.50"),
                    ),
                    NormalizedLine(
                        external_product_id=f"mock-sku-A-{tid}",
                        sku="WEB-SKU-A",
                        title="Canvas Tote",
                        qty=Decimal("1"),
                        unit_price=Decimal("18.00"),
                    ),
                ),
            ),
        ]

    def list_products(
        self,
        session: Session,
        connection: EcommerceConnection,
    ) -> list[NormalizedProduct]:
        tid = connection.tenant_id
        return [
            NormalizedProduct(
                external_product_id=f"mock-sku-A-{tid}",
                sku="WEB-SKU-A",
                title="Canvas Tote",
                price=Decimal("18.00"),
                stock_qty=Decimal("40"),
            ),
            NormalizedProduct(
                external_product_id=f"mock-sku-B-{tid}",
                sku="WEB-SKU-B",
                title="Notebook Pack",
                price=Decimal("12.50"),
                stock_qty=Decimal("100"),
            ),
        ]

    def push_stock(
        self,
        session: Session,
        connection: EcommerceConnection,
        *,
        external_product_id: str,
        qty: Decimal,
    ) -> None:
        return  # mock no-op
