"""V2.3: BoM library + RatePlan + CustomerRatePlan.

Revision ID: 0012_bom_rate_plans
Revises: 0011_stock_locations
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_bom_rate_plans"
down_revision = "0011_stock_locations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "bomheader" not in tables:
        op.create_table(
            "bomheader",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False, index=True),
            sa.Column("output_product_id", sa.Integer(), sa.ForeignKey("product.id"), nullable=False, index=True),
            sa.Column("output_qty", sa.Numeric(18, 4), nullable=False, server_default="1"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "tenant_id", "output_product_id", "version",
                name="unique_bom_per_product_version",
            ),
        )

    if "bomline" not in tables:
        op.create_table(
            "bomline",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("bom_id", sa.Integer(),
                      sa.ForeignKey("bomheader.id", ondelete="CASCADE"),
                      nullable=False, index=True),
            sa.Column("component_product_id", sa.Integer(), sa.ForeignKey("product.id"), nullable=False),
            sa.Column("qty_per_output", sa.Numeric(18, 4), nullable=False),
            sa.Column("source", sa.String(), nullable=False, server_default="own_stock"),
            sa.Column("default_location_id", sa.Integer(), sa.ForeignKey("stocklocation.id"), nullable=True),
            sa.Column("is_optional", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("notes", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "source IN ('own_stock','customer_supplied')",
                name="ck_bom_line_source",
            ),
            sa.CheckConstraint("qty_per_output > 0", name="ck_bom_line_qty_positive"),
        )

    if "rateplan" not in tables:
        op.create_table(
            "rateplan",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False, index=True),
            sa.Column("code", sa.String(), nullable=False, index=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("output_product_id", sa.Integer(), sa.ForeignKey("product.id"), nullable=True),
            sa.Column("per_unit_rate", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("includes_materials_at_cost", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("overhead_pct", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("margin_pct", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("valid_from", sa.String(), nullable=True),
            sa.Column("valid_to", sa.String(), nullable=True),
            sa.Column("notes", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "tenant_id", "code", "version",
                name="unique_rate_plan_code_version",
            ),
            sa.CheckConstraint("per_unit_rate >= 0", name="ck_rate_plan_rate_nonneg"),
            sa.CheckConstraint("overhead_pct >= 0", name="ck_rate_plan_oh_nonneg"),
            sa.CheckConstraint("margin_pct >= 0", name="ck_rate_plan_margin_nonneg"),
        )

    if "customerrateplan" not in tables:
        op.create_table(
            "customerrateplan",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False, index=True),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=False, index=True),
            sa.Column("rate_plan_id", sa.Integer(), sa.ForeignKey("rateplan.id"), nullable=False, index=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("assigned_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "tenant_id", "customer_id", "rate_plan_id",
                name="unique_customer_rate_plan_assignment",
            ),
        )


def downgrade() -> None:
    op.drop_table("customerrateplan")
    op.drop_table("rateplan")
    op.drop_table("bomline")
    op.drop_table("bomheader")
