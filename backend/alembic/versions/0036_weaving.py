"""weaving module — unit control masters + ops docs (#140)

Revision ID: 0036_weaving
Revises: 0035_revoked_tokens
Create Date: 2026-07-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0036_weaving"
down_revision = "0035_revoked_tokens"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, "wv_fabric_quality"):
        op.create_table(
            "wv_fabric_quality",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("code", sa.String, nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("description", sa.String, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("tenant_id", "code", name="uq_wv_fabric_quality_code"),
        )

    if not bind.dialect.has_table(bind, "wv_loom"):
        op.create_table(
            "wv_loom",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("code", sa.String, nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("loom_type", sa.String, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("tenant_id", "code", name="uq_wv_loom_code"),
        )

    if not bind.dialect.has_table(bind, "wv_yarn_type"):
        op.create_table(
            "wv_yarn_type",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("code", sa.String, nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("description", sa.String, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("tenant_id", "code", name="uq_wv_yarn_type_code"),
        )

    if not bind.dialect.has_table(bind, "wv_shift"):
        op.create_table(
            "wv_shift",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("code", sa.String, nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("start_time", sa.String, nullable=True),
            sa.Column("end_time", sa.String, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("tenant_id", "code", name="uq_wv_shift_code"),
        )

    if not bind.dialect.has_table(bind, "wv_operator"):
        op.create_table(
            "wv_operator",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("code", sa.String, nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("phone", sa.String, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("tenant_id", "code", name="uq_wv_operator_code"),
        )

    if not bind.dialect.has_table(bind, "wv_contract"):
        op.create_table(
            "wv_contract",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("number", sa.String, nullable=False, index=True),
            sa.Column("customer_id", sa.Integer, nullable=False, index=True),
            sa.Column("fabric_quality_id", sa.Integer, nullable=True),
            sa.Column("yarn_type_id", sa.Integer, nullable=True),
            sa.Column("start_date", sa.String, nullable=False),
            sa.Column("end_date", sa.String, nullable=True),
            sa.Column("contract_meters", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("pick_per_inch", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("assumed_yarn_rate_per_kg", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("fabric_return_price_per_meter", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("weaving_rate", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("expected_shrinkage_pct", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("payment_terms", sa.String, nullable=True),
            sa.Column("status", sa.String, nullable=False, server_default="draft", index=True),
            sa.Column("notes", sa.String, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "number", name="uq_wv_contract_number"),
        )

    if not bind.dialect.has_table(bind, "wv_yarn_inward"):
        op.create_table(
            "wv_yarn_inward",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("number", sa.String, nullable=False, index=True),
            sa.Column("contract_id", sa.Integer, nullable=False, index=True),
            sa.Column("yarn_type_id", sa.Integer, nullable=True),
            sa.Column("date", sa.String, nullable=False, index=True),
            sa.Column("gross_kg", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("tare_kg", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("net_kg", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("rate_per_kg", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("yarn_value", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("notes", sa.String, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "number", name="uq_wv_yarn_inward_number"),
        )

    if not bind.dialect.has_table(bind, "wv_sizing"):
        op.create_table(
            "wv_sizing",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("number", sa.String, nullable=False, index=True),
            sa.Column("contract_id", sa.Integer, nullable=False, index=True),
            sa.Column("vendor_id", sa.Integer, nullable=True),
            sa.Column("date", sa.String, nullable=False, index=True),
            sa.Column("input_kg", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("output_kg", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("gain_shrink_pct", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("sizing_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("notes", sa.String, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "number", name="uq_wv_sizing_number"),
        )

    if not bind.dialect.has_table(bind, "wv_production"):
        op.create_table(
            "wv_production",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("number", sa.String, nullable=False, index=True),
            sa.Column("contract_id", sa.Integer, nullable=False, index=True),
            sa.Column("loom_id", sa.Integer, nullable=True),
            sa.Column("shift_id", sa.Integer, nullable=True),
            sa.Column("operator_id", sa.Integer, nullable=True),
            sa.Column("date", sa.String, nullable=False, index=True),
            sa.Column("warp_yarn_kg", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("weft_yarn_kg", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("total_yarn_kg", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("grey_meters", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("efficiency_pct", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("weaving_charges", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("notes", sa.String, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "number", name="uq_wv_production_number"),
        )

    if not bind.dialect.has_table(bind, "wv_dispatch"):
        op.create_table(
            "wv_dispatch",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("number", sa.String, nullable=False, index=True),
            sa.Column("contract_id", sa.Integer, nullable=False, index=True),
            sa.Column("date", sa.String, nullable=False, index=True),
            sa.Column("meters", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("dispatch_value", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("weaving_charges_billed", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("net_receivable", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("notes", sa.String, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "number", name="uq_wv_dispatch_number"),
        )


def downgrade():
    bind = op.get_bind()
    for t in (
        "wv_dispatch", "wv_production", "wv_sizing", "wv_yarn_inward", "wv_contract",
        "wv_operator", "wv_shift", "wv_yarn_type", "wv_loom", "wv_fabric_quality",
    ):
        if bind.dialect.has_table(bind, t):
            op.drop_table(t)
