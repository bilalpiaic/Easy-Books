"""P5: multi-currency — Tenant.base_currency, ExchangeRate, doc currency/rate.

Revision ID: 0005_multi_currency
Revises: 0004_idempotency_keys
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_multi_currency"
down_revision = "0004_idempotency_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Tenant.base_currency
    tenant_cols = {c["name"] for c in insp.get_columns("tenant")}
    if "base_currency" not in tenant_cols:
        with op.batch_alter_table("tenant", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "base_currency", sa.String(), nullable=False,
                    server_default="USD",
                )
            )

    # Invoice.currency, Invoice.exchange_rate
    inv_cols = {c["name"] for c in insp.get_columns("invoice")}
    if "currency" not in inv_cols:
        with op.batch_alter_table("invoice", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("currency", sa.String(), nullable=False, server_default="USD")
            )
            batch_op.add_column(
                sa.Column(
                    "exchange_rate", sa.Numeric(18, 4),
                    nullable=False, server_default="1",
                )
            )

    # Bill.currency, Bill.exchange_rate
    bill_cols = {c["name"] for c in insp.get_columns("bill")}
    if "currency" not in bill_cols:
        with op.batch_alter_table("bill", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("currency", sa.String(), nullable=False, server_default="USD")
            )
            batch_op.add_column(
                sa.Column(
                    "exchange_rate", sa.Numeric(18, 4),
                    nullable=False, server_default="1",
                )
            )

    # ExchangeRate table
    if "exchangerate" not in insp.get_table_names():
        op.create_table(
            "exchangerate",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False, index=True),
            sa.Column("date", sa.String(), nullable=False, index=True),
            sa.Column("from_currency", sa.String(), nullable=False),
            sa.Column("to_currency", sa.String(), nullable=False),
            sa.Column("rate", sa.Numeric(18, 4), nullable=False, server_default="1"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "tenant_id", "date", "from_currency", "to_currency",
                name="unique_rate_per_pair_per_day",
            ),
            sa.CheckConstraint("rate > 0", name="ck_rate_positive"),
        )


def downgrade() -> None:
    op.drop_table("exchangerate")
    with op.batch_alter_table("bill", schema=None) as batch_op:
        batch_op.drop_column("exchange_rate")
        batch_op.drop_column("currency")
    with op.batch_alter_table("invoice", schema=None) as batch_op:
        batch_op.drop_column("exchange_rate")
        batch_op.drop_column("currency")
    with op.batch_alter_table("tenant", schema=None) as batch_op:
        batch_op.drop_column("base_currency")
