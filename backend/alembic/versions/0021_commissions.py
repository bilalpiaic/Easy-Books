"""commission_plan, commission_ledger tables + Invoice.assigned_to_id

Revision ID: 0021_commissions
Revises: 0020_user_rights
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0021_commissions"
down_revision = "0020_user_rights"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # ── commission_plan ──────────────────────────────────────────────────────
    if not bind.dialect.has_table(bind, "commission_plan"):
        op.create_table(
            "commission_plan",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenant.id"), nullable=False, index=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False, index=True),
            sa.Column("rate", sa.Numeric(10, 4), nullable=False),
            sa.Column("sales_target", sa.Numeric(18, 4), nullable=True),
            sa.Column("recovery_target", sa.Numeric(18, 4), nullable=True),
            sa.Column("target_bonus", sa.Numeric(18, 4), nullable=True),
            sa.Column("effective_from", sa.String, nullable=False, index=True),
            sa.Column("effective_to", sa.String, nullable=True),
            sa.Column("active", sa.Boolean, nullable=False, server_default="1"),
        )

    # ── commission_ledger ────────────────────────────────────────────────────
    if not bind.dialect.has_table(bind, "commission_ledger"):
        op.create_table(
            "commission_ledger",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenant.id"), nullable=False, index=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False, index=True),
            sa.Column("period", sa.String, nullable=False, index=True),
            sa.Column("total_invoiced", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("total_recovered", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("rate", sa.Numeric(10, 4), nullable=False),
            sa.Column("commission_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("bonus_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("total_payable", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("status", sa.String, nullable=False, server_default="'draft'"),
            sa.Column("transaction_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "user_id", "period", name="uq_commission_period"),
        )

    # ── Invoice.assigned_to_id ───────────────────────────────────────────────
    with op.batch_alter_table("invoice") as batch_op:
        existing = [c["name"] for c in sa.inspect(bind).get_columns("invoice")]
        if "assigned_to_id" not in existing:
            batch_op.add_column(sa.Column("assigned_to_id", sa.Integer, nullable=True))


def downgrade():
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "commission_ledger"):
        op.drop_table("commission_ledger")
    if bind.dialect.has_table(bind, "commission_plan"):
        op.drop_table("commission_plan")
    with op.batch_alter_table("invoice") as batch_op:
        existing = [c["name"] for c in sa.inspect(bind).get_columns("invoice")]
        if "assigned_to_id" in existing:
            batch_op.drop_column("assigned_to_id")
