"""eCommerce store connectors (#305) — Shopify / WooCommerce (+ mock)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, UniqueConstraint
from sqlmodel import Field, SQLModel


class EcommerceConnection(SQLModel, table=True):
    """One connected store per provider+shop for a tenant."""
    __tablename__ = "ecommerceconnection"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "provider", "shop_domain",
            name="uq_ecommerce_conn_provider_shop",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    provider: str = Field(index=True)  # shopify | woocommerce | daraz | mock
    shop_domain: str = Field(default="", index=True)
    shop_name: str = Field(default="")
    # API key / access token (opaque; never returned raw from GET)
    access_token: str = Field(default="")
    # Woo also needs consumer secret
    api_secret: Optional[str] = None
    # eb_to_store | store_to_eb | off
    stock_sync_direction: str = Field(default="off")
    default_customer_id: Optional[int] = Field(default=None, foreign_key="customer.id")
    is_active: bool = Field(default=True)
    last_sync: Optional[datetime] = None
    last_error: Optional[str] = None
    sync_status: str = Field(default="never")  # never | ok | error
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EcommerceProductMap(SQLModel, table=True):
    """Map external SKU / product id → Easy-Books Product."""
    __tablename__ = "ecommerceproductmap"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "connection_id", "external_product_id",
            name="uq_ecommerce_product_map",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    connection_id: int = Field(foreign_key="ecommerceconnection.id", index=True)
    external_product_id: str = Field(index=True)
    external_sku: Optional[str] = None
    external_title: Optional[str] = None
    product_id: int = Field(foreign_key="product.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EcommerceOrderImport(SQLModel, table=True):
    """Audit of imported store orders → draft invoices."""
    __tablename__ = "ecommerceorderimport"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "connection_id", "external_order_id",
            name="uq_ecommerce_order_import",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    connection_id: int = Field(foreign_key="ecommerceconnection.id", index=True)
    external_order_id: str = Field(index=True)
    external_order_number: Optional[str] = None
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    status: str = Field(default="imported")  # imported | skipped | error
    error: Optional[str] = None
    imported_at: datetime = Field(default_factory=datetime.utcnow)
