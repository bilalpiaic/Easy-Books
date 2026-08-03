"""IFRS 15 remaining — SSP allocation + contract assets (#259).

Revision ID: 0060_ifrs15_allocation
Revises: 0059_fixed_asset_depth
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "0060_ifrs15_allocation"
down_revision: Union[str, Sequence[str], None] = "0059_fixed_asset_depth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    prod_cols = {c["name"] for c in sa.inspect(bind).get_columns("product")}
    with op.batch_alter_table("product") as batch:
        if "standalone_selling_price" not in prod_cols:
            batch.add_column(
                sa.Column("standalone_selling_price", sa.Numeric(18, 4), nullable=True)
            )

    line_cols = {c["name"] for c in sa.inspect(bind).get_columns("invoiceline")}
    with op.batch_alter_table("invoiceline") as batch:
        if "ssp" not in line_cols:
            batch.add_column(sa.Column("ssp", sa.Numeric(18, 4), nullable=True))
        if "pre_allocation_amount" not in line_cols:
            batch.add_column(
                sa.Column("pre_allocation_amount", sa.Numeric(18, 4), nullable=True)
            )

    if not bind.dialect.has_table(bind, "revenueallocationaudit"):
        op.create_table(
            "revenueallocationaudit",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("invoice_id", sa.Integer(), nullable=False),
            sa.Column("transaction_price", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("method", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("detail_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_revenueallocationaudit_tenant_id",
            "revenueallocationaudit",
            ["tenant_id"],
        )
        op.create_index(
            "ix_revenueallocationaudit_invoice_id",
            "revenueallocationaudit",
            ["invoice_id"],
        )

    if not bind.dialect.has_table(bind, "contractasset"):
        op.create_table(
            "contractasset",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("customer_id", sa.Integer(), nullable=False),
            sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("certify_date", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column(
                "recognised_amount", sa.Numeric(18, 4), nullable=False, server_default="0"
            ),
            sa.Column("revenue_account_id", sa.Integer(), nullable=True),
            sa.Column("asset_account_id", sa.Integer(), nullable=True),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("transaction_id", sa.Integer(), nullable=True),
            sa.Column("invoice_id", sa.Integer(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint(
                "status IN ('open','closed')",
                name="ck_contract_asset_status",
            ),
        )
        op.create_index("ix_contractasset_tenant_id", "contractasset", ["tenant_id"])
        op.create_index("ix_contractasset_customer_id", "contractasset", ["customer_id"])
        op.create_index("ix_contractasset_status", "contractasset", ["status"])
        op.create_index("ix_contractasset_invoice_id", "contractasset", ["invoice_id"])


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("contractasset", "revenueallocationaudit"):
        if bind.dialect.has_table(bind, table):
            op.drop_table(table)

    line_cols = {c["name"] for c in sa.inspect(bind).get_columns("invoiceline")}
    with op.batch_alter_table("invoiceline") as batch:
        if "pre_allocation_amount" in line_cols:
            batch.drop_column("pre_allocation_amount")
        if "ssp" in line_cols:
            batch.drop_column("ssp")

    prod_cols = {c["name"] for c in sa.inspect(bind).get_columns("product")}
    with op.batch_alter_table("product") as batch:
        if "standalone_selling_price" in prod_cols:
            batch.drop_column("standalone_selling_price")
