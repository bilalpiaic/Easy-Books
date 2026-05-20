"""P7: materialised AccountBalance for closed periods.

Revision ID: 0007_account_balance
Revises: 0006_bank_imports
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_account_balance"
down_revision = "0006_bank_imports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "accountbalance" in insp.get_table_names():
        return
    op.create_table(
        "accountbalance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False, index=True),
        sa.Column("period_id", sa.Integer(), sa.ForeignKey("accountingperiod.id"), nullable=False, index=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=False),
        sa.Column("debit_total", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("credit_total", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "period_id", "account_id",
            name="unique_balance_per_period_account",
        ),
    )


def downgrade() -> None:
    op.drop_table("accountbalance")
