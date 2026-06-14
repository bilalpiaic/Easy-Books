"""promo_rules: PromoRule table + InvoiceLine.discount_pct/promo_rule_id

Revision ID: 0022
Revises: 0021
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = "0022_promo_rules"
down_revision = "0021_commissions"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)

    # ── promo_rule table ──────────────────────────────────────────────────────
    if not bind.dialect.has_table(bind, "promo_rule"):
        op.create_table(
            "promo_rule",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenant.id"), nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("description", sa.String, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("start_date", sa.String, nullable=True),
            sa.Column("end_date", sa.String, nullable=True),
            sa.Column("product_id", sa.Integer, nullable=True),
            sa.Column("category_id", sa.Integer, nullable=True),
            sa.Column("min_qty", sa.Numeric(18, 4), nullable=True),
            sa.Column("min_invoice_value", sa.Numeric(18, 4), nullable=True),
            sa.Column("discount_type", sa.String, nullable=False, server_default="percent"),
            sa.Column("discount_value", sa.Numeric(18, 4), nullable=True),
            sa.Column("giveaway_product_id", sa.Integer, nullable=True),
            sa.Column("giveaway_qty", sa.Numeric(18, 4), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )

    # ── invoiceline: discount_pct + promo_rule_id ─────────────────────────────
    existing_cols = {c["name"] for c in insp.get_columns("invoiceline")}
    with op.batch_alter_table("invoiceline") as batch:
        if "discount_pct" not in existing_cols:
            batch.add_column(sa.Column("discount_pct", sa.Numeric(5, 2), nullable=False, server_default="0"))
        if "promo_rule_id" not in existing_cols:
            batch.add_column(sa.Column("promo_rule_id", sa.Integer, nullable=True))


def downgrade():
    with op.batch_alter_table("invoiceline") as batch:
        batch.drop_column("promo_rule_id")
        batch.drop_column("discount_pct")
    op.drop_table("promo_rule")
