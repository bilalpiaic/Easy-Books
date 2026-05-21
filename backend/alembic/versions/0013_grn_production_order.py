"""V2.4: GoodsReceiptNote + GRNLine + ProductionOrder.

Revision ID: 0013_grn_production_order
Revises: 0012_bom_rate_plans
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_grn_production_order"
down_revision = "0012_bom_rate_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "goodsreceiptnote" not in tables:
        op.create_table(
            "goodsreceiptnote",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False, index=True),
            sa.Column("number", sa.String(), nullable=False, index=True),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=False, index=True),
            sa.Column("received_date", sa.String(), nullable=False),
            sa.Column("location_id", sa.Integer(), sa.ForeignKey("stocklocation.id"), nullable=False),
            sa.Column("declared_value", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transaction.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "number", name="unique_grn_number_per_tenant"),
        )

    if "grnline" not in tables:
        op.create_table(
            "grnline",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "grn_id", sa.Integer(),
                sa.ForeignKey("goodsreceiptnote.id", ondelete="CASCADE"),
                nullable=False, index=True,
            ),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("product.id"), nullable=False),
            sa.Column("qty", sa.Numeric(18, 4), nullable=False),
            sa.Column("lot_no", sa.String(), nullable=True),
            sa.Column("declared_value", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("notes", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint("qty > 0", name="ck_grn_line_qty_positive"),
        )

    if "productionorder" not in tables:
        op.create_table(
            "productionorder",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False, index=True),
            sa.Column("number", sa.String(), nullable=False, index=True),
            sa.Column("bom_id", sa.Integer(), sa.ForeignKey("bomheader.id"), nullable=False, index=True),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=False, index=True),
            sa.Column("rate_plan_id", sa.Integer(), sa.ForeignKey("rateplan.id"), nullable=True),
            sa.Column("output_qty", sa.Numeric(18, 4), nullable=False),
            sa.Column("state", sa.String(), nullable=False, server_default="draft", index=True),
            sa.Column("own_material_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("output_unit_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoice.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("delivered_at", sa.DateTime(), nullable=True),
            sa.Column("billed_at", sa.DateTime(), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(), nullable=True),
            sa.Column("notes", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "number", name="unique_po_number_per_tenant"),
            sa.CheckConstraint(
                "state IN ('draft','started','completed','delivered','billed','cancelled')",
                name="ck_production_order_state",
            ),
            sa.CheckConstraint("output_qty > 0", name="ck_production_order_qty_positive"),
        )


def downgrade() -> None:
    op.drop_table("productionorder")
    op.drop_table("grnline")
    op.drop_table("goodsreceiptnote")
