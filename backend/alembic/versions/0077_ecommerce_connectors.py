"""eCommerce connectors tables (#305)

Revision ID: 0077_ecommerce_connectors
Revises: 0076_grey_inward_form
Create Date: 2026-08-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0077_ecommerce_connectors"
down_revision: Union[str, Sequence[str], None] = "0076_grey_inward_form"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "ecommerceconnection"):
        op.create_table(
            "ecommerceconnection",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("provider", sa.String(), nullable=False, index=True),
            sa.Column("shop_domain", sa.String(), nullable=False, server_default="", index=True),
            sa.Column("shop_name", sa.String(), nullable=False, server_default=""),
            sa.Column("access_token", sa.String(), nullable=False, server_default=""),
            sa.Column("api_secret", sa.String(), nullable=True),
            sa.Column("stock_sync_direction", sa.String(), nullable=False, server_default="off"),
            sa.Column("default_customer_id", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("last_sync", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.String(), nullable=True),
            sa.Column("sync_status", sa.String(), nullable=False, server_default="never"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "uq_ecommerce_conn_provider_shop",
            "ecommerceconnection",
            ["tenant_id", "provider", "shop_domain"],
            unique=True,
        )

    if not bind.dialect.has_table(bind, "ecommerceproductmap"):
        op.create_table(
            "ecommerceproductmap",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("connection_id", sa.Integer(), nullable=False, index=True),
            sa.Column("external_product_id", sa.String(), nullable=False, index=True),
            sa.Column("external_sku", sa.String(), nullable=True),
            sa.Column("external_title", sa.String(), nullable=True),
            sa.Column("product_id", sa.Integer(), nullable=False, index=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "uq_ecommerce_product_map",
            "ecommerceproductmap",
            ["tenant_id", "connection_id", "external_product_id"],
            unique=True,
        )

    if not bind.dialect.has_table(bind, "ecommerceorderimport"):
        op.create_table(
            "ecommerceorderimport",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("connection_id", sa.Integer(), nullable=False, index=True),
            sa.Column("external_order_id", sa.String(), nullable=False, index=True),
            sa.Column("external_order_number", sa.String(), nullable=True),
            sa.Column("invoice_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="imported"),
            sa.Column("error", sa.String(), nullable=True),
            sa.Column("imported_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "uq_ecommerce_order_import",
            "ecommerceorderimport",
            ["tenant_id", "connection_id", "external_order_id"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    for t in ("ecommerceorderimport", "ecommerceproductmap", "ecommerceconnection"):
        if bind.dialect.has_table(bind, t):
            op.drop_table(t)
