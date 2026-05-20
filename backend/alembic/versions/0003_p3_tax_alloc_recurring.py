"""P3: tax codes, payment allocations, recurring templates.

Revision ID: 0003_p3_tax_alloc_recurring
Revises: 0002_user_role
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_p3_tax_alloc_recurring"
down_revision = "0002_user_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = set(insp.get_table_names())

    if "taxcode" not in existing:
        op.create_table(
            "taxcode",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False, index=True),
            sa.Column("code", sa.String(), nullable=False, index=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("rate", sa.Numeric(18, 4), nullable=False),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("gl_account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "code", name="unique_tax_code_per_tenant"),
            sa.CheckConstraint("type IN ('output','input')", name="ck_tax_code_type"),
            sa.CheckConstraint("rate >= 0", name="ck_tax_code_rate_nonneg"),
        )

    if "paymentallocation" not in existing:
        op.create_table(
            "paymentallocation",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False, index=True),
            sa.Column("payment_received_id", sa.Integer(), sa.ForeignKey("paymentreceived.id"), nullable=True),
            sa.Column("bill_payment_id", sa.Integer(), sa.ForeignKey("billpayment.id"), nullable=True),
            sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoice.id"), nullable=True),
            sa.Column("bill_id", sa.Integer(), sa.ForeignKey("bill.id"), nullable=True),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "(invoice_id IS NOT NULL) <> (bill_id IS NOT NULL)",
                name="ck_alloc_one_target",
            ),
            sa.CheckConstraint("amount > 0", name="ck_alloc_amount_pos"),
        )

    if "recurringtemplate" not in existing:
        op.create_table(
            "recurringtemplate",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False, index=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("frequency", sa.String(), nullable=False),
            sa.Column("next_run", sa.String(), nullable=False),
            sa.Column("last_run", sa.String(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("entries_json", sa.String(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "frequency IN ('daily','weekly','monthly','quarterly','yearly')",
                name="ck_recurring_frequency",
            ),
        )


def downgrade() -> None:
    op.drop_table("recurringtemplate")
    op.drop_table("paymentallocation")
    op.drop_table("taxcode")
