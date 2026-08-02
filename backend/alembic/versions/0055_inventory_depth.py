"""Inventory depth (#257): landed cost, lot/serial columns, NRV tables.

Revision ID: 0055_inventory_depth
Revises: 0054_integration_ops
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "0055_inventory_depth"
down_revision: Union[str, Sequence[str], None] = "0054_integration_ops"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Product tracking flags
    cols = {c["name"] for c in sa.inspect(bind).get_columns("product")}
    with op.batch_alter_table("product") as batch:
        if "track_lot" not in cols:
            batch.add_column(sa.Column("track_lot", sa.Boolean(), server_default=sa.false(), nullable=False))
        if "track_serial" not in cols:
            batch.add_column(sa.Column("track_serial", sa.Boolean(), server_default=sa.false(), nullable=False))
        if "nrv_unit" not in cols:
            batch.add_column(sa.Column("nrv_unit", sa.Numeric(18, 4), nullable=True))

    if not bind.dialect.has_table(bind, "stockserial"):
        op.create_table(
            "stockserial",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("product_id", sa.Integer(), nullable=False),
            sa.Column("serial", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="available"),
            sa.Column("layer_id", sa.Integer(), nullable=True),
            sa.Column("source_doc", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("sold_doc_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("sold_doc_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("tenant_id", "product_id", "serial", name="uq_stock_serial"),
        )
        op.create_index("ix_stockserial_tenant_id", "stockserial", ["tenant_id"])
        op.create_index("ix_stockserial_product_id", "stockserial", ["product_id"])
        op.create_index("ix_stockserial_serial", "stockserial", ["serial"])
        op.create_index("ix_stockserial_status", "stockserial", ["status"])

    if not bind.dialect.has_table(bind, "landedcost"):
        op.create_table(
            "landedcost",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("number", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("cost_date", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("charge_bill_id", sa.Integer(), nullable=True),
            sa.Column("goods_bill_id", sa.Integer(), nullable=True),
            sa.Column("goods_source_doc", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("allocation_method", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="value"),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="draft"),
            sa.Column("transaction_id", sa.Integer(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("tenant_id", "number", name="uq_landed_cost_number"),
        )
        op.create_index("ix_landedcost_tenant_id", "landedcost", ["tenant_id"])
        op.create_index("ix_landedcost_status", "landedcost", ["status"])
        op.create_index("ix_landedcost_goods_source_doc", "landedcost", ["goods_source_doc"])

    if not bind.dialect.has_table(bind, "landedcostallocation"):
        op.create_table(
            "landedcostallocation",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("landed_cost_id", sa.Integer(), nullable=False),
            sa.Column("product_id", sa.Integer(), nullable=False),
            sa.Column("layer_id", sa.Integer(), nullable=False),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("qty_basis", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("value_basis", sa.Numeric(18, 4), nullable=False, server_default="0"),
        )
        op.create_index("ix_landedcostallocation_tenant_id", "landedcostallocation", ["tenant_id"])
        op.create_index("ix_landedcostallocation_landed_cost_id", "landedcostallocation", ["landed_cost_id"])

    if not bind.dialect.has_table(bind, "nrvrun"):
        op.create_table(
            "nrvrun",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("number", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("run_date", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="draft"),
            sa.Column("use_allowance", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("transaction_id", sa.Integer(), nullable=True),
            sa.Column("reverse_transaction_id", sa.Integer(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("tenant_id", "number", name="uq_nrv_run_number"),
        )
        op.create_index("ix_nrvrun_tenant_id", "nrvrun", ["tenant_id"])
        op.create_index("ix_nrvrun_status", "nrvrun", ["status"])

    if not bind.dialect.has_table(bind, "nrvline"):
        op.create_table(
            "nrvline",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("run_id", sa.Integer(), nullable=False),
            sa.Column("product_id", sa.Integer(), nullable=False),
            sa.Column("qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("nrv_unit", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("write_down", sa.Numeric(18, 4), nullable=False, server_default="0"),
        )
        op.create_index("ix_nrvline_tenant_id", "nrvline", ["tenant_id"])
        op.create_index("ix_nrvline_run_id", "nrvline", ["run_id"])


def downgrade() -> None:
    bind = op.get_bind()
    for t in ("nrvline", "nrvrun", "landedcostallocation", "landedcost", "stockserial"):
        if bind.dialect.has_table(bind, t):
            op.drop_table(t)
